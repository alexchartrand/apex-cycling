"""Goals: the target is stored, everything else (current best, gap, progress,
predicted time) is worked out when read. Functions return None when the goal
isn't this athlete's; those that change something commit.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import athlete_timezone, best_power_curve, local_day
from app.aero import service as aero_service
from app.analysis import physics
from app.athletes.models import Athlete
from app.athletes.service import metrics_at
from app.auth.models import User
from app.equipment.models import Bike
from app.goals.models import Goal
from app.goals.prediction import pick_power, predict_time_s
from app.goals.schemas import GoalBest, GoalPrediction, GoalRead, GoalUpdate, GoalWrite
from app.seasons.models import Competition
from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType
from app.training.models import Track
from app.training.records_service import UnknownTrackError, best_entry, get_records_board
from app.training.schemas import RecordEntry

# Power older than this says little about today's form.
POWER_WINDOW = timedelta(days=120)


@dataclass
class _Inputs:
    """What every goal of one request shares, loaded once and only when a goal needs it."""

    db: AsyncSession
    athlete: Athlete
    viewer: User
    board: list[RecordEntry]
    today: date
    tracks: dict[uuid.UUID, Track]
    bikes: dict[uuid.UUID, Bike]
    _power: list | None = None
    _cda: tuple[float, str, float] | None | bool = False  # False = not looked up yet
    _weight: float | None | bool = False

    async def power_curve(self):
        if self._power is None:
            now = datetime.now(timezone.utc)
            self._power = await best_power_curve(
                self.db, self.athlete, self.viewer, start=now - POWER_WINDOW, end=None
            )
        return self._power

    async def cda(self) -> tuple[float, str, float] | None:
        """The CdA of the newest saved aero test that has a fit, with its label
        and the bike weight it was worked out with."""
        if self._cda is False:
            self._cda = None
            for test in await aero_service.list_tests(self.db, self.athlete, self.viewer):
                if test.fit is not None:
                    self._cda = (test.fit.cda_m2, test.label, test.conditions.bike_kg)
                    break
        return self._cda

    async def weight(self) -> float | None:
        if self._weight is False:
            latest = (await metrics_at(self.db, self.athlete.id, self.today))["weight_kg"]
            self._weight = float(latest.value) if latest is not None else None
        return self._weight


async def _inputs(db: AsyncSession, athlete: Athlete, viewer: User) -> _Inputs:
    zone = await athlete_timezone(db, athlete)
    tracks = {track.id: track for track in await db.scalars(select(Track))}
    bikes = {bike.id: bike for bike in await db.scalars(select(Bike).where(Bike.athlete_id == athlete.id))}
    return _Inputs(
        db=db,
        athlete=athlete,
        viewer=viewer,
        board=await get_records_board(db, athlete.id),
        today=local_day(datetime.now(timezone.utc), zone),
        tracks=tracks,
        bikes=bikes,
    )


async def _predict(
    inputs: _Inputs, goal: Goal, best: RecordEntry | None
) -> tuple[GoalPrediction | None, str | None]:
    event = STANDARD_EVENTS_BY_KEY[goal.event_key]
    track_id = goal.track_id or (best.track_id if best else None)
    track = inputs.tracks.get(track_id) if track_id else None
    distance_m = event.distance_m
    if distance_m is None:  # one lap of whatever track
        if track is None:
            return None, "no_track"
        if not track.length_m:
            return None, "no_track_length"
        distance_m = track.length_m

    weight = await inputs.weight()
    if weight is None:
        return None, "no_weight"
    pick = pick_power(
        [(point.duration_s, point.power_w) for point in await inputs.power_curve()], goal.target_time_ms / 1000
    )
    if pick is None:
        return None, "no_power"
    cda = await inputs.cda()
    if cda is None:
        return None, "no_cda"

    point = next(p for p in await inputs.power_curve() if p.duration_s == pick.duration_s)
    rho = physics.air_density(
        track.default_temp_c if track and track.default_temp_c is not None else aero_service.DEFAULT_TEMP_C,
        elevation_m=track.elevation_m if track and track.elevation_m is not None else 0.0,
        humidity_pct=aero_service.DEFAULT_HUMIDITY_PCT,
    )
    bike = inputs.bikes.get(goal.bike_id) if goal.bike_id else None
    bike_kg = bike.weight_kg if bike is not None and bike.weight_kg is not None else cda[2]
    setup = physics.Setup(mass_kg=weight + bike_kg, cda_m2=cda[0], rho=rho)
    seconds = predict_time_s(distance_m, goal.start_type == StartType.STANDING.value, pick.power_w, setup)
    if seconds is None:
        return None, "no_power"
    return (
        GoalPrediction(
            time_ms=round(seconds * 1000),
            power_w=pick.power_w,
            power_duration_s=pick.duration_s,
            power_on=point.start_time,
            cda_m2=cda[0],
            cda_label=cda[1],
            rider_kg=weight,
            bike_kg=bike_kg,
        ),
        None,
    )


def progress_towards(goal: Goal, best: RecordEntry | None) -> float | None:
    if best is None or goal.baseline_ms is None or goal.baseline_ms <= goal.target_time_ms:
        return None
    done = (goal.baseline_ms - best.time_ms) / (goal.baseline_ms - goal.target_time_ms)
    return min(1.0, max(0.0, done))


async def _read(inputs: _Inputs, goal: Goal) -> GoalRead:
    best = best_entry(inputs.board, goal.event_key, goal.start_type, goal.track_id)
    prediction, problem = await _predict(inputs, goal, best)
    track = inputs.tracks.get(goal.track_id) if goal.track_id else None
    bike = inputs.bikes.get(goal.bike_id) if goal.bike_id else None
    return GoalRead(
        id=goal.id,
        event_key=goal.event_key,
        start_type=StartType(goal.start_type),
        track_id=goal.track_id,
        track_name=track.name if track else None,
        bike_id=goal.bike_id,
        bike_name=bike.name if bike else None,
        target_time_ms=goal.target_time_ms,
        target_date=goal.target_date,
        notes=goal.notes,
        baseline_ms=goal.baseline_ms,
        created_at=goal.created_at,
        best=GoalBest(time_ms=best.time_ms, achieved_on=best.achieved_on, place=best.place, track_id=best.track_id)
        if best
        else None,
        gap_ms=best.time_ms - goal.target_time_ms if best else None,
        achieved=best is not None and best.time_ms <= goal.target_time_ms,
        progress=progress_towards(goal, best),
        days_left=(goal.target_date - inputs.today).days,
        prediction=prediction,
        prediction_problem=problem,
    )


async def list_goals(db: AsyncSession, athlete: Athlete, viewer: User) -> list[GoalRead]:
    """Soonest target date first."""
    goals = list(
        await db.scalars(select(Goal).where(Goal.athlete_id == athlete.id).order_by(Goal.target_date, Goal.created_at))
    )
    if not goals:
        return []
    inputs = await _inputs(db, athlete, viewer)
    return [await _read(inputs, goal) for goal in goals]


async def _own_goal(db: AsyncSession, athlete_id: uuid.UUID, goal_id: uuid.UUID) -> Goal | None:
    goal = await db.get(Goal, goal_id)
    return goal if goal is not None and goal.athlete_id == athlete_id else None


async def _check_track(db: AsyncSession, track_id: uuid.UUID | None) -> None:
    if track_id is not None and await db.get(Track, track_id) is None:
        raise UnknownTrackError(str(track_id))


class UnknownBike(Exception):
    """The bike isn't one of this athlete's."""


async def _check_bike(db: AsyncSession, athlete_id: uuid.UUID, bike_id: uuid.UUID | None) -> None:
    if bike_id is None:
        return
    bike = await db.get(Bike, bike_id)
    if bike is None or bike.athlete_id != athlete_id:
        raise UnknownBike


async def create_goal(db: AsyncSession, athlete: Athlete, viewer: User, payload: GoalWrite) -> GoalRead:
    await _check_track(db, payload.track_id)
    await _check_bike(db, athlete.id, payload.bike_id)
    inputs = await _inputs(db, athlete, viewer)
    baseline = best_entry(inputs.board, payload.event_key, payload.start_type, payload.track_id)
    goal = Goal(
        athlete_id=athlete.id,
        event_key=payload.event_key,
        start_type=payload.start_type.value,
        track_id=payload.track_id,
        bike_id=payload.bike_id,
        target_time_ms=payload.target_time_ms,
        target_date=payload.target_date,
        notes=payload.notes,
        baseline_ms=baseline.time_ms if baseline else None,
    )
    db.add(goal)
    await db.commit()
    return await _read(inputs, goal)


async def update_goal(
    db: AsyncSession, athlete: Athlete, viewer: User, goal_id: uuid.UUID, payload: GoalUpdate
) -> GoalRead | None:
    goal = await _own_goal(db, athlete.id, goal_id)
    if goal is None:
        return None
    changes = payload.model_dump(exclude_unset=True)
    await _check_track(db, changes.get("track_id"))
    await _check_bike(db, athlete.id, changes.get("bike_id"))
    for field_name, value in changes.items():
        setattr(goal, field_name, value)
    await db.commit()
    return await _read(await _inputs(db, athlete, viewer), goal)


async def delete_goal(db: AsyncSession, athlete_id: uuid.UUID, goal_id: uuid.UUID) -> bool:
    goal = await _own_goal(db, athlete_id, goal_id)
    if goal is None:
        return False
    # A race aiming for this goal just loses the target.
    await db.execute(update(Competition).where(Competition.goal_id == goal_id).values(goal_id=None))
    await db.delete(goal)
    await db.commit()
    return True
