"""An athlete's Strava connection: OAuth authorization, status, sync, disconnect
— and the optional webhook Strava pushes events to.

Strava's API terms drive the shape: their data is shown only to the athlete it
belongs to (see `activities.metrics_service.visible_conditions`), and it is
deleted when access ends (disconnecting here, or revoking on Strava)."""

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.connections.intervals_router import IntervalsRunRead, get_session_factory
from app.connections.models import (
    DataSourceConnection,
    DataSourceConnectionStatus,
    DataSourceProvider,
    IngestionRun,
)
from app.core.config import API_PREFIX, get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.ingestion.strava.client import SCOPE, StravaClientError, StravaHttpClient, authorize_url
from app.ingestion.strava.factory import build_strava_sync_service
from app.ingestion.strava.ports import StravaClientPort
from app.ingestion.strava.repositories import SqlAlchemyStravaConnectionRepository, purge_strava_data

logger = logging.getLogger("connections.strava")

router = APIRouter(prefix="/athletes/{athlete_id}/strava", tags=["connections"])
public_router = APIRouter(prefix="/strava", tags=["connections"])

_STATE_TTL = timedelta(minutes=15)


def get_strava_client() -> StravaClientPort:
    return StravaHttpClient()


def _configured() -> bool:
    settings = get_settings()
    return bool(settings.strava_client_id and settings.strava_client_secret)


def _require_configured() -> None:
    if not _configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Strava is not set up on this server")


def _callback_url() -> str:
    return f"{get_settings().app_base_url.rstrip('/')}{API_PREFIX}/strava/callback"


def _import_page(result: str) -> RedirectResponse:
    query = urlencode({"strava": result})
    return RedirectResponse(f"{get_settings().app_base_url.rstrip('/')}/import?{query}", status.HTTP_303_SEE_OTHER)


def _make_state(user: User, athlete: Athlete) -> str:
    settings = get_settings()
    claims = {
        "type": "strava_oauth",
        "sub": str(user.id),
        "athlete": str(athlete.id),
        "exp": datetime.now(timezone.utc) + _STATE_TTL,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _read_state(state: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    settings = get_settings()
    try:
        claims = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if claims.get("type") != "strava_oauth":
            return None
        return uuid.UUID(claims["sub"]), uuid.UUID(claims["athlete"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


class StravaStatus(BaseModel):
    available: bool  # the server has a Strava application configured
    connected: bool
    active: bool
    strava_athlete_name: str | None
    last_synced_at: datetime | None
    runs: list[IntervalsRunRead]


class AuthorizeUrl(BaseModel):
    url: str


async def _require_data_owner(db: AsyncSession, user: User, athlete: Athlete) -> None:
    if not await speaks_for_athlete(db, user, athlete):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the athlete can manage their connections")


async def _connection(db: AsyncSession, athlete_id: uuid.UUID) -> DataSourceConnection | None:
    return await db.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.provider == DataSourceProvider.STRAVA, DataSourceConnection.athlete_id == athlete_id
        )
    )


async def _status(db: AsyncSession, connection: DataSourceConnection | None) -> StravaStatus:
    runs = []
    if connection is not None:
        found = await db.scalars(
            select(IngestionRun)
            .where(IngestionRun.data_source_connection_id == connection.id)
            .order_by(IngestionRun.requested_at.desc())
            .limit(10)
        )
        runs = [
            IntervalsRunRead(
                status=r.status, requested_at=r.requested_at, completed_at=r.completed_at,
                error_message=r.error_message, imported_count=r.imported_count,
            )  # fmt: skip
            for r in found
        ]
    return StravaStatus(
        available=_configured(),
        connected=connection is not None,
        active=connection is not None and connection.status == DataSourceConnectionStatus.ACTIVE,
        strava_athlete_name=(connection.credentials or {}).get("athlete_name") if connection else None,
        last_synced_at=connection.last_synced_at if connection else None,
        runs=runs,
    )


async def _sync_in_background(session_factory: Callable, client: StravaClientPort, connection_id: uuid.UUID) -> None:
    async with session_factory() as db:
        await build_strava_sync_service(db, client=client).sync_by_id(connection_id)


@router.get("", response_model=StravaStatus)
async def strava_status(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StravaStatus:
    await _require_data_owner(db, current_user, athlete)
    return await _status(db, await _connection(db, athlete.id))


@router.get("/authorize-url", response_model=AuthorizeUrl)
async def strava_authorize_url(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthorizeUrl:
    """Where to send the athlete to approve access on Strava."""
    _require_configured()
    await _require_data_owner(db, current_user, athlete)
    return AuthorizeUrl(url=authorize_url(_callback_url(), _make_state(current_user, athlete)))


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED, response_model=StravaStatus)
@limiter.limit("6/minute")
async def sync_strava_now(
    request: Request,
    background: BackgroundTasks,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    client: StravaClientPort = Depends(get_strava_client),
    session_factory: Callable = Depends(get_session_factory),
    db: AsyncSession = Depends(get_db),
) -> StravaStatus:
    _require_configured()
    await _require_data_owner(db, current_user, athlete)
    connection = await _connection(db, athlete.id)
    if connection is None or connection.status != DataSourceConnectionStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Strava first")
    background.add_task(_sync_in_background, session_factory, client, connection.id)
    return await _status(db, connection)


@router.delete("", response_model=StravaStatus)
async def disconnect_strava(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    client: StravaClientPort = Depends(get_strava_client),
    db: AsyncSession = Depends(get_db),
) -> StravaStatus:
    """Revokes ApexCycling's access on Strava and deletes the Strava activities
    imported so far (Strava's terms require it)."""
    await _require_data_owner(db, current_user, athlete)
    connection = await _connection(db, athlete.id)
    if connection is not None:
        credentials = connection.credentials or {}
        if credentials.get("access_token"):
            await client.deauthorize(credentials["access_token"])
        connection.credentials = None
        connection.status = DataSourceConnectionStatus.INACTIVE
        await purge_strava_data(db, athlete.id)
        await db.commit()
    return await _status(db, connection)


# --- OAuth callback (Strava sends the browser here) --------------------------------


@public_router.get("/callback")
async def strava_callback(
    background: BackgroundTasks,
    code: str | None = None,
    state: str = "",
    scope: str = "",
    error: str | None = None,
    client: StravaClientPort = Depends(get_strava_client),
    session_factory: Callable = Depends(get_session_factory),
    db: AsyncSession = Depends(get_db),
):
    """Finishes the authorization and sends the browser back to the import
    page with `?strava=connected|denied|error`. The signed `state` says which
    athlete started it, so no login cookie is needed (it may have expired
    while the athlete was on Strava)."""
    if not _configured():
        return _import_page("error")
    parsed_state = _read_state(state)
    if parsed_state is None:
        return _import_page("error")
    user_id, athlete_id = parsed_state
    if error or not code:
        return _import_page("denied")
    if "activity:read" not in scope:  # unticked on the consent screen
        return _import_page("denied")

    athlete = await db.get(Athlete, athlete_id)
    user = await db.get(User, user_id)
    if athlete is None or user is None or not await speaks_for_athlete(db, user, athlete):
        return _import_page("error")
    try:
        authorized = await client.exchange_code(code)
    except StravaClientError:
        logger.warning("Strava code exchange failed", exc_info=True)
        return _import_page("error")

    existing = await _connection(db, athlete.id)
    taken = await db.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.provider == DataSourceProvider.STRAVA,
            DataSourceConnection.external_id == authorized.athlete.id,
        )
    )
    if (taken is not None and taken.athlete_id != athlete.id) or (
        existing is not None and existing.external_id != authorized.athlete.id
    ):
        return _import_page("error")
    connection = existing
    if connection is None:
        connection = DataSourceConnection(
            provider=DataSourceProvider.STRAVA, external_id=authorized.athlete.id, athlete_id=athlete.id
        )
        db.add(connection)
    connection.credentials = {
        "access_token": authorized.tokens.access_token,
        "refresh_token": authorized.tokens.refresh_token,
        "expires_at": authorized.tokens.expires_at,
        "athlete_name": authorized.athlete.name,
        "scope": scope or SCOPE,
    }
    connection.status = DataSourceConnectionStatus.ACTIVE
    await db.commit()
    background.add_task(_sync_in_background, session_factory, client, connection.id)
    return _import_page("connected")


# --- webhook ----------------------------------------------------------------------------


@public_router.get("/webhook")
async def strava_webhook_challenge(
    mode: str = Query(alias="hub.mode", default=""),
    token: str = Query(alias="hub.verify_token", default=""),
    challenge: str = Query(alias="hub.challenge", default=""),
) -> dict[str, str]:
    """Strava calls this once, when the subscription is created."""
    expected = get_settings().strava_webhook_verify_token
    if not expected or mode != "subscribe" or token != expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a Strava subscription request")
    return {"hub.challenge": challenge}


class WebhookEvent(BaseModel):
    object_type: str
    object_id: int
    aspect_type: str
    owner_id: int
    subscription_id: int | None = None
    updates: dict | None = None


async def _handle_event(
    session_factory: Callable, client: StravaClientPort, event: WebhookEvent
) -> None:
    """Events are hints, not facts: anything destructive is first checked with
    Strava using the athlete's own tokens, because the endpoint is public."""
    async with session_factory() as db:
        service = build_strava_sync_service(db, client=client)
        owner = str(event.owner_id)
        if event.object_type == "activity" and event.aspect_type == "create":
            connection = await SqlAlchemyStravaConnectionRepository(db).get_by_strava_athlete(owner)
            if connection is not None:
                await service.sync(connection)
        elif event.object_type == "activity" and event.aspect_type == "delete":
            await service.handle_activity_deleted(owner, str(event.object_id))
        elif event.object_type == "athlete" and (event.updates or {}).get("authorized") == "false":
            await service.handle_deauthorized(owner)


@public_router.post("/webhook", status_code=status.HTTP_200_OK)
@limiter.limit("120/minute")
async def strava_webhook(
    request: Request,
    event: WebhookEvent,
    background: BackgroundTasks,
    client: StravaClientPort = Depends(get_strava_client),
    session_factory: Callable = Depends(get_session_factory),
) -> dict[str, str]:
    """Strava needs a quick 200; the work happens after the response."""
    settings = get_settings()
    if settings.strava_webhook_subscription_id and event.subscription_id != settings.strava_webhook_subscription_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown subscription")
    background.add_task(_handle_event, session_factory, client, event)
    return {"status": "received"}
