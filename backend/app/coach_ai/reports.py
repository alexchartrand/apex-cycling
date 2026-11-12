"""Training reports (weekly, at the athlete's chosen day and hour, or on
demand) and the missed-session replan, both run as AI conversations of
their own so the athlete can carry on discussing them in the chat."""

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import _ftp_on, _metric_rows, athlete_timezone, training_load
from app.athletes.models import Athlete
from app.auth.models import User
from app.coach_ai import context, prompts
from app.coach_ai.access import access_row
from app.coach_ai.models import (
    AiCoachAccess,
    AiProposal,
    AiReport,
    ConversationKind,
    ProposalStatus,
    ReportKind,
)
from app.coach_ai.ports import LlmClientPort
from app.coach_ai.schemas import ReportRead
from app.coach_ai.service import run_turn, start_conversation
from app.db.base import utcnow
from app.notifications.kinds import NotificationKind
from app.notifications.service import notify
from app.planning.models import PlannedSession, PlanStatus
from app.training.insights_service import compute_insights
from app.workouts import structure

logger = logging.getLogger("coach_ai.reports")

# A replan at most this often, and only for sessions missed since the last one.
REPLAN_COOLDOWN = timedelta(hours=48)
MISSED_LOOKBACK_DAYS = 7
LOAD_DRIFT = 0.25
MIN_PLANNED_TSS_FOR_DRIFT = 100


def _aware(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def report_read(row: AiReport) -> ReportRead:
    return ReportRead(
        id=row.id,
        kind=ReportKind(row.kind),
        period_start=row.period_start,
        period_end=row.period_end,
        content=row.content,
        stats=row.stats or {},
        created_at=row.created_at,
        conversation_id=row.conversation_id,
        proposal_id=row.proposal_id,
    )


async def _planned(db: AsyncSession, athlete: Athlete, start: date, end: date) -> list[PlannedSession]:
    return list(
        await db.scalars(
            select(PlannedSession).where(
                PlannedSession.athlete_id == athlete.id,
                PlannedSession.planned_date >= start,
                PlannedSession.planned_date <= end,
            )
        )
    )


def _plan_tss(plan: PlannedSession, metric_rows) -> float | None:
    if not plan.workout:
        return None
    return structure.estimate(
        context._ITEMS.validate_python(plan.workout), ftp_w=_ftp_on(metric_rows, plan.planned_date)
    ).tss


async def period_stats(db: AsyncSession, athlete: Athlete, start: date, end: date, today: date) -> dict:
    """The numbers a report stands on (also shown next to it)."""
    metric_rows = await _metric_rows(db, athlete.id)
    plans = await _planned(db, athlete, start, end)
    planned_tss = sum(t for p in plans if p.status != PlanStatus.SKIPPED.value and (t := _plan_tss(p, metric_rows)))
    load = await training_load(db, athlete, context.ai_viewer(), through=end, days=(end - start).days + 1 + 28)
    window = [d for d in load.days if start <= d.day <= end]
    before = [d for d in load.days if d.day < start]
    training = await context.recent_training(db, athlete, start, end)
    rpes = [t["rpe"] for t in training if t.get("rpe")]
    insights = [i for i in await compute_insights(db, athlete.id) if start <= i.event_date <= end]
    return {
        "plans": {
            "total": len(plans),
            "done": sum(p.status == PlanStatus.DONE.value for p in plans),
            "skipped": sum(p.status == PlanStatus.SKIPPED.value for p in plans),
            "missed": sum(p.status == PlanStatus.PLANNED.value and p.planned_date < today for p in plans),
            "planned_tss": round(planned_tss) if planned_tss else None,
            "list": await context.plan_lines(db, athlete, start, end),
        },
        "actual_tss": round(sum(d.tss for d in window)),
        "sessions": len(training),
        "hours": round(sum(t.get("minutes") or 0 for t in training) / 60, 1),
        "avg_rpe": round(sum(rpes) / len(rpes), 1) if rpes else None,
        "ctl": [round(before[-1].ctl, 1) if before else None, round(window[-1].ctl, 1) if window else None],
        "atl_end": round(window[-1].atl, 1) if window else None,
        "tsb_end": round(window[-1].tsb, 1) if window else None,
        "highlights": [
            {
                "kind": i.kind.value,
                "date": i.event_date.isoformat(),
                "event": i.event_key,
                "time": context.ms_text(i.time_ms),
                "previous": context.ms_text(i.previous_ms),
            }
            for i in insights
        ],
        "training": training,
    }


def _headline(content: str) -> str:
    for line in content.splitlines():
        line = line.strip().lstrip("#*>- ").strip("*_ ")
        if line:
            return line[:140]
    return ""


async def generate_report(
    db: AsyncSession, client: LlmClientPort, athlete: Athlete, *, kind: ReportKind, start: date, end: date
) -> AiReport:
    """Writes a report as a conversation of its own, stores it and tells
    the athlete. Raises `CapReached`, `LlmError`."""
    today = await context.today_of(db, athlete)
    stats = await period_stats(db, athlete, start, end, today)
    conversation = await start_conversation(db, athlete, ConversationKind.REPORT, f"{start.isoformat()} – {end.isoformat()}")
    conversation_id = conversation.id
    athlete_id, user_id = athlete.id, athlete.user_id
    messages, proposals = await run_turn(
        db,
        client,
        athlete,
        conversation,
        user_text=prompts.report_kickoff(start, end, context.to_json({k: v for k, v in stats.items() if k != "training"})),
        hidden_user_text=True,
        extra={"period_start": start.isoformat(), "period_end": end.isoformat()},
    )
    content = next((m.content for m in reversed(messages) if m.role == "assistant" and m.content), "") or ""
    stats.pop("training", None)
    stats["plans"].pop("list", None)
    report = AiReport(
        athlete_id=athlete_id,
        conversation_id=conversation_id,
        kind=kind.value,
        period_start=start,
        period_end=end,
        content=content,
        stats=stats,
        proposal_id=proposals[-1].id if proposals else None,
    )
    db.add(report)
    await db.flush()
    if user_id is not None:
        await notify(
            db,
            user_id,
            NotificationKind.AI_REPORT,
            {"report_id": str(report.id), "headline": _headline(content), "period_end": end.isoformat()},
            dedupe_key=f"ai_report:{report.id}",
        )
    await db.commit()
    return report


# --- the worker's schedule -----------------------------------------------------------


def due_report_period(access: AiCoachAccess, now: datetime, zone: ZoneInfo) -> tuple[date, date] | None:
    """The 7 days ending on the latest scheduled report day, when that
    report moment has passed and no report was made since."""
    if not access.weekly_reports:
        return None
    local = now.astimezone(zone)
    days_back = (local.isoweekday() - access.report_weekday) % 7
    day = local.date() - timedelta(days=days_back)
    moment = datetime.combine(day, time(hour=access.report_hour), tzinfo=zone)
    if moment > local:
        day -= timedelta(days=7)
        moment -= timedelta(days=7)
    last = _aware(access.last_report_at)
    if last is not None and last >= moment:
        return None
    # Approved after that moment: the first report is the next one.
    approved = _aware(access.approved_at)
    if approved is not None and approved > moment:
        return None
    return day - timedelta(days=6), day


async def replan_reason(db: AsyncSession, athlete: Athlete, access: AiCoachAccess, now: datetime) -> dict | None:
    """Why the plan should be rebalanced now, or None: sessions missed since
    the last replan, or last week's load more than 25 % off the plan."""
    last = _aware(access.last_replan_at)
    if last is not None and now - last < REPLAN_COOLDOWN:
        return None
    last_report = _aware(access.last_report_at)
    if last_report is not None and now - last_report < timedelta(hours=24):
        return None  # the report just looked at it
    pending = await db.scalar(
        select(AiProposal.id).where(AiProposal.athlete_id == athlete.id, AiProposal.status == ProposalStatus.PENDING.value).limit(1)
    )
    if pending is not None:
        return None
    zone = await athlete_timezone(db, athlete)
    today = now.astimezone(zone).date()
    since = today - timedelta(days=MISSED_LOOKBACK_DAYS)
    if last is not None:
        since = max(since, last.astimezone(zone).date())
    upcoming = await _planned(db, athlete, today, today + timedelta(days=10))
    if not any(p.status == PlanStatus.PLANNED.value for p in upcoming):
        return None  # nothing ahead to rebalance
    plans = await _planned(db, athlete, since, today - timedelta(days=1))
    missed = [p for p in plans if p.status == PlanStatus.PLANNED.value]
    reason: dict = {}
    if missed:
        reason["missed"] = [
            {"plan_id": str(p.id), "date": p.planned_date.isoformat(), "title": p.title, "by": context.plan_author(p, athlete)}
            for p in missed
        ]
    metric_rows = await _metric_rows(db, athlete.id)
    week = await _planned(db, athlete, today - timedelta(days=7), today - timedelta(days=1))
    planned_tss = sum(t for p in week if p.status != PlanStatus.SKIPPED.value and (t := _plan_tss(p, metric_rows)))
    if planned_tss >= MIN_PLANNED_TSS_FOR_DRIFT:
        load = await training_load(db, athlete, context.ai_viewer(), through=today - timedelta(days=1), days=7)
        actual = sum(d.tss for d in load.days)
        if abs(actual - planned_tss) / planned_tss > LOAD_DRIFT:
            reason["load_last_7_days"] = {"planned_tss": round(planned_tss), "actual_tss": round(actual)}
    return reason or None


async def generate_replan(db: AsyncSession, client: LlmClientPort, athlete: Athlete, reason: dict) -> AiProposal | None:
    conversation = await start_conversation(db, athlete, ConversationKind.REPLAN, None)
    user_id = athlete.user_id
    _, proposals = await run_turn(
        db, client, athlete, conversation, user_text=prompts.replan_kickoff(context.to_json(reason)), hidden_user_text=True
    )
    if not proposals:
        return None
    proposal = proposals[-1]
    if user_id is not None:
        await notify(
            db,
            user_id,
            NotificationKind.AI_PROPOSAL,
            {"proposal_id": str(proposal.id), "summary": proposal.summary[:200]},
            dedupe_key=f"ai_proposal:{proposal.id}",
        )
        await db.commit()
    return proposal


async def run_due_work(db: AsyncSession, client: LlmClientPort, athlete_id: uuid.UUID, now: datetime | None = None) -> str | None:
    """One athlete's scheduled work: the weekly report when due, else a
    replan when one is called for. Returns what was done."""
    now = now or utcnow()
    athlete = await db.get(Athlete, athlete_id)
    access = await access_row(db, athlete_id)
    if athlete is None or access is None or not access.enabled or access.consent_at is None:
        return None
    zone = await athlete_timezone(db, athlete)
    period = due_report_period(access, now, zone)
    if period is not None:
        access.last_report_at = now  # first, so a failing model isn't retried every round
        await db.commit()
        await generate_report(db, client, athlete, kind=ReportKind.WEEKLY, start=period[0], end=period[1])
        return "report"
    reason = await replan_reason(db, athlete, access, now)
    if reason is not None:
        access.last_replan_at = now
        await db.commit()
        await generate_replan(db, client, athlete, reason)
        return "replan"
    return None


async def scheduled_athletes(db: AsyncSession) -> list[uuid.UUID]:
    rows = await db.scalars(
        select(AiCoachAccess.athlete_id)
        .join(Athlete, Athlete.id == AiCoachAccess.athlete_id)
        .join(User, User.id == Athlete.user_id)
        .where(AiCoachAccess.enabled.is_(True), AiCoachAccess.consent_at.is_not(None), User.is_active.is_(True))
    )
    return list(rows)
