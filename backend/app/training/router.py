import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.fusion_service import add_activity_metrics_to_efforts, add_activity_metrics_to_session
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.db.session import get_db
from app.equipment.service import add_gear_to_efforts, add_gear_to_session
from app.training.insights_service import list_insights
from app.training.edit_service import set_effort_label, update_lap, update_session
from app.training.efforts import StartType
from app.training.schemas import (
    EffortDetail,
    EffortLabel,
    EffortLabelUpdate,
    InsightRead,
    LapEdit,
    LapUpdate,
    ProgressionMetric,
    ProgressionPoint,
    SessionDetail,
    SessionMeta,
    SessionSummary,
    SessionUpdate,
    TrackSummary,
)
from app.training.tracks_service import track_edit_rights
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
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int | None = Query(default=None, ge=1, le=1000),
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[SessionSummary]:
    """Newest first. All of the athlete's sessions unless bounded by `from` / `to` (inclusive) or `limit` (the newest N)."""
    return await list_athlete_sessions(db, athlete.id, from_date=from_date, to_date=to_date, limit=limit)


@router.get("/tracks", response_model=list[TrackSummary])
async def tracks(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackSummary]:
    rights = await track_edit_rights(db, current_user)
    return await list_athlete_tracks(db, athlete.id, can_edit=rights.can_edit)


@router.get("/sessions/{event_id}", response_model=SessionDetail)
async def session_detail(
    athlete_id: uuid.UUID,
    event_id: str,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionDetail:
    detail = await get_session_detail(db, athlete.id, event_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await add_activity_metrics_to_session(db, athlete, current_user, detail)
    efforts = await get_session_efforts(db, athlete.id, event_id) or []
    await add_gear_to_session(db, athlete.id, detail, efforts)
    return detail


@router.get("/insights", response_model=list[InsightRead])
async def insights_feed(
    athlete_id: uuid.UUID,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[InsightRead]:
    """What's new: the headlines of the last `days` days of sessions, newest first."""
    return await list_insights(db, athlete.id, since=date.today() - timedelta(days=days), limit=limit)


@router.get("/sessions/{event_id}/insights", response_model=list[InsightRead])
async def session_insights(
    athlete_id: uuid.UUID,
    event_id: str,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[InsightRead]:
    return await list_insights(db, athlete.id, external_event_id=event_id)


@router.patch("/sessions/{event_id}", response_model=SessionMeta)
async def edit_session(
    athlete_id: uuid.UUID,
    event_id: str,
    payload: SessionUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> SessionMeta:
    updated = await update_session(db, athlete.id, event_id, payload)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return updated


@router.patch("/laps/{lap_id}", response_model=LapEdit)
async def edit_lap(
    athlete_id: uuid.UUID,
    lap_id: uuid.UUID,
    payload: LapUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> LapEdit:
    updated = await update_lap(db, athlete.id, lap_id, payload)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lap not found")
    return updated


@router.put("/sessions/{event_id}/efforts/{first_lap_id}/label", response_model=EffortLabel)
async def label_effort(
    athlete_id: uuid.UUID,
    event_id: str,
    first_lap_id: uuid.UUID,
    payload: EffortLabelUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> EffortLabel:
    labelled = await set_effort_label(db, athlete.id, event_id, first_lap_id, payload.label)
    if labelled is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Effort not found")
    return labelled


@router.get("/sessions/{event_id}/efforts", response_model=list[EffortDetail])
async def session_efforts(
    athlete_id: uuid.UUID,
    event_id: str,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EffortDetail]:
    efforts = await get_session_efforts(db, athlete.id, event_id)
    if efforts is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await add_activity_metrics_to_efforts(db, athlete, current_user, event_id, efforts)
    await add_gear_to_efforts(db, athlete.id, event_id, efforts)
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
