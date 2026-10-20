"""SQLAlchemy implementations of the ports shared by the personal-source syncs."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import IngestionRun, IngestionRunStatus


class SqlAlchemySyncRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, connection_id: uuid.UUID, requested_at: datetime) -> uuid.UUID:
        run = IngestionRun(data_source_connection_id=connection_id, requested_at=requested_at)
        self._db.add(run)
        await self._db.flush()
        return run.id

    async def finish(
        self,
        run_id: uuid.UUID,
        *,
        success: bool,
        completed_at: datetime,
        http_status: int | None,
        error_message: str | None,
        imported: int,
    ) -> None:
        run = await self._db.get(IngestionRun, run_id)
        run.status = IngestionRunStatus.SUCCESS if success else IngestionRunStatus.FAILED
        run.completed_at = completed_at
        run.http_status = http_status
        run.error_message = error_message
        run.imported_count = imported


class SqlAlchemySessionCommitter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()
