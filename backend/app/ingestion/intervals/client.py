"""HTTP client for the Intervals.icu API (https://intervals.icu/api/v1).

Authenticates with the athlete's own API key (HTTP basic, user name
"API_KEY"). The API never serves Strava-sourced activities (Strava's terms
forbid forwarding them), so those come back without a file.
"""

import zlib
from datetime import date, datetime, timezone

import httpx

from app.core.config import get_settings
from app.ingestion.intervals.dtos import RemoteActivity, RemoteAthlete

_TIMEOUT = httpx.Timeout(30.0)


class IntervalsClientError(Exception):
    def __init__(self, message: str, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class IntervalsAuthError(IntervalsClientError):
    """The API key was refused (wrong, revoked or without activity access)."""


class IntervalsRateLimited(IntervalsClientError):
    def __init__(self, retry_after_s: int | None) -> None:
        super().__init__("Intervals.icu is rate limiting requests", 429)
        self.retry_after_s = retry_after_s


def gunzip_limited(data: bytes, limit: int) -> bytes:
    """Decompresses gzip data, refusing to produce more than `limit` bytes."""
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = decompressor.decompress(data, limit + 1)
    except zlib.error as exc:
        raise IntervalsClientError(f"corrupt gzip data: {exc}") from exc
    if len(out) > limit:
        raise IntervalsClientError("file too large")
    return out


def _parse_local(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_utc(value: object) -> datetime | None:
    moment = _parse_local(value) if value else None
    if moment is None:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _number(value: object, *, positive: bool = True) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if not positive or value > 0 else None


def _rpe(value: object) -> int | None:
    number = _number(value)
    return None if number is None else min(10, max(1, round(number)))


class IntervalsHttpClient:
    def __init__(self, *, base_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base_url = (base_url or get_settings().intervals_base_url).rstrip("/")
        self._transport = transport

    def _client(self, api_key: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, auth=("API_KEY", api_key), timeout=_TIMEOUT, transport=self._transport
        )

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise IntervalsAuthError("Intervals.icu refused the API key", response.status_code)
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "")
            raise IntervalsRateLimited(int(retry) if retry.isdigit() else None)
        if response.status_code >= 400:
            raise IntervalsClientError(f"Intervals.icu answered HTTP {response.status_code}", response.status_code)

    async def get_athlete(self, api_key: str) -> RemoteAthlete:
        async with self._client(api_key) as client:
            response = await _send(client, "/athlete/0")
        self._check(response)
        body = response.json()
        body = body.get("athlete", body) if isinstance(body, dict) else {}
        if not body.get("id"):
            raise IntervalsClientError("Intervals.icu did not say whose key this is")
        return RemoteAthlete(id=str(body["id"]), name=body.get("name"))

    async def list_activities(self, api_key: str, oldest: date, newest: date) -> list[RemoteActivity]:
        async with self._client(api_key) as client:
            response = await _send(client, "/athlete/0/activities", params={"oldest": oldest.isoformat(), "newest": newest.isoformat()})
        self._check(response)
        body = response.json()
        if not isinstance(body, list):
            raise IntervalsClientError("unexpected activity list from Intervals.icu")
        activities = []
        for item in body:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            activities.append(
                RemoteActivity(
                    id=str(item["id"]),
                    name=item.get("name"),
                    type=item.get("type"),
                    source=item.get("source"),
                    start_local=_parse_local(item.get("start_date_local")),
                    has_note=bool(item.get("_note")),
                    start_utc=_parse_utc(item.get("start_date")),
                    elapsed_s=_number(item.get("elapsed_time")),
                    moving_s=_number(item.get("moving_time")),
                    distance_m=_number(item.get("distance")),
                    avg_heart_rate=_number(item.get("average_heartrate")),
                    max_heart_rate=_number(item.get("max_heartrate")),
                    rpe=_rpe(item.get("icu_rpe")),
                    description=(item.get("description") or None),
                )
            )
        return activities

    async def download_file(self, api_key: str, activity_id: str) -> bytes | None:
        """The activity's original file (FIT/TCX/GPX), or None when
        Intervals.icu has none to give (Strava-sourced, manual entries)."""
        limit = get_settings().max_activity_file_bytes
        async with self._client(api_key) as client:
            try:
                async with client.stream("GET", f"/activity/{activity_id}/file") as response:
                    if response.status_code in (404, 410, 422):
                        return None
                    self._check(response)
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > limit:
                            raise IntervalsClientError("file too large")
            except httpx.HTTPError as exc:
                raise IntervalsClientError(f"could not reach Intervals.icu: {type(exc).__name__}") from exc
        data = bytes(content)
        return gunzip_limited(data, limit) if data[:2] == b"\x1f\x8b" else data


async def _send(client: httpx.AsyncClient, path: str, **kwargs) -> httpx.Response:
    try:
        return await client.get(path, **kwargs)
    except httpx.HTTPError as exc:
        raise IntervalsClientError(f"could not reach Intervals.icu: {type(exc).__name__}") from exc
