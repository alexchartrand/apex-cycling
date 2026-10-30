import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.workouts import service, structure
from app.workouts.schemas import (
    WorkoutEstimate,
    WorkoutRead,
    WorkoutSteps,
    WorkoutSummary,
    WorkoutUpdate,
    WorkoutWrite,
)

router = APIRouter(prefix="/workouts", tags=["workouts"])

_NO_WORKOUT = HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found")
_FORBIDDEN = HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner changes this workout")


@router.get("", response_model=list[WorkoutSummary])
async def list_workouts(
    q: str | None = Query(default=None, max_length=100),
    tag: str | None = Query(default=None, max_length=30),
    track: bool | None = None,
    mine: bool | None = None,
    min_duration_s: float | None = Query(default=None, ge=0),
    max_duration_s: float | None = Query(default=None, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkoutSummary]:
    """My workouts and my active coaches' libraries."""
    return await service.list_workouts(
        db,
        current_user,
        query=q,
        tag=tag,
        track=track,
        mine=mine,
        min_duration_s=min_duration_s,
        max_duration_s=max_duration_s,
    )


@router.post("/estimate", response_model=WorkoutEstimate)
async def estimate_workout(payload: WorkoutSteps, current_user: User = Depends(get_current_user)) -> WorkoutEstimate:
    """Duration, TSS and profile of steps being edited; stores nothing."""
    return structure.estimate(payload.steps, track_length_m=payload.track_length_m, ftp_w=payload.ftp_w)


@router.post("", response_model=WorkoutRead, status_code=status.HTTP_201_CREATED)
async def create_workout(
    payload: WorkoutWrite,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutRead:
    return await service.create_workout(db, current_user, payload)


@router.get("/{workout_id}", response_model=WorkoutRead)
async def get_workout(
    workout_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutRead:
    workout = await service.get_workout(db, current_user, workout_id)
    if workout is None:
        raise _NO_WORKOUT
    return workout


@router.patch("/{workout_id}", response_model=WorkoutRead)
async def update_workout(
    workout_id: uuid.UUID,
    payload: WorkoutUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutRead:
    try:
        updated = await service.update_workout(db, current_user, workout_id, payload)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    if updated is None:
        raise _NO_WORKOUT
    return updated


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workout(
    workout_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        deleted = await service.delete_workout(db, current_user, workout_id)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    if not deleted:
        raise _NO_WORKOUT
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{workout_id}/duplicate", response_model=WorkoutRead, status_code=status.HTTP_201_CREATED)
async def duplicate_workout(
    workout_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutRead:
    """Copy a workout I can see into my own library."""
    copy = await service.duplicate_workout(db, current_user, workout_id)
    if copy is None:
        raise _NO_WORKOUT
    return copy
