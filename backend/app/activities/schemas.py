import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
    file_format: str | None
    created_at: datetime


class UploadResult(BaseModel):
    filename: str
    status: Literal["created", "duplicate", "failed"]
    # The new activity, or the one already stored when `duplicate`.
    activity: ActivityRead | None = None
    error: str | None = None
