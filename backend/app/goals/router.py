import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.db.session import get_db
from app.goals import service
from app.goals.schemas import GoalRead, GoalUpdate, GoalWrite
from app.training.records_service import UnknownTrackError

router = APIRouter(prefix="/athletes/{athlete_id}/goals", tags=["goals"])

_NO_GOAL = HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
_NO_TRACK = HTTPException(status.HTTP_404_NOT_FOUND, "Track not found")


@router.get("", response_model=list[GoalRead])
async def list_goals(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GoalRead]:
    return await service.list_goals(db, athlete, current_user)


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    athlete_id: uuid.UUID,
    payload: GoalWrite,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalRead:
    try:
        return await service.create_goal(db, athlete, current_user, payload)
    except UnknownTrackError:
        raise _NO_TRACK from None


@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(
    athlete_id: uuid.UUID,
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalRead:
    try:
        updated = await service.update_goal(db, athlete, current_user, goal_id, payload)
    except UnknownTrackError:
        raise _NO_TRACK from None
    if updated is None:
        raise _NO_GOAL
    return updated


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    athlete_id: uuid.UUID,
    goal_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not await service.delete_goal(db, athlete.id, goal_id):
        raise _NO_GOAL
    return Response(status_code=status.HTTP_204_NO_CONTENT)
