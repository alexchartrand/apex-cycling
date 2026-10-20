"""HTTP client for the Strava API (v3) and its OAuth endpoints."""

from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.ingestion.strava.dtos import (
    AuthorizedAthlete,
    RemoteStravaActivity,
    StravaAthleteInfo,
    StravaTokens,
)
from app.ingestion.strava.mapping import STREAM_KEYS

_TIMEOUT = httpx.Timeout(30.0)
SCOPE = "activity:read_all"


class StravaClientError(Exception):
    def __init__(self, message: str, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class StravaAuthError(StravaClientError):
    """Strava refused the token or grant: revoked, expired beyond refresh, or
    missing the activity scope."""


class StravaRateLimited(StravaClientError):
    def __init__(self) -> None:
        super().__init__("Strava is rate limiting this application", 429)


def authorize_url(redirect_uri: str, state: str) -> str:
    settings = get_settings()
    query = urlencode(
        {
            "client_id": settings.strava_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": SCOPE,
            "state": state,
        }
    )
    return f"{settings.strava_base_url}/oauth/authorize?{query}"


def _tokens(body: dict) -> StravaTokens:
    try:
        return StravaTokens(
            access_token=body["access_token"], refresh_token=body["refresh_token"], expires_at=int(body["expires_at"])
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StravaClientError("unexpected token response from Strava") from exc


class StravaHttpClient:
    def __init__(self, *, base_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._base = (base_url or get_settings().strava_base_url).rstrip("/")
        self._transport = transport

    async def _request(
        self, method: str, path: str, *, access_token: str | None = None, **kwargs
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                response = await client.request(method, f"{self._base}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise StravaClientError(f"could not reach Strava: {type(exc).__name__}") from exc
        if response.status_code == 429:
            raise StravaRateLimited()
        if response.status_code in (401, 403):
            raise StravaAuthError("Strava refused the access", response.status_code)
        return response

    @staticmethod
    def _ok(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise StravaClientError(f"Strava answered HTTP {response.status_code}", response.status_code)

    async def exchange_code(self, code: str) -> AuthorizedAthlete:
        settings = get_settings()
        response = await self._request(
            "POST",
            "/oauth/token",
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        self._ok(response)
        body = response.json()
        athlete = body.get("athlete") or {}
        if not athlete.get("id"):
            raise StravaClientError("Strava did not say who authorized the application")
        name = " ".join(part for part in (athlete.get("firstname"), athlete.get("lastname")) if part) or None
        return AuthorizedAthlete(StravaAthleteInfo(str(athlete["id"]), name), _tokens(body))

    async def refresh_tokens(self, refresh_token: str) -> StravaTokens:
        settings = get_settings()
        response = await self._request(
            "POST",
            "/oauth/token",
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        if response.status_code == 400:  # invalid_grant: the athlete revoked access
            raise StravaAuthError("Strava no longer accepts this connection", response.status_code)
        self._ok(response)
        return _tokens(response.json())

    async def list_activities(
        self, access_token: str, after: datetime, before: datetime, page: int
    ) -> list[RemoteStravaActivity]:
        response = await self._request(
            "GET",
            "/api/v3/athlete/activities",
            access_token=access_token,
            params={"after": int(after.timestamp()), "before": int(before.timestamp()), "page": page, "per_page": 100},
        )
        self._ok(response)
        body = response.json()
        if not isinstance(body, list):
            raise StravaClientError("unexpected activity list from Strava")
        activities = []
        for item in body:
            try:
                start = datetime.fromisoformat(item["start_date"].replace("Z", "+00:00")).astimezone(timezone.utc)
                activities.append(
                    RemoteStravaActivity(
                        id=str(item["id"]),
                        name=item.get("name"),
                        sport_type=item.get("sport_type") or item.get("type"),
                        start=start,
                        elapsed_s=float(item["elapsed_time"]),
                        moving_s=float(item["moving_time"]) if item.get("moving_time") is not None else None,
                        device_watts=bool(item.get("device_watts")),
                        manual=bool(item.get("manual")),
                    )
                )
            except (KeyError, TypeError, ValueError, AttributeError):
                continue  # an entry we can't make sense of isn't worth failing the run
        return activities

    async def get_streams(self, access_token: str, activity_id: str) -> dict[str, list] | None:
        response = await self._request(
            "GET",
            f"/api/v3/activities/{activity_id}/streams",
            access_token=access_token,
            params={"keys": ",".join(STREAM_KEYS), "key_by_type": "true"},
        )
        if response.status_code == 404:
            return None
        self._ok(response)
        body = response.json()
        if not isinstance(body, dict):
            return None
        return {key: stream["data"] for key, stream in body.items() if isinstance(stream, dict) and "data" in stream}

    async def activity_exists(self, access_token: str, activity_id: str) -> bool:
        response = await self._request("GET", f"/api/v3/activities/{activity_id}", access_token=access_token)
        if response.status_code == 404:
            return False
        self._ok(response)
        return True

    async def deauthorize(self, access_token: str) -> None:
        """Tells Strava the application no longer has access. Best effort."""
        try:
            await self._request("POST", "/oauth/deauthorize", access_token=access_token)
        except StravaClientError:
            pass
