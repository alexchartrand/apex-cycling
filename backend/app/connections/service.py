import uuid
from datetime import date, timedelta

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
    existing assignment belonging to a DIFFERENT athlete for the same
    connection — one transponder maps to at most one athlete at any given
    time. Overlaps against the same athlete's own assignments are merged
    instead (see `create_transponder_assignment`).
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

    existing = list(
        await db.scalars(
            select(TransponderAssignment).where(
                TransponderAssignment.data_source_connection_id == connection.id
            )
        )
    )

    same_athlete_overlaps: list[TransponderAssignment] = []
    for other in existing:
        if not _ranges_overlap(start_date, end_date, other.start_date, other.end_date):
            continue
        if other.athlete_id != athlete_id:
            raise OverlappingAssignmentError(
                f"Transponder {transponder_code} is already assigned for an overlapping date range"
            )
        same_athlete_overlaps.append(other)

    if not same_athlete_overlaps:
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

    # Same athlete reporting usage over a range that touches one or more of
    # their own existing assignments — merge into a single row spanning the
    # union instead of rejecting. A single wide new range can bridge more
    # than one previously-disjoint same-athlete assignment (e.g. existing
    # Jan-Feb and Apr-May rows, new Jan15-Apr15 request), so this merges
    # however many same-athlete rows the new range overlaps.
    same_athlete_overlaps.sort(key=lambda a: a.start_date)
    target = same_athlete_overlaps[0]
    redundant = same_athlete_overlaps[1:]

    all_starts = [start_date, *(a.start_date for a in same_athlete_overlaps)]
    all_ends = [end_date, *(a.end_date for a in same_athlete_overlaps)]
    merged_end = None if any(e is None for e in all_ends) else max(all_ends)

    target.start_date = min(all_starts)
    target.end_date = merged_end
    if notes is not None:
        target.notes = notes

    for stale in redundant:
        await db.delete(stale)

    await db.flush()
    return target


async def stop_transponder_assignment(
    db: AsyncSession, *, athlete_id: uuid.UUID, assignment_id: uuid.UUID
) -> TransponderAssignment | None:
    """Ends an open-ended (autoimport) assignment as of yesterday, so it's
    immediately excluded from the next scheduler poll
    (`app/ingestion/jobs.py::get_active_sqorz_connection_ids`, which treats
    `end_date >= today` as still active).
    """
    assignment = await db.get(TransponderAssignment, assignment_id)
    if assignment is None or assignment.athlete_id != athlete_id:
        return None
    assignment.end_date = date.today() - timedelta(days=1)
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
