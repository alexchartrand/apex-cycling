"""SQLAlchemy-backed implementations of the sqorz ingestion repository
ports. This is the only module in app/ingestion/sqorz allowed to import
sqlalchemy or app.connections.models directly.
"""
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import (
    DataSourceConnection,
    DataSourceProvider,
    IngestionRun,
    IngestionRunStatus,
    RawSnapshot,
)
from app.ingestion.sqorz.dtos import DataSourceConnectionRecord, IngestionRunRecord


def _to_connection_record(connection: DataSourceConnection) -> DataSourceConnectionRecord:
    return DataSourceConnectionRecord(
        id=connection.id,
        external_id=connection.external_id,
        sqorz_account_id=connection.sqorz_account_id,
        sqorz_account_name=connection.sqorz_account_name,
    )


def _to_run_record(run: IngestionRun) -> IngestionRunRecord:
    return IngestionRunRecord(
        id=run.id,
        status=run.status.value,
        http_status=run.http_status,
        error_message=run.error_message,
        requested_at=run.requested_at,
        completed_at=run.completed_at,
    )


class SqlAlchemyDataSourceConnectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, connection_id: uuid.UUID) -> DataSourceConnectionRecord | None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        if connection is None:
            return None
        return _to_connection_record(connection)

    async def update_after_sync(
        self,
        connection_id: uuid.UUID,
        *,
        sqorz_account_id: str | None,
        sqorz_account_name: str | None,
        last_synced_at: datetime,
    ) -> None:
        connection = await self._db.get(DataSourceConnection, connection_id)
        if connection is None:
            return
        if sqorz_account_id is not None:
            connection.sqorz_account_id = sqorz_account_id
            connection.sqorz_account_name = sqorz_account_name
        connection.last_synced_at = last_synced_at


class SqlAlchemyIngestionRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, connection_id: uuid.UUID, requested_at: datetime) -> IngestionRunRecord:
        run = IngestionRun(
            data_source_connection_id=connection_id,
            requested_at=requested_at,
            status=IngestionRunStatus.PENDING,
        )
        self._db.add(run)
        await self._db.flush()
        return _to_run_record(run)

    async def mark_failed(
        self, run_id: uuid.UUID, *, http_status: int | None, error_message: str, completed_at: datetime
    ) -> IngestionRunRecord:
        run = await self._db.get(IngestionRun, run_id)
        run.status = IngestionRunStatus.FAILED
        run.http_status = http_status
        run.error_message = error_message
        run.completed_at = completed_at
        return _to_run_record(run)

    async def mark_success(
        self, run_id: uuid.UUID, *, http_status: int, completed_at: datetime
    ) -> IngestionRunRecord:
        run = await self._db.get(IngestionRun, run_id)
        run.status = IngestionRunStatus.SUCCESS
        run.http_status = http_status
        run.completed_at = completed_at
        return _to_run_record(run)


class SqlAlchemyRawSnapshotRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_latest_hash(self, external_ref: str) -> str | None:
        latest = await self._db.scalar(
            select(RawSnapshot)
            .where(RawSnapshot.external_ref == external_ref)
            .order_by(RawSnapshot.fetched_at.desc())
            .limit(1)
        )
        return latest.content_hash if latest is not None else None

    async def create(
        self,
        *,
        ingestion_run_id: uuid.UUID,
        external_ref: str,
        payload: dict,
        content_hash: str,
        fetched_at: datetime,
    ) -> None:
        self._db.add(
            RawSnapshot(
                ingestion_run_id=ingestion_run_id,
                provider=DataSourceProvider.SQORZ,
                external_ref=external_ref,
                payload=payload,
                content_hash=content_hash,
                fetched_at=fetched_at,
            )
        )


class SqlAlchemySessionCommitter:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def commit(self) -> None:
        await self._db.commit()
