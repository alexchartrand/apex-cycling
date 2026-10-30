import enum
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Discriminator, Field, Tag, field_validator, model_validator

from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType

# Head units count every step and repeat marker; Garmin refuses workouts of
# more than about a hundred.
MAX_STRUCTURE_STEPS = 100
MAX_STEP_DURATION_S = 6 * 3600


class StepKind(str, enum.Enum):
    WARMUP = "warmup"
    WORK = "work"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


class PowerTarget(BaseModel):
    """A single value (`high` null) or a range, in % of FTP or watts."""

    unit: Literal["ftp_pct", "watts"]
    low: float = Field(gt=0, le=3000)
    high: float | None = Field(default=None, gt=0, le=3000)

    @model_validator(mode="after")
    def _check(self) -> "PowerTarget":
        if self.high is not None and self.high < self.low:
            raise ValueError("The top of a power range is below its bottom")
        if self.unit == "ftp_pct" and max(self.low, self.high or 0) > 300:
            raise ValueError("A power target is at most 300 % of FTP")
        return self

    def mid(self) -> float:
        return self.low if self.high is None else (self.low + self.high) / 2


class CadenceTarget(BaseModel):
    low: int = Field(ge=20, le=250)
    high: int | None = Field(default=None, ge=20, le=250)

    @model_validator(mode="after")
    def _check(self) -> "CadenceTarget":
        if self.high is not None and self.high < self.low:
            raise ValueError("The top of a cadence range is below its bottom")
        return self


class GearRatio(BaseModel):
    """Teeth only: a library workout isn't anyone's, so it can't name an
    athlete's saved gear; scheduling it finds the athlete's matching one."""

    chainring_teeth: int = Field(ge=10, le=100)
    cog_teeth: int = Field(ge=5, le=60)


class WorkoutStep(BaseModel):
    """One step. Its length is a time, a distance or a number of laps, or
    none (open: ends on the lap button) — a step with a standard event and
    no length of its own lasts the event's distance. Targets are all
    optional: power, cadence, an RPE, or just the label and notes."""

    type: Literal["step"] = "step"
    kind: StepKind = StepKind.WORK
    label: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    duration_s: int | None = Field(default=None, ge=1, le=MAX_STEP_DURATION_S)
    distance_m: float | None = Field(default=None, gt=0, le=100_000)
    laps: int | None = Field(default=None, ge=1, le=400)
    power: PowerTarget | None = None
    cadence: CadenceTarget | None = None
    rpe: int | None = Field(default=None, ge=1, le=10)
    # Track: a standard event ridden from this start, aiming at a time, in a gear.
    event_key: str | None = None
    start_type: StartType | None = None
    target_time_ms: int | None = Field(default=None, gt=0, le=7_200_000)
    gear: GearRatio | None = None

    _clean_text = field_validator("label", "notes")(_blank_is_none)

    @model_validator(mode="after")
    def _check(self) -> "WorkoutStep":
        lengths = [v for v in (self.duration_s, self.distance_m, self.laps) if v is not None]
        if len(lengths) > 1:
            raise ValueError("A step lasts a time, a distance or a number of laps, not several")
        if self.event_key is None:
            if self.start_type is not None or self.target_time_ms is not None:
                raise ValueError("A start or a target time goes with an event")
            return self
        event = STANDARD_EVENTS_BY_KEY.get(self.event_key)
        if event is None:
            raise ValueError(f"Unknown event {self.event_key!r}")
        if self.start_type is not None and self.start_type not in event.start_types:
            raise ValueError(f"{self.event_key} has no {self.start_type.value} start")
        return self

    @property
    def is_track(self) -> bool:
        return self.laps is not None or self.event_key is not None


def _item_type(value) -> str:
    """A step may leave out `"type": "step"`; a repeat must say so."""
    raw = value.get("type", "step") if isinstance(value, dict) else getattr(value, "type", "step")
    return raw if raw in ("step", "repeat") else "unknown"


class InnerRepeat(BaseModel):
    """A repeat inside a repeat: steps only, so nesting stops at one level."""

    type: Literal["repeat"] = "repeat"
    count: int = Field(ge=2, le=50)
    steps: list[WorkoutStep] = Field(min_length=1, max_length=20)


class RepeatBlock(BaseModel):
    type: Literal["repeat"] = "repeat"
    count: int = Field(ge=2, le=50)
    steps: list[
        Annotated[Annotated[WorkoutStep, Tag("step")] | Annotated[InnerRepeat, Tag("repeat")], Discriminator(_item_type)]
    ] = Field(
        min_length=1, max_length=20
    )


WorkoutItem = Annotated[
    Annotated[WorkoutStep, Tag("step")] | Annotated[RepeatBlock, Tag("repeat")], Discriminator(_item_type)
]


def structure_size(items: list[WorkoutStep | RepeatBlock | InnerRepeat]) -> int:
    """Steps plus repeat markers, as a head unit counts them."""
    return sum(1 if isinstance(item, WorkoutStep) else 1 + structure_size(item.steps) for item in items)


def _check_steps(items: list) -> list:
    if structure_size(items) > MAX_STRUCTURE_STEPS:
        raise ValueError(f"A workout has at most {MAX_STRUCTURE_STEPS} steps and repeats")
    return items


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        tag = tag.strip().lower()
        if len(tag) > 30:
            raise ValueError("A tag is at most 30 characters")
        if tag and tag not in cleaned:
            cleaned.append(tag)
    return cleaned


def _trim_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("A workout needs a name")
    return value


class WorkoutSteps(BaseModel):
    """Compute-only body of `POST /workouts/estimate` (the editor's live chart)."""

    steps: list[WorkoutItem] = Field(min_length=1, max_length=50)
    track_length_m: float | None = Field(default=None, gt=0, le=1000)
    ftp_w: float | None = Field(default=None, gt=0, le=1000)

    _check_steps = field_validator("steps")(_check_steps)


class WorkoutWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=10)
    steps: list[WorkoutItem] = Field(min_length=1, max_length=50)

    _clean_description = field_validator("description")(_blank_is_none)
    _trim_name = field_validator("name")(_trim_name)
    _clean_tags = field_validator("tags")(_clean_tags)
    _check_steps = field_validator("steps")(_check_steps)


class WorkoutUpdate(BaseModel):
    """PATCH body: only the fields sent change."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=10)
    steps: list[WorkoutItem] | None = Field(default=None, min_length=1, max_length=50)

    _clean_description = field_validator("description")(_blank_is_none)

    @field_validator("name", "tags", "steps")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This value can't be cleared")
        return value

    _trim_name = field_validator("name")(_trim_name)
    _clean_tags = field_validator("tags")(_clean_tags)
    _check_steps = field_validator("steps")(_check_steps)


class ProfileSegment(BaseModel):
    """One step as ridden, in order (repeats expanded). `intensity` is the
    fraction of FTP the estimate uses (from power, else the RPE), and
    `power_low`/`power_high` the target as fractions of FTP."""

    start_s: float
    duration_s: float
    kind: StepKind
    label: str | None
    intensity: float | None
    power_low: float | None
    power_high: float | None
    is_track: bool


class WorkoutEstimate(BaseModel):
    """`duration_s` leaves out open steps (`open_steps` counts them); `tss`
    counts only steps with a known intensity (`unrated_s` is the rest), and
    is null when none has one. Distances are turned into time at a nominal
    speed unless the step has a target time."""

    duration_s: float
    tss: float | None
    unrated_s: float
    open_steps: int
    segments: list[ProfileSegment]


class WorkoutSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    tags: list[str]
    is_track: bool
    duration_s: float
    tss: float | None
    owner_name: str | None
    # Only the owner edits; everyone who sees it may duplicate it.
    can_edit: bool
    created_at: datetime


class WorkoutRead(WorkoutSummary):
    steps: list[WorkoutItem]
    estimate: WorkoutEstimate
