import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Why there is no estimate, most fundamental first.
AeroProblem = Literal["no_track_length", "no_weight", "no_power", "too_few_laps"]


class AeroInputs(BaseModel):
    """What an estimate assumes. A null field takes its default: the track's
    temperature and elevation, the athlete's weight on the day, the physics
    defaults (bike 8 kg, 50 % humidity, pressure from the elevation, Crr fitted
    when the laps allow)."""

    temp_c: float | None = Field(default=None, ge=-30, le=50)
    elevation_m: float | None = Field(default=None, ge=-400, le=5000)
    pressure_hpa: float | None = Field(default=None, ge=500, le=1100)
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    rider_kg: float | None = Field(default=None, ge=20, le=250)
    # Bike, shoes, helmet and skinsuit.
    bike_kg: float | None = Field(default=None, ge=0, le=40)
    crr: float | None = Field(default=None, ge=0.001, le=0.02)


class AeroEstimateRequest(AeroInputs):
    # The session's track with the most laps when not given.
    track_id: uuid.UUID | None = None
    # The laps to use; null picks the steady ones.
    lap_ids: list[uuid.UUID] | None = Field(default=None, max_length=2000)


class AeroConditionsRead(BaseModel):
    """The values the estimate actually used."""

    temp_c: float
    elevation_m: float
    pressure_hpa: float | None
    humidity_pct: float
    rho: float
    rider_kg: float | None
    # The profile entry the weight came from; null when it was given.
    rider_kg_date: date | None
    bike_kg: float
    efficiency: float


class AeroPointRead(BaseModel):
    lap_id: uuid.UUID
    start_time: datetime
    # 1-based, among the track's efforts in this session / within the effort.
    effort_index: int
    lap_in_effort: int
    time_s: float
    speed_ms: float
    power_w: float | None
    resistance_n: float | None
    cda_m2: float | None
    # Why the automatic pick leaves the lap out (see `analysis/aero.py`).
    issue: str | None
    used: bool


class AeroFitRead(BaseModel):
    cda_m2: float
    crr: float
    crr_source: Literal["fitted", "given", "default"]
    r_squared: float | None
    cda_se_m2: float | None
    laps_used: int
    speed_ms: float
    power_w: float
    speed_spread: float


class AeroTrackChoice(BaseModel):
    track_id: uuid.UUID
    track_name: str
    length_m: float | None
    lap_count: int


class AeroEstimateRead(BaseModel):
    external_event_id: str
    event_name: str
    event_date: date
    track_id: uuid.UUID
    track_name: str
    track_length_m: float | None
    tracks: list[AeroTrackChoice]
    conditions: AeroConditionsRead
    points: list[AeroPointRead]
    fit: AeroFitRead | None
    problem: AeroProblem | None


class AeroTestCreate(AeroInputs):
    external_event_id: str = Field(min_length=1, max_length=255)
    track_id: uuid.UUID | None = None
    lap_ids: list[uuid.UUID] | None = Field(default=None, max_length=2000)
    label: str = Field(min_length=1, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    helmet: str | None = Field(default=None, max_length=100)
    skinsuit: str | None = Field(default=None, max_length=100)
    bike: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)


class AeroTestUpdate(AeroInputs):
    """Only the fields sent change; null clears one (back to its default, or
    to the automatic lap pick). The label can be changed but not cleared."""

    lap_ids: list[uuid.UUID] | None = Field(default=None, max_length=2000)
    label: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    helmet: str | None = Field(default=None, max_length=100)
    skinsuit: str | None = Field(default=None, max_length=100)
    bike: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _label_kept(self) -> "AeroTestUpdate":
        if "label" in self.model_fields_set and self.label is None:
            raise ValueError("label can't be cleared")
        return self


class AeroTestRead(BaseModel):
    id: uuid.UUID
    external_event_id: str
    event_name: str
    event_date: date
    track_id: uuid.UUID
    track_name: str
    label: str
    position: str | None
    helmet: str | None
    skinsuit: str | None
    bike: str | None
    notes: str | None
    lap_ids: list[uuid.UUID] | None
    # What was set; `conditions` is what that came to with the defaults.
    inputs: AeroInputs
    created_at: datetime
    conditions: AeroConditionsRead
    fit: AeroFitRead | None
    problem: AeroProblem | None


class AeroTestDetail(AeroTestRead):
    points: list[AeroPointRead]
