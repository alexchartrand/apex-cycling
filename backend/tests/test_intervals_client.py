import gzip

import httpx
import pytest

from app.core.config import get_settings
from app.ingestion.intervals.client import (
    IntervalsAuthError,
    IntervalsClientError,
    IntervalsHttpClient,
    IntervalsRateLimited,
    gunzip_limited,
)
from datetime import date


def _client(handler) -> IntervalsHttpClient:
    return IntervalsHttpClient(base_url="https://intervals.test/api/v1", transport=httpx.MockTransport(handler))


async def test_get_athlete_uses_basic_auth_with_the_api_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"], seen["path"] = request.headers["authorization"], request.url.path
        return httpx.Response(200, json={"id": "i123", "name": "Alex"})

    athlete = await _client(handler).get_athlete("secret-key")

    assert (athlete.id, athlete.name) == ("i123", "Alex")
    assert seen["path"] == "/api/v1/athlete/0"
    import base64

    assert seen["auth"] == "Basic " + base64.b64encode(b"API_KEY:secret-key").decode()


async def test_list_activities_sends_the_date_range_and_parses_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/athlete/0/activities"
        assert dict(request.url.params) == {"oldest": "2026-06-01", "newest": "2026-06-10"}
        return httpx.Response(
            200,
            json=[
                {"id": "i1", "name": "Track", "type": "Ride", "source": "GARMIN_CONNECT", "start_date_local": "2026-06-05T18:00:00"},
                {"id": "i2", "type": "Ride", "source": "STRAVA", "_note": "STRAVA activities are not available via the API"},
                {"id": "i3", "type": "Run"},
                {"name": "no id"},
            ],
        )

    activities = await _client(handler).list_activities("k", date(2026, 6, 1), date(2026, 6, 10))

    assert [a.id for a in activities] == ["i1", "i2", "i3"]
    assert activities[0].is_ride and not activities[0].is_strava and activities[0].start_local.hour == 18
    assert activities[1].is_strava and activities[1].has_note
    assert not activities[2].is_ride


async def test_download_returns_plain_and_gzipped_files_alike():
    content = b".FIT-ish bytes " * 10
    for body in (content, gzip.compress(content)):
        client = _client(lambda request, body=body: httpx.Response(200, content=body))
        assert await client.download_file("k", "i1") == content


async def test_files_intervals_cannot_serve_are_none():
    for status in (404, 410, 422):
        assert await _client(lambda request, s=status: httpx.Response(s)).download_file("k", "i1") is None


async def test_refused_keys_and_rate_limits_are_distinct_errors():
    with pytest.raises(IntervalsAuthError):
        await _client(lambda request: httpx.Response(401)).get_athlete("bad")
    with pytest.raises(IntervalsRateLimited) as limited:
        await _client(lambda request: httpx.Response(429, headers={"Retry-After": "42"})).list_activities(
            "k", date(2026, 6, 1), date(2026, 6, 2)
        )
    assert limited.value.retry_after_s == 42
    with pytest.raises(IntervalsClientError, match="HTTP 500"):
        await _client(lambda request: httpx.Response(500)).get_athlete("k")


async def test_network_failures_become_client_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(IntervalsClientError, match="could not reach"):
        await _client(handler).get_athlete("k")


async def test_oversized_downloads_are_refused(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_activity_file_bytes", 1000)
    with pytest.raises(IntervalsClientError, match="too large"):
        await _client(lambda request: httpx.Response(200, content=b"x" * 5000)).download_file("k", "i1")
    # A small gzip that inflates beyond the limit must not be expanded.
    bomb = gzip.compress(b"\0" * 1_000_000)
    assert len(bomb) < 2000
    with pytest.raises(IntervalsClientError, match="too large"):
        await _client(lambda request: httpx.Response(200, content=bomb)).download_file("k", "i1")


def test_gunzip_limited_rejects_garbage():
    with pytest.raises(IntervalsClientError, match="corrupt"):
        gunzip_limited(b"\x1f\x8b" + b"garbage", 1000)
