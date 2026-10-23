import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.training.efforts import StartType

Priority = Literal["A", "B", "C"]
Phase = Literal["past", "race_day", "taper", "build"]


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


def _trimmed(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This can't be blank")
    return value


# --- seasons -----------------------------------------------------------------------------


class SeasonWrite(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start_date: date

    _trim_name = field_validator("name")(_trimmed)


class SeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    start_date: date | None = None

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("This value can't be cleared")
        return _trimmed(value)

    @field_validator("start_date")
    @classmethod
    def _not_null(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("This value can't be cleared")
        return value


class SeasonRead(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    # The day before the next season starts; null for the latest.
    end_date: date | None
    is_current: bool


class SeasonBest(BaseModel):
    """The athlete's best at one place, event and start within a season."""

    place: str
    track_id: uuid.UUID | None
    event_key: str
    start_type: StartType
    time_ms: int
    achieved_on: date
    source: Literal["sqorz", "manual"]
    external_event_id: str | None
    # The best before the season began; null when this is the first result there.
    previous_best_ms: int | None
    # Faster than everything before the season.
    improved: bool


class SeasonSummary(BaseModel):
    season: SeasonRead
    sessions: int
    races: int
    bests: list[SeasonBest]


# --- competitions ---------------------------------------------------------------------------


class CompetitionWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    competition_date: date
    priority: Priority = "B"
    location: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    # One of the athlete's goals: what they are aiming for there.
    goal_id: uuid.UUID | None = None

    _trim_name = field_validator("name")(_trimmed)
    _clean = field_validator("location", "notes")(_blank_is_none)


class CompetitionUpdate(BaseModel):
    """PATCH body: only the fields sent change; null clears `location`, `notes` and `goal_id`."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    competition_date: date | None = None
    priority: Priority | None = None
    location: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    goal_id: uuid.UUID | None = None

    _clean = field_validator("location", "notes")(_blank_is_none)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("This value can't be cleared")
        return _trimmed(value)

    @field_validator("competition_date", "priority")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This value can't be cleared")
        return value


class CompetitionGoal(BaseModel):
    id: uuid.UUID
    event_key: str
    start_type: StartType
    target_time_ms: int


class CompetitionRead(BaseModel):
    id: uuid.UUID
    name: str
    competition_date: date
    priority: Priority
    location: str | None
    notes: str | None
    goal: CompetitionGoal | None
    days_until: int
    taper_starts_on: date | None
    # Days until the taper begins, in the club's time zone; null when there is none or it has begun.
    days_to_taper: int | None
    phase: Phase
    # The athlete's session on that day that is marked as a race.
    race_session_id: str | None


# --- calendar feed -------------------------------------------------------------------------


class CalendarFeedStatus(BaseModel):
    enabled: bool
    # Only on the response that made the link; it can't be shown again.
    url: str | None = None
