import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import require_athlete_access
from app.db.session import get_db
from app.training.efforts import StartType
from app.training.schemas import EffortDetail, ProgressionMetric, ProgressionPoint, SessionDetail, SessionSummary, TrackSummary
from app.training.service import (
    get_progression,
    get_session_detail,
    get_session_efforts,
    list_athlete_sessions,
    list_athlete_tracks,
)

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["training"])


@router.get("/sessions", response_model=list[SessionSummary])
async def sessions(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[SessionSummary]:
    return await list_athlete_sessions(db, athlete.id)


@router.get("/tracks", response_model=list[TrackSummary])
async def tracks(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[TrackSummary]:
    return await list_athlete_tracks(db, athlete.id)


@router.get("/sessions/{event_id}", response_model=SessionDetail)
async def session_detail(
    athlete_id: uuid.UUID,
    event_id: str,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> SessionDetail:
    detail = await get_session_detail(db, athlete.id, event_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return detail


@router.get("/sessions/{event_id}/efforts", response_model=list[EffortDetail])
async def session_efforts(
    athlete_id: uuid.UUID,
    event_id: str,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[EffortDetail]:
    efforts = await get_session_efforts(db, athlete.id, event_id)
    if efforts is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return efforts


@router.get("/progression", response_model=list[ProgressionPoint])
async def progression(
    athlete_id: uuid.UUID,
    metric: ProgressionMetric,
    track_id: uuid.UUID | None = None,
    track_view_id: uuid.UUID | None = None,
    distance_m: float | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    start_type: StartType | None = None,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[ProgressionPoint]:
    if metric == ProgressionMetric.VIEW and track_view_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "track_view_id is required for metric=view")
    if metric in (ProgressionMetric.LAP_TIME, ProgressionMetric.CUSTOM_DISTANCE) and track_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"track_id is required for metric={metric.value}")
    if metric == ProgressionMetric.CUSTOM_DISTANCE and distance_m is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "distance_m is required for metric=custom_distance")

    return await get_progression(
        db,
        athlete_id=athlete.id,
        metric=metric,
        track_id=track_id,
        track_view_id=track_view_id,
        distance_m=distance_m,
        from_date=from_date,
        to_date=to_date,
        start_type=start_type,
    )
