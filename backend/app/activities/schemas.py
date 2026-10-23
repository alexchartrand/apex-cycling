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
    # The sqorz session this ride contains; `clock_offset_s` is added to the
    # device's timestamps to get sqorz time. Filled in by the router.
    external_event_id: str | None = None
    # Where the ride lives on its source (Strava requires linking back to it).
    external_url: str | None = None
    clock_offset_s: float = 0.0
    session_link_manual: bool = False


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


class CriticalPowerRead(BaseModel):
    cp_w: float
    w_prime_j: float
    r_squared: float
    # Efforts (standard durations between 3 and 20 min) the line went through.
    points: int


class FtpSuggestion(BaseModel):
    ftp_w: float
    # The effort it comes from: 95 % of the best power over `source_duration_s`.
    source_duration_s: int
    source_activity_id: uuid.UUID
    source_power_w: float


class PowerProfile(BaseModel):
    """What the last `days` days of power say about threshold. Each part is
    null when the data can't support it."""

    days: int
    critical_power: CriticalPowerRead | None
    ftp_current_w: float | None
    # Set only when it differs from the current FTP by more than a couple of percent.
    ftp_suggestion: FtpSuggestion | None


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


class SessionLinkWrite(BaseModel):
    external_event_id: str
    # Omitted: estimated from the lap times, else 0.
    clock_offset_s: float | None = Field(default=None, ge=-3600, le=3600)


class SessionSuggestion(BaseModel):
    """What auto-linking would do for this activity. `clock_offset_s` is null
    when the laps can't pin it down; `confident` says it is safe to apply
    without asking."""

    external_event_id: str | None
    event_name: str | None
    clock_offset_s: float | None
    correlation: float | None
    margin: float | None
    laps_used: int | None
    confident: bool


class ActivityStreamsRead(BaseModel):
    """The recording thinned to at most `max_points` samples for charting.
    Channels the file doesn't carry are null; `null` entries are gaps."""

    sample_count: int
    point_count: int
    time_s: list[float | None]
    power_w: list[float | None] | None
    heart_rate: list[float | None] | None
    cadence: list[float | None] | None
    speed_mps: list[float | None] | None
    distance_m: list[float | None] | None
    altitude_m: list[float | None] | None


class ZoneDistribution(BaseModel):
    """Seconds in each zone; `limits` are the upper bounds of all but the last."""

    limits: list[float]
    seconds: list[int]


class CurvePoint(BaseModel):
    duration_s: int
    power_w: float


class ActivityAnalysis(BaseModel):
    ftp_w: float | None
    weight_kg: float | None
    max_hr: int | None
    intensity_factor: float | None
    variability_index: float | None
    avg_power_w_per_kg: float | None
    normalized_power_w_per_kg: float | None
    work_kj: float | None
    power_zones: ZoneDistribution | None
    hr_zones: ZoneDistribution | None
    power_curve: list[CurvePoint]
