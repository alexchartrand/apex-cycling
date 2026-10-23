import uuid
from datetime import datetime, timezone

from app.ingestion.sqorz.client import SqorzClientError
from app.ingestion.sqorz.dtos import DataSourceConnectionRecord, IngestionRunRecord
from app.ingestion.sqorz.service import NORMALIZER_VERSION, SqorzIngestionService, _content_hash

SAMPLE_PAYLOAD = {
    "transponderCode": "LS-03407",
    "eventTrainingDetails": [
        {
            "accountId": "acc-1",
            "accountName": "CNCB",
            "trainingDetail": {"eventId": "evt-1", "eventDate": "2026-07-07"},
        }
    ],
}

CONNECTION = DataSourceConnectionRecord(
    id=uuid.uuid4(), external_id="LS-03407", sqorz_account_id=None, sqorz_account_name=None
)


class FakeSqorzClient:
    def __init__(self, *, payload=None, error: Exception | None = None):
        self._payload = payload if payload is not None else SAMPLE_PAYLOAD
        self._error = error

    async def fetch_transponder_history(self, transponder_code: str) -> dict:
        if self._error is not None:
            raise self._error
        return self._payload


class FakeConnectionRepo:
    def __init__(self, connection: DataSourceConnectionRecord | None, *, assignments_changed: bool = False):
        self._connection = connection
        self._assignments_changed = assignments_changed
        self.update_calls: list[dict] = []
        self.normalized_calls: list[dict] = []

    async def get_by_id(self, connection_id):
        return self._connection

    async def update_after_sync(self, connection_id, *, sqorz_account_id, sqorz_account_name, last_synced_at):
        self.update_calls.append(
            {
                "connection_id": connection_id,
                "sqorz_account_id": sqorz_account_id,
                "sqorz_account_name": sqorz_account_name,
                "last_synced_at": last_synced_at,
            }
        )


    async def assignments_changed_since(self, connection_id, since):
        return self._assignments_changed

    async def mark_normalized(self, connection_id, *, at, version):
        self.normalized_calls.append({"connection_id": connection_id, "at": at, "version": version})


class FakeRunRepo:
    def __init__(self):
        self.created = 0
        self.failed_calls: list[dict] = []
        self.success_calls: list[dict] = []

    async def create(self, connection_id, requested_at):
        self.created += 1
        return IngestionRunRecord(
            id=uuid.uuid4(),
            status="pending",
            http_status=None,
            error_message=None,
            requested_at=requested_at,
            completed_at=None,
        )

    async def mark_failed(self, run_id, *, http_status, error_message, completed_at):
        self.failed_calls.append({"run_id": run_id, "http_status": http_status, "error_message": error_message})
        return IngestionRunRecord(
            id=run_id,
            status="failed",
            http_status=http_status,
            error_message=error_message,
            requested_at=datetime.now(timezone.utc),
            completed_at=completed_at,
        )

    async def mark_success(self, run_id, *, http_status, completed_at):
        self.success_calls.append({"run_id": run_id, "http_status": http_status})
        return IngestionRunRecord(
            id=run_id,
            status="success",
            http_status=http_status,
            error_message=None,
            requested_at=datetime.now(timezone.utc),
            completed_at=completed_at,
        )


class FakeSnapshotRepo:
    def __init__(self, latest_hash: str | None = None):
        self._latest_hash = latest_hash
        self.create_calls: list[dict] = []

    async def get_latest_hash(self, external_ref):
        return self._latest_hash

    async def create(self, *, ingestion_run_id, external_ref, payload, content_hash, fetched_at):
        self.create_calls.append({"ingestion_run_id": ingestion_run_id, "content_hash": content_hash})


class FakeNormalizer:
    def __init__(self, athlete_ids: set[uuid.UUID] | None = None):
        self.calls: list[dict] = []
        self._athlete_ids = athlete_ids or set()

    async def normalize(self, payload):
        self.calls.append(payload)
        return self._athlete_ids


class FakeRecords:
    def __init__(self):
        self.calls: list[set[uuid.UUID]] = []

    async def recompute(self, athlete_ids):
        self.calls.append(set(athlete_ids))


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def _build_service(
    *, client, connection_repo=None, run_repo=None, snapshot_repo=None, normalizer=None, records=None, uow=None
):
    return SqorzIngestionService(
        client=client,
        connection_repo=connection_repo or FakeConnectionRepo(CONNECTION),
        run_repo=run_repo or FakeRunRepo(),
        snapshot_repo=snapshot_repo or FakeSnapshotRepo(),
        normalizer=normalizer or FakeNormalizer(),
        records=records or FakeRecords(),
        unit_of_work=uow or FakeUnitOfWork(),
    )


async def test_ingest_creates_snapshot_and_marks_success():
    run_repo = FakeRunRepo()
    snapshot_repo = FakeSnapshotRepo(latest_hash=None)
    normalizer = FakeNormalizer()
    uow = FakeUnitOfWork()
    service = _build_service(
        client=FakeSqorzClient(),
        run_repo=run_repo,
        snapshot_repo=snapshot_repo,
        normalizer=normalizer,
        uow=uow,
    )

    run = await service.ingest(CONNECTION)

    assert run.status == "success"
    assert run.http_status == 200
    assert len(snapshot_repo.create_calls) == 1
    assert normalizer.calls == [SAMPLE_PAYLOAD]
    assert uow.commits == 1


def _normalized_connection(**overrides) -> DataSourceConnectionRecord:
    fields = dict(
        id=CONNECTION.id,
        external_id=CONNECTION.external_id,
        sqorz_account_id=None,
        sqorz_account_name=None,
        normalized_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
        normalizer_version=NORMALIZER_VERSION,
    )
    return DataSourceConnectionRecord(**{**fields, **overrides})


async def test_ingest_remembers_when_it_normalized():
    connection_repo = FakeConnectionRepo(CONNECTION)
    service = _build_service(client=FakeSqorzClient(), connection_repo=connection_repo)

    await service.ingest(CONNECTION)

    assert [c["version"] for c in connection_repo.normalized_calls] == [NORMALIZER_VERSION]


async def test_ingest_with_unchanged_hash_and_assignments_skips_normalizing():
    connection = _normalized_connection()
    snapshot_repo = FakeSnapshotRepo(latest_hash=_content_hash(SAMPLE_PAYLOAD))
    normalizer, records = FakeNormalizer(), FakeRecords()
    connection_repo = FakeConnectionRepo(connection)
    uow = FakeUnitOfWork()
    service = _build_service(
        client=FakeSqorzClient(),
        connection_repo=connection_repo,
        snapshot_repo=snapshot_repo,
        normalizer=normalizer,
        records=records,
        uow=uow,
    )

    run = await service.ingest(connection)

    assert run.status == "success"
    assert snapshot_repo.create_calls == []
    assert normalizer.calls == [] and records.calls == []
    assert connection_repo.normalized_calls == []
    assert len(connection_repo.update_calls) == 1  # still counted as synced
    assert uow.commits == 1


async def test_ingest_with_unchanged_hash_renormalizes_after_an_assignment_changed():
    connection = _normalized_connection()
    normalizer = FakeNormalizer()
    service = _build_service(
        client=FakeSqorzClient(),
        connection_repo=FakeConnectionRepo(connection, assignments_changed=True),
        snapshot_repo=FakeSnapshotRepo(latest_hash=_content_hash(SAMPLE_PAYLOAD)),
        normalizer=normalizer,
    )

    await service.ingest(connection)

    assert normalizer.calls == [SAMPLE_PAYLOAD]


async def test_ingest_with_unchanged_hash_renormalizes_when_the_normalizer_moved_on():
    connection = _normalized_connection(normalizer_version=NORMALIZER_VERSION - 1)
    normalizer = FakeNormalizer()
    service = _build_service(
        client=FakeSqorzClient(),
        connection_repo=FakeConnectionRepo(connection),
        snapshot_repo=FakeSnapshotRepo(latest_hash=_content_hash(SAMPLE_PAYLOAD)),
        normalizer=normalizer,
    )

    await service.ingest(connection)

    assert normalizer.calls == [SAMPLE_PAYLOAD]


async def test_ingest_with_a_changed_payload_normalizes_even_when_nothing_else_changed():
    connection = _normalized_connection()
    normalizer = FakeNormalizer()
    service = _build_service(
        client=FakeSqorzClient(),
        connection_repo=FakeConnectionRepo(connection),
        snapshot_repo=FakeSnapshotRepo(latest_hash="an older hash"),
        normalizer=normalizer,
    )

    await service.ingest(connection)

    assert normalizer.calls == [SAMPLE_PAYLOAD]


async def test_forced_ingest_normalizes_an_unchanged_payload():
    connection = _normalized_connection()
    normalizer = FakeNormalizer()
    service = _build_service(
        client=FakeSqorzClient(),
        connection_repo=FakeConnectionRepo(connection),
        snapshot_repo=FakeSnapshotRepo(latest_hash=_content_hash(SAMPLE_PAYLOAD)),
        normalizer=normalizer,
    )

    await service.ingest_by_id(connection.id, force=True)

    assert normalizer.calls == [SAMPLE_PAYLOAD]


async def test_ingest_marks_failed_on_client_error():
    error = SqorzClientError("boom", http_status=503)
    run_repo = FakeRunRepo()
    snapshot_repo = FakeSnapshotRepo()
    normalizer = FakeNormalizer()
    connection_repo = FakeConnectionRepo(CONNECTION)
    uow = FakeUnitOfWork()
    service = _build_service(
        client=FakeSqorzClient(error=error),
        connection_repo=connection_repo,
        run_repo=run_repo,
        snapshot_repo=snapshot_repo,
        normalizer=normalizer,
        uow=uow,
    )

    run = await service.ingest(CONNECTION)

    assert run.status == "failed"
    assert run.http_status == 503
    assert "boom" in run.error_message
    assert snapshot_repo.create_calls == []
    assert normalizer.calls == []
    assert connection_repo.update_calls == []
    assert uow.commits == 1


async def test_ingest_by_id_returns_none_for_unknown_connection():
    service = _build_service(client=FakeSqorzClient(), connection_repo=FakeConnectionRepo(None))

    run = await service.ingest_by_id(uuid.uuid4())

    assert run is None


async def test_ingest_recomputes_records_for_the_athletes_normalization_touched():
    athlete_ids = {uuid.uuid4(), uuid.uuid4()}
    records = FakeRecords()
    service = _build_service(
        client=FakeSqorzClient(), normalizer=FakeNormalizer(athlete_ids), records=records
    )

    await service.ingest(CONNECTION)

    assert records.calls == [athlete_ids]


async def test_ingest_does_not_recompute_records_when_the_fetch_fails():
    records = FakeRecords()
    service = _build_service(
        client=FakeSqorzClient(error=SqorzClientError("boom", http_status=503)), records=records
    )

    await service.ingest(CONNECTION)

    assert records.calls == []
