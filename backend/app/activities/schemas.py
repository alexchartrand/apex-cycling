import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.activities.models import ActivitySource


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    athlete_id: uuid.UUID
    source: ActivitySource
    name: str | None
    sport: str | None
    start_time: datetime
    elapsed_s: float
    moving_s: float | None
    distance_m: float | None
    elevation_gain_m: float | None
    has_power: bool
    has_heart_rate: bool
    has_cadence: bool
    avg_power_w: float | None
    max_power_w: float | None
    normalized_power_w: float | None
    tss: float | None
    avg_heart_rate: float | None
    max_heart_rate: float | None
    avg_cadence: float | None
    avg_speed_mps: float | None
    notes: str | None
    rpe: int | None
    file_format: str | None
    created_at: datetime


class ActivityUpdate(BaseModel):
    """Only the fields sent change; null clears one."""

    name: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    rpe: int | None = Field(default=None, ge=1, le=10)


class PowerCurvePoint(BaseModel):
    duration_s: int
    power_w: float
    activity_id: uuid.UUID
    start_time: datetime


class TrainingLoadDay(BaseModel):
    day: date
    tss: float
    ctl: float
    atl: float
    tsb: float


class TrainingLoadRead(BaseModel):
    days: list[TrainingLoadDay]
    # Activities in the window with neither power-based TSS nor an RPE: they
    # add no load, and rating their effort would.
    unrated_activities: int


class UploadResult(BaseModel):
    filename: str
    status: Literal["created", "duplicate", "failed"]
    # The new activity, or the one already stored when `duplicate`.
    activity: ActivityRead | None = None
    error: str | None = None
