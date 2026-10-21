"""Planned sessions: what the coach (or the athlete) put on the calendar,
and the athlete's answer: done, skipped, or linked to the session ridden.
Functions return None when the plan isn't this athlete's; those that change
something commit.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.models import User
from app.planning.models import PlannedSession, PlanStatus
from app.planning.schemas import (
    LinkedSession,
    PlannedEffort,
    PlannedSessionRead,
    PlannedSessionUpdate,
    PlannedSessionWrite,
)
from app.training.models import TrainingEvent


class NotAllowed(Exception):
    """The viewer may not make this change."""


async def _reads(
    db: AsyncSession, athlete: Athlete, viewer: User, plans: list[PlannedSession]
) -> list[PlannedSessionRead]:
    if not plans:
        return []
    athlete_side = await speaks_for_athlete(db, viewer, athlete)
    author_ids = {p.created_by_user_id for p in plans if p.created_by_user_id}
    names = dict(
        (await db.execute(select(Athlete.user_id, Athlete.display_name).where(Athlete.user_id.in_(author_ids)))).all()
    )
    event_ids = {p.training_event_id for p in plans if p.training_event_id}
    events = {e.id: e for e in await db.scalars(select(TrainingEvent).where(TrainingEvent.id.in_(event_ids)))}
    reads = []
    for plan in plans:
        event = events.get(plan.training_event_id) if plan.training_event_id else None
        reads.append(
            PlannedSessionRead(
                id=plan.id,
                planned_date=plan.planned_date,
                title=plan.title,
                description=plan.description,
                targets=[PlannedEffort.model_validate(t) for t in plan.targets or []],
                status=PlanStatus(plan.status),
                created_by_name=names.get(plan.created_by_user_id),
                session=LinkedSession(
                    external_event_id=event.external_event_id,
                    event_name=event.title_override or event.name,
                    event_date=event.event_date,
                )
                if event
                else None,
                can_edit=athlete_side or plan.created_by_user_id == viewer.id,
                can_mark=athlete_side,
            )
        )
    return reads


async def list_plans(
    db: AsyncSession, athlete: Athlete, viewer: User, *, start: date | None, end: date | None
) -> list[PlannedSessionRead]:
    """Soonest first, between `start` and `end` (inclusive) when given."""
    query = select(PlannedSession).where(PlannedSession.athlete_id == athlete.id)
    if start is not None:
        query = query.where(PlannedSession.planned_date >= start)
    if end is not None:
        query = query.where(PlannedSession.planned_date <= end)
    plans = list(await db.scalars(query.order_by(PlannedSession.planned_date, PlannedSession.created_at)))
    return await _reads(db, athlete, viewer, plans)


async def _own(db: AsyncSession, athlete: Athlete, plan_id: uuid.UUID) -> PlannedSession | None:
    plan = await db.get(PlannedSession, plan_id)
    return plan if plan is not None and plan.athlete_id == athlete.id else None


async def _read_one(db: AsyncSession, athlete: Athlete, viewer: User, plan: PlannedSession) -> PlannedSessionRead:
    return (await _reads(db, athlete, viewer, [plan]))[0]


async def create_plan(
    db: AsyncSession, athlete: Athlete, viewer: User, payload: PlannedSessionWrite
) -> PlannedSessionRead:
    plan = PlannedSession(
        athlete_id=athlete.id,
        created_by_user_id=viewer.id,
        planned_date=payload.planned_date,
        title=payload.title,
        description=payload.description,
        targets=[t.model_dump(mode="json", exclude_none=True) for t in payload.targets],
    )
    db.add(plan)
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


async def update_plan(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID, payload: PlannedSessionUpdate
) -> PlannedSessionRead | None:
    """Raises `NotAllowed` when the viewer may not make one of the changes."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return None
    athlete_side = await speaks_for_athlete(db, viewer, athlete)
    changes = payload.model_dump(exclude_unset=True)
    new_status = changes.pop("status", None)
    if changes and not (athlete_side or plan.created_by_user_id == viewer.id):
        raise NotAllowed
    if new_status is not None and not athlete_side:
        raise NotAllowed
    if "targets" in changes:
        changes["targets"] = [t.model_dump(mode="json", exclude_none=True) for t in payload.targets or []]
    for field, value in changes.items():
        setattr(plan, field, value)
    if new_status is not None:
        plan.status = new_status.value
        if new_status is not PlanStatus.DONE:
            plan.training_event_id = None  # only a done plan stays linked
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


async def delete_plan(db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID) -> bool:
    """Raises `NotAllowed`; False when the plan isn't this athlete's."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return False
    if not (plan.created_by_user_id == viewer.id or await speaks_for_athlete(db, viewer, athlete)):
        raise NotAllowed
    await db.delete(plan)
    await db.commit()
    return True


class UnknownSession(Exception):
    """The athlete has no such session."""


async def link_session(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID, external_event_id: str
) -> PlannedSessionRead | None:
    """Ties the plan to the session that was ridden, which makes it done.
    Raises `NotAllowed` and `UnknownSession`."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return None
    if not await speaks_for_athlete(db, viewer, athlete):
        raise NotAllowed
    event = await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete.id, TrainingEvent.external_event_id == external_event_id
        )
    )
    if event is None:
        raise UnknownSession
    plan.training_event_id = event.id
    plan.status = PlanStatus.DONE.value
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


async def unlink_session(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID
) -> PlannedSessionRead | None:
    """Back to planned. Raises `NotAllowed`."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return None
    if not await speaks_for_athlete(db, viewer, athlete):
        raise NotAllowed
    plan.training_event_id = None
    plan.status = PlanStatus.PLANNED.value
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)
