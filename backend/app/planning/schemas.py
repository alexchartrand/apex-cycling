import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.planning.matching import RepStatus
from app.planning.models import PlanStatus
from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType
from app.workouts.schemas import WorkoutEstimate, WorkoutItem, check_steps


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


class PlannedEffort(BaseModel):
    """One block of the plan: "3 × 500 m standing, aiming at 34.0, on 50×15".
    The event, time and gear are optional (a "4 × 10 min tempo" has none)."""

    label: str = Field(min_length=1, max_length=100)
    reps: int = Field(default=1, ge=1, le=99)
    event_key: str | None = None
    start_type: StartType | None = None
    target_time_ms: int | None = Field(default=None, gt=0, le=7_200_000)
    # One of the athlete's gears (`equipment`), to ride it in.
    gear_setup_id: uuid.UUID | None = None

    @field_validator("label")
    @classmethod
    def _trim_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A planned effort needs a label")
        return value

    @model_validator(mode="after")
    def _check_event(self) -> "PlannedEffort":
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


class PlannedEffortRead(PlannedEffort):
    # "Track bike · 50×15"; the gear id and its label are null once the gear is deleted.
    gear_label: str | None = None


def _check_workout(items: list | None) -> list | None:
    return None if items is None else check_steps(items)


class PlannedSessionWrite(BaseModel):
    """`workout` is the step tree to ride, usually copied from a library
    workout (`source_workout_id`) and maybe adapted; `targets` is the older
    free-form list, still accepted."""

    planned_date: date
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    targets: list[PlannedEffort] = Field(default_factory=list, max_length=30)
    workout: list[WorkoutItem] | None = Field(default=None, min_length=1, max_length=50)
    source_workout_id: uuid.UUID | None = None

    _clean_description = field_validator("description")(_blank_is_none)
    _check_workout = field_validator("workout")(_check_workout)

    @field_validator("title")
    @classmethod
    def _trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A planned session needs a title")
        return value


class PlannedSessionUpdate(BaseModel):
    """PATCH body: only the fields sent change. The content (date, title,
    description, targets, workout) is the author's and the athlete's to edit;
    `status` is the athlete's side only. A null `workout` removes it, and the
    library workout it came from with it."""

    planned_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    targets: list[PlannedEffort] | None = Field(default=None, max_length=30)
    workout: list[WorkoutItem] | None = Field(default=None, min_length=1, max_length=50)
    source_workout_id: uuid.UUID | None = None
    status: PlanStatus | None = None

    _clean_description = field_validator("description")(_blank_is_none)
    _check_workout = field_validator("workout")(_check_workout)

    @field_validator("planned_date", "title", "targets", "status")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This value can't be cleared")
        return value

    @field_validator("title")
    @classmethod
    def _trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A planned session needs a title")
        return value


class PlanSessionLink(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=255)


class LinkedSession(BaseModel):
    external_event_id: str
    event_name: str
    event_date: date


class PlanWorkoutGear(BaseModel):
    """A gear the workout asks for (as teeth), found among the athlete's
    saved gears: "Track bike · 50×15"."""

    chainring_teeth: int
    cog_teeth: int
    gear_setup_id: uuid.UUID
    label: str


class PlannedSessionRead(BaseModel):
    id: uuid.UUID
    planned_date: date
    title: str
    description: str | None
    targets: list[PlannedEffortRead]
    workout: list[WorkoutItem] | None
    # Derived on read with the athlete's FTP on the planned date.
    workout_estimate: WorkoutEstimate | None
    workout_gears: list[PlanWorkoutGear]
    # The library workout it was copied from, only while the viewer can open it.
    source_workout_id: uuid.UUID | None
    status: PlanStatus
    created_by_name: str | None
    # The session that was ridden, when linked.
    session: LinkedSession | None
    # What the viewer may do: the author and the athlete's side edit the
    # content; only the athlete's side marks it done, skipped or linked.
    can_edit: bool
    can_mark: bool
    # Its copy on the athlete's Intervals.icu calendar, when they push plans
    # there: on its way, there, or the last attempt failed (retried).
    intervals: Literal["pending", "sent", "failed"] | None = None


class RepResult(BaseModel):
    """One rep of the plan and how the ridden session answered it."""

    target_index: int
    rep: int
    label: str
    event_key: str | None
    target_time_ms: int | None
    status: RepStatus
    # The effort of the session that answers it (its 1-based number in the
    # session's effort list) and what it scored; `delta_ms` = time − target.
    effort_index: int | None = None
    start_type: StartType | None = None
    time_ms: int | None = None
    delta_ms: int | None = None


class PlanComparison(BaseModel):
    """The plan against the session linked to it. `measured` counts the reps
    with a target time, `hits` those that made it."""

    reps: list[RepResult]
    measured: int
    hits: int
