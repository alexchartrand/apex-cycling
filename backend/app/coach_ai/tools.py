"""The functions the model may call during a conversation.

All are reads through the existing services (as `AI_VIEWER`, so no Strava
data), except `save_profile`, which stores intake answers, and
`propose_changes`, which stores a *proposal* — nothing reaches the calendar
until the athlete accepts it.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.fusion_service import add_activity_metrics_to_efforts
from app.athletes.models import Athlete
from app.coach_ai import context
from app.coach_ai.models import AiCoachProfile, AiProposal, ProposalKind
from app.coach_ai.proposals import athlete_user, create_proposal
from app.coach_ai.schemas import PROFILE_FIELDS, CoachProfile
from app.db.base import utcnow
from app.training.service import get_session_efforts
from app.workouts.service import get_workout, list_workouts

logger = logging.getLogger("coach_ai.tools")

MAX_RANGE_DAYS = 120


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


_DATE = {"type": "string", "description": "YYYY-MM-DD"}

READ_TOOLS = [
    _fn(
        "get_plans",
        "Planned sessions between two dates (inclusive), with plan_id, status (planned/done/skipped), "
        "author (athlete/coach/ai; 'locked' = the coach's, never change it), minutes and TSS. "
        "with_steps=true adds each workout's step tree.",
        {"start": _DATE, "end": _DATE, "with_steps": {"type": "boolean"}},
        ["start", "end"],
    ),
    _fn(
        "get_training",
        "What was actually done between two dates: rides/gym recordings (minutes, TSS, NP, HR, RPE, notes) "
        "and track sessions (session_id, RPE, notes).",
        {"start": _DATE, "end": _DATE},
        ["start", "end"],
    ),
    _fn(
        "get_session_efforts",
        "The efforts of one track session (by session_id from get_training): laps, times, start type, pacing, "
        "average power/HR when a recording is linked.",
        {"session_id": {"type": "string"}},
        ["session_id"],
    ),
    _fn(
        "get_training_load",
        "Weekly TSS and the current CTL (fitness), ATL (fatigue), TSB (form) over the last N weeks.",
        {"weeks": {"type": "integer", "minimum": 1, "maximum": 26}},
        ["weeks"],
    ),
    _fn(
        "get_power_profile",
        "Best power at standard durations, critical power and W′ over the last N days.",
        {"days": {"type": "integer", "minimum": 14, "maximum": 365}},
        ["days"],
    ),
    _fn(
        "list_workouts",
        "The athlete's workout library and the built-in presets: id, name, tags, minutes, TSS, track or not. "
        "Optional text search.",
        {"search": {"type": "string"}},
    ),
    _fn("get_workout", "One library workout or preset with its step tree.", {"workout_id": {"type": "string"}}, ["workout_id"]),
]

PROFILE_TOOL = _fn(
    "save_profile",
    "Store what the athlete told you about themself (only the fields you learnt). Fields: "
    "goal (text), goal_date (YYYY-MM-DD), hours_per_week (number), available_days and track_days "
    "(ISO weekdays 1=Mon…7=Sun), max_weekday_minutes, max_weekend_minutes, experience (text), "
    "injuries (text, 'none' if none), gym (bool), gym_details (equipment, experience), indoor_trainer (bool), "
    "power_meter (bool), other (text).",
    {"fields": {"type": "object"}},
    ["fields"],
)

PROPOSE_TOOL = _fn(
    "propose_changes",
    "Propose changes to the calendar. Nothing changes until the athlete accepts. ops is a list of "
    '{"op":"create","date","title","description"?, and either "workout_id" (library/preset) or "workout":'
    '{"name","description"?,"steps":[…],"save_to_library"?}} | {"op":"update","plan_id", any of date/title/'
    'description/workout_id/workout} | {"op":"skip","plan_id","reason"?} | {"op":"delete","plan_id","reason"?}. '
    "For a new program also give goal and outline (weeks not yet detailed: "
    '[{"week_start":"YYYY-MM-DD (a Monday)","focus","hours"?,"notes"?}]). '
    "The answer lists errors to fix (then call again) or the proposal id.",
    {
        "summary": {"type": "string", "description": "What changes and why, 1-4 sentences, athlete's language"},
        "ops": {"type": "array", "items": {"type": "object"}},
        "goal": {"type": "string"},
        "outline": {"type": "array", "items": {"type": "object"}},
    },
    ["summary", "ops"],
)


@dataclass
class ToolContext:
    db: AsyncSession
    athlete: Athlete
    conversation_id: uuid.UUID
    proposal_kind: ProposalKind
    allow_profile: bool = True
    allow_proposals: bool = True
    proposals: list[AiProposal] = field(default_factory=list)


def tools_for(ctx: ToolContext) -> list[dict]:
    tools = list(READ_TOOLS)
    if ctx.allow_profile:
        tools.append(PROFILE_TOOL)
    if ctx.allow_proposals:
        tools.append(PROPOSE_TOOL)
    return tools


class ToolArgumentError(Exception):
    pass


def _date(args: dict, key: str) -> date:
    try:
        return date.fromisoformat(str(args[key]))
    except (KeyError, ValueError) as exc:
        raise ToolArgumentError(f"{key} must be a date YYYY-MM-DD") from exc


def _range(args: dict) -> tuple[date, date]:
    start, end = _date(args, "start"), _date(args, "end")
    if end < start:
        start, end = end, start
    if (end - start).days > MAX_RANGE_DAYS:
        raise ToolArgumentError(f"at most {MAX_RANGE_DAYS} days at a time")
    return start, end


def _int(args: dict, key: str, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(args.get(key, default))))
    except (TypeError, ValueError):
        return default


async def _efforts(ctx: ToolContext, args: dict) -> object:
    session_id = str(args.get("session_id", ""))
    efforts = await get_session_efforts(ctx.db, ctx.athlete.id, session_id)
    if efforts is None:
        return {"error": "no such session"}
    await add_activity_metrics_to_efforts(ctx.db, ctx.athlete, context.ai_viewer(), session_id, efforts)
    out = []
    for effort in efforts:
        out.append(
            {
                "index": effort.index,
                "track": effort.track_name,
                "label": effort.label,
                "start": effort.start_type.value,
                "laps": effort.completed_lap_count,
                "distance_m": effort.distance_m,
                "total": context.ms_text(effort.total_time_ms),
                "best_lap": context.ms_text(effort.best_lap_ms),
                "lap_times": [context.ms_text(t) for t in effort.lap_times_ms],
                "avg_kmh": effort.avg_speed_kmh,
                "pacing_cv_pct": effort.pacing.cv_pct if effort.pacing else None,
                "fade_pct": effort.pacing.fade_pct if effort.pacing else None,
                "avg_power_w": effort.avg_power_w,
                "avg_hr": effort.avg_heart_rate,
                "avg_cadence": effort.avg_cadence,
            }
        )
    return out


async def _workouts(ctx: ToolContext, args: dict) -> object:
    user = await athlete_user(ctx.db, ctx.athlete)
    search = str(args.get("search") or "").strip() or None
    rows = await list_workouts(ctx.db, user, query=search)
    return [
        {
            "workout_id": str(w.id),
            "name": w.name,
            "source": w.source.value,
            "tags": w.tags,
            "minutes": round(w.duration_s / 60),
            "tss": round(w.tss) if w.tss is not None else None,
            "track": w.is_track,
        }
        for w in rows[:80]
    ]


async def _workout(ctx: ToolContext, args: dict) -> object:
    try:
        workout_id = uuid.UUID(str(args.get("workout_id")))
    except ValueError:
        return {"error": "workout_id is not an id"}
    read = await get_workout(ctx.db, await athlete_user(ctx.db, ctx.athlete), workout_id)
    if read is None:
        return {"error": "no such workout"}
    return {
        "workout_id": str(read.id),
        "name": read.name,
        "description": read.description,
        "minutes": round(read.duration_s / 60),
        "tss": round(read.tss) if read.tss is not None else None,
        "steps": [item.model_dump(mode="json", exclude_none=True) for item in read.steps],
    }


async def _save_profile(ctx: ToolContext, args: dict) -> object:
    fields = args.get("fields")
    if not isinstance(fields, dict):
        return {"error": "fields must be an object"}
    unknown = sorted(set(fields) - set(PROFILE_FIELDS))
    row = await ctx.db.scalar(select(AiCoachProfile).where(AiCoachProfile.athlete_id == ctx.athlete.id))
    if row is None:
        row = AiCoachProfile(athlete_id=ctx.athlete.id, answers={})
        ctx.db.add(row)
    merged = {**(row.answers or {}), **{k: v for k, v in fields.items() if k in PROFILE_FIELDS}}
    try:
        profile = CoachProfile.model_validate(merged)
    except ValidationError as exc:
        return {"error": [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]}
    row.answers = profile.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    row.updated_at = utcnow()
    await ctx.db.flush()
    return {"saved": sorted(set(fields) - set(unknown)), "ignored": unknown, "profile": row.answers}


async def _propose(ctx: ToolContext, args: dict) -> object:
    raw = {key: args[key] for key in ("ops", "goal", "outline") if args.get(key) not in (None, "", [])}
    proposal, _, errors = await create_proposal(
        ctx.db,
        ctx.athlete,
        kind=ctx.proposal_kind,
        summary=str(args.get("summary") or ""),
        raw_payload=raw,
        conversation_id=ctx.conversation_id,
    )
    if proposal is None:
        return {"ok": False, "errors": errors}
    ctx.proposals.append(proposal)
    return {
        "ok": True,
        "proposal_id": str(proposal.id),
        "note": "Shown to the athlete as a card with Accept / Reject. Don't repeat its content in detail.",
    }


async def run_tool(ctx: ToolContext, name: str, arguments: str) -> str:
    """The tool's answer as JSON text (errors included, for the model to read)."""
    try:
        args = json.loads(arguments or "{}")
        if not isinstance(args, dict):
            raise ToolArgumentError("arguments must be an object")
        db, athlete = ctx.db, ctx.athlete
        if name == "get_plans":
            start, end = _range(args)
            result: object = await context.plan_lines(db, athlete, start, end, with_steps=bool(args.get("with_steps")))
        elif name == "get_training":
            start, end = _range(args)
            result = await context.recent_training(db, athlete, start, end)
        elif name == "get_session_efforts":
            result = await _efforts(ctx, args)
        elif name == "get_training_load":
            weeks = _int(args, "weeks", 1, 26, 8)
            result = await context.load_summary(db, athlete, await context.today_of(db, athlete), weeks=weeks)
        elif name == "get_power_profile":
            result = await context.power_summary(db, athlete, days=_int(args, "days", 14, 365, 90))
        elif name == "list_workouts":
            result = await _workouts(ctx, args)
        elif name == "get_workout":
            result = await _workout(ctx, args)
        elif name == "save_profile" and ctx.allow_profile:
            result = await _save_profile(ctx, args)
        elif name == "propose_changes" and ctx.allow_proposals:
            result = await _propose(ctx, args)
        else:
            result = {"error": f"unknown tool {name}"}
    except json.JSONDecodeError:
        result = {"error": "arguments are not valid JSON"}
    except ToolArgumentError as exc:
        result = {"error": str(exc)}
    except Exception:  # a tool bug must not end the conversation
        logger.exception("AI coach tool %s failed", name)
        result = {"error": "the tool failed"}
    return context.to_json(result)


def default_range(today: date) -> tuple[date, date]:
    return today - timedelta(days=14), today + timedelta(days=28)
