"""The plan answered by what was ridden: expands the plan's workout (its
track steps), else its targets, into reps, scores each effort of the linked
session, and matches them (`matching.py`); then lays the workout's power and
cadence steps over a recording (`power_matching.py`) — the plan's own, else
the session's. Sqorz efforts aren't Strava-derived; recordings are read
through `visible_conditions`, so a coach never gets Strava numbers.
"""

import asyncio

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities import streams
from app.activities.metrics_service import _ftp_on, _metric_rows, visible_conditions
from app.activities.models import Activity, ActivityStream
from app.analysis.metrics import resample_1hz
from app.athletes.models import Athlete
from app.auth.models import User
from app.planning import power_matching
from app.planning.matching import EffortResults, RepOutcome, RepStatus, expand_reps, match_reps, workout_reps
from app.planning.models import PlannedSession
from app.planning.schemas import LinkedRecording, PlanComparison, RepResult, StepResult
from app.training.models import TrainingEvent
from app.training.records import session_results
from app.training.records_service import view_times_of
from app.training.service import _load_event_laps, detect_session_efforts
from app.workouts import structure
from app.workouts.schemas import WorkoutItem, WorkoutStep

_ITEMS = TypeAdapter(list[WorkoutItem])


class NoLinkedSession(Exception):
    """The plan has neither a session nor a recording to compare with."""


async def _effort_results(db: AsyncSession, plan: PlannedSession) -> tuple[list[EffortResults], float | None]:
    """The session's efforts, and the length of the track it was ridden on."""
    event = await db.get(TrainingEvent, plan.training_event_id)
    loaded = await _load_event_laps(db, plan.athlete_id, event.external_event_id) if event else None
    if loaded is None:
        return [], None
    event, laps = loaded
    laps_by_id = {lap.id: lap for lap in laps}
    results = []
    track_length_m = None
    for index, (track, effort) in enumerate(detect_session_efforts(laps), start=1):
        track_length_m = track_length_m or track.length_m
        results_of_effort = session_results(
            track_id=track.id,
            track_length_m=track.length_m,
            training_event_id=event.id,
            event_date=event.event_date,
            laps=list(effort.laps),
            view_times_ms=view_times_of(track, (laps_by_id[lap.lap_id] for lap in effort.laps)),
        )
        results.append(EffortResults(index, {(r.event_key, r.start_type): r.time_ms for r in results_of_effort}))
    return results, track_length_m


def _read(outcome: RepOutcome) -> RepResult:
    rep = outcome.rep
    return RepResult(
        target_index=rep.target_index,
        rep=rep.rep,
        label=rep.label,
        event_key=rep.event_key,
        target_time_ms=rep.target_time_ms,
        status=outcome.status,
        effort_index=outcome.effort_index,
        start_type=outcome.start_type,
        time_ms=outcome.time_ms,
        delta_ms=outcome.delta_ms,
    )


async def _recording(db: AsyncSession, athlete: Athlete, viewer: User, plan: PlannedSession) -> Activity | None:
    """The plan's own recording, else the first powered one linked to its session."""
    visible = visible_conditions(athlete, viewer)
    if plan.activity_id is not None:
        activity = await db.scalar(select(Activity).where(*visible, Activity.id == plan.activity_id))
        if activity is not None:
            return activity
    if plan.training_event_id is None:
        return None
    return await db.scalar(
        select(Activity)
        .where(*visible, Activity.training_event_id == plan.training_event_id, Activity.has_power.is_(True))
        .order_by(Activity.start_time)
        .limit(1)
    )


def _score(
    steps: list[WorkoutStep], stream: ActivityStream, ftp_w: float | None, track_length_m: float
) -> list[power_matching.StepOutcome]:
    time_s = streams.unpack("time_s", stream.time_s)

    def series(name: str) -> list[float] | None:
        blob = getattr(stream, name)
        return resample_1hz(time_s, streams.unpack(name, blob), pauses="zero") if blob is not None else None

    distance = (
        power_matching.cumulative_distance_1hz(time_s, streams.unpack("distance_m", stream.distance_m))
        if stream.distance_m is not None
        else None
    )
    return power_matching.score_steps(
        steps, series("power_w"), series("cadence"), distance, ftp_w=ftp_w, track_length_m=track_length_m
    )


def _step_read(outcome: power_matching.StepOutcome) -> StepResult:
    step = outcome.step
    return StepResult(
        step_index=outcome.step_index,
        kind=step.kind,
        label=step.label,
        power=step.power,
        cadence=step.cadence,
        power_low_w=outcome.power_target_w[0] if outcome.power_target_w else None,
        power_high_w=outcome.power_target_w[1] if outcome.power_target_w else None,
        start_s=outcome.start_s,
        end_s=outcome.end_s,
        avg_power_w=outcome.avg_power_w,
        avg_cadence=outcome.avg_cadence,
        power_status=outcome.power_status,
        cadence_status=outcome.cadence_status,
    )


async def compare_plan(db: AsyncSession, athlete: Athlete, viewer: User, plan: PlannedSession) -> PlanComparison:
    """Raises `NoLinkedSession`."""
    if plan.training_event_id is None and plan.activity_id is None:
        raise NoLinkedSession
    items = _ITEMS.validate_python(plan.workout) if plan.workout else None
    outcomes: list[RepOutcome] = []
    track_length_m = None
    if plan.training_event_id is not None:
        reps = workout_reps(items) if items else expand_reps(plan.targets or [])
        efforts, track_length_m = await _effort_results(db, plan)
        outcomes = match_reps(reps, efforts)
    measured = [o for o in outcomes if o.rep.target_time_ms is not None and o.rep.event_key is not None]
    comparison = PlanComparison(
        reps=[_read(o) for o in outcomes],
        measured=len(measured),
        hits=sum(1 for o in measured if o.status is RepStatus.HIT),
    )

    steps = list(structure.expand(items)) if items else []
    activity = await _recording(db, athlete, viewer, plan)
    if activity is None:
        return comparison
    comparison.recording = LinkedRecording(id=activity.id, name=activity.name, start_time=activity.start_time)
    stream = await db.get(ActivityStream, activity.id)
    if stream is None or not any(s.power is not None or s.cadence is not None for s in steps):
        return comparison
    ftp_w = _ftp_on(await _metric_rows(db, athlete.id), plan.planned_date)
    scored = await asyncio.to_thread(
        _score, steps, stream, ftp_w, track_length_m or structure.DEFAULT_TRACK_LENGTH_M
    )
    comparison.steps = [_step_read(o) for o in scored]
    with_power = [o for o in scored if o.power_status not in (None, power_matching.StepStatus.UNMEASURED)]
    comparison.power_measured = len(with_power)
    comparison.power_hits = sum(1 for o in with_power if o.power_status is power_matching.StepStatus.HIT)
    return comparison
