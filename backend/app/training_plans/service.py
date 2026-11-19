"""Training plans: CRUD, permissions and reads (with progress).

Anyone who passes `require_athlete_access` may make one for the athlete (a
coach plans). The author and the athlete's side edit or delete it, and so
does the athlete's active coach for a plan the AI coach wrote — the same rule
as for planned sessions. Functions return None when the plan isn't this
athlete's; those that change something commit.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import athlete_timezone, local_day
from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.models import User
from app.goals.models import Goal
from app.planning.models import PlannedSession, PlanStatus
from app.planning.push import plan_changed
from app.planning.service import _is_active_coach
from app.seasons.models import Competition
from app.training.efforts import StartType
from app.training_plans import phases as phase_rules
from app.training_plans.models import TrainingPlan
from app.training_plans.progress import session_facts, summarize
from app.training_plans.schemas import (
    Author,
    OutlineWeek,
    Phase,
    PlanGoal,
    PlanRace,
    TrainingPlanRead,
    TrainingPlanUpdate,
    TrainingPlanWrite,
)


class NotAllowed(Exception):
    """The viewer may not change this plan."""


class UnknownGoal(Exception):
    pass


class UnknownRace(Exception):
    pass


async def today_for(db: AsyncSession, athlete: Athlete) -> date:
    return local_day(datetime.now(timezone.utc), await athlete_timezone(db, athlete))


def author_of(plan: TrainingPlan, athlete: Athlete) -> Author:
    if plan.created_by_ai:
        return "ai"
    if plan.created_by_user_id is None or plan.created_by_user_id == athlete.user_id:
        return "athlete"
    return "coach"


def is_locked_for_ai(plan: TrainingPlan, athlete: Athlete) -> bool:
    """A plan the athlete's coach wrote: the AI coach doesn't add to it."""
    return author_of(plan, athlete) == "coach"


async def _may_edit(db: AsyncSession, viewer: User, athlete: Athlete, plan: TrainingPlan, athlete_side: bool) -> bool:
    if athlete_side or (plan.created_by_user_id is not None and plan.created_by_user_id == viewer.id):
        return True
    return plan.created_by_ai and await _is_active_coach(db, viewer, athlete)


async def _check_links(db: AsyncSession, athlete: Athlete, goal_id: uuid.UUID | None, race_id: uuid.UUID | None) -> None:
    """Raises `UnknownGoal` / `UnknownRace` for one that isn't this athlete's."""
    if goal_id is not None:
        goal = await db.get(Goal, goal_id)
        if goal is None or goal.athlete_id != athlete.id:
            raise UnknownGoal
    if race_id is not None:
        race = await db.get(Competition, race_id)
        if race is None or race.athlete_id != athlete.id:
            raise UnknownRace


async def _reads(
    db: AsyncSession, athlete: Athlete, viewer: User, plans: list[TrainingPlan], today: date
) -> list[TrainingPlanRead]:
    if not plans:
        return []
    athlete_side = await speaks_for_athlete(db, viewer, athlete)
    coach = not athlete_side and any(p.created_by_ai for p in plans) and await _is_active_coach(db, viewer, athlete)
    plan_ids = [p.id for p in plans]
    sessions = list(
        await db.scalars(select(PlannedSession).where(PlannedSession.training_plan_id.in_(plan_ids)))
    )
    facts = await session_facts(db, athlete, viewer, sessions)
    by_plan: dict[uuid.UUID, list] = {}
    for session in sessions:
        by_plan.setdefault(session.training_plan_id, []).append(facts[session.id])
    goal_ids = {p.goal_id for p in plans if p.goal_id}
    goals = {g.id: g for g in (await db.scalars(select(Goal).where(Goal.id.in_(goal_ids))) if goal_ids else [])}
    race_ids = {p.competition_id for p in plans if p.competition_id}
    races = {
        r.id: r for r in (await db.scalars(select(Competition).where(Competition.id.in_(race_ids))) if race_ids else [])
    }
    author_ids = {p.created_by_user_id for p in plans if p.created_by_user_id}
    names = (
        dict((await db.execute(select(Athlete.user_id, Athlete.display_name).where(Athlete.user_id.in_(author_ids)))).all())
        if author_ids
        else {}
    )
    reads = []
    for plan in plans:
        phases = [Phase.model_validate(p) for p in plan.phases or []]
        goal = goals.get(plan.goal_id) if plan.goal_id else None
        race = races.get(plan.competition_id) if plan.competition_id else None
        reads.append(
            TrainingPlanRead(
                id=plan.id,
                name=plan.name,
                sport=plan.sport,
                start_date=plan.start_date,
                end_date=plan.end_date,
                goal_text=plan.goal_text,
                goal_date=plan.goal_date,
                goal=PlanGoal(
                    id=goal.id,
                    event_key=goal.event_key,
                    start_type=StartType(goal.start_type),
                    target_time_ms=goal.target_time_ms,
                    target_date=goal.target_date,
                )
                if goal
                else None,
                race=PlanRace(id=race.id, name=race.name, date=race.competition_date, priority=race.priority)
                if race
                else None,
                hours_per_week=plan.hours_per_week,
                phases=phases,
                weeks=[OutlineWeek.model_validate(w) for w in plan.weeks or []],
                current_phase=phase_rules.current_phase(phases, today),
                state=phase_rules.plan_state(plan.start_date, plan.end_date, today),
                author=author_of(plan, athlete),
                created_by_name=names.get(plan.created_by_user_id),
                can_edit=athlete_side
                or (plan.created_by_user_id is not None and plan.created_by_user_id == viewer.id)
                or (plan.created_by_ai and coach),
                progress=summarize(by_plan.get(plan.id, []), today),
            )
        )
    return reads


async def list_plans(db: AsyncSession, athlete: Athlete, viewer: User) -> list[TrainingPlanRead]:
    """Newest start first."""
    plans = list(
        await db.scalars(
            select(TrainingPlan)
            .where(TrainingPlan.athlete_id == athlete.id)
            .order_by(TrainingPlan.start_date.desc(), TrainingPlan.created_at.desc())
        )
    )
    return await _reads(db, athlete, viewer, plans, await today_for(db, athlete))


async def own_plan(db: AsyncSession, athlete_id: uuid.UUID, plan_id: uuid.UUID) -> TrainingPlan | None:
    plan = await db.get(TrainingPlan, plan_id)
    return plan if plan is not None and plan.athlete_id == athlete_id else None


async def read_plan(db: AsyncSession, athlete: Athlete, viewer: User, plan: TrainingPlan) -> TrainingPlanRead:
    return (await _reads(db, athlete, viewer, [plan], await today_for(db, athlete)))[0]


async def get_plan(db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID) -> TrainingPlanRead | None:
    plan = await own_plan(db, athlete.id, plan_id)
    return None if plan is None else await read_plan(db, athlete, viewer, plan)


def _stored(payload: TrainingPlanWrite) -> dict:
    return {
        "name": payload.name,
        "sport": payload.sport,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "goal_text": payload.goal_text,
        "goal_date": payload.goal_date,
        "goal_id": payload.goal_id,
        "competition_id": payload.competition_id,
        "hours_per_week": payload.hours_per_week,
        "phases": [p.model_dump(mode="json", exclude_none=True) for p in payload.phases],
        "weeks": [w.model_dump(mode="json", exclude_none=True) for w in payload.weeks],
    }


async def create_plan(db: AsyncSession, athlete: Athlete, viewer: User, payload: TrainingPlanWrite) -> TrainingPlanRead:
    """Raises `UnknownGoal`, `UnknownRace`."""
    await _check_links(db, athlete, payload.goal_id, payload.competition_id)
    plan = TrainingPlan(athlete_id=athlete.id, created_by_user_id=viewer.id, **_stored(payload))
    db.add(plan)
    await db.commit()
    return await read_plan(db, athlete, viewer, plan)


def as_write(plan: TrainingPlan) -> dict:
    """The plan's stored fields in `TrainingPlanWrite` shape."""
    return {
        "name": plan.name,
        "sport": plan.sport,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "goal_text": plan.goal_text,
        "goal_date": plan.goal_date,
        "goal_id": plan.goal_id,
        "competition_id": plan.competition_id,
        "hours_per_week": plan.hours_per_week,
        "phases": plan.phases or [],
        "weeks": plan.weeks or [],
    }


async def update_plan(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID, payload: TrainingPlanUpdate
) -> TrainingPlanRead | None:
    """Raises `NotAllowed`, `UnknownGoal`, `UnknownRace`, and pydantic's
    ValidationError when the changed plan doesn't hold together."""
    plan = await own_plan(db, athlete.id, plan_id)
    if plan is None:
        return None
    if not await _may_edit(db, viewer, athlete, plan, await speaks_for_athlete(db, viewer, athlete)):
        raise NotAllowed
    merged = TrainingPlanWrite.model_validate({**as_write(plan), **payload.model_dump(exclude_unset=True)})
    await _check_links(db, athlete, merged.goal_id, merged.competition_id)
    for field, value in _stored(merged).items():
        setattr(plan, field, value)
    await db.commit()
    return await read_plan(db, athlete, viewer, plan)


async def delete_plan(db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID) -> bool:
    """Deletes the plan and its sessions still to ride (still planned, today
    or later; their Intervals.icu events go too); the others — done, skipped,
    missed — stay on the calendar without a plan. Pending AI proposals for it
    are superseded. Raises `NotAllowed`; False when it isn't this athlete's."""
    from app.coach_ai.proposals import supersede_for_plan  # coach_ai imports this module

    plan = await own_plan(db, athlete.id, plan_id)
    if plan is None:
        return False
    if not await _may_edit(db, viewer, athlete, plan, await speaks_for_athlete(db, viewer, athlete)):
        raise NotAllowed
    today = await today_for(db, athlete)
    for session in await db.scalars(select(PlannedSession).where(PlannedSession.training_plan_id == plan.id)):
        if session.status == PlanStatus.PLANNED.value and session.planned_date >= today:
            await plan_changed(db, session)
            await db.delete(session)
        else:
            session.training_plan_id = None
    await supersede_for_plan(db, athlete.id, plan.id)
    await db.flush()
    await db.delete(plan)
    await db.commit()
    return True


async def plan_names(db: AsyncSession, plan_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not plan_ids:
        return {}
    return dict((await db.execute(select(TrainingPlan.id, TrainingPlan.name).where(TrainingPlan.id.in_(plan_ids)))).all())


async def plans_covering(db: AsyncSession, athlete_id: uuid.UUID, start: date, end: date) -> list[TrainingPlan]:
    """The athlete's plans overlapping `start`…`end`, soonest first."""
    return list(
        await db.scalars(
            select(TrainingPlan)
            .where(TrainingPlan.athlete_id == athlete_id, TrainingPlan.start_date <= end, TrainingPlan.end_date >= start)
            .order_by(TrainingPlan.start_date)
        )
    )
