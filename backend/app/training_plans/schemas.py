import uuid
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.training.efforts import StartType

Sport = Literal["cycling", "track_cycling"]  # = kinds.PLAN_SPORTS
PhaseKind = Literal["base", "build", "peak", "taper", "race", "recovery", "transition"]
Author = Literal["athlete", "coach", "ai"]
PlanState = Literal["upcoming", "active", "finished"]

# A plan is a season block at most: a year, rounded up to whole weeks.
MAX_PLAN_DAYS = 53 * 7


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


class OutlineWeek(BaseModel):
    """A week of the plan not yet written session by session."""

    week_start: date
    focus: str = Field(min_length=1, max_length=200)
    hours: float | None = Field(default=None, ge=0, le=40)
    notes: str | None = Field(default=None, max_length=500)


class Phase(BaseModel):
    """A stretch of the plan with one purpose (base, build, peak, taper…), from
    `start` to `end` inclusive."""

    kind: PhaseKind
    name: str | None = Field(default=None, max_length=60)
    start: date
    end: date
    focus: str | None = Field(default=None, max_length=300)
    hours: float | None = Field(default=None, ge=0, le=40)

    _clean = field_validator("name", "focus")(_blank_is_none)

    @model_validator(mode="after")
    def _ordered(self) -> "Phase":
        if self.end < self.start:
            raise ValueError("A phase ends on or after its start")
        return self


def check_phases(phases: list[Phase], start: date, end: date) -> list[Phase]:
    """Sorted by start; raises ValueError when they overlap or leave the plan."""
    ordered = sorted(phases, key=lambda p: p.start)
    for phase in ordered:
        if phase.start < start or phase.end > end:
            raise ValueError("Every phase lies within the plan's dates")
    for before, after in zip(ordered, ordered[1:]):
        if after.start <= before.end:
            raise ValueError("Phases can't overlap")
    return ordered


class TrainingPlanWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sport: Sport
    start_date: date
    end_date: date
    goal_text: str | None = Field(default=None, max_length=500)
    goal_date: date | None = None
    # A time to beat (`goals`), track plans only, and the target race (`competitions`).
    goal_id: uuid.UUID | None = None
    competition_id: uuid.UUID | None = None
    hours_per_week: float | None = Field(default=None, ge=0.5, le=40)
    phases: list[Phase] = Field(default_factory=list, max_length=20)
    weeks: list[OutlineWeek] = Field(default_factory=list, max_length=60)

    _clean = field_validator("goal_text")(_blank_is_none)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A plan needs a name")
        return value

    @model_validator(mode="after")
    def _check(self) -> "TrainingPlanWrite":
        if self.end_date < self.start_date:
            raise ValueError("The plan ends on or after its start")
        if (self.end_date - self.start_date).days >= MAX_PLAN_DAYS:
            raise ValueError("A plan lasts a year at most")
        if self.goal_date is not None and not (self.start_date <= self.goal_date <= self.end_date):
            raise ValueError("The goal date lies within the plan")
        if self.goal_id is not None and self.sport != "track_cycling":
            raise ValueError("A time goal goes with a track cycling plan")
        self.phases = check_phases(self.phases, self.start_date, self.end_date)
        self.weeks = sorted(
            {w.week_start: w for w in self.weeks if w.week_start + timedelta(days=6) >= self.start_date}.values(),
            key=lambda w: w.week_start,
        )
        return self


class TrainingPlanUpdate(BaseModel):
    """PATCH body: only the fields sent change; the result is checked as a whole."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    sport: Sport | None = None
    start_date: date | None = None
    end_date: date | None = None
    goal_text: str | None = Field(default=None, max_length=500)
    goal_date: date | None = None
    goal_id: uuid.UUID | None = None
    competition_id: uuid.UUID | None = None
    hours_per_week: float | None = Field(default=None, ge=0.5, le=40)
    phases: list[Phase] | None = Field(default=None, max_length=20)
    weeks: list[OutlineWeek] | None = Field(default=None, max_length=60)

    @field_validator("name", "sport", "start_date", "end_date", "phases", "weeks")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This value can't be cleared")
        return value


class PhaseSuggestionRequest(BaseModel):
    start_date: date
    end_date: date
    # The target race's priority: sets the taper (A 10 days, B 5, C none) and
    # ends the plan on a race day; none = no race.
    race_priority: Literal["A", "B", "C"] | None = None

    @model_validator(mode="after")
    def _check(self) -> "PhaseSuggestionRequest":
        if self.end_date < self.start_date or (self.end_date - self.start_date).days >= MAX_PLAN_DAYS:
            raise ValueError("The plan ends on or after its start, within a year")
        return self


class PlanGoal(BaseModel):
    id: uuid.UUID
    event_key: str
    start_type: StartType
    target_time_ms: int
    target_date: date


class PlanRace(BaseModel):
    id: uuid.UUID
    name: str
    date: date
    priority: str


class ProgressWeek(BaseModel):
    """One Monday week of the plan: what its sessions ask for and what the done
    ones took (from their linked recording or sqorz session)."""

    week_start: date
    sessions: int
    done_sessions: int
    planned_s: float
    planned_tss: float | None
    done_s: float
    done_tss: float | None


class PlanProgress(BaseModel):
    done: int
    skipped: int
    # Still planned once their day has passed.
    missed: int
    # Still planned, today or later (what deleting the plan removes).
    upcoming: int
    # done / (done + skipped + missed); null while nothing is due yet.
    compliance: float | None
    weeks: list[ProgressWeek]


class TrainingPlanRead(BaseModel):
    id: uuid.UUID
    name: str
    sport: Sport
    start_date: date
    end_date: date
    goal_text: str | None
    goal_date: date | None
    goal: PlanGoal | None
    race: PlanRace | None
    hours_per_week: float | None
    phases: list[Phase]
    weeks: list[OutlineWeek]
    # The phase today falls in (index into `phases`), and where the plan stands.
    current_phase: int | None
    state: PlanState
    author: Author
    created_by_name: str | None
    can_edit: bool
    progress: PlanProgress
