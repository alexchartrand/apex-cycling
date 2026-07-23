import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.connections.models import IngestionRunStatus


class TransponderAssignmentCreate(BaseModel):
    transponder_code: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date | None = None
    notes: str | None = None
    import_now: bool = True


class TransponderAssignmentRead(BaseModel):
    id: uuid.UUID
    athlete_id: uuid.UUID
    transponder_code: str
    start_date: date
    end_date: date | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionRunRead(BaseModel):
    id: uuid.UUID
    status: IngestionRunStatus
    requested_at: datetime
    completed_at: datetime | None
    http_status: int | None
    error_message: str | None

    model_config = {"from_attributes": True}
