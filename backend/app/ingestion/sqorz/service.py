import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import (
    DataSourceConnection,
    DataSourceProvider,
    IngestionRun,
    IngestionRunStatus,
    RawSnapshot,
)
from app.db.base import utcnow
from app.ingestion.sqorz.client import SqorzClientError, fetch_transponder_history
from app.ingestion.sqorz.normalizer import normalize_snapshot


def _content_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _extract_account_info(payload: dict) -> tuple[str | None, str | None]:
    details = payload.get("eventTrainingDetails") or []
    if not details:
        return None, None
    first = details[0]
    return first.get("accountId"), first.get("accountName")


async def ingest_sqorz_connection(db: AsyncSession, connection: DataSourceConnection) -> IngestionRun:
    """Fetch the transponder's full history, dedupe against the latest
    stored snapshot by content hash, record an `IngestionRun`, and
    normalize the payload into the query-friendly training tables.
    """
    run = IngestionRun(
        data_source_connection_id=connection.id,
        requested_at=utcnow(),
        status=IngestionRunStatus.PENDING,
    )
    db.add(run)
    await db.flush()

    try:
        payload = await fetch_transponder_history(connection.external_id)
    except SqorzClientError as exc:
        run.status = IngestionRunStatus.FAILED
        run.http_status = exc.http_status
        run.error_message = str(exc)
        run.completed_at = utcnow()
        await db.commit()
        return run

    content_hash = _content_hash(payload)

    latest = await db.scalar(
        select(RawSnapshot)
        .where(RawSnapshot.external_ref == connection.external_id)
        .order_by(RawSnapshot.fetched_at.desc())
        .limit(1)
    )
    if latest is None or latest.content_hash != content_hash:
        db.add(
            RawSnapshot(
                ingestion_run_id=run.id,
                provider=DataSourceProvider.SQORZ,
                external_ref=connection.external_id,
                payload=payload,
                content_hash=content_hash,
                fetched_at=utcnow(),
            )
        )

    account_id, account_name = _extract_account_info(payload)
    if account_id is not None:
        connection.sqorz_account_id = account_id
        connection.sqorz_account_name = account_name

    connection.last_synced_at = utcnow()

    # Always re-normalize the freshly fetched payload (even if unchanged from
    # the last snapshot) so a newly-added TransponderAssignment backfills
    # attribution for laps that were previously unattributed.
    await normalize_snapshot(db, payload)

    run.status = IngestionRunStatus.SUCCESS
    run.http_status = 200
    run.completed_at = utcnow()

    await db.commit()
    return run


async def ingest_sqorz_connection_by_id(db: AsyncSession, connection_id: uuid.UUID) -> IngestionRun | None:
    connection = await db.get(DataSourceConnection, connection_id)
    if connection is None:
        return None
    return await ingest_sqorz_connection(db, connection)
