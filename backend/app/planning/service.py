"""Planned sessions: what the coach (or the athlete) put on the calendar,
and the athlete's answer: done, skipped, or linked to what was ridden (the
sqorz session, a recording, or both).
Functions return None when the plan isn't this athlete's; those that change
something commit.
"""

import uuid
from datetime import date

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import _ftp_on, _metric_rows, visible_conditions
from app.activities.models import Activity
from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.models import User
from app.equipment.models import Bike, GearSetup
from app.notifications.producers import notify_plan_added
from app.planning.comparison import NoLinkedSession, compare_plan  # noqa: F401  (re-exported for the router)
from app.planning.models import PlannedSession, PlanStatus
from app.planning.push import plan_changed, push_states
from app.planning.schemas import (
    PlanComparison,
    LinkedRecording,
    LinkedSession,
    PlannedEffort,
    PlannedEffortRead,
    PlannedSessionRead,
    PlannedSessionUpdate,
    PlannedSessionWrite,
    PlanWorkoutGear,
)
from app.training.models import TrainingEvent
from app.workouts import structure
from app.workouts.schemas import WorkoutItem
from app.workouts.service import visible_workout_ids

_ITEMS = TypeAdapter(list[WorkoutItem])


class NotAllowed(Exception):
    """The viewer may not make this change."""


class UnknownGear(Exception):
    """A planned effort names a gear that isn't one of this athlete's."""


class UnknownWorkout(Exception):
    """The plan names a library workout the viewer can't see."""


async def _gears(db: AsyncSession, athlete_id: uuid.UUID) -> list[PlanWorkoutGear]:
    """The athlete's gears as riders say them ("Track bike · 50×15"), by bike name."""
    rows = await db.execute(
        select(GearSetup.id, Bike.name, GearSetup.chainring_teeth, GearSetup.cog_teeth)
        .join(Bike, Bike.id == GearSetup.bike_id)
        .where(GearSetup.athlete_id == athlete_id)
        .order_by(Bike.name, GearSetup.chainring_teeth, GearSetup.cog_teeth)
    )
    return [
        PlanWorkoutGear(chainring_teeth=ring, cog_teeth=cog, gear_setup_id=gear_id, label=f"{bike} · {ring}×{cog}")
        for gear_id, bike, ring, cog in rows.all()
    ]


async def _gear_labels(db: AsyncSession, athlete_id: uuid.UUID) -> dict[uuid.UUID, str]:
    return {gear.gear_setup_id: gear.label for gear in await _gears(db, athlete_id)}


def _workout_gears(items: list, gears: list[PlanWorkoutGear]) -> list[PlanWorkoutGear]:
    """For each ratio the workout asks for, the athlete's first gear with
    those teeth (several bikes may have one; ratios they lack are left out)."""
    wanted = {(s.gear.chainring_teeth, s.gear.cog_teeth) for s in structure.expand(items) if s.gear is not None}
    matched: dict[tuple[int, int], PlanWorkoutGear] = {}
    for gear in gears:
        matched.setdefault((gear.chainring_teeth, gear.cog_teeth), gear)
    return [matched[teeth] for teeth in sorted(wanted) if teeth in matched]


async def _check_source(db: AsyncSession, viewer: User, workout_id: uuid.UUID | None) -> None:
    """Raises `UnknownWorkout`."""
    if workout_id is not None and not await visible_workout_ids(db, viewer, {workout_id}):
        raise UnknownWorkout


def _stored_workout(items: list | None) -> list[dict] | None:
    return None if items is None else _ITEMS.dump_python(items, mode="json", exclude_none=True)


async def _stored_targets(db: AsyncSession, athlete: Athlete, targets: list[PlannedEffort]) -> list[dict]:
    """Raises `UnknownGear`."""
    gear_ids = {t.gear_setup_id for t in targets if t.gear_setup_id is not None}
    if gear_ids - set(await _gear_labels(db, athlete.id)):
        raise UnknownGear
    return [t.model_dump(mode="json", exclude_none=True) for t in targets]


def _target_read(stored: dict, gear_labels: dict[uuid.UUID, str]) -> PlannedEffortRead:
    target = PlannedEffortRead.model_validate(stored)
    label = gear_labels.get(target.gear_setup_id) if target.gear_setup_id else None
    return target.model_copy(update={"gear_setup_id": target.gear_setup_id if label else None, "gear_label": label})


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
    activity_ids = {p.activity_id for p in plans if p.activity_id}
    activities = {
        a.id: a
        for a in await db.scalars(
            select(Activity).where(*visible_conditions(athlete, viewer), Activity.id.in_(activity_ids))
        )
    }
    gears = await _gears(db, athlete.id)
    gear_labels = {gear.gear_setup_id: gear.label for gear in gears}
    with_workout = [p for p in plans if p.workout]
    metric_rows = await _metric_rows(db, athlete.id) if with_workout else []
    sources = await visible_workout_ids(db, viewer, {p.source_workout_id for p in plans if p.source_workout_id})
    pushed = await push_states(db, {p.id for p in plans})
    reads = []
    for plan in plans:
        event = events.get(plan.training_event_id) if plan.training_event_id else None
        activity = activities.get(plan.activity_id) if plan.activity_id else None
        workout = _ITEMS.validate_python(plan.workout) if plan.workout else None
        reads.append(
            PlannedSessionRead(
                id=plan.id,
                planned_date=plan.planned_date,
                title=plan.title,
                description=plan.description,
                targets=[_target_read(t, gear_labels) for t in plan.targets or []],
                workout=workout,
                workout_estimate=structure.estimate(workout, ftp_w=_ftp_on(metric_rows, plan.planned_date))
                if workout
                else None,
                workout_gears=_workout_gears(workout, gears) if workout else [],
                source_workout_id=plan.source_workout_id if plan.source_workout_id in sources else None,
                status=PlanStatus(plan.status),
                created_by_name=names.get(plan.created_by_user_id),
                session=LinkedSession(
                    external_event_id=event.external_event_id,
                    event_name=event.title_override or event.name,
                    event_date=event.event_date,
                )
                if event
                else None,
                activity=LinkedRecording(id=activity.id, name=activity.name, start_time=activity.start_time)
                if activity
                else None,
                can_edit=athlete_side or plan.created_by_user_id == viewer.id,
                can_mark=athlete_side,
                intervals=pushed.get(plan.id),
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


async def comparison(db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID) -> PlanComparison | None:
    """The plan against its linked session and recording. None when the plan
    isn't this athlete's; raises `NoLinkedSession`."""
    plan = await _own(db, athlete, plan_id)
    return None if plan is None else await compare_plan(db, athlete, viewer, plan)


async def _read_one(db: AsyncSession, athlete: Athlete, viewer: User, plan: PlannedSession) -> PlannedSessionRead:
    return (await _reads(db, athlete, viewer, [plan]))[0]


async def create_plan(
    db: AsyncSession, athlete: Athlete, viewer: User, payload: PlannedSessionWrite
) -> PlannedSessionRead:
    """Raises `UnknownGear` for another athlete's gear, `UnknownWorkout` for
    a library workout the viewer can't see."""
    await _check_source(db, viewer, payload.source_workout_id)
    plan = PlannedSession(
        athlete_id=athlete.id,
        created_by_user_id=viewer.id,
        planned_date=payload.planned_date,
        title=payload.title,
        description=payload.description,
        targets=await _stored_targets(db, athlete, payload.targets),
        workout=_stored_workout(payload.workout),
        source_workout_id=payload.source_workout_id if payload.workout else None,
    )
    db.add(plan)
    await notify_plan_added(db, athlete, viewer, payload.title, payload.planned_date)
    await plan_changed(db, plan)
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


async def update_plan(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID, payload: PlannedSessionUpdate
) -> PlannedSessionRead | None:
    """Raises `NotAllowed` when the viewer may not make one of the changes,
    `UnknownGear` for another athlete's gear, `UnknownWorkout`."""
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
        changes["targets"] = await _stored_targets(db, athlete, payload.targets or [])
    if "source_workout_id" in changes:
        await _check_source(db, viewer, payload.source_workout_id)
    if "workout" in changes:
        changes["workout"] = _stored_workout(payload.workout)
        if payload.workout is None:
            changes["source_workout_id"] = None  # nothing copied from it any more
    for field, value in changes.items():
        setattr(plan, field, value)
    if new_status is not None:
        plan.status = new_status.value
        if new_status is not PlanStatus.DONE:
            plan.training_event_id = plan.activity_id = None  # only a done plan stays linked
    await plan_changed(db, plan)
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


async def delete_plan(db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID) -> bool:
    """Raises `NotAllowed`; False when the plan isn't this athlete's."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return False
    if not (plan.created_by_user_id == viewer.id or await speaks_for_athlete(db, viewer, athlete)):
        raise NotAllowed
    await plan_changed(db, plan)  # its event goes too
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
    """Back to planned, unless a recording is still linked. Raises `NotAllowed`."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return None
    if not await speaks_for_athlete(db, viewer, athlete):
        raise NotAllowed
    plan.training_event_id = None
    if plan.activity_id is None:
        plan.status = PlanStatus.PLANNED.value
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


class UnknownActivity(Exception):
    """The athlete has no such recording, or the viewer can't see it."""


async def link_activity(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID, activity_id: uuid.UUID
) -> PlannedSessionRead | None:
    """Ties the plan to the recording of the ride, which makes it done.
    Raises `NotAllowed` and `UnknownActivity`."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return None
    if not await speaks_for_athlete(db, viewer, athlete):
        raise NotAllowed
    activity = await db.scalar(
        select(Activity).where(*visible_conditions(athlete, viewer), Activity.id == activity_id)
    )
    if activity is None:
        raise UnknownActivity
    plan.activity_id = activity.id
    plan.status = PlanStatus.DONE.value
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)


async def unlink_activity(
    db: AsyncSession, athlete: Athlete, viewer: User, plan_id: uuid.UUID
) -> PlannedSessionRead | None:
    """Back to planned, unless a session is still linked. Raises `NotAllowed`."""
    plan = await _own(db, athlete, plan_id)
    if plan is None:
        return None
    if not await speaks_for_athlete(db, viewer, athlete):
        raise NotAllowed
    plan.activity_id = None
    if plan.training_event_id is None:
        plan.status = PlanStatus.PLANNED.value
    await db.commit()
    return await _read_one(db, athlete, viewer, plan)
