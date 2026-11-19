import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.coach_ai.models import ConversationKind, ProposalKind, ProposalStatus, ReportKind
from app.planning.models import PlanStatus
from app.training.distances import STANDARD_EVENTS_BY_KEY
from app.training.efforts import StartType
from app.training_plans.schemas import OutlineWeek, Phase, Sport
from app.workouts.schemas import WorkoutEstimate, WorkoutItem, check_steps


Day = date  # for fields named `date`, which would shadow the type


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


# --- the intake ---------------------------------------------------------------


class CoachProfile(BaseModel):
    """What the interview learnt about the athlete (all optional: the AI asks
    for what's missing, the athlete can edit it in Settings). Days are ISO
    weekdays, 1 = Monday. A plan's goal, dates and weekly hours are the
    plan's (`TrainingPlan`), not the athlete's."""

    available_days: list[int] = Field(default_factory=list, max_length=7)
    track_days: list[int] = Field(default_factory=list, max_length=7)
    max_weekday_minutes: int | None = Field(default=None, ge=15, le=600)
    max_weekend_minutes: int | None = Field(default=None, ge=15, le=720)
    experience: str | None = Field(default=None, max_length=500)
    injuries: str | None = Field(default=None, max_length=1000)
    gym: bool | None = None
    gym_details: str | None = Field(default=None, max_length=500)
    indoor_trainer: bool | None = None
    power_meter: bool | None = None
    other: str | None = Field(default=None, max_length=1000)

    _clean = field_validator("experience", "injuries", "gym_details", "other")(_blank_is_none)

    @field_validator("available_days", "track_days")
    @classmethod
    def _days(cls, days: list[int]) -> list[int]:
        if any(d < 1 or d > 7 for d in days):
            raise ValueError("Days are 1 (Monday) to 7 (Sunday)")
        return sorted(set(days))


PROFILE_FIELDS = tuple(CoachProfile.model_fields)


class CoachSettings(BaseModel):
    weekly_reports: bool = True
    report_weekday: int = Field(default=7, ge=1, le=7)
    report_hour: int = Field(default=19, ge=0, le=23)


class CoachProfileRead(BaseModel):
    answers: CoachProfile
    settings: CoachSettings


class CoachProfileWrite(BaseModel):
    answers: CoachProfile | None = None
    settings: CoachSettings | None = None


# --- proposals ------------------------------------------------------------------


class ProposedWorkout(BaseModel):
    """A workout written by the AI. `save_to_library` also keeps it in the
    athlete's library (tagged "ai")."""

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[WorkoutItem] = Field(min_length=1, max_length=50)
    save_to_library: bool = False

    _check_steps = field_validator("steps")(check_steps)


class _WithWorkout(BaseModel):
    workout_id: uuid.UUID | None = None  # a library workout or preset
    workout: ProposedWorkout | None = None

    @model_validator(mode="after")
    def _one_workout(self):
        if self.workout_id is not None and self.workout is not None:
            raise ValueError("Give either workout_id or workout, not both")
        return self


class CreateOp(_WithWorkout):
    op: Literal["create"] = "create"
    date: Day
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    # The plan it goes in, when not the proposal's own (`ProposalPayload`).
    training_plan_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _needs_workout(self) -> "CreateOp":
        if self.workout_id is None and self.workout is None:
            raise ValueError("A new session needs workout_id or workout")
        return self


class UpdateOp(_WithWorkout):
    op: Literal["update"] = "update"
    plan_id: uuid.UUID
    date: Day | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class SkipOp(BaseModel):
    op: Literal["skip"] = "skip"
    plan_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=300)


class DeleteOp(BaseModel):
    op: Literal["delete"] = "delete"
    plan_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=300)


ProposalOp = Annotated[CreateOp | UpdateOp | SkipOp | DeleteOp, Field(discriminator="op")]


class ProposalPlan(BaseModel):
    """A new training plan the proposal makes. Dates left out are taken from
    the sessions, the outline and the race."""

    name: str = Field(min_length=1, max_length=120)
    sport: Sport
    start_date: date | None = None
    end_date: date | None = None
    goal_text: str | None = Field(default=None, max_length=500)
    goal_date: date | None = None
    hours_per_week: float | None = Field(default=None, ge=0.5, le=40)
    phases: list[Phase] = Field(default_factory=list, max_length=20)


class ProposalRace(BaseModel):
    """The race a program aims at. On Accept it goes on the season calendar
    (a `Competition`, so the taper countdown follows) and, with an event, a
    start and a time, becomes a `Goal` tied to it."""

    name: str = Field(min_length=1, max_length=120)
    date: Day
    priority: Literal["A", "B", "C"] = "A"
    location: str | None = Field(default=None, max_length=120)
    event_key: str | None = None
    start_type: StartType | None = None
    target_time_ms: int | None = Field(default=None, gt=0, le=7_200_000)

    @model_validator(mode="after")
    def _event(self) -> "ProposalRace":
        if self.event_key is None:
            return self
        event = STANDARD_EVENTS_BY_KEY.get(self.event_key)
        if event is None:
            raise ValueError(f"Unknown event {self.event_key!r}")
        if self.start_type is not None and self.start_type not in event.start_types:
            raise ValueError(f"{self.event_key} has no {self.start_type.value} start")
        return self

    @property
    def makes_goal(self) -> bool:
        return self.event_key is not None and self.start_type is not None and self.target_time_ms is not None


class ProposalPayload(BaseModel):
    """`plan` makes a new training plan, `training_plan_id` works on an
    existing one (never both); created sessions go in it. `goal` is the plan's
    goal text and `outline` the weeks after the detailed ones."""

    ops: list[ProposalOp] = Field(default_factory=list, max_length=80)
    training_plan_id: uuid.UUID | None = None
    plan: ProposalPlan | None = None
    goal: str | None = Field(default=None, max_length=500)
    race: ProposalRace | None = None
    outline: list[OutlineWeek] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def _not_empty(self) -> "ProposalPayload":
        if not self.ops and not self.outline and self.plan is None:
            raise ValueError("A proposal changes at least one session")
        if self.plan is not None and self.training_plan_id is not None:
            raise ValueError("Give either plan (a new one) or training_plan_id, not both")
        return self


class PlanSnapshot(BaseModel):
    """A planned session as it is now (the "before" of a change)."""

    planned_date: date
    title: str
    status: PlanStatus
    duration_s: float | None
    tss: float | None


class ProposalItem(BaseModel):
    op: Literal["create", "update", "skip", "delete"]
    plan_id: uuid.UUID | None
    before: PlanSnapshot | None
    # After the change (null for skip/delete).
    planned_date: date | None
    title: str | None
    description: str | None
    workout_name: str | None
    workout: list[WorkoutItem] | None
    estimate: WorkoutEstimate | None
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    # A delete the app adds: an upcoming session the AI wrote for this plan
    # before, replaced by the new program.
    replaced: bool = False


class ProposalWeek(BaseModel):
    week_start: date
    sessions: int
    duration_s: float
    tss: float | None


class ProposalRead(BaseModel):
    id: uuid.UUID
    kind: ProposalKind
    status: ProposalStatus
    summary: str
    goal: str | None
    race: ProposalRace | None = None
    # The plan it makes (`plan`) or works on (`training_plan_id` + its name).
    plan: ProposalPlan | None = None
    training_plan_id: uuid.UUID | None = None
    training_plan_name: str | None = None
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    conversation_id: uuid.UUID | None
    items: list[ProposalItem]
    weeks: list[ProposalWeek]
    outline: list[OutlineWeek]
    # Problems found now (a plan it changes is gone…): Accept is refused while there are any.
    errors: list[str]
    warnings: list[str]
    can_decide: bool


# --- conversations ---------------------------------------------------------------


class MessageRead(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    proposal: ProposalRead | None = None


class ConversationSummary(BaseModel):
    id: uuid.UUID
    kind: ConversationKind
    title: str | None
    training_plan_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None


class ConversationRead(ConversationSummary):
    messages: list[MessageRead]


class ConversationCreate(BaseModel):
    kind: Literal["chat", "intake"] = "chat"
    # An intake started from a plan builds that plan.
    training_plan_id: uuid.UUID | None = None
    # The first message (a chat starts with the athlete's; an intake with the AI's questions).
    content: str | None = Field(default=None, max_length=4000)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def _trim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Say something")
        return value


class TurnRead(BaseModel):
    """What one message produced: the new messages to append."""

    conversation_id: uuid.UUID
    messages: list[MessageRead]


# --- reports, access, admin ---------------------------------------------------------


class ReportRead(BaseModel):
    id: uuid.UUID
    kind: ReportKind
    period_start: date
    period_end: date
    content: str
    stats: dict
    created_at: datetime
    conversation_id: uuid.UUID | None
    proposal_id: uuid.UUID | None


class UsageRead(BaseModel):
    month_tokens: int
    monthly_cap: int


class AccessRead(BaseModel):
    """`available`: the server has a model configured. `enabled`: a platform
    admin turned it on for this athlete. `consented`: the athlete agreed.
    `can_use` = all three and under the cap (only the athlete themself)."""

    available: bool
    enabled: bool
    consented: bool
    is_self: bool
    can_use: bool
    usage: UsageRead | None
    provider: str
    model: str


class ConsentWithdraw(BaseModel):
    delete_history: bool = False


class AdminAiRow(BaseModel):
    athlete_id: uuid.UUID
    display_name: str
    email: str
    enabled: bool
    consented: bool
    approved_at: datetime | None
    monthly_token_cap: int | None
    month_tokens: int
    month_cost_usd: float


class AdminAiOverview(BaseModel):
    available: bool
    model: str
    default_monthly_tokens: int
    rows: list[AdminAiRow]
    month_tokens: int
    month_cost_usd: float


class AdminAiUpdate(BaseModel):
    enabled: bool | None = None
    # 0 = back to the server default.
    monthly_token_cap: int | None = Field(default=None, ge=0, le=1_000_000_000)
