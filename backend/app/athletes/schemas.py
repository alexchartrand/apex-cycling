import uuid
from datetime import date

from pydantic import BaseModel


class AthleteRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    club_id: uuid.UUID | None
    display_name: str
    birthdate: date | None
    gender: str | None

    model_config = {"from_attributes": True}
