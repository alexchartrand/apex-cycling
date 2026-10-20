from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.activities.parsers import ActivityParseError
from app.core.config import get_settings
from app.ingestion.strava.client import (
    StravaAuthError,
    StravaClientError,
    StravaHttpClient,
    StravaRateLimited,
    authorize_url,
)
from app.ingestion.strava.dtos import RemoteStravaActivity
from app.ingestion.strava.mapping import to_parsed_activity

START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def strava_app(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "strava_client_id", "4242")
    monkeypatch.setattr(settings, "strava_client_secret", "app-secret")


def _client(handler) -> StravaHttpClient:
    return StravaHttpClient(base_url="https://strava.test", transport=httpx.MockTransport(handler))


def _ride(device_watts: bool = True) -> RemoteStravaActivity:
    return RemoteStravaActivity(
        id="99", name="Track night", sport_type="Ride", start=START, elapsed_s=5, moving_s=5,
        device_watts=device_watts, manual=False,
    )  # fmt: skip


# --- mapping ---------------------------------------------------------------------


def test_streams_become_a_parsed_activity():
    streams = {
        "time": [0, 1, 2, 3, 4],
        "watts": [100, 200, 300, 400, 500],
        "heartrate": [120, 125, 130, 135, 140],
        "cadence": [80, 85, 90, 95, 100],
        "velocity_smooth": [5.0, 6.0, 7.0, 8.0, 9.0],
        "distance": [0, 5, 11, 18, 26],
        "altitude": [100, 100, 101, 101, 102],
    }

    parsed = to_parsed_activity(_ride(), streams)

    assert parsed.start_time == START and parsed.time_s == [0, 1, 2, 3, 4]
    assert parsed.channels["power_w"] == [100, 200, 300, 400, 500]
    assert parsed.channels["heart_rate"] == [120, 125, 130, 135, 140]
    assert parsed.channels["speed_mps"] == [5, 6, 7, 8, 9]
    assert (parsed.sport, parsed.name, parsed.timer_s) == ("Ride", "Track night", 5)


def test_strava_estimated_power_is_not_a_measurement():
    parsed = to_parsed_activity(_ride(device_watts=False), {"time": [0, 1, 2], "watts": [150, 150, 150]})
    assert "power_w" not in parsed.channels


def test_streams_without_time_are_rejected():
    with pytest.raises(ActivityParseError):
        to_parsed_activity(_ride(), {"watts": [1, 2, 3]})
    with pytest.raises(ActivityParseError, match="fewer than two"):
        to_parsed_activity(_ride(), {"time": [0]})


def test_a_short_side_stream_is_ignored_not_misaligned():
    parsed = to_parsed_activity(_ride(), {"time": [0, 1, 2, 3], "heartrate": [100, 110]})
    assert "heart_rate" not in parsed.channels


# --- client ----------------------------------------------------------------------


def test_authorize_url_carries_app_redirect_scope_and_state():
    url = urlparse(authorize_url("https://apex.test/api/strava/callback", "STATE"))
    query = parse_qs(url.query)
    assert url.path == "/oauth/authorize"
    assert query["client_id"] == ["4242"] and query["state"] == ["STATE"]
    assert query["redirect_uri"] == ["https://apex.test/api/strava/callback"]
    assert query["scope"] == ["activity:read_all"] and query["response_type"] == ["code"]


async def test_exchange_code():
    def handler(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        assert form["grant_type"] == ["authorization_code"] and form["code"] == ["the-code"]
        assert form["client_id"] == ["4242"] and form["client_secret"] == ["app-secret"]
        return httpx.Response(
            200,
            json={"access_token": "a", "refresh_token": "r", "expires_at": 1_900_000_000,
                  "athlete": {"id": 777, "firstname": "Alex", "lastname": "R"}},
        )  # fmt: skip

    authorized = await _client(handler).exchange_code("the-code")

    assert (authorized.athlete.id, authorized.athlete.name) == ("777", "Alex R")
    assert (authorized.tokens.access_token, authorized.tokens.refresh_token, authorized.tokens.expires_at) == ("a", "r", 1_900_000_000)


async def test_a_revoked_grant_is_an_auth_error():
    with pytest.raises(StravaAuthError):
        await _client(lambda request: httpx.Response(400, json={"message": "Bad Request"})).refresh_tokens("old")
    with pytest.raises(StravaAuthError):
        await _client(lambda request: httpx.Response(401)).list_activities("t", START, START, 1)


async def test_refresh_rotates_the_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        assert parse_qs(request.content.decode())["refresh_token"] == ["old"]
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2", "expires_at": 1_900_000_100})

    tokens = await _client(handler).refresh_tokens("old")
    assert (tokens.access_token, tokens.refresh_token) == ("a2", "r2")


async def test_list_activities_parses_rides_and_survives_junk():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        assert request.url.path == "/api/v3/athlete/activities"
        assert request.url.params["after"] == str(int(START.timestamp()))
        return httpx.Response(
            200,
            json=[
                {"id": 1, "name": "Ride", "sport_type": "VirtualRide", "start_date": "2026-06-01T07:00:00Z",
                 "elapsed_time": 100, "moving_time": 90, "device_watts": True},
                {"id": 2, "type": "Run", "start_date": "2026-06-02T07:00:00Z", "elapsed_time": 50, "manual": True},
                {"broken": True},
            ],
        )  # fmt: skip

    activities = await _client(handler).list_activities("tok", START, START + timedelta(days=1), 1)

    assert [a.id for a in activities] == ["1", "2"]
    assert activities[0].is_ride and activities[0].device_watts and activities[0].start == START
    assert not activities[1].is_ride and activities[1].manual


async def test_streams_are_keyed_by_type_and_missing_ones_are_none():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gone/streams"):
            return httpx.Response(404)
        assert request.url.params["key_by_type"] == "true" and "watts" in request.url.params["keys"]
        return httpx.Response(200, json={"time": {"data": [0, 1], "series_type": "time"}, "watts": {"data": [10, 20]}})

    client = _client(handler)
    assert await client.get_streams("t", "5") == {"time": [0, 1], "watts": [10, 20]}
    assert await client.get_streams("t", "gone") is None


async def test_rate_limit_and_outage_are_distinct():
    with pytest.raises(StravaRateLimited):
        await _client(lambda request: httpx.Response(429)).get_streams("t", "5")
    with pytest.raises(StravaClientError, match="HTTP 500"):
        await _client(lambda request: httpx.Response(500)).get_streams("t", "5")

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(StravaClientError, match="could not reach"):
        await _client(down).get_streams("t", "5")


async def test_activity_exists_and_deauthorize():
    client = _client(lambda request: httpx.Response(404 if request.url.path.endswith("/1") else 200, json={}))
    assert await client.activity_exists("t", "2") is True
    assert await client.activity_exists("t", "1") is False
    await _client(lambda request: httpx.Response(500)).deauthorize("t")  # best effort: never raises
