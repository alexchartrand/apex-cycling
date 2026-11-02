"""What every workout export shares. Pure.

A trainer file (`.zwo`, `.erg`, `.mrc`) is a timeline: every step needs a
duration and a power. `trainer_steps` gives it, repeats unrolled:

- A track step (laps or a standard event) lasts its event's pace over its
  distance: the step's target time, else the athlete's best at that event
  and start (anywhere), else `physics.simulate` at the tools' defaults.
  Laps without an event go at the nominal speeds of `structure`.
- An open step (lap button) lasts `structure.OPEN_STEP_S`.
- Power is the target as fractions of FTP (watts need the FTP), else what
  each format does without one: Zwift rides it free, ERG/MRC use
  `fallback_fraction` — the RPE's IF, all out for a track effort, an easy
  pace otherwise.

The FIT workout keeps the step tree instead (`fit.py`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.analysis import physics
from app.notifications.messages import DEFAULT_LOCALE
from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType
from app.workouts import structure
from app.workouts.cues import step_cue
from app.workouts.schemas import InnerRepeat, RepeatBlock, StepKind, WorkoutStep

# `physics.simulate` inputs for a track step nobody has a time for: the
# tools' fallbacks (`frontend/src/features/tools/toolInputs.ts`).
DEFAULT_MASS_KG = 75 + 8
DEFAULT_CDA_M2 = 0.22
DEFAULT_TEMP_C = 20.0
DEFAULT_HUMIDITY_PCT = 50.0
DEFAULT_EFFORT_POWER_W = 400.0

# ERG/MRC need a number on every step: a track effort without a power
# target is all out, anything else without one is ridden easy.
MAX_EFFORT_FRACTION = 1.5
EASY_FRACTION = {StepKind.WARMUP: 0.55, StepKind.WORK: 0.75, StepKind.RECOVERY: 0.5, StepKind.COOLDOWN: 0.5}


class NeedsFtp(Exception):
    """The format writes watts or % of FTP and a target is in the other unit."""


@dataclass(frozen=True)
class ExportContext:
    """`ftp_w`: the athlete's FTP on the day (None: unknown); `best_times_ms`:
    their best per (event key, start), any track."""

    ftp_w: float | None = None
    best_times_ms: Mapping[tuple[str, StartType], int] = field(default_factory=dict)
    locale: str = DEFAULT_LOCALE


@dataclass(frozen=True)
class TrainerStep:
    """One step as ridden. `power` is (low, high) in fractions of FTP, None
    when the step has no target or one in watts without a known FTP."""

    step: WorkoutStep
    start_s: float
    duration_s: float
    power: tuple[float, float] | None
    cue: str

    @property
    def is_ramp(self) -> bool:
        """A warmup or cooldown range is ridden as a ramp (up, resp. down)."""
        return self.power is not None and self.power[0] != self.power[1] and self.step.kind in (
            StepKind.WARMUP,
            StepKind.COOLDOWN,
        )

    @property
    def is_max_effort(self) -> bool:
        return self.step.kind == StepKind.WORK and self.step.is_track


def _start(step: WorkoutStep) -> StartType:
    event = STANDARD_EVENTS_BY_KEY[step.event_key]
    return step.start_type or event.start_types[0]


def _target_power_w(step: WorkoutStep, ftp_w: float | None) -> float | None:
    if step.power is None:
        return None
    if step.power.unit == "watts":
        return step.power.mid()
    return step.power.mid() / 100 * ftp_w if ftp_w else None


def event_time_s(step: WorkoutStep, context: ExportContext) -> float | None:
    """How long the step's event takes: the target, else the athlete's best,
    else simulated. None for a step without an event."""
    if step.event_key is None:
        return None
    if step.target_time_ms is not None:
        return step.target_time_ms / 1000
    start = _start(step)
    if (best := context.best_times_ms.get((step.event_key, start))) is not None:
        return best / 1000
    event = STANDARD_EVENTS_BY_KEY[step.event_key]
    setup = physics.Setup(
        mass_kg=DEFAULT_MASS_KG,
        cda_m2=DEFAULT_CDA_M2,
        rho=physics.air_density(DEFAULT_TEMP_C, humidity_pct=DEFAULT_HUMIDITY_PCT),
    )
    power = _target_power_w(step, context.ftp_w) or DEFAULT_EFFORT_POWER_W
    ride = physics.simulate(
        event.distance_m or structure.DEFAULT_TRACK_LENGTH_M, power, setup, standing=start == StartType.STANDING
    )
    return ride.time_s if ride else None


def step_duration_s(step: WorkoutStep, context: ExportContext) -> float:
    """Never None: an open step gets `OPEN_STEP_S`."""
    if step.duration_s is not None:
        return float(step.duration_s)
    track_length = structure.DEFAULT_TRACK_LENGTH_M
    if (time_s := event_time_s(step, context)) is not None:
        event = STANDARD_EVENTS_BY_KEY[step.event_key]
        event_distance = event.distance_m or track_length
        return (structure.step_distance_m(step, track_length) or event_distance) * time_s / event_distance
    return structure.step_duration_s(step, track_length) or structure.OPEN_STEP_S


def power_fractions(step: WorkoutStep, ftp_w: float | None) -> tuple[float, float] | None:
    if step.power is None:
        return None
    low = step.power.low
    high = step.power.high if step.power.high is not None else low
    if step.power.unit == "ftp_pct":
        return low / 100, high / 100
    return (low / ftp_w, high / ftp_w) if ftp_w else None


def fallback_fraction(step: WorkoutStep) -> float:
    """For a step without a power target, where the format needs one."""
    if step.rpe is not None:
        return 0.30 + 0.08 * step.rpe  # the IF behind `srpe_training_stress`
    if step.kind == StepKind.WORK and step.is_track:
        return MAX_EFFORT_FRACTION
    return EASY_FRACTION[step.kind]


def trainer_steps(items: Sequence[WorkoutStep | RepeatBlock | InnerRepeat], context: ExportContext) -> list[TrainerStep]:
    steps: list[TrainerStep] = []
    elapsed = 0.0
    for step in structure.expand(items):
        duration = max(1.0, round(step_duration_s(step, context)))
        steps.append(
            TrainerStep(
                step=step,
                start_s=elapsed,
                duration_s=duration,
                power=power_fractions(step, context.ftp_w),
                cue=step_cue(step, context.locale),
            )
        )
        elapsed += duration
    return steps


def one_line(text: str | None) -> str:
    return " ".join((text or "").split())
