import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

import app.ingestion.jobs as jobs
from app.activities.models import Activity, ActivitySource
from app.athletes.models import CoachAthlete, CoachAthleteStatus
from app.connections.intervals_router import get_session_factory
from app.connections.models import DataSourceConnection, DataSourceConnectionStatus
from app.connections.strava_router import get_strava_client
from app.core.config import get_settings
from app.ingestion.strava.client import StravaAuthError, StravaClientError, StravaRateLimited
from app.ingestion.strava.dtos import AuthorizedAthlete, RemoteStravaActivity, StravaAthleteInfo, StravaTokens
from app.ingestion.strava.factory import build_strava_sync_service
from app.main import app as real_app
from tests.fit_builder import build_fit
from tests.test_account import _signup

START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)
FAR_FUTURE = int(time.time()) + 6 * 3600


def _ride(id: str, day: int = 1, *, device_watts: bool = True, name: str = "Track night", elapsed: int = 120):
    return RemoteStravaActivity(
        id=id, name=name, sport_type="Ride", start=START.replace(day=day), elapsed_s=elapsed, moving_s=elapsed,
        device_watts=device_watts, manual=False,
    )  # fmt: skip


def _streams(seconds: int = 120, watts: int = 220) -> dict:
    return {
        "time": list(range(seconds)),
        "watts": [watts] * seconds,
        "heartrate": [140] * seconds,
        "velocity_smooth": [10.0] * seconds,
        "distance": [10.0 * t for t in range(seconds)],
    }


class FakeStrava:
    def __init__(self) -> None:
        self.athlete = AuthorizedAthlete(
            StravaAthleteInfo("777", "Alex R"), StravaTokens("access-1", "refresh-1", FAR_FUTURE)
        )
        self.activities: list[RemoteStravaActivity] = []
        self.streams: dict[str, dict | None] = {}
        self.streams_requested: list[str] = []
        self.refreshes: list[str] = []
        self.deauthorized: list[str] = []
        self.existing: set[str] = set()
        self.error: Exception | None = None
        self.refresh_error: Exception | None = None
        self.codes: list[str] = []

    async def exchange_code(self, code):
        self.codes.append(code)
        if code == "bad":
            raise StravaClientError("nope", 400)
        return self.athlete

    async def deauthorize(self, access_token):
        self.deauthorized.append(access_token)

    async def refresh_tokens(self, refresh_token):
        self.refreshes.append(refresh_token)
        if self.refresh_error:
            raise self.refresh_error
        return StravaTokens(f"access-{len(self.refreshes) + 1}", f"refresh-{len(self.refreshes) + 1}", FAR_FUTURE)

    async def list_activities(self, access_token, after, before, page):
        if self.error:
            raise self.error
        return list(self.activities) if page == 1 else []

    async def get_streams(self, access_token, activity_id):
        self.streams_requested.append(activity_id)
        return self.streams.get(activity_id)

    async def activity_exists(self, access_token, activity_id):
        return activity_id in self.existing


@pytest.fixture
def strava(db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "strava_client_id", "4242")
    monkeypatch.setattr(settings, "strava_client_secret", "app-secret")
    monkeypatch.setattr(settings, "app_base_url", "https://apex.test")
    fake = FakeStrava()
    real_app.dependency_overrides[get_strava_client] = lambda: fake
    real_app.dependency_overrides[get_session_factory] = lambda: db_session
    return fake


@pytest.fixture(autouse=True)
def uploads_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


def _other_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=real_app), base_url="http://test/api")


async def _rider(client) -> str:
    await _signup(client, "rider@example.com")
    return (await client.get("/athletes/me")).json()["id"]


async def _authorize(client, athlete_id) -> str:
    url = (await client.get(f"/athletes/{athlete_id}/strava/authorize-url")).json()["url"]
    return parse_qs(urlparse(url).query)["state"][0]


async def _connect(client, athlete_id, *, code="good", scope="read,activity:read_all"):
    state = await _authorize(client, athlete_id)
    return await client.get("/strava/callback", params={"code": code, "state": state, "scope": scope})


async def _activities(client, athlete_id):
    return (await client.get(f"/athletes/{athlete_id}/activities")).json()


async def _status(client, athlete_id):
    return (await client.get(f"/athletes/{athlete_id}/strava")).json()


async def _connection(db_session) -> DataSourceConnection:
    async with db_session() as session:
        return await session.scalar(select(DataSourceConnection))


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


# --- the server's Strava application ----------------------------------------------------


async def test_without_a_strava_application_the_feature_is_off(client, monkeypatch):
    athlete_id = await _rider(client)
    monkeypatch.setattr(get_settings(), "strava_client_id", None)

    status = await _status(client, athlete_id)
    assert status["available"] is False and status["connected"] is False
    assert (await client.get(f"/athletes/{athlete_id}/strava/authorize-url")).status_code == 503
    assert (await client.get("/strava/callback", params={"code": "x", "state": "y"})).headers["location"].endswith("strava=error")


# --- OAuth ---------------------------------------------------------------------------------


async def test_authorize_url_sends_the_athlete_to_strava_with_a_signed_state(client, strava):
    athlete_id = await _rider(client)

    url = urlparse((await client.get(f"/athletes/{athlete_id}/strava/authorize-url")).json()["url"])

    query = parse_qs(url.query)
    assert url.netloc == "www.strava.com" and url.path == "/oauth/authorize"
    assert query["client_id"] == ["4242"] and query["scope"] == ["activity:read_all"]
    assert query["redirect_uri"] == ["https://apex.test/api/strava/callback"]
    assert query["state"][0].count(".") == 2  # a signed token, not a guessable id


async def test_the_callback_stores_encrypted_tokens_and_imports_the_first_rides(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1")]
    strava.streams = {"a1": _streams()}

    resp = await _connect(client, athlete_id)

    assert resp.status_code == 303 and resp.headers["location"] == "https://apex.test/import?strava=connected"
    assert strava.codes == ["good"]
    async with db_session() as session:
        raw = (await session.execute(text("SELECT credentials FROM data_source_connections"))).scalar_one()
        assert "refresh-1" not in raw and "access-1" not in raw
    status = await _status(client, athlete_id)
    assert status["connected"] and status["active"] and status["strava_athlete_name"] == "Alex R"
    assert (status["runs"][0]["status"], status["runs"][0]["imported_count"]) == ("success", 1)

    (activity,) = await _activities(client, athlete_id)
    assert activity["source"] == "strava" and activity["file_format"] is None
    assert activity["external_url"] == "https://www.strava.com/activities/a1"
    assert activity["has_power"] and activity["avg_power_w"] == pytest.approx(220)
    assert "refresh-1" not in str(status)


async def test_a_denied_or_broken_authorization_connects_nothing(client, strava):
    athlete_id = await _rider(client)

    cases = [
        await _connect(client, athlete_id, scope="read"),  # activity access unticked
        await client.get("/strava/callback", params={"error": "access_denied", "state": await _authorize(client, athlete_id)}),
        await _connect(client, athlete_id, code="bad"),
        await client.get("/strava/callback", params={"code": "good", "state": "forged.state.value", "scope": "activity:read_all"}),
    ]

    assert [r.headers["location"].split("strava=")[1] for r in cases] == ["denied", "denied", "error", "error"]
    assert (await _status(client, athlete_id))["connected"] is False


async def test_a_strava_account_belongs_to_one_athlete(client, strava):
    athlete_id = await _rider(client)
    assert (await _connect(client, athlete_id)).headers["location"].endswith("connected")

    async with _other_client() as other:
        await _signup(other, "other@example.com")
        other_athlete = (await other.get("/athletes/me")).json()["id"]
        assert (await _connect(other, other_athlete)).headers["location"].endswith("error")


async def test_only_the_athlete_manages_the_connection(client, strava, db_session):
    athlete_id = await _rider(client)
    async with _coach_of(db_session, athlete_id) as coach:
        for response in (
            await coach.get(f"/athletes/{athlete_id}/strava"),
            await coach.get(f"/athletes/{athlete_id}/strava/authorize-url"),
            await coach.post(f"/athletes/{athlete_id}/strava/sync"),
            await coach.delete(f"/athletes/{athlete_id}/strava"),
        ):
            assert response.status_code == 403


# --- syncing -----------------------------------------------------------------------------------


async def test_repeat_syncs_do_not_refetch_and_runs_are_recorded(client, strava):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1")]
    strava.streams = {"a1": _streams()}
    await _connect(client, athlete_id)

    assert (await client.post(f"/athletes/{athlete_id}/strava/sync")).status_code == 202

    assert strava.streams_requested == ["a1"]
    assert len(await _activities(client, athlete_id)) == 1
    assert len((await _status(client, athlete_id))["runs"]) == 2


async def test_only_real_rides_are_fetched(client, strava):
    athlete_id = await _rider(client)
    run = RemoteStravaActivity("run", "Run", "Run", START, 100, 100, False, False)
    manual = RemoteStravaActivity("manual", "Manual", "Ride", START.replace(day=2), 100, 100, False, True)
    strava.activities = [run, manual, _ride("ride", 3)]
    strava.streams = {"ride": _streams()}

    await _connect(client, athlete_id)

    assert strava.streams_requested == ["ride"]


async def test_power_without_a_meter_is_not_imported(client, strava):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1", device_watts=False)]
    strava.streams = {"a1": _streams()}

    await _connect(client, athlete_id)

    (activity,) = await _activities(client, athlete_id)
    assert activity["has_power"] is False and activity["avg_power_w"] is None and activity["has_heart_rate"]


async def test_a_ride_the_athlete_already_has_is_not_fetched_from_strava(client, strava):
    athlete_id = await _rider(client)
    fit = build_fit(START, [{"t": t, "power": 200, "speed": 10.0} for t in range(121)])
    await client.post(f"/athletes/{athlete_id}/activities/upload", files=[("files", ("a.fit", fit, "application/octet-stream"))])
    strava.activities = [_ride("a1", elapsed=120)]
    strava.streams = {"a1": _streams()}

    await _connect(client, athlete_id)

    assert strava.streams_requested == []  # no API calls spent on it
    assert [a["source"] for a in await _activities(client, athlete_id)] == ["upload"]


async def test_a_later_upload_replaces_the_strava_copy_and_keeps_the_athletes_notes(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1", elapsed=120)]
    strava.streams = {"a1": _streams()}
    await _connect(client, athlete_id)
    (strava_copy,) = await _activities(client, athlete_id)
    await client.patch(f"/athletes/{athlete_id}/activities/{strava_copy['id']}", json={"rpe": 6, "notes": "felt good"})

    fit = build_fit(START, [{"t": t, "power": 200, "speed": 10.0} for t in range(121)])
    resp = await client.post(f"/athletes/{athlete_id}/activities/upload", files=[("files", ("a.fit", fit, "application/octet-stream"))])

    assert resp.json()[0]["status"] == "created"
    (activity,) = await _activities(client, athlete_id)
    assert activity["source"] == "upload" and activity["rpe"] == 6 and activity["notes"] == "felt good"
    assert activity["name"] == "Track night"
    # ... and syncing Strava again doesn't bring the copy back.
    await client.post(f"/athletes/{athlete_id}/strava/sync")
    assert [a["source"] for a in await _activities(client, athlete_id)] == ["upload"]
    assert strava.streams_requested == ["a1"]


async def test_strava_rides_are_for_their_owner_only(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1")]
    strava.streams = {"a1": _streams()}
    await _connect(client, athlete_id)
    activity_id = (await _activities(client, athlete_id))[0]["id"]

    async with _coach_of(db_session, athlete_id) as coach:
        assert await _activities(coach, athlete_id) == []
        assert (await coach.get(f"/athletes/{athlete_id}/activities/{activity_id}")).status_code == 404
        assert (await coach.get(f"/athletes/{athlete_id}/power-curve")).json() == []


async def test_a_long_history_arrives_over_several_runs(client, strava, monkeypatch):
    athlete_id = await _rider(client)
    monkeypatch.setattr(get_settings(), "strava_max_downloads_per_run", 1)
    strava.activities = [_ride("old", 1), _ride("new", 2)]
    strava.streams = {"old": _streams(), "new": _streams()}

    await _connect(client, athlete_id)
    assert [a["external_url"][-3:] for a in await _activities(client, athlete_id)] == ["new"]
    assert (await _status(client, athlete_id))["last_synced_at"] is None

    await client.post(f"/athletes/{athlete_id}/strava/sync")
    assert len(await _activities(client, athlete_id)) == 2
    assert (await _status(client, athlete_id))["last_synced_at"] is not None


# --- tokens ---------------------------------------------------------------------------------------


async def test_expired_tokens_are_refreshed_and_the_rotated_ones_saved(client, strava, db_session):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    async with db_session() as session:
        connection = await session.scalar(select(DataSourceConnection))
        connection.credentials = {**connection.credentials, "expires_at": int(time.time()) - 10}
        await session.commit()

    await client.post(f"/athletes/{athlete_id}/strava/sync")

    assert strava.refreshes == ["refresh-1"]
    credentials = (await _connection(db_session)).credentials
    assert (credentials["access_token"], credentials["refresh_token"]) == ("access-2", "refresh-2")
    assert credentials["athlete_name"] == "Alex R"  # untouched


async def test_revoking_access_on_strava_ends_the_connection_and_deletes_its_data(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1")]
    strava.streams = {"a1": _streams()}
    await _connect(client, athlete_id)
    assert len(await _activities(client, athlete_id)) == 1
    async with db_session() as session:
        connection = await session.scalar(select(DataSourceConnection))
        connection.credentials = {**connection.credentials, "expires_at": 0}
        await session.commit()
    strava.refresh_error = StravaAuthError("Strava no longer accepts this connection", 400)

    await client.post(f"/athletes/{athlete_id}/strava/sync")

    status = await _status(client, athlete_id)
    assert status["connected"] and not status["active"] and status["runs"][0]["status"] == "failed"
    assert await _activities(client, athlete_id) == []
    assert (await _connection(db_session)).credentials is None


async def test_rate_limits_and_outages_fail_the_run_but_keep_the_connection(client, strava):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)

    for error in (StravaRateLimited(), StravaClientError("Strava answered HTTP 500", 500)):
        strava.error = error
        await client.post(f"/athletes/{athlete_id}/strava/sync")
        status = await _status(client, athlete_id)
        assert status["active"] and status["runs"][0]["status"] == "failed"


async def test_disconnecting_tells_strava_and_deletes_the_strava_data(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1", 1), _ride("a2", 2)]
    strava.streams = {"a1": _streams(), "a2": _streams()}
    await _connect(client, athlete_id)
    fit = build_fit(START.replace(day=9), [{"t": t, "power": 200, "speed": 10.0} for t in range(60)])
    await client.post(f"/athletes/{athlete_id}/activities/upload", files=[("files", ("a.fit", fit, "application/octet-stream"))])

    status = (await client.delete(f"/athletes/{athlete_id}/strava")).json()

    assert strava.deauthorized == ["access-1"]
    assert status["connected"] and not status["active"]
    assert [a["source"] for a in await _activities(client, athlete_id)] == ["upload"]  # the athlete's own file stays
    assert (await _connection(db_session)).credentials is None


async def test_the_worker_syncs_strava_connections_and_stops_at_a_rate_limit(client, strava, db_session, monkeypatch):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    strava.activities = [_ride("w1", 5)]
    strava.streams = {"w1": _streams()}
    monkeypatch.setattr(jobs, "AsyncSessionLocal", db_session)
    monkeypatch.setattr(jobs, "build_strava_sync_service", lambda db: build_strava_sync_service(db, client=strava))

    result = await jobs.poll_strava_connections()
    assert (result.connections, result.failures) == (1, 0)
    assert len(await _activities(client, athlete_id)) == 1

    strava.error = StravaRateLimited()
    result = await jobs.poll_strava_connections()
    assert result.failures == 1 and "rate limiting" in result.last_error


# --- webhook ------------------------------------------------------------------------------------


async def test_the_webhook_subscription_handshake(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "strava_webhook_verify_token", "secret-token")
    good = {"hub.mode": "subscribe", "hub.verify_token": "secret-token", "hub.challenge": "abc123"}

    resp = await client.get("/strava/webhook", params=good)
    assert resp.status_code == 200 and resp.json() == {"hub.challenge": "abc123"}
    assert (await client.get("/strava/webhook", params={**good, "hub.verify_token": "wrong"})).status_code == 403
    monkeypatch.setattr(get_settings(), "strava_webhook_verify_token", None)
    assert (await client.get("/strava/webhook", params=good)).status_code == 403


def _event(**fields) -> dict:
    return {"object_type": "activity", "object_id": 1, "aspect_type": "create", "owner_id": 777, "subscription_id": 5, **fields}


async def test_a_new_activity_event_triggers_a_sync(client, strava, monkeypatch):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    strava.activities = [_ride("pushed", 7)]
    strava.streams = {"pushed": _streams()}

    resp = await client.post("/strava/webhook", json=_event())

    assert resp.status_code == 200
    assert [a["start_time"][:10] for a in await _activities(client, athlete_id)] == ["2026-06-07"]


async def test_events_from_unknown_athletes_or_subscriptions_do_nothing(client, strava, monkeypatch):
    athlete_id = await _rider(client)
    await _connect(client, athlete_id)
    strava.activities = [_ride("x", 8)]
    strava.streams = {"x": _streams()}

    assert (await client.post("/strava/webhook", json=_event(owner_id=1))).status_code == 200
    assert await _activities(client, athlete_id) == []
    monkeypatch.setattr(get_settings(), "strava_webhook_subscription_id", 5)
    assert (await client.post("/strava/webhook", json=_event(subscription_id=6))).status_code == 403
    assert (await client.post("/strava/webhook", json={"nonsense": True})).status_code == 422


async def test_a_delete_event_removes_the_activity_only_if_strava_agrees(client, strava):
    athlete_id = await _rider(client)
    strava.activities = [_ride("101")]
    strava.streams = {"101": _streams()}
    await _connect(client, athlete_id)

    strava.existing = {"101"}  # still there on Strava: a forged event changes nothing
    await client.post("/strava/webhook", json=_event(aspect_type="delete", object_id=101))
    assert len(await _activities(client, athlete_id)) == 1

    strava.existing = set()
    await client.post("/strava/webhook", json=_event(aspect_type="delete", object_id=101))
    assert await _activities(client, athlete_id) == []


async def test_a_deauthorization_event_purges_only_when_the_tokens_really_stopped_working(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1")]
    strava.streams = {"a1": _streams()}
    await _connect(client, athlete_id)
    event = _event(object_type="athlete", aspect_type="update", updates={"authorized": "false"})

    await client.post("/strava/webhook", json=event)  # Strava still accepts the refresh: forged or stale
    assert len(await _activities(client, athlete_id)) == 1 and (await _status(client, athlete_id))["active"]

    strava.refresh_error = StravaAuthError("revoked", 400)
    await client.post("/strava/webhook", json=event)
    assert await _activities(client, athlete_id) == []
    assert not (await _status(client, athlete_id))["active"]
    assert (await _connection(db_session)).status == DataSourceConnectionStatus.INACTIVE


# --- account deletion -------------------------------------------------------------------------------


async def test_deleting_the_account_removes_the_strava_connection_and_data(client, strava, db_session):
    athlete_id = await _rider(client)
    strava.activities = [_ride("a1")]
    strava.streams = {"a1": _streams()}
    await _connect(client, athlete_id)

    assert (await client.post("/auth/delete-account", json={"password": "Correcthorse123!"})).status_code == 204

    async with db_session() as session:
        assert (await session.scalars(select(DataSourceConnection))).all() == []
        assert (await session.scalars(select(Activity).where(Activity.source == ActivitySource.STRAVA))).all() == []
