import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

import app.ingestion.jobs as jobs
from app.activities.models import Activity
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.connections.intervals_router import get_intervals_client, get_session_factory
from app.connections.models import DataSourceConnection, DataSourceConnectionStatus, IngestionRun
from app.core.config import get_settings
from app.db.session import get_db  # noqa: F401
from app.ingestion.intervals.client import IntervalsAuthError, IntervalsClientError, IntervalsRateLimited
from app.ingestion.intervals.factory import build_intervals_sync_service
from app.ingestion.intervals.dtos import RemoteActivity, RemoteAthlete
from app.main import app as real_app
from tests.fit_builder import build_fit
from tests.test_account import _signup

START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)


def _fit(day: int = 1, power: int = 200) -> bytes:
    return build_fit(
        START.replace(day=day),
        [{"t": t, "power": power, "heart_rate": 140, "speed": 10.0, "distance": 10.0 * t} for t in range(60)],
    )


def _remote(id: str, name: str = "Ride", *, type: str = "Ride", source: str = "GARMIN_CONNECT", note: bool = False, day: int = 1):
    return RemoteActivity(
        id=id, name=name, type=type, source=source, start_local=datetime(2026, 6, day, 7), has_note=note
    )


class FakeIntervals:
    """Stands in for the Intervals.icu API."""

    def __init__(self) -> None:
        self.athlete = RemoteAthlete("i42", "Alex")
        self.valid_keys = {"good-key-123"}
        self.activities: list[RemoteActivity] = []
        self.files: dict[str, bytes | None] = {}
        self.downloads: list[str] = []
        self.listed: list[tuple[date, date]] = []
        self.error: Exception | None = None

    async def get_athlete(self, api_key):
        if api_key not in self.valid_keys:
            raise IntervalsAuthError("refused", 401)
        return self.athlete

    async def list_activities(self, api_key, oldest, newest):
        if self.error:
            raise self.error
        self.listed.append((oldest, newest))
        return list(self.activities)

    async def download_file(self, api_key, activity_id):
        self.downloads.append(activity_id)
        return self.files.get(activity_id)


@pytest.fixture
def intervals(db_session, monkeypatch):
    fake = FakeIntervals()
    real_app.dependency_overrides[get_intervals_client] = lambda: fake
    real_app.dependency_overrides[get_session_factory] = lambda: db_session
    return fake


def _other_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api")


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


async def _rider(client) -> str:
    await _signup(client, "rider@example.com")
    return (await client.get("/athletes/me")).json()["id"]


async def _connect(client, athlete_id, key="good-key-123"):
    return await client.put(f"/athletes/{athlete_id}/intervals", json={"api_key": key})


async def _activities(client, athlete_id):
    return (await client.get(f"/athletes/{athlete_id}/activities")).json()


# --- connecting ----------------------------------------------------------------


async def test_a_refused_key_is_not_stored(client, intervals, db_session):
    athlete_id = await _rider(client)

    resp = await _connect(client, athlete_id, "wrong-key-xyz")

    assert resp.status_code == 400
    assert (await client.get(f"/athletes/{athlete_id}/intervals")).json()["connected"] is False
    async with db_session() as session:
        assert (await session.scalars(select(DataSourceConnection))).all() == []


async def test_connecting_stores_the_key_encrypted_and_imports_the_first_rides(client, intervals, db_session):
    athlete_id = await _rider(client)
    intervals.activities = [_remote("i1", "Track night")]
    intervals.files = {"i1": _fit()}

    resp = await _connect(client, athlete_id)

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] and body["active"]
    assert (body["intervals_athlete_id"], body["intervals_athlete_name"]) == ("i42", "Alex")
    assert "good-key-123" not in resp.text
    async with db_session() as session:
        raw = (await session.execute(text("SELECT credentials FROM data_source_connections"))).scalar_one()
        assert "good-key-123" not in raw  # encrypted at rest

    # The first sync ran after the response.
    (activity,) = await _activities(client, athlete_id)
    assert (activity["source"], activity["name"]) == ("intervals_icu", "Track night")
    status = (await client.get(f"/athletes/{athlete_id}/intervals")).json()
    assert status["last_synced_at"] is not None
    assert (status["runs"][0]["status"], status["runs"][0]["imported_count"]) == ("success", 1)


async def test_the_first_sync_reaches_back_the_backfill_window_and_later_ones_only_a_little(client, intervals):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    first_oldest, newest = intervals.listed[0]
    assert (newest - first_oldest).days == get_settings().intervals_backfill_days + 1

    await client.post(f"/athletes/{athlete_id}/intervals/sync")
    second_oldest, _ = intervals.listed[1]
    assert (newest - second_oldest).days <= 3


async def test_a_second_sync_does_not_download_again(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [_remote("i1")]
    intervals.files = {"i1": _fit()}
    await _connect(client, athlete_id)
    assert intervals.downloads == ["i1"]

    resp = await client.post(f"/athletes/{athlete_id}/intervals/sync")

    assert resp.status_code == 202
    assert intervals.downloads == ["i1"]
    assert len(await _activities(client, athlete_id)) == 1


# --- what gets imported ------------------------------------------------------------------


async def test_only_rides_and_gym_sessions_with_data_are_imported(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [
        _remote("ride", day=1),
        _remote("virtual", type="VirtualRide", day=2),
        _remote("run", type="Run", day=3),
        _remote("gym", type="WeightTraining", day=7),
        _remote("strava", source="STRAVA", note=True, day=4),
        _remote("noted", note=True, day=5),
        _remote("nofile", day=6),
    ]
    intervals.files = {"ride": _fit(1), "virtual": _fit(2), "run": _fit(3), "strava": _fit(4), "noted": _fit(5), "gym": _fit(7)}

    await _connect(client, athlete_id)

    assert sorted(a["start_time"][:10] for a in await _activities(client, athlete_id)) == [
        "2026-06-01",
        "2026-06-02",
        "2026-06-07",
    ]
    assert set(intervals.downloads) == {"ride", "virtual", "gym", "nofile"}  # no point asking for runs or Strava


def _gym(id: str, day: int, **fields):
    return RemoteActivity(
        id=id,
        name="Legs",
        type="WeightTraining",
        source="GARMIN_CONNECT",
        start_local=datetime(2026, 6, day, 7),
        has_note=False,
        start_utc=datetime(2026, 6, day, 5, tzinfo=timezone.utc),
        elapsed_s=3600.0,
        moving_s=3000.0,
        avg_heart_rate=110.0,
        max_heart_rate=150.0,
        rpe=7,
        description="Squats",
        **fields,
    )


async def test_a_gym_session_without_a_file_is_kept_from_its_summary(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [_gym("g1", 3)]  # no file to download

    await _connect(client, athlete_id)

    (gym,) = await _activities(client, athlete_id)
    assert (gym["name"], gym["sport"], gym["source"]) == ("Legs", "WeightTraining", "intervals_icu")
    assert (gym["elapsed_s"], gym["moving_s"], gym["rpe"], gym["notes"]) == (3600, 3000, 7, "Squats")
    assert (gym["avg_heart_rate"], gym["has_power"]) == (110, False)
    assert gym["start_time"].startswith("2026-06-03T05:00")
    # It has no samples, and counts towards the training load through its RPE.
    assert (await client.get(f"/athletes/{athlete_id}/activities/{gym['id']}/streams")).status_code == 404
    load = (await client.get(f"/athletes/{athlete_id}/training-load")).json()
    assert load["unrated_activities"] == 0 and any(day["tss"] > 0 for day in load["days"])


async def test_a_gym_file_with_no_samples_falls_back_to_the_summary(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [_gym("g1", 3)]
    intervals.files = {"g1": b"not an activity"}

    await _connect(client, athlete_id)

    assert len(await _activities(client, athlete_id)) == 1
    assert (await client.get(f"/athletes/{athlete_id}/intervals")).json()["runs"][0]["imported_count"] == 1


async def test_a_gym_summary_is_not_imported_twice_or_refetched(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [_gym("g1", 3)]
    await _connect(client, athlete_id)
    await client.post(f"/athletes/{athlete_id}/intervals/sync")

    assert len(await _activities(client, athlete_id)) == 1
    assert intervals.downloads == ["g1"]


async def test_a_gym_session_that_says_neither_when_nor_how_long_fails_alone(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [_remote("bare", type="WeightTraining", day=1), _remote("ride", day=2)]
    intervals.files = {"ride": _fit(2)}

    await _connect(client, athlete_id)

    assert [a["start_time"][:10] for a in await _activities(client, athlete_id)] == ["2026-06-02"]


async def test_an_unreadable_file_does_not_stop_the_others(client, intervals):
    athlete_id = await _rider(client)
    intervals.activities = [_remote("bad", day=1), _remote("good", day=2)]
    intervals.files = {"bad": b"not an activity", "good": _fit(2)}

    await _connect(client, athlete_id)

    assert [a["start_time"][:10] for a in await _activities(client, athlete_id)] == ["2026-06-02"]
    assert (await client.get(f"/athletes/{athlete_id}/intervals")).json()["runs"][0]["imported_count"] == 1


async def test_a_ride_already_uploaded_is_remembered_not_duplicated_or_refetched(client, intervals, db_session):
    athlete_id = await _rider(client)
    content = _fit()
    await client.post(f"/athletes/{athlete_id}/activities/upload", files=[("files", ("a.fit", content, "application/octet-stream"))])
    intervals.activities = [_remote("i1")]
    intervals.files = {"i1": content}

    await _connect(client, athlete_id)

    (activity,) = await _activities(client, athlete_id)
    assert activity["source"] == "upload"
    async with db_session() as session:
        row = await session.scalar(select(Activity))
        assert row.external_id == "i1" and row.data_source_connection_id is not None
    await client.post(f"/athletes/{athlete_id}/intervals/sync")
    assert intervals.downloads == ["i1"]


async def test_a_long_history_arrives_over_several_runs(client, intervals, monkeypatch):
    athlete_id = await _rider(client)
    monkeypatch.setattr(get_settings(), "intervals_max_downloads_per_run", 1)
    intervals.activities = [_remote("old", day=1), _remote("new", day=2)]
    intervals.files = {"old": _fit(1), "new": _fit(2)}

    await _connect(client, athlete_id)
    assert [a["start_time"][:10] for a in await _activities(client, athlete_id)] == ["2026-06-02"]  # newest first
    assert (await client.get(f"/athletes/{athlete_id}/intervals")).json()["last_synced_at"] is None

    await client.post(f"/athletes/{athlete_id}/intervals/sync")
    assert len(await _activities(client, athlete_id)) == 2
    assert (await client.get(f"/athletes/{athlete_id}/intervals")).json()["last_synced_at"] is not None


async def test_imported_rides_are_linked_and_scored_like_uploads(client, intervals):
    athlete_id = await _rider(client)
    await client.post(f"/athletes/{athlete_id}/metrics", json={"effective_date": "2026-05-01", "ftp_w": 200})
    intervals.activities = [_remote("i1")]
    intervals.files = {"i1": _fit(power=200)}

    await _connect(client, athlete_id)

    (activity,) = await _activities(client, athlete_id)
    assert activity["has_power"] and activity["avg_power_w"] == pytest.approx(200)
    assert activity["normalized_power_w"] == pytest.approx(200) and activity["tss"] > 0


# --- failures -----------------------------------------------------------------------------


async def test_a_key_that_stops_working_pauses_the_connection_until_reconnected(client, intervals, db_session):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    intervals.error = IntervalsAuthError("Intervals.icu refused the API key", 401)

    await client.post(f"/athletes/{athlete_id}/intervals/sync")

    status = (await client.get(f"/athletes/{athlete_id}/intervals")).json()
    assert status["connected"] and not status["active"]
    assert status["runs"][0]["status"] == "failed" and "refused" in status["runs"][0]["error_message"]
    assert (await client.post(f"/athletes/{athlete_id}/intervals/sync")).status_code == 409

    intervals.error = None
    assert (await _connect(client, athlete_id)).json()["active"]
    reconnected = (await client.get(f"/athletes/{athlete_id}/intervals")).json()  # after the first sync ran
    assert reconnected["active"] and reconnected["runs"][0]["status"] == "success"


async def test_rate_limits_and_outages_fail_the_run_but_keep_the_connection(client, intervals):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)

    for error in (IntervalsRateLimited(30), IntervalsClientError("Intervals.icu answered HTTP 500", 500)):
        intervals.error = error
        await client.post(f"/athletes/{athlete_id}/intervals/sync")
        status = (await client.get(f"/athletes/{athlete_id}/intervals")).json()
        assert status["active"] and status["runs"][0]["status"] == "failed"

    assert "retry in 30" in (await client.get(f"/athletes/{athlete_id}/intervals")).json()["runs"][1]["error_message"]


async def test_disconnecting_forgets_the_key_but_keeps_the_rides(client, intervals, db_session):
    athlete_id = await _rider(client)
    intervals.activities = [_remote("i1")]
    intervals.files = {"i1": _fit()}
    await _connect(client, athlete_id)

    status = (await client.delete(f"/athletes/{athlete_id}/intervals")).json()

    assert status["connected"] and not status["active"]
    async with db_session() as session:
        connection = await session.scalar(select(DataSourceConnection))
        assert connection.credentials is None and connection.status == DataSourceConnectionStatus.INACTIVE
    assert len(await _activities(client, athlete_id)) == 1
    assert (await client.post(f"/athletes/{athlete_id}/intervals/sync")).status_code == 409


# --- who may connect -------------------------------------------------------------------------


async def test_one_intervals_account_belongs_to_one_athlete(client, intervals):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)

    async with _other_client() as other:
        await _signup(other, "other@example.com")
        other_athlete = (await other.get("/athletes/me")).json()["id"]
        assert (await _connect(other, other_athlete)).status_code == 409

    intervals.athlete = RemoteAthlete("i99", "Someone else")
    assert (await _connect(client, athlete_id)).status_code == 409  # disconnect before switching accounts


@asynccontextmanager
async def _coach_of(db_session, athlete_id: str):
    async with _other_client() as coach_client:
        coach = await _signup(coach_client, "coach@example.com")
        async with db_session() as session:
            session.add(
                CoachAthlete(coach_user_id=uuid.UUID(coach["id"]), athlete_id=uuid.UUID(athlete_id), status=CoachAthleteStatus.ACTIVE)
            )
            await session.commit()
        yield coach_client


async def test_coaches_and_strangers_cannot_see_or_change_the_connection(client, intervals, db_session):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    url = f"/athletes/{athlete_id}/intervals"

    async with _coach_of(db_session, athlete_id) as coach:
        assert (await coach.get(url)).status_code == 403
        assert (await coach.put(url, json={"api_key": "good-key-123"})).status_code == 403
        assert (await coach.post(url + "/sync")).status_code == 403
        assert (await coach.delete(url)).status_code == 403
    async with _other_client() as anonymous:
        assert (await anonymous.get(url)).status_code == 401


async def test_deleting_the_account_removes_the_connection_its_rides_and_runs(client, intervals, db_session):
    athlete_id = await _rider(client)
    intervals.activities = [_remote("i1")]
    intervals.files = {"i1": _fit()}
    await _connect(client, athlete_id)

    assert (await client.post("/auth/delete-account", json={"password": "Correcthorse123!"})).status_code == 204

    async with db_session() as session:
        for model in (DataSourceConnection, Activity, IngestionRun):
            assert (await session.scalars(select(model))).all() == []


# --- the worker -------------------------------------------------------------------------------


async def test_the_worker_syncs_every_active_connection(client, intervals, db_session, monkeypatch):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    intervals.activities = [_remote("i9")]
    intervals.files = {"i9": _fit(9)}
    monkeypatch.setattr(jobs, "AsyncSessionLocal", db_session)
    monkeypatch.setattr(jobs, "build_intervals_sync_service", lambda db: build_intervals_sync_service(db, client=intervals))

    result = await jobs.poll_intervals_connections()

    assert (result.connections, result.failures) == (1, 0)
    assert [a["start_time"][:10] for a in await _activities(client, athlete_id)] == ["2026-06-09"]
    # A disconnected athlete is left alone.
    await client.delete(f"/athletes/{athlete_id}/intervals")
    assert (await jobs.poll_intervals_connections()).connections == 0
