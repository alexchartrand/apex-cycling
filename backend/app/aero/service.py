"""CdA estimates from a session's laps and the recording linked to it.

The arithmetic is in `analysis/aero.py`; this module gathers its inputs: lap
times from sqorz (grouped into efforts, so each lap knows its neighbours), the
recording's power over each lap (shifted by its clock offset, through the same
`fusion_service.Recording` the lap table uses, so a viewer only ever gets
numbers from recordings they may see), the air from the track's settings and
the rider's weight from their profile.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.fusion_service import Recording, _ts, linked_recordings
from app.aero.models import AeroTest
from app.aero.schemas import (
    AeroConditionsRead,
    AeroEstimateRead,
    AeroFitRead,
    AeroInputs,
    AeroPointRead,
    AeroTestCreate,
    AeroTestDetail,
    AeroTestRead,
    AeroTestUpdate,
    AeroTrackChoice,
)
from app.analysis import aero, physics
from app.athletes.models import Athlete, AthleteMetric
from app.athletes.service import metrics_as_of
from app.equipment.models import Bike, GearSetup
from app.auth.models import User
from app.training.efforts import group_continuous_laps
from app.training.models import Track, TrainingEvent, TrainingLap
from app.training.service import _lap_input, _load_event_laps

DEFAULT_TEMP_C = 20.0
DEFAULT_HUMIDITY_PCT = 50.0
DEFAULT_BIKE_KG = 8.0
# Power has to cover nearly all of a lap for its mean to stand for the lap.
_POWER_COVERAGE = 0.9


class TrackNotInSession(Exception):
    pass


@dataclass
class SessionData:
    """Everything an estimate needs from the database, loaded once so several
    estimates on one session (saved aero tests) don't reload it."""

    event: TrainingEvent
    laps_by_track: dict[uuid.UUID, list[TrainingLap]]
    tracks: dict[uuid.UUID, Track]
    recordings: list[Recording]
    metric_rows: list[AthleteMetric]
    # Weight of the bike in the session's gear, when it has one and the bike's weight is known.
    session_bike_kg: float | None = None


async def load_session(
    db: AsyncSession, athlete: Athlete, viewer: User, external_event_id: str
) -> SessionData | None:
    loaded = await _load_event_laps(db, athlete.id, external_event_id)
    if loaded is None:
        return None
    event, laps = loaded
    laps_by_track: dict[uuid.UUID, list[TrainingLap]] = {}
    tracks: dict[uuid.UUID, Track] = {}
    for lap in laps:
        track = lap.event_track.track
        tracks[track.id] = track
        laps_by_track.setdefault(track.id, []).append(lap)
    metric_rows = list(await db.scalars(select(AthleteMetric).where(AthleteMetric.athlete_id == athlete.id)))
    bike_kg = None
    if event.gear_setup_id is not None:
        gear = await db.get(GearSetup, event.gear_setup_id)
        bike = await db.get(Bike, gear.bike_id) if gear is not None else None
        bike_kg = bike.weight_kg if bike is not None else None
    return SessionData(
        event, laps_by_track, tracks, await linked_recordings(db, athlete, viewer, event), metric_rows, bike_kg
    )


def _rider_weight(rows: list[AthleteMetric], day: date) -> tuple[float, date] | None:
    """The weight on the day, else the first one entered after it (people
    tend to fill in their profile after their first sessions)."""
    on_day = metrics_as_of(rows, day)["weight_kg"]
    if on_day is not None:
        return float(on_day.value), on_day.effective_date
    later = sorted((r for r in rows if r.weight_kg is not None), key=lambda r: r.effective_date)
    return (later[0].weight_kg, later[0].effective_date) if later else None


def _power(recordings: list[Recording], start: float, end: float) -> tuple[float, float] | None:
    for recording in recordings:
        if "power_w" in recording.channels and recording.covers(start, end):
            return recording.stats("power_w", start, end, min_coverage=_POWER_COVERAGE)
    return None


@dataclass(frozen=True)
class _LapRef:
    lap: TrainingLap
    effort_index: int
    lap_in_effort: int


def _aero_laps(laps: list[TrainingLap], length_m: float, recordings: list[Recording]) -> list[tuple[aero.AeroLap, _LapRef]]:
    by_id = {lap.id: lap for lap in laps}
    result = []
    for effort_index, group in enumerate(group_continuous_laps([_lap_input(lap) for lap in laps]), start=1):
        for i, lap_input in enumerate(group):
            total_ms = lap_input.total_time_ms
            if not total_ms:
                continue  # unfinished: no lap time
            previous = group[i - 1].total_time_ms if i > 0 else None
            following = group[i + 1].total_time_ms if i + 1 < len(group) else None
            start = _ts(lap_input.start_time)
            power = _power(recordings, start, start + total_ms / 1000)
            aero_lap = aero.AeroLap(
                key=str(lap_input.lap_id),
                length_m=length_m,
                time_s=total_ms / 1000,
                power_w=power[0] if power else None,
                power_sd_w=power[1] if power else None,
                previous_time_s=previous / 1000 if previous else None,
                next_time_s=following / 1000 if following else None,
                excluded=lap_input.excluded,
            )
            result.append((aero_lap, _LapRef(by_id[lap_input.lap_id], effort_index, i + 1)))
    return result


def estimate(
    data: SessionData,
    inputs: AeroInputs,
    *,
    track_id: uuid.UUID | None = None,
    lap_ids: Collection[uuid.UUID] | None = None,
) -> AeroEstimateRead:
    """The estimate for one track of the session. Raises `TrackNotInSession`."""
    if track_id is None:
        track_id = max(data.laps_by_track, key=lambda t: len(data.laps_by_track[t])) if data.laps_by_track else None
    if track_id not in data.laps_by_track:
        raise TrackNotInSession
    track = data.tracks[track_id]

    temp_c = inputs.temp_c if inputs.temp_c is not None else track.default_temp_c if track.default_temp_c is not None else DEFAULT_TEMP_C
    elevation_m = inputs.elevation_m if inputs.elevation_m is not None else track.elevation_m or 0.0
    humidity_pct = inputs.humidity_pct if inputs.humidity_pct is not None else DEFAULT_HUMIDITY_PCT
    rho = physics.air_density(
        temp_c,
        pressure_pa=inputs.pressure_hpa * 100 if inputs.pressure_hpa is not None else None,
        elevation_m=elevation_m,
        humidity_pct=humidity_pct,
    )
    weight = (inputs.rider_kg, None) if inputs.rider_kg is not None else _rider_weight(data.metric_rows, data.event.event_date)
    bike_kg = (
        inputs.bike_kg
        if inputs.bike_kg is not None
        else data.session_bike_kg
        if data.session_bike_kg is not None
        else DEFAULT_BIKE_KG
    )
    conditions = AeroConditionsRead(
        temp_c=temp_c,
        elevation_m=elevation_m,
        pressure_hpa=inputs.pressure_hpa,
        humidity_pct=humidity_pct,
        rho=rho,
        rider_kg=weight[0] if weight else None,
        rider_kg_date=weight[1] if weight else None,
        bike_kg=bike_kg,
        efficiency=physics.DEFAULT_EFFICIENCY,
    )

    points: list[AeroPointRead] = []
    fit = None
    if track.length_m is None:
        problem = "no_track_length"
    elif weight is None:
        problem = "no_weight"
    else:
        pairs = _aero_laps(data.laps_by_track[track_id], track.length_m, data.recordings)
        result = aero.estimate(
            [aero_lap for aero_lap, _ in pairs],
            aero.AeroConditions(rho=rho, mass_kg=weight[0] + bike_kg),
            crr=inputs.crr,
            selected={str(lap_id) for lap_id in lap_ids} if lap_ids is not None else None,
        )
        for point, (aero_lap, ref) in zip(result.points, pairs):
            points.append(
                AeroPointRead(
                    lap_id=ref.lap.id,
                    start_time=ref.lap.start_time,
                    effort_index=ref.effort_index,
                    lap_in_effort=ref.lap_in_effort,
                    time_s=aero_lap.time_s,
                    speed_ms=point.speed_ms,
                    power_w=point.power_w,
                    resistance_n=point.resistance_n,
                    cda_m2=point.cda_m2,
                    issue=point.issue,
                    used=point.used,
                )
            )
        if result.fit is not None:
            fit = AeroFitRead(**result.fit.__dict__)
            problem = None
        elif not any(point.power_w is not None for point in points):
            problem = "no_power"
        else:
            problem = "too_few_laps"

    return AeroEstimateRead(
        external_event_id=data.event.external_event_id,
        event_name=data.event.title_override or data.event.name,
        event_date=data.event.event_date,
        track_id=track.id,
        track_name=track.name,
        track_length_m=track.length_m,
        tracks=[
            AeroTrackChoice(track_id=t.id, track_name=t.name, length_m=t.length_m, lap_count=len(data.laps_by_track[t.id]))
            for t in data.tracks.values()
        ],
        conditions=conditions,
        points=points,
        fit=fit,
        problem=problem,
    )


# --- saved tests ---------------------------------------------------------------

_INPUT_FIELDS = tuple(AeroInputs.model_fields)
_SETUP_FIELDS = ("label", "position", "helmet", "skinsuit", "bike", "notes")


def _inputs(test: AeroTest) -> AeroInputs:
    return AeroInputs.model_validate({field: getattr(test, field) for field in _INPUT_FIELDS})


def _lap_ids(test: AeroTest) -> list[uuid.UUID] | None:
    return [uuid.UUID(lap_id) for lap_id in test.lap_ids] if test.lap_ids is not None else None


def _test_read(test: AeroTest, data: SessionData, *, detail: bool) -> AeroTestRead:
    result = estimate(data, _inputs(test), track_id=test.track_id, lap_ids=_lap_ids(test))
    fields = dict(
        id=test.id,
        external_event_id=result.external_event_id,
        event_name=result.event_name,
        event_date=result.event_date,
        track_id=result.track_id,
        track_name=result.track_name,
        lap_ids=_lap_ids(test),
        inputs=_inputs(test),
        created_at=test.created_at,
        conditions=result.conditions,
        fit=result.fit,
        problem=result.problem,
        **{field: getattr(test, field) for field in _SETUP_FIELDS},
    )
    return AeroTestDetail(**fields, points=result.points) if detail else AeroTestRead(**fields)


async def _session_of(db: AsyncSession, athlete: Athlete, viewer: User, test: AeroTest) -> SessionData:
    event = await db.get(TrainingEvent, test.training_event_id)
    data = await load_session(db, athlete, viewer, event.external_event_id)
    assert data is not None  # tests belong to the athlete's own sessions
    return data


async def list_tests(db: AsyncSession, athlete: Athlete, viewer: User) -> list[AeroTestRead]:
    """Newest session first; each session is loaded once for all its tests."""
    rows = await db.execute(
        select(AeroTest, TrainingEvent.external_event_id)
        .join(TrainingEvent, TrainingEvent.id == AeroTest.training_event_id)
        .where(AeroTest.athlete_id == athlete.id)
        .order_by(TrainingEvent.event_date.desc(), AeroTest.created_at)
    )
    sessions: dict[str, SessionData] = {}
    reads = []
    for test, external_event_id in rows:
        if external_event_id not in sessions:
            loaded = await load_session(db, athlete, viewer, external_event_id)
            assert loaded is not None
            sessions[external_event_id] = loaded
        reads.append(_test_read(test, sessions[external_event_id], detail=False))
    return reads


async def get_test(db: AsyncSession, athlete: Athlete, test_id: uuid.UUID) -> AeroTest | None:
    return await db.scalar(select(AeroTest).where(AeroTest.id == test_id, AeroTest.athlete_id == athlete.id))


async def read_test(db: AsyncSession, athlete: Athlete, viewer: User, test: AeroTest) -> AeroTestDetail:
    return _test_read(test, await _session_of(db, athlete, viewer, test), detail=True)


async def create_test(
    db: AsyncSession, athlete: Athlete, viewer: User, payload: AeroTestCreate
) -> AeroTestDetail | None:
    """None when the athlete has no such session; raises `TrackNotInSession`.
    Commits."""
    data = await load_session(db, athlete, viewer, payload.external_event_id)
    if data is None:
        return None
    track_id = estimate(data, payload, track_id=payload.track_id).track_id  # resolves the default track
    test = AeroTest(
        athlete_id=athlete.id,
        training_event_id=data.event.id,
        track_id=track_id,
        lap_ids=[str(lap_id) for lap_id in payload.lap_ids] if payload.lap_ids is not None else None,
        **{field: getattr(payload, field) for field in (*_INPUT_FIELDS, *_SETUP_FIELDS)},
    )
    db.add(test)
    await db.commit()
    return _test_read(test, data, detail=True)


async def update_test(
    db: AsyncSession, athlete: Athlete, viewer: User, test: AeroTest, payload: AeroTestUpdate
) -> AeroTestDetail:
    """Commits."""
    changes = payload.model_dump(exclude_unset=True)
    if "lap_ids" in changes:
        lap_ids = changes.pop("lap_ids")
        test.lap_ids = [str(lap_id) for lap_id in lap_ids] if lap_ids is not None else None
    for field, value in changes.items():
        setattr(test, field, value)
    await db.commit()
    return await read_test(db, athlete, viewer, test)
