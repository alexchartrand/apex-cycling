"""SQLAlchemy-backed implementations of the Intervals.icu sync ports — the
only module of this package that talks to the database."""

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.models import Activity, ActivitySource
from app.activities.parsers import ActivityParseError
from app.activities.service import import_activity_file
from app.connections.models import (
    DataSourceConnection,
    DataSourceConnectionStatus,
    DataSourceProvider,
    IngestionRun,
    IngestionRunStatus,
)
from app.ingestion.intervals.dtos import IntervalsConnectionRecord, RemoteActivity
from app.ingestion.intervals.ports import ActivityRejected


class SqlAlchemyIntervalsConnectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active(self, connection_id: uuid.UUID) -> IntervalsConnectionRecord | None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        if (
            connection is None
            or connection.provider != DataSourceProvider.INTERVALS_ICU
            or connection.status != DataSourceConnectionStatus.ACTIVE
            or connection.athlete_id is None
            or not (connection.credentials or {}).get("api_key")
        ):
            return None
        return IntervalsConnectionRecord(
            id=connection.id,
            athlete_id=connection.athlete_id,
            api_key=connection.credentials["api_key"],
            last_synced_at=connection.last_synced_at,
        )

    async def known_external_ids(self, connection_id: uuid.UUID, candidates: Collection[str]) -> set[str]:
        if not candidates:
            return set()
        rows = await self._db.scalars(
            select(Activity.external_id).where(
                Activity.data_source_connection_id == connection_id, Activity.external_id.in_(list(candidates))
            )
        )
        return set(rows)

    async def mark_synced(self, connection_id: uuid.UUID, at: datetime) -> None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        connection.last_synced_at = at

    async def deactivate(self, connection_id: uuid.UUID) -> None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        connection.status = DataSourceConnectionStatus.INACTIVE


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


class SqlAlchemyActivityImporter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def import_file(
        self, connection: IntervalsConnectionRecord, remote: RemoteActivity, content: bytes
    ) -> Literal["created", "duplicate"]:
        try:
            outcome = await import_activity_file(
                self._db,
                connection.athlete_id,
                content,
                source=ActivitySource.INTERVALS_ICU,
                external_id=remote.id,
                data_source_connection_id=connection.id,
                name=remote.name,
            )
        except ActivityParseError as exc:
            raise ActivityRejected(str(exc)) from exc
        existing = outcome.activity
        if outcome.status == "duplicate" and existing.external_id is None and existing.data_source_connection_id is None:
            # The same ride came in another way (an upload): remember it is
            # also this Intervals.icu activity so it isn't fetched again.
            existing.external_id = remote.id
            existing.data_source_connection_id = connection.id
        return outcome.status


class SqlAlchemySessionCommitter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def commit(self) -> None:
        await self._db.commit()

    async def rollback(self) -> None:
        await self._db.rollback()
