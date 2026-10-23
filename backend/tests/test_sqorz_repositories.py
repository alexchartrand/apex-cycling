import uuid
from datetime import date, datetime, timedelta, timezone

import app.db.models  # noqa: F401  (registers every model)
from app.connections.models import DataSourceConnection, DataSourceProvider, IngestionRun, TransponderAssignment
from app.db.base import utcnow
from app.ingestion.sqorz.repositories import SqlAlchemyDataSourceConnectionRepository, SqlAlchemyRawSnapshotRepository


async def _connection(db) -> DataSourceConnection:
    connection = DataSourceConnection(provider=DataSourceProvider.SQORZ, external_id="LS-1")
    db.add(connection)
    await db.flush()
    return connection


async def test_assignments_changed_since_sees_new_and_edited_assignments(db_session):
    async with db_session() as db:
        connection = await _connection(db)
        repo = SqlAlchemyDataSourceConnectionRepository(db)
        long_ago = utcnow() - timedelta(days=1)

        assert not await repo.assignments_changed_since(connection.id, long_ago)

        assignment = TransponderAssignment(
            athlete_id=uuid.uuid4(), data_source_connection_id=connection.id, start_date=date(2026, 10, 1)
        )
        db.add(assignment)
        await db.commit()
        assert await repo.assignments_changed_since(connection.id, long_ago)
        assert not await repo.assignments_changed_since(connection.id, utcnow() + timedelta(minutes=1))

        # Another connection's assignments don't count.
        other = DataSourceConnection(provider=DataSourceProvider.SQORZ, external_id="LS-2")
        db.add(other)
        await db.flush()
        assert not await repo.assignments_changed_since(other.id, long_ago)

        # An edit (stopping the assignment) moves updated_at on.
        before_edit = utcnow()
        assignment.end_date = date(2026, 10, 15)
        await db.commit()
        assert assignment.updated_at >= before_edit
        assert await repo.assignments_changed_since(connection.id, before_edit)


async def test_mark_normalized_is_read_back_on_the_record(db_session):
    async with db_session() as db:
        connection = await _connection(db)
        repo = SqlAlchemyDataSourceConnectionRepository(db)
        at = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)

        await repo.mark_normalized(connection.id, at=at, version=3)
        record = await repo.get_by_id(connection.id)

        assert record.normalized_at is not None and record.normalizer_version == 3


async def test_latest_hash_is_the_newest_snapshots_hash_and_none_without_snapshots(db_session):
    async with db_session() as db:
        connection = await _connection(db)
        run = IngestionRun(data_source_connection_id=connection.id, requested_at=utcnow())
        db.add(run)
        await db.flush()
        repo = SqlAlchemyRawSnapshotRepository(db)
        assert await repo.get_latest_hash("LS-1") is None

        now = utcnow()
        for hash_, age in (("old", 2), ("new", 1)):
            await repo.create(
                ingestion_run_id=run.id, external_ref="LS-1", payload={}, content_hash=hash_,
                fetched_at=now - timedelta(days=age),
            )
        await db.flush()

        assert await repo.get_latest_hash("LS-1") == "new"
        assert await repo.get_latest_hash("LS-2") is None
