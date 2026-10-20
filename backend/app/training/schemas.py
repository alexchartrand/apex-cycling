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
    loop_id: uuid.UUID
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
    excluded: bool
    label: str | None
    segments: list[SegmentDetail]
    views: list[ViewTime]


class TrackSessionDetail(BaseModel):
    track_id: uuid.UUID
    track_name: str
    laps: list[LapDetail]


class SessionDetail(BaseModel):
    """`event_name` is the title to show: the athlete's `title_override` if
    they set one, else sqorz's own session name.
    """

    external_event_id: str
    event_name: str
    original_name: str
    title_override: str | None
    event_date: date
    notes: str | None
    rpe: int | None
    tags: list[str]
    tracks: list[TrackSessionDetail]


class SessionSummary(BaseModel):
    external_event_id: str
    event_name: str
    event_date: date
    lap_count: int
    track_names: list[str]
    rpe: int | None
    tags: list[str]
    # First lap start / last lap start for this athlete — not sqorz's
    # event window, which spans the whole day for every rider.
    first_lap_at: datetime | None
    last_lap_at: datetime | None


class TrackViewSummary(BaseModel):
    id: uuid.UUID
    name: str
    hidden: bool


class TrackLoopSummary(BaseModel):
    id: uuid.UUID
    name: str
    distance_m: float | None
    hidden: bool


class TrackSummary(BaseModel):
    """`hidden` loops/views are display-only choices; `can_edit` says whether
    the requesting user may change this track's settings.
    """

    id: uuid.UUID
    name: str
    views: list[TrackViewSummary]
    loops: list[TrackLoopSummary]
    length_m: float | None
    indoor: bool | None
    elevation_m: float | None
    default_temp_c: float | None
    can_edit: bool


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
    label: str | None
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


def _clean_text(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


class SessionUpdate(BaseModel):
    """PATCH body: only the fields sent change; null (or blank) clears one."""

    title_override: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    rpe: int | None = Field(default=None, ge=1, le=10)
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("title_override", "notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str] | None) -> list[str]:
        """Trimmed, non-empty, at most 32 characters each, no duplicates
        (ignoring case), in the order given. Null clears them all."""
        seen: set[str] = set()
        cleaned = []
        for tag in value or []:
            tag = tag.strip()
            if not tag:
                continue
            if len(tag) > 32:
                raise ValueError("A tag is at most 32 characters")
            if tag.casefold() not in seen:
                seen.add(tag.casefold())
                cleaned.append(tag)
        return cleaned


class SessionMeta(BaseModel):
    external_event_id: str
    event_name: str
    original_name: str
    title_override: str | None
    notes: str | None
    rpe: int | None
    tags: list[str]


class LapUpdate(BaseModel):
    """PATCH body for one lap: only the fields sent change. `excluded` can't
    be null; a blank `label` clears it."""

    excluded: bool | None = None
    label: str | None = Field(default=None, max_length=100)

    @field_validator("excluded")
    @classmethod
    def _excluded_not_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("excluded must be true or false")
        return value

    @field_validator("label")
    @classmethod
    def _blank_label_is_none(cls, value: str | None) -> str | None:
        return _clean_text(value)


class LapEdit(BaseModel):
    lap_id: uuid.UUID
    excluded: bool
    label: str | None


class EffortLabelUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=100)

    @field_validator("label")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return _clean_text(value)


class EffortLabel(BaseModel):
    first_lap_id: uuid.UUID
    label: str | None


class TrackUpdate(BaseModel):
    """PATCH body: only the fields sent change. The facts (length…) may be
    null to clear them; `hidden_loop_ids` / `hidden_view_ids` are the full
    set to hide on this track (everything else is shown).
    """

    length_m: float | None = Field(default=None, gt=0, le=1000)
    indoor: bool | None = None
    elevation_m: float | None = Field(default=None, ge=-500, le=6000)
    default_temp_c: float | None = Field(default=None, ge=-40, le=60)
    hidden_loop_ids: list[uuid.UUID] | None = None
    hidden_view_ids: list[uuid.UUID] | None = None

    @field_validator("hidden_loop_ids", "hidden_view_ids")
    @classmethod
    def _sets_not_null(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID]:
        if value is None:
            raise ValueError("Send the full list (empty to show everything)")
        return value


class CommentWrite(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A comment can't be empty")
        return value


class CommentRead(BaseModel):
    id: uuid.UUID
    author_user_id: uuid.UUID
    author_name: str | None
    # Written by the athlete themself, as opposed to a coach or club admin.
    by_athlete: bool
    body: str
    created_at: datetime
    edited_at: datetime | None
    # What the requesting user may do with it.
    can_edit: bool
    can_delete: bool


class CommentInboxItem(BaseModel):
    """New comments on one session, for the inbox."""

    athlete_id: uuid.UUID
    athlete_name: str
    external_event_id: str
    event_name: str
    event_date: date
    unread_count: int
    latest_at: datetime
    latest_author_name: str | None
    latest_excerpt: str
