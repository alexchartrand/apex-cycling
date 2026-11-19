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
from app.goals.models import Goal
from app.seasons.models import Competition
from app.training.records_service import best_entry, get_records_board
from app.planning.models import PlannedSession, PlanStatus
from app.planning.push import plan_changed
from app.training_plans.models import TrainingPlan
from app.training_plans.schemas import TrainingPlanWrite
from app.training_plans.service import is_locked_for_ai, plans_covering
from app.workouts import structure
from app.workouts.models import Workout
from app.workouts.schemas import WorkoutItem
from app.workouts.service import get_workout

_ITEMS = TypeAdapter(list[WorkoutItem])

PROPOSAL_LIFETIME = timedelta(days=7)
MAX_DAYS_AHEAD = 26 * 7
# Over the stated weekly hours by more than this is worth a warning.
HOURS_SLACK = 1.15
# Weekdays 1-5 use max_weekday_minutes, 6-7 max_weekend_minutes.
WEEKEND = (6, 7)


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
    # Upcoming sessions the AI wrote for the target plan, which a new program for it removes.
    replaced: list[PlannedSession] = field(default_factory=list)
    # The plan the proposal works on (`training_plan_id`), or the new one it
    # makes as it would be stored (`plan`); other plans its creates name.
    target: TrainingPlan | None = None
    new_plan: TrainingPlanWrite | None = None
    other_plans: dict[uuid.UUID, TrainingPlan] = field(default_factory=dict)


def _snapshot(plan: PlannedSession, ftp_w: float | None) -> PlanSnapshot:
    estimate = structure.estimate(_ITEMS.validate_python(plan.workout), ftp_w=ftp_w) if plan.workout else None
    return PlanSnapshot(
        planned_date=plan.planned_date,
        title=plan.title,
        status=PlanStatus(plan.status),
        duration_s=estimate.duration_s if estimate else None,
        tss=estimate.tss if estimate else None,
    )


async def check(
    db: AsyncSession,
    athlete: Athlete,
    payload: ProposalPayload,
    *,
    kind: ProposalKind | str | None = None,
    today: date | None = None,
) -> Checked:
    """`kind` plan: a new program, which also removes the previous AI
    program's sessions from its first session on (worked out on every check,
    so a session done meanwhile is simply kept)."""
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
    await _resolve_target(db, athlete, payload, kind, result)

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
        elif op.training_plan_id is not None and op.training_plan_id not in result.other_plans:
            other = await db.get(TrainingPlan, op.training_plan_id)
            if other is None or other.athlete_id != athlete.id:
                result.errors.append(f"{where}: no training plan {op.training_plan_id}")
                continue
            if is_locked_for_ai(other, athlete):
                result.errors.append(f"{where}: “{other.name}” is the coach's plan and can't be changed")
                continue
            result.other_plans[other.id] = other
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
            limit = profile.max_weekend_minutes if new_date and new_date.isoweekday() in WEEKEND else profile.max_weekday_minutes
            if estimate is not None and limit and estimate.duration_s > limit * 60:
                warnings.append("too_long")
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

    if (
        kind is not None
        and ProposalKind(kind) is ProposalKind.PLAN
        and result.target is not None
        and not result.errors
    ):
        await _replace_previous_program(db, athlete, result, touched, today, metric_rows)
    if payload.race is not None and payload.race.date < today:
        result.errors.append(f"race: {payload.race.date} is in the past")
    if payload.plan is not None and not result.errors:
        _resolve_new_plan(result, payload, today)
    _check_reach(result, payload)
    await _weeks(db, athlete, result, profile, metric_rows)
    return result


async def _resolve_target(
    db: AsyncSession, athlete: Athlete, payload: ProposalPayload, kind: ProposalKind | str | None, result: Checked
) -> None:
    if payload.training_plan_id is not None:
        target = await db.get(TrainingPlan, payload.training_plan_id)
        if target is None or target.athlete_id != athlete.id:
            result.errors.append(f"training_plan_id: no training plan {payload.training_plan_id}")
        elif is_locked_for_ai(target, athlete):
            result.errors.append(f"training_plan_id: “{target.name}” is the coach's plan and can't be changed")
        else:
            result.target = target
    elif kind is not None and ProposalKind(kind) is ProposalKind.PLAN and payload.plan is None:
        result.errors.append(
            "a new program needs plan {name, sport, …} for a new training plan, or training_plan_id to rebuild one"
        )


def _resolve_new_plan(result: Checked, payload: ProposalPayload, today: date) -> None:
    """The new plan as it would be stored: dates left out come from the
    sessions, the outline and the race."""
    plan = payload.plan
    created = [item.planned_date for item in result.items if item.op == "create" and item.planned_date]
    weeks = [w.week_start for w in payload.outline]
    start = plan.start_date or min([*created, *weeks], default=today)
    ends = [*created, *(w + timedelta(days=6) for w in weeks)]
    end = plan.end_date or (payload.race.date if payload.race else None) or plan.goal_date or max(ends, default=start)
    try:
        result.new_plan = TrainingPlanWrite(
            name=plan.name,
            sport=plan.sport,
            start_date=start,
            end_date=end,
            goal_text=plan.goal_text or payload.goal,
            goal_date=plan.goal_date or (payload.race.date if payload.race else None),
            hours_per_week=plan.hours_per_week,
            phases=plan.phases,
            weeks=payload.outline,
        )
    except ValidationError as exc:
        result.errors.extend(f"plan: {err['msg']}" for err in exc.errors()[:5])
        return
    outside = [d for d in created if not start <= d <= end]
    if outside:
        result.errors.append(f"plan: sessions on {outside[0]} fall outside the plan ({start} – {end})")


async def _replace_previous_program(
    db: AsyncSession, athlete: Athlete, result: Checked, touched: set[uuid.UUID], today: date, metric_rows
) -> None:
    """A new program for an existing plan replaces the upcoming sessions the
    AI wrote for that plan before, from the new program's first session on.
    Other plans are never touched."""
    created = [item.planned_date for item in result.items if item.op == "create" and item.planned_date]
    if not created:
        return
    start = max(min(created), today)
    plans = await db.scalars(
        select(PlannedSession)
        .where(
            PlannedSession.athlete_id == athlete.id,
            PlannedSession.training_plan_id == result.target.id,
            PlannedSession.created_by_ai.is_(True),
            PlannedSession.status == PlanStatus.PLANNED.value,
            PlannedSession.planned_date >= start,
        )
        .order_by(PlannedSession.planned_date)
    )
    for plan in plans:
        if plan.id in touched:  # the model already changes it
            continue
        result.replaced.append(plan)
        result.items.append(
            ProposalItem(
                op="delete",
                plan_id=plan.id,
                before=_snapshot(plan, _ftp_on(metric_rows, plan.planned_date)),
                planned_date=None,
                title=None,
                description=None,
                workout_name=None,
                workout=None,
                estimate=None,
                replaced=True,
            )
        )


def _check_reach(result: Checked, payload: ProposalPayload) -> None:
    """A program (it has a goal, a race or a new plan) should run up to its
    race or goal date: the detailed sessions and the outline together cover it."""
    if payload.goal is None and payload.race is None and payload.plan is None:
        return
    plan_goal = result.new_plan.goal_date if result.new_plan else (result.target.goal_date if result.target else None)
    target = payload.race.date if payload.race else plan_goal
    if target is None:
        return
    ends = [item.planned_date for item in result.items if item.planned_date]
    ends += [week.week_start + timedelta(days=6) for week in payload.outline]
    if result.target is not None:  # its outline already covers some weeks
        ends += [date.fromisoformat(w["week_start"]) + timedelta(days=6) for w in result.target.weeks or []]
    if not ends or max(ends) < target:
        result.warnings.append(f"outline_short:{target.isoformat()}")


def _stored_plan(plan: TrainingPlanWrite) -> dict:
    return {
        "name": plan.name,
        "sport": plan.sport,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "goal_text": plan.goal_text,
        "goal_date": plan.goal_date,
        "hours_per_week": plan.hours_per_week,
        "phases": [p.model_dump(mode="json", exclude_none=True) for p in plan.phases],
        "weeks": [w.model_dump(mode="json", exclude_none=True) for w in plan.weeks],
    }


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
    # The hours of every plan running that week (the new one included).
    covering = await plans_covering(db, athlete.id, first, last)
    if result.new_plan is not None:
        covering = [*covering, TrainingPlan(**_stored_plan(result.new_plan))]
    for week in result.weeks:
        week_end = week.week_start + timedelta(days=6)
        hours = sum(
            p.hours_per_week or 0 for p in covering if p.start_date <= week_end and p.end_date >= week.week_start
        )
        if hours and week.duration_s > hours * 3600 * HOURS_SLACK:
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
    checked = await check(db, athlete, payload, kind=kind)
    if checked.errors:
        return None, checked, checked.errors
    # One replan proposal at a time, and one per conversation: a newer one
    # (the model fixing its warnings, or the athlete asking for changes)
    # replaces the older.
    same = AiProposal.kind == ProposalKind.REPLAN.value if kind is ProposalKind.REPLAN else None
    if conversation_id is not None:
        same = AiProposal.conversation_id == conversation_id if same is None else (same | (AiProposal.conversation_id == conversation_id))
    if same is not None:
        for older in await db.scalars(
            select(AiProposal).where(
                AiProposal.athlete_id == athlete.id,
                AiProposal.status == ProposalStatus.PENDING.value,
                same,
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
    checked = await check(db, athlete, payload, kind=proposal.kind) if payload is not None else None
    return ProposalRead(
        id=proposal.id,
        kind=ProposalKind(proposal.kind),
        status=ProposalStatus(proposal.status),
        summary=proposal.summary,
        goal=payload.goal if payload else None,
        race=payload.race if payload else None,
        plan=payload.plan if payload else None,
        training_plan_id=payload.training_plan_id if payload else None,
        training_plan_name=checked.target.name if checked and checked.target else None,
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
    checked = await check(db, athlete, payload, kind=proposal.kind)
    if checked.errors:
        raise StaleProposal(checked.errors)

    plan_row = checked.target
    if checked.new_plan is not None:
        plan_row = TrainingPlan(
            athlete_id=athlete.id,
            created_by_user_id=None,
            created_by_ai=True,
            ai_proposal_id=proposal.id,
            **_stored_plan(checked.new_plan),
        )
        db.add(plan_row)
        await db.flush()

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
                training_plan_id=op.training_plan_id or (plan_row.id if plan_row else None),
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

    for plan in checked.replaced:
        await plan_changed(db, plan)
        await db.delete(plan)

    race = await _add_race(db, athlete, payload) if payload.race is not None else None
    if plan_row is not None:
        _refine_plan(plan_row, payload, proposal, race)

    proposal.status = ProposalStatus.ACCEPTED.value
    proposal.decided_at = utcnow()
    if checked.target is not None and proposal.kind == ProposalKind.PLAN.value:
        # A new program for a plan replaces the other ones still waiting for it.
        await supersede_for_plan(db, athlete.id, checked.target.id, keep=proposal.id)
    await db.commit()
    return touched


def _refine_plan(
    plan: TrainingPlan, payload: ProposalPayload, proposal: AiProposal, race: tuple[Competition, Goal | None] | None
) -> None:
    """The outline weeks the proposal gives replace those of the same weeks,
    and the plan's race is the proposal's. A plan the AI wrote also takes its
    goal; the athlete's own plan keeps theirs (they change it on the plan)."""
    if payload.outline and plan.weeks is not None:
        weeks = {w["week_start"]: w for w in plan.weeks or []}
        for week in payload.outline:
            weeks[week.week_start.isoformat()] = week.model_dump(mode="json", exclude_none=True)
        plan.weeks = [weeks[k] for k in sorted(weeks)]
    if plan.created_by_ai:
        plan.ai_proposal_id = proposal.id
        if payload.goal and payload.plan is None:
            plan.goal_text = payload.goal
    if race is not None:
        competition, goal = race
        if plan.competition_id is None or plan.created_by_ai:
            plan.competition_id = competition.id
        if goal is not None and plan.sport == "track_cycling" and (plan.goal_id is None or plan.created_by_ai):
            plan.goal_id = goal.id
    if plan.created_by_ai and plan.competition_id is None:
        # A plan the AI extends past its end grows with it (one aiming at a race ends there).
        for week in payload.outline:
            plan.end_date = max(plan.end_date, week.week_start + timedelta(days=6))


async def supersede_for_plan(
    db: AsyncSession, athlete_id: uuid.UUID, plan_id: uuid.UUID, *, keep: uuid.UUID | None = None
) -> None:
    """Pending proposals working on this plan are superseded (it was deleted,
    or another program for it was accepted)."""
    for other in await db.scalars(
        select(AiProposal).where(AiProposal.athlete_id == athlete_id, AiProposal.status == ProposalStatus.PENDING.value)
    ):
        if other.id != keep and (other.payload or {}).get("training_plan_id") == str(plan_id):
            other.status = ProposalStatus.SUPERSEDED.value
            other.decided_at = utcnow()


async def _add_race(db: AsyncSession, athlete: Athlete, payload: ProposalPayload) -> tuple[Competition, Goal | None]:
    """Puts the program's race on the season calendar, with its goal — unless
    the athlete already has a race that day or that goal (then they are
    reused, never duplicated). Returns both."""
    race = payload.race
    competition = await db.scalar(
        select(Competition).where(Competition.athlete_id == athlete.id, Competition.competition_date == race.date).limit(1)
    )
    if competition is None:
        competition = Competition(
            athlete_id=athlete.id,
            competition_date=race.date,
            name=race.name.strip(),
            priority=race.priority,
            location=race.location,
        )
        db.add(competition)
        await db.flush()
    if not race.makes_goal:
        return competition, None
    if competition.goal_id is not None:
        return competition, await db.get(Goal, competition.goal_id)
    goal = await db.scalar(
        select(Goal).where(
            Goal.athlete_id == athlete.id,
            Goal.event_key == race.event_key,
            Goal.start_type == race.start_type.value,
            Goal.target_date == race.date,
        ).limit(1)
    )
    if goal is None:
        baseline = best_entry(await get_records_board(db, athlete.id), race.event_key, race.start_type, None)
        goal = Goal(
            athlete_id=athlete.id,
            event_key=race.event_key,
            start_type=race.start_type.value,
            target_time_ms=race.target_time_ms,
            target_date=race.date,
            baseline_ms=baseline.time_ms if baseline else None,
        )
        db.add(goal)
        await db.flush()
    competition.goal_id = goal.id
    return competition, goal


async def reject(db: AsyncSession, proposal: AiProposal) -> None:
    """Raises `NotPending`."""
    await expire_if_due(proposal)
    if proposal.status != ProposalStatus.PENDING.value:
        await db.commit()
        raise NotPending
    proposal.status = ProposalStatus.REJECTED.value
    proposal.decided_at = utcnow()
    await db.commit()
