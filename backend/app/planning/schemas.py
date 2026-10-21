import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.planning.models import PlanStatus
from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType


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


class PlannedSessionWrite(BaseModel):
    planned_date: date
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    targets: list[PlannedEffort] = Field(default_factory=list, max_length=30)

    _clean_description = field_validator("description")(_blank_is_none)

    @field_validator("title")
    @classmethod
    def _trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A planned session needs a title")
        return value


class PlannedSessionUpdate(BaseModel):
    """PATCH body: only the fields sent change. The content (date, title,
    description, targets) is the author's and the athlete's to edit; `status`
    is the athlete's side only."""

    planned_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    targets: list[PlannedEffort] | None = Field(default=None, max_length=30)
    status: PlanStatus | None = None

    _clean_description = field_validator("description")(_blank_is_none)

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


class PlannedSessionRead(BaseModel):
    id: uuid.UUID
    planned_date: date
    title: str
    description: str | None
    targets: list[PlannedEffortRead]
    status: PlanStatus
    created_by_name: str | None
    # The session that was ridden, when linked.
    session: LinkedSession | None
    # What the viewer may do: the author and the athlete's side edit the
    # content; only the athlete's side marks it done, skipped or linked.
    can_edit: bool
    can_mark: bool
