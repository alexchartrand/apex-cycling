import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import (
    DataSourceConnection,
    DataSourceProvider,
    IngestionRun,
    TransponderAssignment,
)


class OverlappingAssignmentError(Exception):
    """Raised when a new transponder assignment's date range overlaps an
    existing assignment for the same connection — one transponder maps to
    at most one athlete at any given time.
    """


def _ranges_overlap(
    start_a: date, end_a: date | None, start_b: date, end_b: date | None
) -> bool:
    # Treat a null end_date as "ongoing" (open-ended).
    a_ends_after_b_starts = end_a is None or end_a >= start_b
    b_ends_after_a_starts = end_b is None or end_b >= start_a
    return a_ends_after_b_starts and b_ends_after_a_starts


async def get_or_create_sqorz_connection(db: AsyncSession, transponder_code: str) -> DataSourceConnection:
    # Sqorz's API is case-insensitive on transponder code, so normalize here
    # to avoid creating a second `DataSourceConnection` for the same physical
    # transponder just because someone typed a different case.
    normalized_code = transponder_code.strip().upper()
    connection = await db.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.provider == DataSourceProvider.SQORZ,
            DataSourceConnection.external_id == normalized_code,
        )
    )
    if connection is None:
        connection = DataSourceConnection(provider=DataSourceProvider.SQORZ, external_id=normalized_code)
        db.add(connection)
        await db.flush()
    return connection


async def create_transponder_assignment(
    db: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    transponder_code: str,
    start_date: date,
    end_date: date | None,
    created_by_user_id: uuid.UUID,
    notes: str | None,
) -> TransponderAssignment:
    connection = await get_or_create_sqorz_connection(db, transponder_code)

    existing = await db.scalars(
        select(TransponderAssignment).where(
            TransponderAssignment.data_source_connection_id == connection.id
        )
    )
    for other in existing:
        if _ranges_overlap(start_date, end_date, other.start_date, other.end_date):
            raise OverlappingAssignmentError(
                f"Transponder {transponder_code} is already assigned for an overlapping date range"
            )

    assignment = TransponderAssignment(
        athlete_id=athlete_id,
        data_source_connection_id=connection.id,
        start_date=start_date,
        end_date=end_date,
        created_by_user_id=created_by_user_id,
        notes=notes,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def list_ingestion_runs_for_athlete(
    db: AsyncSession, *, athlete_id: uuid.UUID, limit: int = 20
) -> list[tuple[IngestionRun, str]]:
    """Recent ingestion runs across every connection this athlete has ever
    reported usage of, newest first, paired with the connection's
    transponder code — so a failed background sync is visible to the
    athlete, not just buried in `ingestion_runs`.
    """
    connection_ids = await db.scalars(
        select(TransponderAssignment.data_source_connection_id)
        .where(TransponderAssignment.athlete_id == athlete_id)
        .distinct()
    )
    connection_ids = list(connection_ids)
    if not connection_ids:
        return []

    rows = await db.execute(
        select(IngestionRun, DataSourceConnection.external_id)
        .join(DataSourceConnection, IngestionRun.data_source_connection_id == DataSourceConnection.id)
        .where(IngestionRun.data_source_connection_id.in_(connection_ids))
        .order_by(IngestionRun.requested_at.desc())
        .limit(limit)
    )
    return list(rows.all())
