import uuid

from sqlalchemy import select

from app.athletes.models import Athlete
from app.connections.models import DataSourceConnection, IngestionRun, RawSnapshot
from app.ingestion.sqorz.client import SqorzClientError
from app.training.models import TrainingEvent

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
        "/auth/signup", json={"email": email, "password": "Correcthorse123!", "display_name": display_name}
    )
    assert resp.status_code == 201
    return resp.json()


async def _self_athlete_id(db_session, user_id: str) -> uuid.UUID:
    async with db_session() as session:
        athlete = await session.scalar(select(Athlete).where(Athlete.user_id == uuid.UUID(user_id)))
        return athlete.id


def _patch_fetch(monkeypatch, result=None, error: Exception | None = None):
    class FakeSqorzHttpClient:
        async def fetch_transponder_history(self, transponder_code: str):
            if error is not None:
                raise error
            return result if result is not None else SAMPLE_PAYLOAD

    monkeypatch.setattr("app.ingestion.sqorz.factory.SqorzHttpClient", FakeSqorzHttpClient)


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


async def test_stop_assignment_ends_the_open_ended_assignment(client, db_session, monkeypatch):
    from datetime import date, timedelta

    _patch_fetch(monkeypatch)
    user = await _signup(client, "athlete-stop@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-STOP", "start_date": "2026-06-01", "end_date": None},
    )
    assert resp.status_code == 201
    assignment_id = resp.json()["id"]

    list_before = await client.get(f"/athletes/{athlete_id}/transponder-assignments")
    assert next(a for a in list_before.json() if a["id"] == assignment_id)["end_date"] is None

    stop_resp = await client.post(f"/athletes/{athlete_id}/transponder-assignments/{assignment_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["end_date"] == (date.today() - timedelta(days=1)).isoformat()

    list_after = await client.get(f"/athletes/{athlete_id}/transponder-assignments")
    assert next(a for a in list_after.json() if a["id"] == assignment_id)["end_date"] is not None

    missing = await client.post(f"/athletes/{athlete_id}/transponder-assignments/{uuid.uuid4()}/stop")
    assert missing.status_code == 404


async def test_overlapping_same_athlete_assignment_merges(client, db_session, monkeypatch):
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
    assert overlapping.status_code == 201

    list_resp = await client.get(f"/athletes/{athlete_id}/transponder-assignments")
    assert list_resp.status_code == 200
    matching = [a for a in list_resp.json() if a["transponder_code"] == "LS-11111"]
    assert len(matching) == 1
    assert matching[0]["start_date"] == "2026-06-01"
    assert matching[0]["end_date"] == "2026-06-20"


async def test_overlapping_assignment_for_different_athlete_still_rejected(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    user_a = await _signup(client, "athlete9a@example.com")
    athlete_a_id = await _self_athlete_id(db_session, user_a["id"])

    first = await client.post(
        f"/athletes/{athlete_a_id}/transponder-assignments",
        json={"transponder_code": "LS-88888", "start_date": "2026-06-01", "end_date": "2026-06-15"},
    )
    assert first.status_code == 201

    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as other_client:
        user_b = await _signup(other_client, "athlete9b@example.com")
        athlete_b_id = await _self_athlete_id(db_session, user_b["id"])

        conflicting = await other_client.post(
            f"/athletes/{athlete_b_id}/transponder-assignments",
            json={"transponder_code": "LS-88888", "start_date": "2026-06-10", "end_date": "2026-06-20"},
        )
        assert conflicting.status_code == 409


def _two_event_payload(transponder_code: str) -> dict:
    def _detail(event_id: str, event_date: str) -> dict:
        return {
            "accountId": "acc-1",
            "accountName": "CNCB",
            "cacheSeconds": 60,
            "trainingDetail": {
                "eventId": event_id,
                "eventName": f"Session {event_date}",
                "eventDate": event_date,
            },
        }

    return {
        "transponderCode": transponder_code,
        "eventTrainingDetails": [
            _detail("evt-early", "2026-06-05"),
            _detail("evt-late", "2026-06-25"),
        ],
    }


async def test_widening_same_athlete_assignment_backfills_previously_dropped_events(client, db_session, monkeypatch):
    payload = _two_event_payload("LS-03407-WIDE")
    _patch_fetch(monkeypatch, result=payload)
    user = await _signup(client, "athlete10@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    narrow = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-03407-WIDE", "start_date": "2026-06-01", "end_date": "2026-06-10"},
    )
    assert narrow.status_code == 201

    async with db_session() as session:
        early = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt-early"))
        late = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt-late"))
        assert early is not None
        assert late is None  # outside the narrow window — dropped, reproducing the reported bug's precondition

    wide = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-03407-WIDE", "start_date": "2026-06-01", "end_date": "2026-06-30"},
    )
    assert wide.status_code == 201  # previously: 409

    async with db_session() as session:
        early = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt-early"))
        late = await session.scalar(select(TrainingEvent).where(TrainingEvent.external_event_id == "evt-late"))
        assert early is not None
        assert late is not None  # backfilled by widening + auto re-import, no manual action needed

    list_resp = await client.get(f"/athletes/{athlete_id}/transponder-assignments")
    matching = [a for a in list_resp.json() if a["transponder_code"] == "LS-03407-WIDE"]
    assert len(matching) == 1
    assert matching[0]["start_date"] == "2026-06-01"
    assert matching[0]["end_date"] == "2026-06-30"


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

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as other_client:
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


async def test_ingestion_runs_lists_recent_runs_including_failures(client, db_session, monkeypatch):
    user = await _signup(client, "athlete7@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    _patch_fetch(monkeypatch)
    ok_resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-66666", "start_date": "2026-06-01", "end_date": "2026-06-10"},
    )
    assert ok_resp.status_code == 201

    _patch_fetch(monkeypatch, error=SqorzClientError("boom", http_status=503))
    fail_resp = await client.post(
        f"/athletes/{athlete_id}/transponder-assignments",
        json={"transponder_code": "LS-77777", "start_date": "2026-06-11", "end_date": None},
    )
    assert fail_resp.status_code == 201

    runs_resp = await client.get(f"/athletes/{athlete_id}/ingestion-runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.json()
    assert len(runs) == 2
    by_code = {run["transponder_code"]: run for run in runs}
    assert by_code["LS-66666"]["status"] == "success"
    assert by_code["LS-77777"]["status"] == "failed"
    assert "boom" in by_code["LS-77777"]["error_message"]


async def test_ingestion_runs_empty_for_athlete_with_no_transponders(client, db_session, monkeypatch):
    user = await _signup(client, "athlete8@example.com")
    athlete_id = await _self_athlete_id(db_session, user["id"])

    runs_resp = await client.get(f"/athletes/{athlete_id}/ingestion-runs")
    assert runs_resp.status_code == 200
    assert runs_resp.json() == []


async def test_unrelated_user_cannot_report_usage_for_other_athlete(client, db_session, monkeypatch):
    _patch_fetch(monkeypatch)
    owner = await _signup(client, "owner-conn@example.com")
    owner_athlete_id = await _self_athlete_id(db_session, owner["id"])

    from httpx import ASGITransport, AsyncClient

    from app.main import app as real_app

    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api") as stranger_client:
        await _signup(stranger_client, "stranger-conn@example.com")

        resp = await stranger_client.post(
            f"/athletes/{owner_athlete_id}/transponder-assignments",
            json={"transponder_code": "LS-55555", "start_date": "2026-06-01", "end_date": None},
        )
        assert resp.status_code == 403
