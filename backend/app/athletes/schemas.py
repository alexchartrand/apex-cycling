import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator

from app.athletes.categories import age_category

Sex = Literal["female", "male"]


class AthleteRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    club_id: uuid.UUID | None
    display_name: str
    birthdate: date | None
    sex: Sex | None
    height_cm: float | None

    model_config = {"from_attributes": True}

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

    @model_validator(mode="after")
    def _display_name_not_null(self) -> "AthleteUpdate":
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null")
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
