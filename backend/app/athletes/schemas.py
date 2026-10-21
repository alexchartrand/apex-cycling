import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, computed_field, model_validator

from app.athletes.categories import age_category
from app.athletes.models import CoachAthleteStatus

Sex = Literal["female", "male"]


class AthleteRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    club_id: uuid.UUID | None
    display_name: str
    birthdate: date | None
    sex: Sex | None
    height_cm: float | None
    leaderboard_club_id: uuid.UUID | None = Field(default=None, exclude=True)

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def leaderboard_opt_in(self) -> bool:
        """Whether this athlete's best times show on their club's leaderboard."""
        return self.leaderboard_club_id is not None and self.leaderboard_club_id == self.club_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def category(self) -> str | None:
        category = age_category(self.birthdate)
        return category.code if category else None


class AthleteUpdate(BaseModel):
    """Partial update: only the fields present in the request are applied
    (so an explicit null clears a field, an absent one leaves it alone)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    birthdate: date | None = None
    sex: Sex | None = None
    height_cm: float | None = Field(default=None, gt=50, lt=260)
    # Privacy: only the athlete (or a club admin for a managed athlete) may set it.
    leaderboard_opt_in: bool | None = None

    @model_validator(mode="after")
    def _display_name_not_null(self) -> "AthleteUpdate":
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null")
        if "leaderboard_opt_in" in self.model_fields_set and self.leaderboard_opt_in is None:
            raise ValueError("leaderboard_opt_in cannot be null")
        if self.birthdate is not None and not date(1900, 1, 1) <= self.birthdate <= date.today():
            raise ValueError("birthdate is out of range")
        return self


class AthleteMetricWrite(BaseModel):
    effective_date: date
    weight_kg: float | None = Field(default=None, gt=20, lt=250)
    ftp_w: int | None = Field(default=None, gt=0, lt=2500)
    max_hr: int | None = Field(default=None, ge=80, le=250)
    resting_hr: int | None = Field(default=None, ge=20, le=150)

    @model_validator(mode="after")
    def _at_least_one_value(self) -> "AthleteMetricWrite":
        if all(getattr(self, f) is None for f in ("weight_kg", "ftp_w", "max_hr", "resting_hr")):
            raise ValueError("At least one of weight_kg, ftp_w, max_hr, resting_hr is required")
        return self


class AthleteMetricRead(BaseModel):
    id: uuid.UUID
    effective_date: date
    weight_kg: float | None
    ftp_w: int | None
    max_hr: int | None
    resting_hr: int | None

    model_config = {"from_attributes": True}


class DatedValueRead(BaseModel):
    value: int | float
    effective_date: date

    model_config = {"from_attributes": True}


class CurrentMetricsRead(BaseModel):
    """Each value as of `on`, with the date it was recorded."""

    on: date
    weight_kg: DatedValueRead | None
    ftp_w: DatedValueRead | None
    max_hr: DatedValueRead | None
    resting_hr: DatedValueRead | None


class CoachLinkRead(BaseModel):
    """One coach–athlete link as the requesting user sees it."""

    id: uuid.UUID
    status: CoachAthleteStatus
    athlete_id: uuid.UUID
    athlete_name: str
    coach_user_id: uuid.UUID
    coach_name: str | None
    initiated_by_me: bool
    # A pending request that is mine to accept or decline.
    needs_my_response: bool
    created_at: datetime
    responded_at: datetime | None


class CoachLinkRequest(BaseModel):
    """Asks for a link, as the coach (`acting_as="coach"`: I want to coach
    this athlete) or as the athlete side (`"athlete"`: I want this person to
    coach me, or the managed athlete I run). The other person is named by id
    (someone in a club I belong to) or by email; an email answer never says
    whether the address has an account."""

    acting_as: Literal["coach", "athlete"]
    athlete_id: uuid.UUID | None = None
    athlete_email: EmailStr | None = None
    coach_user_id: uuid.UUID | None = None
    coach_email: EmailStr | None = None

    @model_validator(mode="after")
    def _names_the_other_person(self) -> "CoachLinkRequest":
        if self.acting_as == "coach":
            if (self.athlete_id is None) == (self.athlete_email is None):
                raise ValueError("Give exactly one of athlete_id or athlete_email")
        elif (self.coach_user_id is None) == (self.coach_email is None):
            raise ValueError("Give exactly one of coach_user_id or coach_email")
        return self


class CoachLinkRequested(BaseModel):
    requested: bool = True
