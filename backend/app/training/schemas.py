import enum
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.training.distances import STANDARD_EVENTS_BY_KEY
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


class RecordEntry(BaseModel):
    """One line of the records board or of a record's history. `place` is
    the track's name, or the venue text of a manual result with no track.
    """

    place: str
    track_id: uuid.UUID | None
    event_key: str
    start_type: StartType
    time_ms: int
    achieved_on: date
    source: Literal["sqorz", "manual"]
    is_competition: bool = False
    external_event_id: str | None = None
    lap_id: uuid.UUID | None = None
    manual_result_id: uuid.UUID | None = None


class ManualResultWrite(BaseModel):
    """A result entered by hand. Either `track_id` or `venue` says where."""

    event_key: str
    start_type: StartType
    time_ms: int = Field(gt=0, le=7_200_000)
    achieved_on: date
    track_id: uuid.UUID | None = None
    venue: str | None = Field(default=None, max_length=255)
    is_competition: bool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("venue", "notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def _check_event_and_place(self) -> "ManualResultWrite":
        event = STANDARD_EVENTS_BY_KEY.get(self.event_key)
        if event is None:
            raise ValueError(f"Unknown event {self.event_key!r}")
        if self.start_type not in event.start_types:
            raise ValueError(f"{self.event_key} has no {self.start_type.value} start")
        if self.track_id is None and self.venue is None:
            raise ValueError("Give either a track or a venue")
        return self


class ManualResultRead(BaseModel):
    id: uuid.UUID
    event_key: str
    start_type: StartType
    time_ms: int
    achieved_on: date
    track_id: uuid.UUID | None
    venue: str | None
    place: str
    is_competition: bool
    notes: str | None
