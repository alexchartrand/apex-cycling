"""What a workout's step tree adds up to: the steps in riding order, how
long they take and the training stress. Pure; the library uses it on every
read and the editor through `POST /workouts/estimate`.

Distances become time at a nominal speed (a step's own target time wins),
and laps become distance on `DEFAULT_TRACK_LENGTH_M` unless the caller
knows the track. These are rough on purpose: a library workout belongs to
no athlete and no track; exports refine them with the athlete's data.
"""

from collections.abc import Iterator, Sequence

from app.analysis.metrics import srpe_training_stress, training_stress_score
from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.workouts.schemas import (
    InnerRepeat,
    ProfileSegment,
    RepeatBlock,
    StepKind,
    WorkoutEstimate,
    WorkoutStep,
)

DEFAULT_TRACK_LENGTH_M = 250.0
# m/s: about 50 km/h for an effort, 36 km/h for anything else.
NOMINAL_SPEED_MPS = {StepKind.WORK: 14.0}
EASY_SPEED_MPS = 10.0
# What an open step (ends on the lap button) counts for where a step needs
# a length — Intervals.icu, trainer files.
OPEN_STEP_S = 60


def expand(items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat]) -> Iterator[WorkoutStep]:
    """The steps in the order they are ridden, repeats unrolled."""
    for item in items:
        if isinstance(item, WorkoutStep):
            yield item
        else:
            for _ in range(item.count):
                yield from expand(item.steps)


def is_track(items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat]) -> bool:
    return any(step.is_track for step in expand(items))


def step_distance_m(step: WorkoutStep, track_length_m: float) -> float | None:
    """Its own distance or laps, else its event's; None for a timed or open step."""
    if step.distance_m is not None:
        return step.distance_m
    if step.laps is not None:
        return step.laps * track_length_m
    if step.duration_s is None and step.event_key is not None:
        event = STANDARD_EVENTS_BY_KEY[step.event_key]
        return event.distance_m if event.distance_m is not None else track_length_m
    return None


def step_duration_s(step: WorkoutStep, track_length_m: float) -> float | None:
    """None for an open step."""
    if step.duration_s is not None:
        return float(step.duration_s)
    distance = step_distance_m(step, track_length_m)
    if distance is None:
        return None
    if step.target_time_ms is not None and step.event_key is not None:
        event = STANDARD_EVENTS_BY_KEY[step.event_key]
        event_distance = event.distance_m if event.distance_m is not None else track_length_m
        return distance / (event_distance / (step.target_time_ms / 1000))
    return distance / NOMINAL_SPEED_MPS.get(step.kind, EASY_SPEED_MPS)


def _power_fractions(step: WorkoutStep, ftp_w: float | None) -> tuple[float, float] | None:
    """The power target as fractions of FTP (low, high); None without one,
    or for watts when the FTP isn't known."""
    if step.power is None:
        return None
    high = step.power.high if step.power.high is not None else step.power.low
    if step.power.unit == "ftp_pct":
        return step.power.low / 100, high / 100
    if ftp_w is None:
        return None
    return step.power.low / ftp_w, high / ftp_w


def estimate(
    items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat],
    *,
    track_length_m: float | None = None,
    ftp_w: float | None = None,
) -> WorkoutEstimate:
    track_length = track_length_m or DEFAULT_TRACK_LENGTH_M
    segments: list[ProfileSegment] = []
    elapsed = tss = unrated = 0.0
    rated = False
    open_steps = 0
    for step in expand(items):
        duration = step_duration_s(step, track_length)
        if duration is None:
            open_steps += 1
            continue
        fractions = _power_fractions(step, ftp_w)
        if fractions is not None:
            intensity = (fractions[0] + fractions[1]) / 2
            tss += training_stress_score(duration, intensity, 1.0)
        elif step.rpe is not None:
            intensity = 0.30 + 0.08 * step.rpe  # the IF behind `srpe_training_stress`
            tss += srpe_training_stress(step.rpe, duration)
        else:
            intensity = None
            unrated += duration
        rated = rated or intensity is not None
        segments.append(
            ProfileSegment(
                start_s=elapsed,
                duration_s=duration,
                kind=step.kind,
                label=step.label,
                intensity=intensity,
                power_low=fractions[0] if fractions else None,
                power_high=fractions[1] if fractions else None,
                is_track=step.is_track,
            )
        )
        elapsed += duration
    return WorkoutEstimate(
        duration_s=elapsed,
        tss=round(tss, 1) if rated else None,
        unrated_s=unrated,
        open_steps=open_steps,
        segments=segments,
    )
