"""The workout library. A viewer sees their own workouts and those of every
coach actively coaching them, and edits only their own; anything they see
they may duplicate into their own library. Functions return None for a
workout the viewer can't see; those that change something commit.
"""

import uuid

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.coaching import self_athlete
from app.athletes.models import Athlete, CoachAthlete, CoachAthleteStatus
from app.auth.models import User
from app.workouts import structure
from app.workouts.models import Workout
from app.workouts.schemas import WorkoutItem, WorkoutRead, WorkoutSummary, WorkoutUpdate, WorkoutWrite

_ITEMS = TypeAdapter(list[WorkoutItem])


class NotAllowed(Exception):
    """Only the owner changes a workout."""


async def visible_owner_ids(db: AsyncSession, viewer: User) -> set[uuid.UUID]:
    """The viewer and their active coaches."""
    owners = {viewer.id}
    athlete = await self_athlete(db, viewer.id)
    if athlete is not None:
        owners |= set(
            await db.scalars(
                select(CoachAthlete.coach_user_id).where(
                    CoachAthlete.athlete_id == athlete.id, CoachAthlete.status == CoachAthleteStatus.ACTIVE
                )
            )
        )
    return owners


async def _owner_names(db: AsyncSession, owner_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    rows = await db.execute(select(Athlete.user_id, Athlete.display_name).where(Athlete.user_id.in_(owner_ids)))
    return dict(rows.all())


def _read(workout: Workout, viewer: User, names: dict[uuid.UUID, str]) -> WorkoutRead:
    steps = _ITEMS.validate_python(workout.steps)
    estimate = structure.estimate(steps)
    return WorkoutRead(
        id=workout.id,
        name=workout.name,
        description=workout.description,
        tags=list(workout.tags or []),
        is_track=structure.is_track(steps),
        duration_s=estimate.duration_s,
        tss=estimate.tss,
        owner_name=names.get(workout.owner_user_id),
        can_edit=workout.owner_user_id == viewer.id,
        created_at=workout.created_at,
        steps=steps,
        estimate=estimate,
    )


def _matches(read: WorkoutRead, query: str | None) -> bool:
    if not query:
        return True
    needle = query.strip().lower()
    haystack = [read.name, read.description or "", *read.tags]
    return any(needle in text.lower() for text in haystack)


async def list_workouts(
    db: AsyncSession,
    viewer: User,
    *,
    query: str | None = None,
    tag: str | None = None,
    track: bool | None = None,
    mine: bool | None = None,
    min_duration_s: float | None = None,
    max_duration_s: float | None = None,
) -> list[WorkoutSummary]:
    """By name. `mine` True keeps the viewer's own, False their coaches';
    `track` True keeps workouts with a track step, False the others. The
    filters on derived values run here rather than in SQL: a library is a
    few dozen rows."""
    owners = await visible_owner_ids(db, viewer)
    if mine is True:
        owners = {viewer.id}
    elif mine is False:
        owners.discard(viewer.id)
    workouts = list(
        await db.scalars(select(Workout).where(Workout.owner_user_id.in_(owners)).order_by(Workout.name, Workout.created_at))
    )
    names = await _owner_names(db, {w.owner_user_id for w in workouts})
    tag = tag.strip().lower() if tag else None
    summaries = []
    for workout in workouts:
        read = _read(workout, viewer, names)
        if not _matches(read, query) or (tag and tag not in read.tags):
            continue
        if track is not None and read.is_track != track:
            continue
        if min_duration_s is not None and read.duration_s < min_duration_s:
            continue
        if max_duration_s is not None and read.duration_s > max_duration_s:
            continue
        summaries.append(WorkoutSummary.model_validate(read.model_dump(include=set(WorkoutSummary.model_fields))))
    return summaries


async def _visible(db: AsyncSession, viewer: User, workout_id: uuid.UUID) -> Workout | None:
    workout = await db.get(Workout, workout_id)
    if workout is None or workout.owner_user_id not in await visible_owner_ids(db, viewer):
        return None
    return workout


async def _read_one(db: AsyncSession, viewer: User, workout: Workout) -> WorkoutRead:
    return _read(workout, viewer, await _owner_names(db, {workout.owner_user_id}))


async def get_workout(db: AsyncSession, viewer: User, workout_id: uuid.UUID) -> WorkoutRead | None:
    workout = await _visible(db, viewer, workout_id)
    return None if workout is None else await _read_one(db, viewer, workout)


def _stored_steps(steps: list) -> list[dict]:
    return _ITEMS.dump_python(steps, mode="json", exclude_none=True)


async def create_workout(db: AsyncSession, viewer: User, payload: WorkoutWrite) -> WorkoutRead:
    workout = Workout(
        owner_user_id=viewer.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
        steps=_stored_steps(payload.steps),
    )
    db.add(workout)
    await db.commit()
    return await _read_one(db, viewer, workout)


async def update_workout(
    db: AsyncSession, viewer: User, workout_id: uuid.UUID, payload: WorkoutUpdate
) -> WorkoutRead | None:
    """Raises `NotAllowed` for someone else's workout."""
    workout = await _visible(db, viewer, workout_id)
    if workout is None:
        return None
    if workout.owner_user_id != viewer.id:
        raise NotAllowed
    changes = payload.model_dump(exclude_unset=True)
    if "steps" in changes:
        changes["steps"] = _stored_steps(payload.steps or [])
    for field, value in changes.items():
        setattr(workout, field, value)
    await db.commit()
    return await _read_one(db, viewer, workout)


async def delete_workout(db: AsyncSession, viewer: User, workout_id: uuid.UUID) -> bool:
    """Raises `NotAllowed`; False when the viewer can't see it."""
    workout = await _visible(db, viewer, workout_id)
    if workout is None:
        return False
    if workout.owner_user_id != viewer.id:
        raise NotAllowed
    await db.delete(workout)
    await db.commit()
    return True


async def duplicate_workout(db: AsyncSession, viewer: User, workout_id: uuid.UUID) -> WorkoutRead | None:
    """A copy in the viewer's own library, to adapt."""
    source = await _visible(db, viewer, workout_id)
    if source is None:
        return None
    copy = Workout(
        owner_user_id=viewer.id,
        name=source.name,
        description=source.description,
        tags=list(source.tags or []),
        steps=list(source.steps or []),
    )
    db.add(copy)
    await db.commit()
    return await _read_one(db, viewer, copy)
