"""Protocols the sqorz ingestion business logic depends on. Concrete
implementations are wired together in factory.py; nothing in service.py
should import sqlalchemy directly, only these interfaces.
"""
import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Protocol

from app.ingestion.sqorz.dtos import DataSourceConnectionRecord, IngestionRunRecord


class SqorzClientPort(Protocol):
    async def fetch_transponder_history(self, transponder_code: str) -> dict: ...


class DataSourceConnectionRepositoryPort(Protocol):
    async def get_by_id(self, connection_id: uuid.UUID) -> DataSourceConnectionRecord | None: ...

    async def update_after_sync(
        self,
        connection_id: uuid.UUID,
        *,
        sqorz_account_id: str | None,
        sqorz_account_name: str | None,
        last_synced_at: datetime,
    ) -> None: ...

    async def assignments_changed_since(self, connection_id: uuid.UUID, since: datetime) -> bool:
        """Whether a transponder assignment of the connection was added or edited after `since`."""
        ...

    async def mark_normalized(self, connection_id: uuid.UUID, *, at: datetime, version: int) -> None: ...


class IngestionRunRepositoryPort(Protocol):
    async def create(self, connection_id: uuid.UUID, requested_at: datetime) -> IngestionRunRecord: ...

    async def mark_failed(
        self, run_id: uuid.UUID, *, http_status: int | None, error_message: str, completed_at: datetime
    ) -> IngestionRunRecord: ...

    async def mark_success(
        self, run_id: uuid.UUID, *, http_status: int, completed_at: datetime
    ) -> IngestionRunRecord: ...


class RawSnapshotRepositoryPort(Protocol):
    async def get_latest_hash(self, external_ref: str) -> str | None: ...

    async def create(
        self,
        *,
        ingestion_run_id: uuid.UUID,
        external_ref: str,
        payload: dict,
        content_hash: str,
        fetched_at: datetime,
    ) -> None: ...


class SnapshotNormalizerPort(Protocol):
    async def normalize(self, payload: dict) -> set[uuid.UUID]:
        """Stores the payload's laps; returns the athletes it wrote data for."""
        ...


class AthleteRecordsPort(Protocol):
    async def recompute(self, athlete_ids: Collection[uuid.UUID]) -> None:
        """Refreshes data derived from the athletes' laps (personal records,
        links to head-unit recordings)."""
        ...


class UnitOfWorkPort(Protocol):
    async def commit(self) -> None: ...


class SyncFailureNotifierPort(Protocol):
    async def sync_failed(self, connection_id: uuid.UUID, run_id: uuid.UUID, error_message: str) -> None:
        """Tells whoever uses the transponder that a sync failed (once per streak)."""
        ...
