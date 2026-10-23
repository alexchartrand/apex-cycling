"""Internal transfer objects that cross the sqorz ingestion business
logic/persistence boundary. Deliberately plain dataclasses rather than
pydantic models: this data is already trusted (it comes straight out of our
own DB), so there's nothing to validate, and keeping them as dataclasses
signals they're distinct from the API-facing pydantic schemas in
connections/schemas.py.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DataSourceConnectionRecord:
    id: uuid.UUID
    external_id: str
    sqorz_account_id: str | None
    sqorz_account_name: str | None
    normalized_at: datetime | None = None
    normalizer_version: int | None = None


@dataclass(frozen=True)
class IngestionRunRecord:
    id: uuid.UUID
    status: str
    http_status: int | None
    error_message: str | None
    requested_at: datetime
    completed_at: datetime | None
