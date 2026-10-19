import enum
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.training.efforts import StartType


class SegmentDetail(BaseModel):
    """`time_ms` is this segment's own duration (a delta), not a cumulative
    or absolute time — see `training/service.py::_segment_deltas`.
    """

    sequence_index: int
    loop_name: str
    time_ms: int | None


class ViewTime(BaseModel):
    track_view_id: uuid.UUID
    name: str
    time_ms: int | None


class LapDetail(BaseModel):
    lap_id: uuid.UUID
    start_time: datetime
    class_code: str | None
    start_number: int | None
    whole_lap_time_ms: int | None
    segments: list[SegmentDetail]
    views: list[ViewTime]


class TrackSessionDetail(BaseModel):
    track_id: uuid.UUID
    track_name: str
    laps: list[LapDetail]


class SessionDetail(BaseModel):
    external_event_id: str
    event_name: str
    event_date: date
    tracks: list[TrackSessionDetail]


class SessionSummary(BaseModel):
    external_event_id: str
    event_name: str
    event_date: date
    lap_count: int
    track_names: list[str]
    # First lap start / last lap start for this athlete — not sqorz's
    # event window, which spans the whole day for every rider.
    first_lap_at: datetime | None
    last_lap_at: datetime | None


class TrackViewSummary(BaseModel):
    id: uuid.UUID
    name: str


class TrackLoopSummary(BaseModel):
    id: uuid.UUID
    name: str
    distance_m: float | None


class TrackSummary(BaseModel):
    id: uuid.UUID
    name: str
    views: list[TrackViewSummary]
    loops: list[TrackLoopSummary]
    length_m: float | None


class ProgressionMetric(str, enum.Enum):
    VIEW = "view"
    LAP_TIME = "lap_time"
    CUSTOM_DISTANCE = "custom_distance"


class ProgressionPoint(BaseModel):
    external_event_id: str
    event_date: date
    best_lap_id: uuid.UUID
    time_ms: int
    achieved_distance_m: float | None = None


class HalfLapSplitDetail(BaseModel):
    """Time between two consecutive pursuit-line crossings; null if either
    crossing was missed.
    """

    index: int
    from_line: str
    to_line: str
    time_ms: int | None


class EffortDetail(BaseModel):
    """One continuous block of laps. `lap_times_ms` has one entry per lap in
    `lap_ids`, null for an unfinished lap; `total_time_ms`/`distance_m` only
    count finished laps, and `distance_m` is null while the track's length
    is unknown.
    """

    index: int
    track_id: uuid.UUID
    track_name: str
    start_time: datetime
    start_type: StartType
    lap_ids: list[uuid.UUID]
    completed_lap_count: int
    lap_times_ms: list[int | None]
    total_time_ms: int | None
    best_lap_ms: int | None
    distance_m: float | None
    avg_speed_kmh: float | None
    half_lap_splits: list[HalfLapSplitDetail]
