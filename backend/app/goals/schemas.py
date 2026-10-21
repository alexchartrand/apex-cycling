import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType

# Why there is no predicted time, most fundamental first.
PredictionProblem = Literal["no_track", "no_track_length", "no_weight", "no_power", "no_cda"]


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


class GoalWrite(BaseModel):
    event_key: str
    start_type: StartType
    target_time_ms: int = Field(gt=0, le=7_200_000)
    target_date: date
    # Null = on any track.
    track_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)

    _clean_notes = field_validator("notes")(_blank_is_none)

    @model_validator(mode="after")
    def _check_event(self) -> "GoalWrite":
        event = STANDARD_EVENTS_BY_KEY.get(self.event_key)
        if event is None:
            raise ValueError(f"Unknown event {self.event_key!r}")
        if self.start_type not in event.start_types:
            raise ValueError(f"{self.event_key} has no {self.start_type.value} start")
        return self


class GoalUpdate(BaseModel):
    """PATCH body: only the fields sent change. The event and its start are
    fixed (set a new goal for another one); `track_id` null = any track."""

    target_time_ms: int | None = Field(default=None, gt=0, le=7_200_000)
    target_date: date | None = None
    track_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)

    _clean_notes = field_validator("notes")(_blank_is_none)

    @field_validator("target_time_ms", "target_date")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This value can't be cleared")
        return value


class GoalBest(BaseModel):
    """The athlete's best result at the goal's event."""

    time_ms: int
    achieved_on: date
    place: str
    track_id: uuid.UUID | None


class GoalPrediction(BaseModel):
    time_ms: int
    # The power it assumes: the best average over `power_duration_s`, set on `power_on`.
    power_w: float
    power_duration_s: int
    power_on: datetime
    cda_m2: float
    cda_label: str
    rider_kg: float


class GoalRead(BaseModel):
    id: uuid.UUID
    event_key: str
    start_type: StartType
    track_id: uuid.UUID | None
    track_name: str | None
    target_time_ms: int
    target_date: date
    notes: str | None
    baseline_ms: int | None
    created_at: datetime
    best: GoalBest | None
    # Best minus target: positive while to go, zero or negative once reached.
    gap_ms: int | None
    achieved: bool
    # 0..1 from the best when the goal was set to the target; null without a start or a best.
    progress: float | None
    days_left: int
    prediction: GoalPrediction | None
    prediction_problem: PredictionProblem | None
