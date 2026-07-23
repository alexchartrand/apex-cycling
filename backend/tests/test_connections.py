import uuid

from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.models import DataSourceConnection, IngestionRun, RawSnapshot
from app.ingestion.sqorz.client import SqorzClientError

SAMPLE_PAYLOAD = {
    "transponderCode": "LS-03407",
    "eventTrainingDetails": [
        {
            "accountId": "acc-1",
            "accountName": "CNCB",
            "cacheSeconds": 60,
            "trainingDetail": {
                "eventId": "evt-1",
                "eventName": "Session 2026-07-07",
                "eventDate": "2026-07-07",
            },
        }
    ],
}


async def _signup(client, email, display_name="Someone"):
    resp = await client.post(
        "/auth/signup", json={"email": email, "password": "correcthorse", "display_name": display_name}
    )
    assert resp.status_code == 201
    return resp.json()


async def _self_athlete_id(db_session, user_id: str) -> uuid.UUID:
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user_id)))
        return athlete.id


def _patch_fetch(monkeypatch, result=None, error: Exception | None = None):
    async def fake_fetch(transponder_code: str):
        if error is not None:
            raise error
        return result if result is not None else SAMPLE_PAYLOAD

    monkeypatch.setattr("app.ingestion.sqorz.service.fetch_transponder_history", fake_fetch)


async def test_report_usage_creates_assignment_and_imports(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    user = await _signup(client, "athlete1@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-03407", "start_date": "2026-06-01", "end_date": "2026-06-15"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["transponder_code"] == "LS-03407"
    assert body["athlete_id"] == str(athlete_id)

    async with db_session() as session:
        connection = await session.scalar(
            select(DataSourceConnection).where(DataSourceConnection.external_id == "LS-03407")
        )
        assert connection is not None
        assert connection.sqorz_account_id == "acc-1"
        assert connection.sqorz_account_name == "CNCB"
        assert connection.last_synced_at is not None

        run = await session.scalar(select(IngestionRun).where(IngestionRun.data_source_connection_id == connection.id))
        assert run is not None
        assert run.status.value == "success"

        snapshot = await session.scalar(select(RawSnapshot).where(RawSnapshot.external_ref == "LS-03407"))
        assert snapshot is not None
        assert snapshot.payload["transponderCode"] == "LS-03407"


async def test_report_usage_without_import_now_skips_ingestion(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    user = await _signup(client, "athlete2@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={
            "transponder_code": "LS-99999",
            "start_date": "2026-06-01",
            "end_date": None,
            "import_now": False,
        },
    )
    assert resp.status_code == 201

    async with db_session() as session:
        run = await session.scalar(select(IngestionRun))
        assert run is None


async def test_overlapping_assignment_rejected(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    user = await _signup(client, "athlete3@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    first = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-11111", "start_date": "2026-06-01", "end_date": "2026-06-15"},
    )
    assert first.status_code == 201

    overlapping = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-11111", "start_date": "2026-06-10", "end_date": "2026-06-20"},
    )
    assert overlapping.status_code == 409


async def test_non_overlapping_assignments_for_different_athletes_allowed(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    user_a = await _signup(client, "athlete4a@example.com")
    athlete_a_id = await _self_athlete_id(db_session, user_a["id"])

    first = await client.post(
        f"/athletes/{athlete_a_id}/transponder-assignments",
        json={"transponder_code": "LS-22222", "start_date": "2026-06-01", "end_date": "2026-06-15"},
    )
    assert first.status_code == 201

    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test") as other_client:
        user_b = await _signup(other_client, "athlete4b@example.com")
        athlete_b_id = await _self_athlete_id(db_session, user_b["id"])

        second = await other_client.post(
            f"/athletes/{athlete_b_id}/transponder-assignments",
            json={"transponder_code": "LS-22222", "start_date": "2026-06-16", "end_date": "2026-06-30"},
        )
        assert second.status_code == 201


async def test_import_now_dedupes_unchanged_snapshot(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    user = await _signup(client, "athlete5@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    create_resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-33333", "start_date": "2026-06-01", "end_date": None},
    )
    assignment_id = create_resp.json()["id"]

    import_resp = await client.post(f"/athletes/{athlete_id}/transponder-assignments/{assignment_id}/import")
    assert import_resp.status_code == 200
    assert import_resp.json()["status"] == "success"

    async with db_session() as session:
        snapshots = (await session.scalars(select(RawSnapshot).where(RawSnapshot.external_ref == "LS-33333"))).all()
        assert len(snapshots) == 1

        runs = (await session.scalars(select(IngestionRun))).all()
        assert len(runs) == 2


async def test_import_records_failed_run_on_sqorz_error(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch, error=SqorzClientError("boom", http_status=503))
    user = await _signup(client, "athlete6@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-44444", "start_date": "2026-06-01", "end_date": None},
    )
    assert resp.status_code == 201

    async with db_session() as session:
        run = await session.scalar(select(IngestionRun))
        assert run.status.value == "failed"
        assert run.http_status == 503
        assert "boom" in run.error_message

        snapshot = await session.scalar(select(RawSnapshot))
        assert snapshot is None


async def test_unrelated_user_cannot_report_usage_for_other_athlete(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    owner = await _signup(client, "owner-conn@example.com")
    owner_athlete_id = await _self_athlete_id(db_session, owner["id"])

    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test") as stranger_client:
        await _signup(stranger_client, "stranger-conn@example.com")

        resp = await stranger_client.post(
            f"/athletes/{owner_athlete_id}/transponder-assignments",
            json={"transponder_code": "LS-55555", "start_date": "2026-06-01", "end_date": None},
        )
        assert resp.status_code == 403
