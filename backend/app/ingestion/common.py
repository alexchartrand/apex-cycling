"""Ports shared by the personal-source syncs (Intervals.icu, Strava)."""

import uuid
from datetime import datetime
from typing import Protocol


class SyncRunRepositoryPort(Protocol):
    async def create(self, connection_id: uuid.UUID, requested_at: datetime) -> uuid.UUID: ...

    async def finish(
        self,
        run_id: uuid.UUID,
        *,
        success: bool,
        completed_at: datetime,
        http_status: int | None,
        error_message: str | None,
        imported: int,
    ) -> None: ...


class UnitOfWorkPort(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
