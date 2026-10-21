import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _blank_is_none(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


class GearWrite(BaseModel):
    chainring_teeth: int = Field(ge=10, le=100)
    cog_teeth: int = Field(ge=5, le=60)
    # One wheel turn, ridden: 700×23–25c is about 2100 mm.
    rollout_mm: float = Field(ge=1000, le=3000)
    tire: str | None = Field(default=None, max_length=100)

    _clean_tire = field_validator("tire")(_blank_is_none)


class GearUpdate(BaseModel):
    """PATCH body: only the fields sent change. The numbers can't be null."""

    chainring_teeth: int | None = Field(default=None, ge=10, le=100)
    cog_teeth: int | None = Field(default=None, ge=5, le=60)
    rollout_mm: float | None = Field(default=None, ge=1000, le=3000)
    tire: str | None = Field(default=None, max_length=100)

    _clean_tire = field_validator("tire")(_blank_is_none)

    @field_validator("chainring_teeth", "cog_teeth", "rollout_mm")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("This value can't be cleared")
        return value


class GearRead(BaseModel):
    id: uuid.UUID
    bike_id: uuid.UUID
    chainring_teeth: int
    cog_teeth: int
    rollout_mm: float
    tire: str | None
    # What the numbers mean on the track.
    ratio: float
    development_m: float
    gear_inches: float


class BikeWrite(BaseModel):
    name: Name
    weight_kg: float | None = Field(default=None, ge=3, le=40)
    notes: str | None = Field(default=None, max_length=2000)

    _clean_notes = field_validator("notes")(_blank_is_none)


class BikeUpdate(BaseModel):
    """PATCH body: only the fields sent change; null clears the weight/notes."""

    name: Name | None = None
    weight_kg: float | None = Field(default=None, ge=3, le=40)
    notes: str | None = Field(default=None, max_length=2000)

    _clean_notes = field_validator("notes")(_blank_is_none)

    @field_validator("name")
    @classmethod
    def _name_not_null(cls, value):
        if value is None:
            raise ValueError("A bike needs a name")
        return value


class BikeRead(BaseModel):
    id: uuid.UUID
    name: str
    weight_kg: float | None
    notes: str | None
    gears: list[GearRead]


class GearAssignment(BaseModel):
    """Which gear a session or effort was ridden in; null = none (an effort
    then falls back to its session's gear)."""

    gear_setup_id: uuid.UUID | None = None
