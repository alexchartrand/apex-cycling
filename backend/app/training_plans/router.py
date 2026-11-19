import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.connections.intervals_router import PlanPusher, get_plan_pusher, push_now
from app.db.session import get_db
from app.training_plans import phases as phase_rules
from app.training_plans import service
from app.training_plans.schemas import (
    Phase,
    PhaseSuggestionRequest,
    TrainingPlanRead,
    TrainingPlanUpdate,
    TrainingPlanWrite,
)

router = APIRouter(prefix="/athletes/{athlete_id}/training-plans", tags=["training-plans"])

_NO_PLAN = HTTPException(status.HTTP_404_NOT_FOUND, "Training plan not found")
_FORBIDDEN = HTTPException(status.HTTP_403_FORBIDDEN, "You can't change this training plan")
_NO_GOAL = HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
_NO_RACE = HTTPException(status.HTTP_404_NOT_FOUND, "Competition not found")


@router.get("", response_model=list[TrainingPlanRead])
async def list_training_plans(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrainingPlanRead]:
    return await service.list_plans(db, athlete, current_user)


@router.post("", response_model=TrainingPlanRead, status_code=status.HTTP_201_CREATED)
async def create_training_plan(
    athlete_id: uuid.UUID,
    payload: TrainingPlanWrite,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingPlanRead:
    try:
        return await service.create_plan(db, athlete, current_user, payload)
    except service.UnknownGoal:
        raise _NO_GOAL from None
    except service.UnknownRace:
        raise _NO_RACE from None


@router.post("/suggest-phases", response_model=list[Phase])
async def suggest_phases(
    athlete_id: uuid.UUID,
    payload: PhaseSuggestionRequest,
    athlete: Athlete = Depends(require_athlete_access),
) -> list[Phase]:
    """The default periodization for these dates (compute only)."""
    return phase_rules.suggest_phases(payload.start_date, payload.end_date, payload.race_priority)


@router.get("/{plan_id}", response_model=TrainingPlanRead)
async def get_training_plan(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingPlanRead:
    plan = await service.get_plan(db, athlete, current_user, plan_id)
    if plan is None:
        raise _NO_PLAN
    return plan


@router.patch("/{plan_id}", response_model=TrainingPlanRead)
async def update_training_plan(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: TrainingPlanUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingPlanRead:
    try:
        updated = await service.update_plan(db, athlete, current_user, plan_id, payload)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    except service.UnknownGoal:
        raise _NO_GOAL from None
    except service.UnknownRace:
        raise _NO_RACE from None
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False, include_context=False)) from None
    if updated is None:
        raise _NO_PLAN
    return updated


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_plan(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    background: BackgroundTasks,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    pusher: PlanPusher = Depends(get_plan_pusher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Deletes the plan and its sessions still to ride; done and past ones stay."""
    try:
        deleted = await service.delete_plan(db, athlete, current_user, plan_id)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    if not deleted:
        raise _NO_PLAN
    await push_now(db, background, pusher, athlete.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
