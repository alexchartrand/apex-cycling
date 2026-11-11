"""An athlete's Intervals.icu connection: connect with an API key, see its
status, sync now, put planned workouts on the Intervals.icu calendar,
disconnect. The key is stored encrypted and never returned."""

import uuid
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import athlete_timezone, local_day
from app.athletes.coaching import speaks_for_athlete
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.connections.models import (
    DataSourceConnection,
    DataSourceConnectionStatus,
    DataSourceProvider,
    IngestionRun,
    IngestionRunStatus,
)
from app.core.rate_limit import limiter
from app.db.base import utcnow
from app.db.session import AsyncSessionLocal, get_db
from app.ingestion.intervals.client import IntervalsAuthError, IntervalsClientError, IntervalsHttpClient
from app.ingestion.intervals.factory import build_intervals_sync_service, build_plan_push_service
from app.ingestion.intervals.ports import IntervalsClientPort
from app.planning.models import IntervalsPlanEvent
from app.planning.push import forget_athlete, has_due_pushes, push_switched

logger = logging.getLogger("connections.intervals")

router = APIRouter(prefix="/athletes/{athlete_id}/intervals", tags=["connections"])


def get_intervals_client() -> IntervalsClientPort:
    return IntervalsHttpClient()


def get_session_factory() -> Callable:
    """Sessions for work that outlives the request (the first sync)."""
    return AsyncSessionLocal


PlanPusher = Callable[[uuid.UUID], Awaitable[None]]


def get_plan_pusher(
    session_factory: Callable = Depends(get_session_factory),
    client: IntervalsClientPort = Depends(get_intervals_client),
) -> PlanPusher:
    """Sends one athlete's due plans to Intervals.icu right away (as a
    background task after the change committed), so the calendar follows an
    edit without waiting for the worker, which still retries what fails."""

    async def push(athlete_id: uuid.UUID) -> None:
        try:
            async with session_factory() as db:
                await build_plan_push_service(db, client=client).run(athlete_id)
        except Exception:
            logger.exception("Pushing plans of athlete %s to Intervals.icu failed", athlete_id)

    return push


async def push_now(db: AsyncSession, background: BackgroundTasks, pusher: PlanPusher, athlete_id: uuid.UUID) -> None:
    """Schedules `pusher` when the athlete has plans waiting to go."""
    if await has_due_pushes(db, athlete_id):
        background.add_task(pusher, athlete_id)


class IntervalsConnect(BaseModel):
    api_key: str = Field(min_length=8, max_length=200)


class IntervalsPush(BaseModel):
    enabled: bool


class IntervalsRunRead(BaseModel):
    status: IngestionRunStatus
    requested_at: datetime
    completed_at: datetime | None
    error_message: str | None
    imported_count: int | None


class IntervalsStatus(BaseModel):
    connected: bool
    # An active connection syncs; an inactive one was disconnected or its key was refused.
    active: bool
    intervals_athlete_id: str | None
    intervals_athlete_name: str | None
    last_synced_at: datetime | None
    runs: list[IntervalsRunRead]
    # Planned workouts are put on the Intervals.icu calendar; how many of
    # them the last attempt failed to send (they are retried).
    push_plans: bool = False
    push_failures: int = 0


async def _require_data_owner(db: AsyncSession, user: User, athlete: Athlete) -> None:
    if not await speaks_for_athlete(db, user, athlete):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the athlete can manage their connections")


async def _connection(db: AsyncSession, athlete: Athlete) -> DataSourceConnection | None:
    return await db.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.provider == DataSourceProvider.INTERVALS_ICU,
            DataSourceConnection.athlete_id == athlete.id,
        )
    )


async def _status(db: AsyncSession, connection: DataSourceConnection | None) -> IntervalsStatus:
    if connection is None:
        return IntervalsStatus(
            connected=False, active=False, intervals_athlete_id=None, intervals_athlete_name=None,
            last_synced_at=None, runs=[],
        )  # fmt: skip
    runs = await db.scalars(
        select(IngestionRun)
        .where(IngestionRun.data_source_connection_id == connection.id)
        .order_by(IngestionRun.requested_at.desc())
        .limit(10)
    )
    failures = await db.scalar(
        select(func.count())
        .select_from(IntervalsPlanEvent)
        .where(IntervalsPlanEvent.athlete_id == connection.athlete_id, IntervalsPlanEvent.last_error.is_not(None))
    )
    return IntervalsStatus(
        connected=True,
        push_plans=connection.push_plans,
        push_failures=failures or 0,
        active=connection.status == DataSourceConnectionStatus.ACTIVE,
        intervals_athlete_id=connection.external_id,
        intervals_athlete_name=(connection.credentials or {}).get("athlete_name"),
        last_synced_at=connection.last_synced_at,
        runs=[
            IntervalsRunRead(
                status=r.status, requested_at=r.requested_at, completed_at=r.completed_at,
                error_message=r.error_message, imported_count=r.imported_count,
            )  # fmt: skip
            for r in runs
        ],
    )


async def _sync_in_background(
    session_factory: Callable, client: IntervalsClientPort, connection_id: uuid.UUID
) -> None:
    async with session_factory() as db:
        await build_intervals_sync_service(db, client=client).sync_by_id(connection_id)


@router.get("", response_model=IntervalsStatus)
async def intervals_status(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntervalsStatus:
    await _require_data_owner(db, current_user, athlete)
    return await _status(db, await _connection(db, athlete))


@router.put("", response_model=IntervalsStatus)
@limiter.limit("10/minute")
async def connect_intervals(
    request: Request,
    payload: IntervalsConnect,
    background: BackgroundTasks,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    client: IntervalsClientPort = Depends(get_intervals_client),
    session_factory: Callable = Depends(get_session_factory),
    db: AsyncSession = Depends(get_db),
) -> IntervalsStatus:
    """Checks the key with Intervals.icu, stores it and starts the first sync
    (it keeps going in the worker). Reconnecting with a new key re-activates a
    connection that was refused or disconnected."""
    await _require_data_owner(db, current_user, athlete)
    api_key = payload.api_key.strip()
    try:
        remote = await client.get_athlete(api_key)
    except IntervalsAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Intervals.icu did not accept that API key") from exc
    except IntervalsClientError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach Intervals.icu, try again later") from exc

    connection = await _connection(db, athlete)
    if connection is not None and connection.external_id != remote.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Another Intervals.icu account is connected: disconnect it first"
        )
    taken = await db.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.provider == DataSourceProvider.INTERVALS_ICU,
            DataSourceConnection.external_id == remote.id,
        )
    )
    if taken is not None and taken.athlete_id != athlete.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "That Intervals.icu account is connected to another athlete")

    if connection is None:
        connection = DataSourceConnection(
            provider=DataSourceProvider.INTERVALS_ICU, external_id=remote.id, athlete_id=athlete.id
        )
        db.add(connection)
    connection.credentials = {"api_key": api_key, "athlete_name": remote.name}
    connection.status = DataSourceConnectionStatus.ACTIVE
    await db.commit()
    background.add_task(_sync_in_background, session_factory, client, connection.id)
    return await _status(db, connection)


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED, response_model=IntervalsStatus)
@limiter.limit("6/minute")
async def sync_intervals_now(
    request: Request,
    background: BackgroundTasks,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    client: IntervalsClientPort = Depends(get_intervals_client),
    session_factory: Callable = Depends(get_session_factory),
    db: AsyncSession = Depends(get_db),
) -> IntervalsStatus:
    await _require_data_owner(db, current_user, athlete)
    connection = await _connection(db, athlete)
    if connection is None or connection.status != DataSourceConnectionStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Intervals.icu first")
    background.add_task(_sync_in_background, session_factory, client, connection.id)
    return await _status(db, connection)


@router.put("/push", response_model=IntervalsStatus)
async def push_plans_to_intervals(
    payload: IntervalsPush,
    background: BackgroundTasks,
    athlete: Athlete = Depends(require_athlete_access),
    pusher: PlanPusher = Depends(get_plan_pusher),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntervalsStatus:
    """Turns on (or off) putting planned workouts on the athlete's
    Intervals.icu calendar. They go right away (the worker retries what
    fails); turning it off removes the upcoming ones it sent."""
    await _require_data_owner(db, current_user, athlete)
    connection = await _connection(db, athlete)
    if connection is None or connection.status != DataSourceConnectionStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect Intervals.icu first")
    if connection.push_plans != payload.enabled:
        connection.push_plans = payload.enabled
        await db.flush()
        await push_switched(db, athlete.id, local_day(utcnow(), await athlete_timezone(db, athlete)))
        await db.commit()
        await push_now(db, background, pusher, athlete.id)
    return await _status(db, connection)


@router.delete("", response_model=IntervalsStatus)
async def disconnect_intervals(
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntervalsStatus:
    """Forgets the API key and stops syncing and pushing plans. Activities
    already imported stay, and so do the plans already on Intervals.icu."""
    await _require_data_owner(db, current_user, athlete)
    connection = await _connection(db, athlete)
    if connection is not None:
        connection.credentials = None
        connection.status = DataSourceConnectionStatus.INACTIVE
        connection.push_plans = False
        await forget_athlete(db, athlete.id)
        await db.commit()
    return await _status(db, connection)
