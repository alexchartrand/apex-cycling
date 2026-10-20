import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.admin.router import worker_status
from app.connections.models import (
    DataSourceConnection,
    DataSourceProvider,
    IngestionRun,
    IngestionRunStatus,
)
from app.core.logging import JsonFormatter, RequestIdFilter, request_id_var
from app.ops.heartbeat import record_beat, touch_heartbeat_file
from app.ops.models import WorkerHeartbeat


async def test_health_reports_database_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


async def test_health_is_503_when_database_is_down(client):
    from app.db.session import get_db
    from app.main import app

    class BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise ConnectionError("db down")

    async def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "error"


async def test_request_id_is_generated_and_echoed(client):
    generated = (await client.get("/health")).headers["x-request-id"]
    assert len(generated) == 32
    echoed = (await client.get("/health", headers={"X-Request-ID": "abc-123"})).headers["x-request-id"]
    assert echoed == "abc-123"
    # Junk is replaced rather than copied into logs and headers.
    replaced = (await client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})).headers[
        "x-request-id"
    ]
    assert replaced != "bad id\twith spaces" and len(replaced) == 32


def test_json_log_line_carries_request_id_and_extras():
    record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "GET /x %s", (200,), None)
    record.status = 200
    token = request_id_var.set("req-1")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)
    entry = json.loads(JsonFormatter().format(record))
    assert entry["msg"] == "GET /x 200"
    assert entry["request_id"] == "req-1"
    assert entry["status"] == 200
    assert entry["level"] == "INFO"


async def test_record_beat_upserts_and_keeps_last_poll(db_session):
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    async with db_session() as db:
        await record_beat(db, started_at=started, now=started + timedelta(minutes=1))
        row = await db.get(WorkerHeartbeat, "ingestion")
        assert row.last_poll_finished_at is None

        await record_beat(
            db,
            started_at=started,
            now=started + timedelta(minutes=2),
            poll=True,
            poll_started_at=started,
            poll_finished_at=started + timedelta(minutes=2),
            connections=3,
            failures=1,
            error="boom",
        )
        # A plain beat afterwards must not erase the last poll's outcome.
        await record_beat(db, started_at=started, now=started + timedelta(minutes=3))
        rows = (await db.scalars(select(WorkerHeartbeat))).all()
        assert len(rows) == 1
        assert rows[0].last_poll_connections == 3
        assert rows[0].last_poll_failures == 1
        assert rows[0].last_error == "boom"


def test_worker_status_states():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert worker_status(None, now).state == "never"
    fresh = WorkerHeartbeat(name="ingestion", started_at=now, last_seen_at=now - timedelta(seconds=30))
    assert worker_status(fresh, now).state == "ok"
    old = WorkerHeartbeat(name="ingestion", started_at=now, last_seen_at=now - timedelta(minutes=10))
    assert worker_status(old, now).state == "stale"


def test_touch_heartbeat_file(tmp_path):
    target = tmp_path / "beat"
    touch_heartbeat_file(target)
    assert target.exists()


async def _signup(client, email, admin_db=None):
    await client.post(
        "/auth/signup",
        json={"email": email, "password": "Correct-Horse-9", "display_name": email.split("@")[0]},
    )


async def test_admin_overview_is_admin_only(client, db_session):
    await _signup(client, "member@example.com")
    assert (await client.get("/admin/overview")).status_code == 403
    client.cookies.clear()
    assert (await client.get("/admin/overview")).status_code == 401


async def test_admin_overview_lists_users_failures_and_worker(client, db_session):
    from app.auth.models import User

    await _signup(client, "boss@example.com")
    async with db_session() as db:
        boss = await db.scalar(select(User).where(User.email == "boss@example.com"))
        boss.is_platform_admin = True
        conn = DataSourceConnection(provider=DataSourceProvider.SQORZ, external_id="LS-1")
        db.add(conn)
        await db.flush()
        db.add(
            IngestionRun(
                data_source_connection_id=conn.id,
                requested_at=datetime.now(timezone.utc),
                status=IngestionRunStatus.FAILED,
                http_status=502,
                error_message="sqorz down",
            )
        )
        await db.commit()
        await record_beat(db, started_at=datetime.now(timezone.utc))

    body = (await client.get("/admin/overview")).json()
    assert body["worker"]["state"] == "ok"
    assert body["counts"]["users"] == 1
    assert body["counts"]["active_transponders"] == 1
    assert body["recent_users"][0]["email"] == "boss@example.com"
    assert body["recent_users"][0]["display_name"] == "boss"
    assert body["failed_runs"] == [
        {
            "id": body["failed_runs"][0]["id"],
            "transponder": "LS-1",
            "requested_at": body["failed_runs"][0]["requested_at"],
            "http_status": 502,
            "error_message": "sqorz down",
        }
    ]
