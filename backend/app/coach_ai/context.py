"""What the AI coach knows about the athlete: a compact brief built fresh
for every turn from the existing services.

Everything is read as `AI_VIEWER`, a viewer who is never the athlete, so
`visible_conditions` leaves Strava activities out exactly as it does for a
coach — Strava's API terms forbid passing that data to anyone else, an AI
provider included.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import (
    _ftp_on,
    _metric_rows,
    athlete_timezone,
    best_power_curve,
    local_day,
    power_profile,
    training_load,
    visible_conditions,
)
from app.activities.models import Activity
from app.athletes.models import Athlete
from app.athletes.service import metrics_at
from app.auth.models import User
from app.coach_ai.models import AiCoachProfile
from app.coach_ai.proposals import is_locked, week_start
from app.goals.models import Goal
from app.goals.service import list_goals
from app.planning.models import PlannedSession
from app.planning.service import _gears
from app.seasons.models import Competition
from app.seasons.service import list_competitions
from app.training.models import TrainingEvent
from app.training.records_service import get_records_board
from app.training_plans.models import TrainingPlan
from app.training_plans.phases import current_phase
from app.training_plans.schemas import Phase
from app.training_plans.service import author_of, is_locked_for_ai
from app.workouts import structure
from app.workouts.schemas import WorkoutItem
from pydantic import TypeAdapter

_ITEMS = TypeAdapter(list[WorkoutItem])

AI_VIEWER_ID = uuid.UUID(int=0)


def ai_viewer() -> User:
    """A transient, never-saved user standing for the model provider."""
    return User(id=AI_VIEWER_ID, email="ai-coach@invalid", hashed_password="!", is_active=True, is_platform_admin=False)


def to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def ms_text(ms: int | None) -> str | None:
    if ms is None:
        return None
    if ms < 60_000:
        return f"{ms / 1000:.3f}s"
    minutes, rest = divmod(ms, 60_000)
    return f"{minutes}:{rest / 1000:06.3f}"


def _round(value: float | None, digits: int = 0) -> float | int | None:
    if value is None:
        return None
    return round(value) if digits == 0 else round(value, digits)


async def today_of(db: AsyncSession, athlete: Athlete) -> date:
    return local_day(datetime.now(timezone.utc), await athlete_timezone(db, athlete))


def plan_author(plan: PlannedSession, athlete: Athlete) -> str:
    if plan.created_by_ai:
        return "ai"
    if plan.created_by_user_id is None or plan.created_by_user_id == athlete.user_id:
        return "athlete"
    return "coach"


async def plan_lines(
    db: AsyncSession, athlete: Athlete, start: date, end: date, *, with_steps: bool = False
) -> list[dict]:
    rows = await _metric_rows(db, athlete.id)
    plans = await db.scalars(
        select(PlannedSession)
        .where(
            PlannedSession.athlete_id == athlete.id,
            PlannedSession.planned_date >= start,
            PlannedSession.planned_date <= end,
        )
        .order_by(PlannedSession.planned_date, PlannedSession.created_at)
    )
    lines = []
    for plan in plans:
        line: dict = {
            "plan_id": str(plan.id),
            "date": plan.planned_date.isoformat(),
            "weekday": plan.planned_date.strftime("%a"),
            "title": plan.title,
            "status": plan.status,
            "by": plan_author(plan, athlete),
        }
        if is_locked(plan, athlete):
            line["locked"] = True
        if plan.training_plan_id:
            line["training_plan_id"] = str(plan.training_plan_id)
        if plan.workout:
            items = _ITEMS.validate_python(plan.workout)
            estimate = structure.estimate(items, ftp_w=_ftp_on(rows, plan.planned_date))
            line["minutes"] = _round(estimate.duration_s / 60)
            if estimate.tss is not None:
                line["tss"] = _round(estimate.tss)
            if with_steps:
                line["steps"] = plan.workout
        if plan.description and with_steps:
            line["description"] = plan.description
        lines.append(line)
    return lines


async def recent_training(db: AsyncSession, athlete: Athlete, start: date, end: date) -> list[dict]:
    """Rides (recordings the AI may see) and sqorz track sessions, oldest first."""
    zone = await athlete_timezone(db, athlete)
    since = datetime.combine(start - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    until = datetime.combine(end + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc)
    items: list[tuple[date, dict]] = []
    linked_events: set[uuid.UUID] = set()
    for activity in await db.scalars(
        select(Activity).where(
            *visible_conditions(athlete, ai_viewer()), Activity.start_time >= since, Activity.start_time < until
        )
    ):
        day = local_day(activity.start_time, zone)
        if not start <= day <= end:
            continue
        if activity.training_event_id:
            linked_events.add(activity.training_event_id)
        entry = {
            "date": day.isoformat(),
            "type": activity.activity_type,
            "name": activity.name,
            "minutes": _round((activity.moving_s or activity.elapsed_s) / 60),
            "km": _round(activity.distance_m / 1000, 1) if activity.distance_m else None,
            "tss": _round(activity.tss),
            "np_w": _round(activity.normalized_power_w),
            "avg_hr": _round(activity.avg_heart_rate),
            "rpe": activity.rpe,
            "notes": (activity.notes or "")[:300] or None,
            "track_session": bool(activity.training_event_id),
        }
        items.append((day, {k: v for k, v in entry.items() if v not in (None, False)}))
    events = await db.scalars(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete.id, TrainingEvent.event_date >= start, TrainingEvent.event_date <= end
        )
    )
    for event in events:
        entry = {
            "date": event.event_date.isoformat(),
            "type": "track",
            "session_id": event.external_event_id,
            "name": event.title_override or event.name,
            "minutes": _round((event.end_timestamp - event.start_timestamp).total_seconds() / 60)
            if event.start_timestamp and event.end_timestamp
            else None,
            "rpe": event.rpe,
            "notes": (event.notes or "")[:300] or None,
            "race": event.is_race or None,
            "has_recording": event.id in linked_events or None,
        }
        items.append((event.event_date, {k: v for k, v in entry.items() if v is not None}))
    return [entry for _, entry in sorted(items, key=lambda pair: pair[0])]


async def last_training(db: AsyncSession, athlete: Athlete, today: date) -> dict | None:
    """The latest ride or track session up to today, however old (recent_training
    only covers 21 days, so a long break would look like a quiet week)."""
    zone = await athlete_timezone(db, athlete)
    until = datetime.combine(today + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc)
    candidates: list[tuple[date, str, str | None]] = []
    activities = await db.scalars(
        select(Activity)
        .where(*visible_conditions(athlete, ai_viewer()), Activity.start_time < until)
        .order_by(Activity.start_time.desc())
        .limit(3)  # the time-zone cut below may drop the newest
    )
    for activity in activities:
        day = local_day(activity.start_time, zone)
        if day <= today:
            candidates.append((day, activity.activity_type, activity.name))
            break
    event = await db.scalar(
        select(TrainingEvent)
        .where(TrainingEvent.athlete_id == athlete.id, TrainingEvent.event_date <= today)
        .order_by(TrainingEvent.event_date.desc())
        .limit(1)
    )
    if event is not None:
        candidates.append((event.event_date, "track", event.title_override or event.name))
    if not candidates:
        return None
    day, kind, name = max(candidates, key=lambda c: c[0])
    return {"date": day.isoformat(), "days_ago": (today - day).days, "type": kind, "name": name}


async def load_summary(db: AsyncSession, athlete: Athlete, today: date, *, weeks: int = 8) -> dict:
    load = await training_load(db, athlete, ai_viewer(), through=today, days=weeks * 7)
    per_week: dict[date, float] = {}
    for day in load.days:
        per_week[week_start(day.day)] = per_week.get(week_start(day.day), 0.0) + day.tss
    last = load.days[-1] if load.days else None
    return {
        "ctl": _round(last.ctl, 1) if last else None,
        "atl": _round(last.atl, 1) if last else None,
        "tsb": _round(last.tsb, 1) if last else None,
        "weekly_tss": [{"week_start": w.isoformat(), "tss": _round(t)} for w, t in sorted(per_week.items())],
        "unrated_activities": load.unrated_activities,
    }


async def power_summary(db: AsyncSession, athlete: Athlete, *, days: int = 90) -> dict:
    viewer = ai_viewer()
    profile = await power_profile(db, athlete, viewer, days=days)
    curve = await best_power_curve(
        db, athlete, viewer, start=datetime.now(timezone.utc) - timedelta(days=days), end=None
    )
    wanted = {5: "5s", 15: "15s", 30: "30s", 60: "1min", 180: "3min", 300: "5min", 600: "10min", 1200: "20min", 3600: "60min"}
    return {
        "days": days,
        "best_w": {wanted[p.duration_s]: _round(p.power_w) for p in curve if p.duration_s in wanted},
        "cp_w": _round(profile.critical_power.cp_w) if profile.critical_power else None,
        "w_prime_kj": _round(profile.critical_power.w_prime_j / 1000, 1) if profile.critical_power else None,
        "ftp_suggestion_w": _round(profile.ftp_suggestion.ftp_w) if profile.ftp_suggestion else None,
    }


async def records_summary(db: AsyncSession, athlete: Athlete) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for entry in await get_records_board(db, athlete.id):
        key = (entry.event_key, entry.start_type.value)
        if key not in best or entry.time_ms < best[key]["ms"]:
            best[key] = {
                "event": entry.event_key,
                "start": entry.start_type.value,
                "ms": entry.time_ms,
                "time": ms_text(entry.time_ms),
                "date": entry.achieved_on.isoformat(),
                "place": entry.place,
            }
    return [{k: v for k, v in r.items() if k != "ms"} for r in best.values()]


async def training_plans_summary(db: AsyncSession, athlete: Athlete, today: date) -> list[dict]:
    """The plans running now or still to come (finished ones are history)."""
    out = []
    for plan in await db.scalars(
        select(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete.id, TrainingPlan.end_date >= today)
        .order_by(TrainingPlan.start_date)
    ):
        phases = [Phase.model_validate(p) for p in plan.phases or []]
        current = current_phase(phases, today)
        line: dict = {
            "training_plan_id": str(plan.id),
            "name": plan.name,
            "sport": plan.sport,
            "start": plan.start_date.isoformat(),
            "end": plan.end_date.isoformat(),
            "by": author_of(plan, athlete),
        }
        if plan.goal_text:
            line["goal"] = plan.goal_text
        if plan.goal_date:
            line["goal_date"] = plan.goal_date.isoformat()
        if plan.hours_per_week:
            line["hours_per_week"] = plan.hours_per_week
        # Spelled out either way, so the athlete's other goals and races aren't read as this plan's.
        race = await db.get(Competition, plan.competition_id) if plan.competition_id else None
        line["race"] = {"name": race.name, "date": race.competition_date.isoformat()} if race else None
        goal = await db.get(Goal, plan.goal_id) if plan.goal_id else None
        line["time_goal"] = (
            {"event": goal.event_key, "start": goal.start_type, "target": ms_text(goal.target_time_ms), "date": goal.target_date.isoformat()}
            if goal
            else None
        )
        if phases:
            line["phases"] = [p.model_dump(mode="json", exclude_none=True) for p in phases]
        if current is not None:
            line["current_phase"] = phases[current].kind
        if plan.weeks:
            line["outline"] = [w for w in plan.weeks if w.get("week_start", "") >= (today - timedelta(days=6)).isoformat()]
        if is_locked_for_ai(plan, athlete):
            line["locked"] = True
        out.append(line)
    return out


async def build_brief(db: AsyncSession, athlete: Athlete, *, locale: str) -> dict:
    today = await today_of(db, athlete)
    zone = await athlete_timezone(db, athlete)
    metrics = await metrics_at(db, athlete.id, today)
    profile_row = await db.scalar(select(AiCoachProfile).where(AiCoachProfile.athlete_id == athlete.id))
    age = None
    if athlete.birthdate:
        age = today.year - athlete.birthdate.year - ((today.month, today.day) < (athlete.birthdate.month, athlete.birthdate.day))

    goals = []
    for goal in await list_goals(db, athlete, ai_viewer()):
        goals.append(
            {
                "event": goal.event_key,
                "start": goal.start_type.value,
                "target": ms_text(goal.target_time_ms),
                "target_date": goal.target_date.isoformat(),
                "best": ms_text(goal.best.time_ms) if goal.best else None,
                "achieved": goal.achieved,
                "days_left": goal.days_left,
                "predicted": ms_text(goal.prediction.time_ms) if goal.prediction else None,
                "notes": goal.notes,
            }
        )
    competitions = [
        {
            "name": c.name,
            "date": c.competition_date.isoformat(),
            "priority": c.priority.value if hasattr(c.priority, "value") else c.priority,
            "days_until": c.days_until,
            "taper_starts_on": c.taper_starts_on.isoformat() if c.taper_starts_on else None,
        }
        for c in await list_competitions(db, athlete)
        if c.days_until >= 0
    ]

    return {
        "today": f"{today.isoformat()} ({today.strftime('%A')})",
        "timezone": str(zone),
        "language": locale,
        "athlete": {
            "name": athlete.display_name,
            "sex": athlete.sex,
            "age": age,
            "height_cm": athlete.height_cm,
            "weight_kg": metrics["weight_kg"].value if metrics["weight_kg"] else None,
            "ftp_w": metrics["ftp_w"].value if metrics["ftp_w"] else None,
            "ftp_set_on": metrics["ftp_w"].effective_date.isoformat() if metrics["ftp_w"] else None,
            "max_hr": metrics["max_hr"].value if metrics["max_hr"] else None,
            "resting_hr": metrics["resting_hr"].value if metrics["resting_hr"] else None,
        },
        "intake": profile_row.answers if profile_row else {},
        "training_plans": await training_plans_summary(db, athlete, today),
        "load": await load_summary(db, athlete, today),
        "power": await power_summary(db, athlete),
        "records": await records_summary(db, athlete),
        "goals": goals,
        "competitions": competitions,
        "plans": await plan_lines(db, athlete, today - timedelta(days=14), today + timedelta(days=28)),
        "last_training": await last_training(db, athlete, today),
        "recent_training": await recent_training(db, athlete, today - timedelta(days=21), today),
        "gears": [g.label for g in await _gears(db, athlete.id)],
    }
