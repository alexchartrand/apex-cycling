import logging
import uuid
from datetime import date

from sqlalchemy import select

from app.connections.models import DataSourceConnection, DataSourceProvider, TransponderAssignment
from app.db.session import AsyncSessionLocal
from app.ingestion.sqorz.service import ingest_sqorz_connection_by_id

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


async def poll_active_connections() -> None:
    connection_ids = await get_active_sqorz_connection_ids()
    logger.info("Polling %d active sqorz connection(s)", len(connection_ids))

    for connection_id in connection_ids:
        try:
            async with AsyncSessionLocal() as db:
                run = await ingest_sqorz_connection_by_id(db, connection_id)
            logger.info("Connection %s: run status=%s", connection_id, run.status if run else "missing")
        except Exception:
            logger.exception("Ingestion failed for connection %s", connection_id)
