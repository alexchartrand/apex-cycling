"""Bikes, gear setups, and what a gear says about a ride: the cadence a fixed
gear implies at the speed of a lap or an effort. Functions return None when
the target isn't this athlete's; those that change something commit.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import physics
from app.equipment.models import Bike, GearSetup
from app.equipment.schemas import BikeRead, BikeUpdate, BikeWrite, GearRead, GearUpdate, GearWrite
from app.goals.models import Goal
from app.training.models import Track, TrainingEvent, TrainingLap
from app.training.schemas import EffortDetail, SessionDetail
from app.training.service import get_session_efforts


def gear_read(gear: GearSetup) -> GearRead:
    rollout_m = gear.rollout_mm / 1000
    return GearRead(
        id=gear.id,
        bike_id=gear.bike_id,
        chainring_teeth=gear.chainring_teeth,
        cog_teeth=gear.cog_teeth,
        rollout_mm=gear.rollout_mm,
        ratio=gear.chainring_teeth / gear.cog_teeth,
        development_m=physics.development_m(gear.chainring_teeth, gear.cog_teeth, rollout_m),
        gear_inches=physics.gear_inches(gear.chainring_teeth, gear.cog_teeth),
    )


def estimated_cadence_rpm(gear: GearSetup, distance_m: float | None, time_ms: int | None) -> float | None:
    """Cadence of a fixed gear over `distance_m` ridden in `time_ms`: the
    average speed, turned into pedal revolutions. It assumes the rider never
    coasts, which holds on a track bike."""
    if not distance_m or not time_ms or time_ms <= 0:
        return None
    return physics.cadence_from_speed_rpm(
        distance_m / (time_ms / 1000), gear.chainring_teeth, gear.cog_teeth, gear.rollout_mm / 1000
    )


# --- bikes and gears -------------------------------------------------------


async def list_bikes(db: AsyncSession, athlete_id: uuid.UUID) -> list[BikeRead]:
    bikes = list(await db.scalars(select(Bike).where(Bike.athlete_id == athlete_id).order_by(Bike.created_at)))
    gears = list(
        await db.scalars(select(GearSetup).where(GearSetup.athlete_id == athlete_id).order_by(GearSetup.created_at))
    )
    return [_bike_read(bike, [g for g in gears if g.bike_id == bike.id]) for bike in bikes]


def _bike_read(bike: Bike, gears: list[GearSetup]) -> BikeRead:
    return BikeRead(
        id=bike.id,
        name=bike.name,
        weight_kg=bike.weight_kg,
        notes=bike.notes,
        tire=bike.tire,
        crr=bike.crr,
        gears=[gear_read(g) for g in gears],
    )


async def _bike_read_by_id(db: AsyncSession, bike: Bike) -> BikeRead:
    gears = await db.scalars(select(GearSetup).where(GearSetup.bike_id == bike.id).order_by(GearSetup.created_at))
    return _bike_read(bike, list(gears))


async def _own_bike(db: AsyncSession, athlete_id: uuid.UUID, bike_id: uuid.UUID) -> Bike | None:
    bike = await db.get(Bike, bike_id)
    return bike if bike is not None and bike.athlete_id == athlete_id else None


async def _own_gear(db: AsyncSession, athlete_id: uuid.UUID, gear_id: uuid.UUID) -> GearSetup | None:
    gear = await db.get(GearSetup, gear_id)
    return gear if gear is not None and gear.athlete_id == athlete_id else None


async def create_bike(db: AsyncSession, athlete_id: uuid.UUID, payload: BikeWrite) -> BikeRead:
    bike = Bike(athlete_id=athlete_id, **payload.model_dump())
    db.add(bike)
    await db.commit()
    return _bike_read(bike, [])


async def update_bike(
    db: AsyncSession, athlete_id: uuid.UUID, bike_id: uuid.UUID, payload: BikeUpdate
) -> BikeRead | None:
    bike = await _own_bike(db, athlete_id, bike_id)
    if bike is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(bike, field, value)
    await db.commit()
    return await _bike_read_by_id(db, bike)


async def delete_bike(db: AsyncSession, athlete_id: uuid.UUID, bike_id: uuid.UUID) -> bool:
    """Removes the bike and its gears; sessions and efforts that used them
    just have no gear any more, goals on it fall back to the default bike."""
    bike = await _own_bike(db, athlete_id, bike_id)
    if bike is None:
        return False
    gear_ids = list(await db.scalars(select(GearSetup.id).where(GearSetup.bike_id == bike.id)))
    for gear_id in gear_ids:
        await _detach(db, gear_id)
        await db.delete(await db.get(GearSetup, gear_id))
    await db.execute(update(Goal).where(Goal.bike_id == bike.id).values(bike_id=None))
    await db.delete(bike)
    await db.commit()
    return True


async def _detach(db: AsyncSession, gear_id: uuid.UUID) -> None:
    await db.execute(update(TrainingEvent).where(TrainingEvent.gear_setup_id == gear_id).values(gear_setup_id=None))
    await db.execute(
        update(TrainingLap).where(TrainingLap.effort_gear_setup_id == gear_id).values(effort_gear_setup_id=None)
    )


async def create_gear(
    db: AsyncSession, athlete_id: uuid.UUID, bike_id: uuid.UUID, payload: GearWrite
) -> GearRead | None:
    if await _own_bike(db, athlete_id, bike_id) is None:
        return None
    gear = GearSetup(athlete_id=athlete_id, bike_id=bike_id, **payload.model_dump())
    db.add(gear)
    await db.commit()
    return gear_read(gear)


async def update_gear(
    db: AsyncSession, athlete_id: uuid.UUID, gear_id: uuid.UUID, payload: GearUpdate
) -> GearRead | None:
    gear = await _own_gear(db, athlete_id, gear_id)
    if gear is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(gear, field, value)
    await db.commit()
    return gear_read(gear)


async def delete_gear(db: AsyncSession, athlete_id: uuid.UUID, gear_id: uuid.UUID) -> bool:
    gear = await _own_gear(db, athlete_id, gear_id)
    if gear is None:
        return False
    await _detach(db, gear.id)
    await db.delete(gear)
    await db.commit()
    return True


# --- assigning a gear to a session or an effort ------------------------------


class UnknownGear(Exception):
    """The gear isn't one of this athlete's."""


async def _check_gear(db: AsyncSession, athlete_id: uuid.UUID, gear_id: uuid.UUID | None) -> None:
    if gear_id is not None and await _own_gear(db, athlete_id, gear_id) is None:
        raise UnknownGear


async def _event(db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str) -> TrainingEvent | None:
    return await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete_id, TrainingEvent.external_event_id == external_event_id
        )
    )


async def set_session_gear(
    db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str, gear_id: uuid.UUID | None
) -> bool:
    """False when the athlete has no such session. Raises `UnknownGear`."""
    event = await _event(db, athlete_id, external_event_id)
    if event is None:
        return False
    await _check_gear(db, athlete_id, gear_id)
    event.gear_setup_id = gear_id
    await db.commit()
    return True


async def set_effort_gear(
    db: AsyncSession,
    athlete_id: uuid.UUID,
    external_event_id: str,
    first_lap_id: uuid.UUID,
    gear_id: uuid.UUID | None,
) -> bool:
    """Gear for the effort starting with `first_lap_id`. False when that lap
    doesn't begin an effort of this athlete's session. Raises `UnknownGear`."""
    efforts = await get_session_efforts(db, athlete_id, external_event_id)
    if efforts is None or not any(effort.lap_ids[0] == first_lap_id for effort in efforts):
        return False
    await _check_gear(db, athlete_id, gear_id)
    lap = await db.get(TrainingLap, first_lap_id)
    lap.effort_gear_setup_id = gear_id
    await db.commit()
    return True


# --- estimated cadence on the session views ------------------------------------


async def _gears_by_id(db: AsyncSession, athlete_id: uuid.UUID) -> dict[uuid.UUID, GearSetup]:
    return {g.id: g for g in await db.scalars(select(GearSetup).where(GearSetup.athlete_id == athlete_id))}


async def add_gear_to_efforts(
    db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str, efforts: list[EffortDetail]
) -> None:
    """Fills each effort's estimated cadence from its own gear, else the
    session's. (`gear_setup_id` on the effort is only its own override.)"""
    event = await _event(db, athlete_id, external_event_id)
    gears = await _gears_by_id(db, athlete_id)
    for effort in efforts:
        gear = gears.get(effort.gear_setup_id) or (gears.get(event.gear_setup_id) if event else None)
        if gear is not None:
            effort.est_cadence_rpm = estimated_cadence_rpm(gear, effort.distance_m, effort.total_time_ms)


async def add_gear_to_session(
    db: AsyncSession, athlete_id: uuid.UUID, detail: SessionDetail, efforts: list[EffortDetail]
) -> None:
    """Sets the session's gear and, lap by lap, the cadence it implies at the
    lap's speed (the track's length over the lap time), using the gear of the
    effort the lap belongs to."""
    event = await _event(db, athlete_id, detail.external_event_id)
    detail.gear_setup_id = event.gear_setup_id if event else None
    gears = await _gears_by_id(db, athlete_id)
    gear_of_lap: dict[uuid.UUID, GearSetup | None] = {}
    for effort in efforts:
        gear = gears.get(effort.gear_setup_id) or gears.get(detail.gear_setup_id)
        for lap_id in effort.lap_ids:
            gear_of_lap[lap_id] = gear
    lengths = {
        track.id: track.length_m
        for track in await db.scalars(select(Track).where(Track.id.in_([t.track_id for t in detail.tracks])))
    }
    session_gear = gears.get(detail.gear_setup_id)
    for track in detail.tracks:
        for lap in track.laps:
            gear = gear_of_lap.get(lap.lap_id, session_gear)
            if gear is not None:
                lap.est_cadence_rpm = estimated_cadence_rpm(gear, lengths.get(track.track_id), lap.whole_lap_time_ms)
