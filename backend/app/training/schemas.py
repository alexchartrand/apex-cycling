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
    # From a linked activity's samples over this lap, when there is one.
    avg_power_w: float | None = None
    avg_heart_rate: float | None = None
    avg_cadence: float | None = None
    # What the session's gear implies at this lap's speed (`equipment/service.py`).
    est_cadence_rpm: float | None = None


class TrackSessionDetail(BaseModel):
    track_id: uuid.UUID
    track_name: str
    laps: list[LapDetail]


class LinkedActivity(BaseModel):
    id: uuid.UUID
    name: str | None
    start_time: datetime
    elapsed_s: float
    clock_offset_s: float
    has_power: bool
    has_heart_rate: bool
    has_cadence: bool


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
    is_race: bool = False
    tracks: list[TrackSessionDetail]
    # Recordings (head unit, power meter) linked to this session.
    activities: list[LinkedActivity] = []
    # The gear ridden by default in this session.
    gear_setup_id: uuid.UUID | None = None


class SessionSummary(BaseModel):
    external_event_id: str
    event_name: str
    event_date: date
    lap_count: int
    track_names: list[str]
    rpe: int | None
    tags: list[str]
    is_race: bool = False
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
    # What sqorz calls it, when `name` was set by hand.
    sqorz_name: str | None
    views: list[TrackViewSummary]
    loops: list[TrackLoopSummary]
    length_m: float | None
    indoor: bool | None
    elevation_m: float | None
    default_temp_c: float | None
    city: str | None
    region: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    width_m: float | None
    surface: str | None
    bank_straight_deg: float | None
    bank_curve_deg: float | None
    notes: str | None
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


class PacingDetail(BaseModel):
    """How even the effort was. Percentages are signed like a rider reads
    them: positive = slower. `deviations_pct` has one entry per lap of the
    effort (null for an unfinished one) against `even_pace_ms`, the mean of
    the laps that count (a standing start's first lap and excluded laps don't).
    """

    reference_lap_count: int
    even_pace_ms: float
    cv_pct: float | None
    fade_pct: float | None
    deviations_pct: list[float | None]
    start_lap_skipped: bool


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
    pacing: PacingDetail | None = None
    # Fastest stretch between two placed checkpoints ("200m", "100m"…) and
    # the lap it was on; the launch is a standing start's first stretch.
    peak_speed_kmh: float | None = None
    peak_speed_lap_id: uuid.UUID | None = None
    launch_time_ms: int | None = None
    launch_distance_m: float | None = None
    launch_accel_ms2: float | None = None
    # Over the effort's finished laps, from a linked activity.
    avg_power_w: float | None = None
    avg_heart_rate: float | None = None
    avg_cadence: float | None = None
    # `gear_setup_id` is this effort's own gear (null = the session's);
    # the estimate follows from whichever applies.
    gear_setup_id: uuid.UUID | None = None
    est_cadence_rpm: float | None = None


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
    is_race: bool | None = None

    @field_validator("title_override", "notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("is_race")
    @classmethod
    def _race_not_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("This value can't be cleared")
        return value

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
    is_race: bool = False


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
    city: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    width_m: float | None = Field(default=None, gt=0, le=100)
    surface: str | None = Field(default=None, max_length=255)
    bank_straight_deg: float | None = Field(default=None, ge=0, le=90)
    bank_curve_deg: float | None = Field(default=None, ge=0, le=90)
    notes: str | None = Field(default=None, max_length=4000)
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


class InsightRead(BaseModel):
    """A headline about a session (`insights.py`). Which fields are set
    depends on `kind`: records and season bests carry the event and times,
    "best Nth lap" the lap number and time, "most consistent" the spread.
    """

    key: str
    kind: Literal["personal_record", "season_best", "best_nth_lap", "most_consistent"]
    external_event_id: str
    session_name: str
    event_date: date
    track_id: uuid.UUID
    track_name: str
    event_key: str | None = None
    start_type: StartType | None = None
    time_ms: int | None = None
    previous_ms: int | None = None
    milestone_ms: int | None = None
    lap_number: int | None = None
    lap_count: int | None = None
    cv_pct: float | None = None
    effort_start_type: StartType | None = None
    first_lap_id: uuid.UUID | None = None
