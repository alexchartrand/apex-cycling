"""AI proposals: calendar changes the athlete accepts or rejects.

The model writes a `ProposalPayload` (create / update / skip / delete
sessions, maybe a program outline); `check` validates it against the
calendar as it is now — the same check runs when it is made (errors go back
to the model) and on Accept (a plan it changes may have moved since) — and
`accept` applies it in one transaction. Plans written by someone other than
the athlete or the AI (their coach) are never touched.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import _ftp_on, _metric_rows, athlete_timezone, local_day
from app.athletes.models import Athlete
from app.auth.models import User
from app.coach_ai.models import AiCoachProfile, AiProposal, ProposalKind, ProposalStatus
from app.coach_ai.schemas import (
    CoachProfile,
    CreateOp,
    DeleteOp,
    PlanSnapshot,
    ProposalItem,
    ProposalPayload,
    ProposalRead,
    ProposalWeek,
    SkipOp,
    UpdateOp,
)
from app.db.base import utcnow
from app.planning.models import PlannedSession, PlanStatus
from app.planning.push import plan_changed
from app.workouts import structure
from app.workouts.models import Workout
from app.workouts.schemas import WorkoutItem
from app.workouts.service import get_workout

_ITEMS = TypeAdapter(list[WorkoutItem])

PROPOSAL_LIFETIME = timedelta(days=7)
MAX_DAYS_AHEAD = 26 * 7
# Over the stated weekly hours by more than this is worth a warning.
HOURS_SLACK = 1.15


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def payload_errors(raw: object) -> tuple[ProposalPayload | None, list[str]]:
    try:
        return ProposalPayload.model_validate(raw), []
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" if err["loc"] else err["msg"]
            for err in exc.errors()[:20]
        ]


def is_locked(plan: PlannedSession, athlete: Athlete) -> bool:
    """A plan someone else wrote (the athlete's coach): the AI leaves it alone."""
    return (
        not plan.created_by_ai
        and plan.created_by_user_id is not None
        and plan.created_by_user_id != athlete.user_id
    )


async def athlete_user(db: AsyncSession, athlete: Athlete) -> User:
    user = await db.get(User, athlete.user_id) if athlete.user_id else None
    if user is None:
        raise ValueError("The AI coach needs an athlete with a login")
    return user


async def profile_answers(db: AsyncSession, athlete_id: uuid.UUID) -> CoachProfile:
    row = await db.scalar(select(AiCoachProfile).where(AiCoachProfile.athlete_id == athlete_id))
    if row is None:
        return CoachProfile()
    try:
        return CoachProfile.model_validate(row.answers or {})
    except ValidationError:
        return CoachProfile()


@dataclass
class _Resolved:
    name: str
    steps: list
    source_workout_id: uuid.UUID | None


@dataclass
class Checked:
    payload: ProposalPayload
    items: list[ProposalItem] = field(default_factory=list)
    weeks: list[ProposalWeek] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Resolved workouts per op index (create/update with a workout).
    workouts: dict[int, _Resolved] = field(default_factory=dict)
    plans: dict[uuid.UUID, PlannedSession] = field(default_factory=dict)


def _snapshot(plan: PlannedSession, ftp_w: float | None) -> PlanSnapshot:
    estimate = structure.estimate(_ITEMS.validate_python(plan.workout), ftp_w=ftp_w) if plan.workout else None
    return PlanSnapshot(
        planned_date=plan.planned_date,
        title=plan.title,
        status=PlanStatus(plan.status),
        duration_s=estimate.duration_s if estimate else None,
        tss=estimate.tss if estimate else None,
    )


async def check(db: AsyncSession, athlete: Athlete, payload: ProposalPayload, *, today: date | None = None) -> Checked:
    user = await athlete_user(db, athlete)
    if today is None:
        today = local_day(datetime.now(timezone.utc), await athlete_timezone(db, athlete))
    profile = await profile_answers(db, athlete.id)
    metric_rows = await _metric_rows(db, athlete.id)
    result = Checked(payload=payload)

    plan_ids = {op.plan_id for op in payload.ops if not isinstance(op, CreateOp)}
    plans = {
        p.id: p
        for p in await db.scalars(
            select(PlannedSession).where(PlannedSession.athlete_id == athlete.id, PlannedSession.id.in_(plan_ids))
        )
    }
    result.plans = plans
    touched: set[uuid.UUID] = set()

    for index, op in enumerate(payload.ops):
        where = f"ops[{index}]"
        warnings: list[str] = []
        plan = None if isinstance(op, CreateOp) else plans.get(op.plan_id)
        if not isinstance(op, CreateOp):
            if plan is None:
                result.errors.append(f"{where}: no planned session {op.plan_id}")
                continue
            if plan.id in touched:
                result.errors.append(f"{where}: session {plan.id} is changed twice")
                continue
            touched.add(plan.id)
            if is_locked(plan, athlete):
                result.errors.append(f"{where}: “{plan.title}” was planned by the coach and can't be changed")
                continue
            if plan.status == PlanStatus.DONE.value:
                result.errors.append(f"{where}: “{plan.title}” is already done")
                continue
        before = _snapshot(plan, _ftp_on(metric_rows, plan.planned_date)) if plan is not None else None

        new_date: date | None = None
        if isinstance(op, (CreateOp, UpdateOp)):
            new_date = op.date if op.date is not None else (plan.planned_date if plan else None)
            if op.date is not None:
                if op.date < today:
                    result.errors.append(f"{where}: {op.date} is in the past")
                elif op.date > today + timedelta(days=MAX_DAYS_AHEAD):
                    result.errors.append(f"{where}: {op.date} is too far ahead")
                elif profile.available_days and op.date.isoweekday() not in profile.available_days:
                    warnings.append("not_available_day")

            resolved = None
            if op.workout_id is not None:
                read = await get_workout(db, user, op.workout_id)
                if read is None:
                    result.errors.append(f"{where}: no workout {op.workout_id} in the library")
                    continue
                resolved = _Resolved(read.name, list(read.steps), read.id)
            elif op.workout is not None:
                resolved = _Resolved(op.workout.name, list(op.workout.steps), None)
            if resolved is not None:
                result.workouts[index] = resolved

            steps = resolved.steps if resolved else (_ITEMS.validate_python(plan.workout) if plan and plan.workout else None)
            estimate = structure.estimate(steps, ftp_w=_ftp_on(metric_rows, new_date)) if steps and new_date else None
            item = ProposalItem(
                op=op.op,
                plan_id=plan.id if plan else None,
                before=before,
                planned_date=new_date,
                title=op.title if op.title is not None else (plan.title if plan else None),
                description=op.description if op.description is not None else (plan.description if plan else None),
                workout_name=resolved.name if resolved else None,
                workout=steps,
                estimate=estimate,
                warnings=warnings,
            )
        else:
            assert isinstance(op, (SkipOp, DeleteOp))
            item = ProposalItem(
                op=op.op,
                plan_id=plan.id,
                before=before,
                planned_date=None,
                title=None,
                description=None,
                workout_name=None,
                workout=None,
                estimate=None,
                reason=op.reason,
            )
        result.items.append(item)

    await _weeks(db, athlete, result, profile, metric_rows)
    return result


async def _weeks(db, athlete, result: Checked, profile: CoachProfile, metric_rows) -> None:
    """Per week the proposal touches, the calendar as it would be after it:
    sessions, time and TSS."""
    weeks: set[date] = set()
    for item in result.items:
        if item.planned_date:
            weeks.add(week_start(item.planned_date))
        if item.before:
            weeks.add(week_start(item.before.planned_date))
    if not weeks:
        return
    first, last = min(weeks), max(weeks) + timedelta(days=6)
    existing = list(
        await db.scalars(
            select(PlannedSession).where(
                PlannedSession.athlete_id == athlete.id,
                PlannedSession.planned_date >= first,
                PlannedSession.planned_date <= last,
                PlannedSession.status != PlanStatus.SKIPPED.value,
            )
        )
    )
    changed = {item.plan_id for item in result.items if item.plan_id}
    totals: dict[date, list[float | None]] = {w: [0, 0.0, 0.0] for w in weeks}

    def add(day: date, estimate) -> None:
        week = week_start(day)
        if week not in totals:
            return
        totals[week][0] += 1
        if estimate is not None:
            totals[week][1] += estimate.duration_s
            if estimate.tss is not None:
                totals[week][2] += estimate.tss

    for plan in existing:
        if plan.id in changed:
            continue
        estimate = (
            structure.estimate(_ITEMS.validate_python(plan.workout), ftp_w=_ftp_on(metric_rows, plan.planned_date))
            if plan.workout
            else None
        )
        add(plan.planned_date, estimate)
    for item in result.items:
        if item.op in ("create", "update") and item.planned_date:
            add(item.planned_date, item.estimate)
    result.weeks = [
        ProposalWeek(week_start=week, sessions=int(t[0]), duration_s=t[1], tss=round(t[2], 1) if t[2] else None)
        for week, t in sorted(totals.items())
    ]
    if profile.hours_per_week:
        for week in result.weeks:
            if week.duration_s > profile.hours_per_week * 3600 * HOURS_SLACK:
                result.warnings.append(f"over_hours:{week.week_start.isoformat()}")


async def create_proposal(
    db: AsyncSession,
    athlete: Athlete,
    *,
    kind: ProposalKind,
    summary: str,
    raw_payload: object,
    conversation_id: uuid.UUID | None,
) -> tuple[AiProposal | None, Checked | None, list[str]]:
    """Validates and stores a proposal (flushes, doesn't commit). Returns the
    errors instead when there are any, for the model to fix."""
    payload, errors = payload_errors(raw_payload)
    if payload is None:
        return None, None, errors
    checked = await check(db, athlete, payload)
    if checked.errors:
        return None, checked, checked.errors
    if kind is ProposalKind.REPLAN:
        # One replan proposal at a time: a newer one replaces the older.
        for older in await db.scalars(
            select(AiProposal).where(
                AiProposal.athlete_id == athlete.id,
                AiProposal.kind == ProposalKind.REPLAN.value,
                AiProposal.status == ProposalStatus.PENDING.value,
            )
        ):
            older.status = ProposalStatus.SUPERSEDED.value
            older.decided_at = utcnow()
    proposal = AiProposal(
        athlete_id=athlete.id,
        conversation_id=conversation_id,
        kind=kind.value,
        summary=summary.strip()[:4000] or "—",
        payload=payload.model_dump(mode="json", exclude_none=True),
        expires_at=utcnow() + PROPOSAL_LIFETIME,
    )
    db.add(proposal)
    await db.flush()
    return proposal, checked, []


def _aware(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


async def expire_if_due(proposal: AiProposal) -> None:
    if proposal.status == ProposalStatus.PENDING.value and _aware(proposal.expires_at) < utcnow():
        proposal.status = ProposalStatus.EXPIRED.value


async def read_proposal(db: AsyncSession, athlete: Athlete, proposal: AiProposal, viewer: User) -> ProposalRead:
    await expire_if_due(proposal)
    payload, errors = payload_errors(proposal.payload)
    pending = proposal.status == ProposalStatus.PENDING.value
    checked = await check(db, athlete, payload) if payload is not None else None
    return ProposalRead(
        id=proposal.id,
        kind=ProposalKind(proposal.kind),
        status=ProposalStatus(proposal.status),
        summary=proposal.summary,
        goal=payload.goal if payload else None,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        decided_at=proposal.decided_at,
        conversation_id=proposal.conversation_id,
        items=checked.items if checked else [],
        weeks=checked.weeks if checked else [],
        outline=payload.outline if payload else [],
        errors=(checked.errors if checked else errors) if pending else [],
        warnings=checked.warnings if checked else [],
        can_decide=pending and viewer.id == athlete.user_id,
    )


class StaleProposal(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class NotPending(Exception):
    pass


async def accept(db: AsyncSession, athlete: Athlete, proposal: AiProposal) -> list[uuid.UUID]:
    """Applies every change, commits, returns the plans created or changed.
    Raises `NotPending`, `StaleProposal`."""
    await expire_if_due(proposal)
    if proposal.status != ProposalStatus.PENDING.value:
        await db.commit()
        raise NotPending
    payload, errors = payload_errors(proposal.payload)
    if payload is None:
        raise StaleProposal(errors)
    checked = await check(db, athlete, payload)
    if checked.errors:
        raise StaleProposal(checked.errors)

    touched: list[uuid.UUID] = []
    for index, op in enumerate(payload.ops):
        resolved = checked.workouts.get(index)
        source_id = resolved.source_workout_id if resolved else None
        if resolved is not None and source_id is None and isinstance(op, (CreateOp, UpdateOp)) and op.workout.save_to_library:
            workout = Workout(
                owner_user_id=athlete.user_id,
                name=resolved.name,
                description=op.workout.description,
                tags=["ai"],
                steps=_ITEMS.dump_python(resolved.steps, mode="json", exclude_none=True),
                created_by_ai=True,
            )
            db.add(workout)
            await db.flush()
            source_id = workout.id
        if isinstance(op, CreateOp):
            plan = PlannedSession(
                athlete_id=athlete.id,
                created_by_user_id=None,
                created_by_ai=True,
                ai_proposal_id=proposal.id,
                planned_date=op.date,
                title=op.title.strip(),
                description=(op.description or (op.workout.description if op.workout else None) or None),
                targets=[],
                workout=_ITEMS.dump_python(resolved.steps, mode="json", exclude_none=True),
                source_workout_id=source_id,
            )
            db.add(plan)
            await plan_changed(db, plan)
            touched.append(plan.id)
            continue
        plan = checked.plans[op.plan_id]
        if isinstance(op, UpdateOp):
            if op.date is not None:
                plan.planned_date = op.date
            if op.title is not None:
                plan.title = op.title.strip()
            if op.description is not None:
                plan.description = op.description.strip() or None
            if resolved is not None:
                plan.workout = _ITEMS.dump_python(resolved.steps, mode="json", exclude_none=True)
                plan.source_workout_id = source_id
                plan.targets = []
            plan.ai_proposal_id = proposal.id
            await plan_changed(db, plan)
            touched.append(plan.id)
        elif isinstance(op, SkipOp):
            plan.status = PlanStatus.SKIPPED.value
            plan.training_event_id = plan.activity_id = None
            await plan_changed(db, plan)
            touched.append(plan.id)
        else:
            await plan_changed(db, plan)
            await db.delete(plan)

    if payload.outline or payload.goal:
        row = await db.scalar(select(AiCoachProfile).where(AiCoachProfile.athlete_id == athlete.id))
        if row is None:
            row = AiCoachProfile(athlete_id=athlete.id, answers={})
            db.add(row)
        if proposal.kind == ProposalKind.PLAN.value or row.program is None:
            row.program = {
                "goal": payload.goal,
                "accepted_at": utcnow().isoformat(),
                "outline": [w.model_dump(mode="json", exclude_none=True) for w in payload.outline],
            }
        else:  # an adjustment refines the outline of the weeks it covers
            program = dict(row.program)
            outline = {w["week_start"]: w for w in program.get("outline", [])}
            for week in payload.outline:
                outline[week.week_start.isoformat()] = week.model_dump(mode="json", exclude_none=True)
            program["outline"] = [outline[k] for k in sorted(outline)]
            if payload.goal:
                program["goal"] = payload.goal
            row.program = program
        row.updated_at = utcnow()

    proposal.status = ProposalStatus.ACCEPTED.value
    proposal.decided_at = utcnow()
    if proposal.kind == ProposalKind.PLAN.value:
        # A new program replaces the other program proposals still waiting.
        for other in await db.scalars(
            select(AiProposal).where(
                AiProposal.athlete_id == athlete.id,
                AiProposal.kind == ProposalKind.PLAN.value,
                AiProposal.status == ProposalStatus.PENDING.value,
                AiProposal.id != proposal.id,
            )
        ):
            other.status = ProposalStatus.SUPERSEDED.value
            other.decided_at = utcnow()
    await db.commit()
    return touched


async def reject(db: AsyncSession, proposal: AiProposal) -> None:
    """Raises `NotPending`."""
    await expire_if_due(proposal)
    if proposal.status != ProposalStatus.PENDING.value:
        await db.commit()
        raise NotPending
    proposal.status = ProposalStatus.REJECTED.value
    proposal.decided_at = utcnow()
    await db.commit()
