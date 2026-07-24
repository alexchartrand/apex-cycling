import enum
import uuid
from datetime import date, datetime

from pydantic import BaseModel


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


class TrackViewSummary(BaseModel):
    id: uuid.UUID
    name: str


class TrackSummary(BaseModel):
    id: uuid.UUID
    name: str
    views: list[TrackViewSummary]


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
