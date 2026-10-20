import logging
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.connections.models import (
    DataSourceConnection,
    DataSourceConnectionStatus,
    DataSourceProvider,
    TransponderAssignment,
)
from app.db.session import AsyncSessionLocal
from app.ingestion.intervals.factory import build_intervals_sync_service
from app.ingestion.sqorz.factory import build_sqorz_ingestion_service

logger = logging.getLogger("ingestion.jobs")


async def get_active_sqorz_connection_ids() -> list[uuid.UUID]:
    """Connections with at least one currently-ongoing transponder
    assignment — no point polling a transponder nobody is currently using.
    """
    today = date.today()
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(DataSourceConnection.id)
            .join(
                TransponderAssignment,
                TransponderAssignment.data_source_connection_id == DataSourceConnection.id,
            )
            .where(
                DataSourceConnection.provider == DataSourceProvider.SQORZ,
                TransponderAssignment.start_date <= today,
                (TransponderAssignment.end_date.is_(None)) | (TransponderAssignment.end_date >= today),
            )
            .distinct()
        )
        return list(rows)


@dataclass
class PollResult:
    connections: int = 0
    failures: int = 0
    last_error: str | None = None


async def poll_active_connections() -> PollResult:
    connection_ids = await get_active_sqorz_connection_ids()
    logger.info("Polling %d active sqorz connection(s)", len(connection_ids))
    result = PollResult(connections=len(connection_ids))

    for connection_id in connection_ids:
        try:
            async with AsyncSessionLocal() as db:
                run = await build_sqorz_ingestion_service(db).ingest_by_id(connection_id)
            logger.info("Connection %s: run status=%s", connection_id, run.status if run else "missing")
        except Exception as exc:
            logger.exception("Ingestion failed for connection %s", connection_id)
            result.failures += 1
            result.last_error = f"{connection_id}: {type(exc).__name__}: {exc}"[:500]
    return result


async def poll_intervals_connections() -> PollResult:
    """Syncs every athlete's active Intervals.icu connection."""
    async with AsyncSessionLocal() as db:
        connection_ids = list(
            await db.scalars(
                select(DataSourceConnection.id).where(
                    DataSourceConnection.provider == DataSourceProvider.INTERVALS_ICU,
                    DataSourceConnection.status == DataSourceConnectionStatus.ACTIVE,
                    DataSourceConnection.athlete_id.is_not(None),
                )
            )
        )
    logger.info("Syncing %d Intervals.icu connection(s)", len(connection_ids))
    result = PollResult(connections=len(connection_ids))
    for connection_id in connection_ids:
        try:
            async with AsyncSessionLocal() as db:
                outcome = await build_intervals_sync_service(db).sync_by_id(connection_id)
            if outcome is not None and outcome.status == "failed":
                result.failures += 1
                result.last_error = f"{connection_id}: {outcome.error}"[:500]
        except Exception as exc:
            logger.exception("Intervals.icu sync failed for connection %s", connection_id)
            result.failures += 1
            result.last_error = f"{connection_id}: {type(exc).__name__}: {exc}"[:500]
    return result
