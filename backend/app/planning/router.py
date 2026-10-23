import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.db.session import get_db
from app.planning import service
from app.planning.schemas import (
    PlanComparison,
    PlannedSessionRead,
    PlannedSessionUpdate,
    PlannedSessionWrite,
    PlanSessionLink,
)

router = APIRouter(prefix="/athletes/{athlete_id}/planned-sessions", tags=["planning"])

_NO_PLAN = HTTPException(status.HTTP_404_NOT_FOUND, "Planned session not found")
_FORBIDDEN = HTTPException(status.HTTP_403_FORBIDDEN, "You can't change this planned session")
_NO_GEAR = HTTPException(status.HTTP_404_NOT_FOUND, "Gear not found")


@router.get("", response_model=list[PlannedSessionRead])
async def list_planned_sessions(
    athlete_id: uuid.UUID,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlannedSessionRead]:
    return await service.list_plans(db, athlete, current_user, start=from_date, end=to_date)


@router.post("", response_model=PlannedSessionRead, status_code=status.HTTP_201_CREATED)
async def create_planned_session(
    athlete_id: uuid.UUID,
    payload: PlannedSessionWrite,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlannedSessionRead:
    try:
        return await service.create_plan(db, athlete, current_user, payload)
    except service.UnknownGear:
        raise _NO_GEAR from None


@router.patch("/{plan_id}", response_model=PlannedSessionRead)
async def update_planned_session(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: PlannedSessionUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlannedSessionRead:
    try:
        updated = await service.update_plan(db, athlete, current_user, plan_id, payload)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    except service.UnknownGear:
        raise _NO_GEAR from None
    if updated is None:
        raise _NO_PLAN
    return updated


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planned_session(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        deleted = await service.delete_plan(db, athlete, current_user, plan_id)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    if not deleted:
        raise _NO_PLAN
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{plan_id}/session", response_model=PlannedSessionRead)
async def link_planned_session(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: PlanSessionLink,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlannedSessionRead:
    """Link the plan to the sqorz session that was ridden (marks it done)."""
    try:
        linked = await service.link_session(db, athlete, current_user, plan_id, payload.external_event_id)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    except service.UnknownSession:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found") from None
    if linked is None:
        raise _NO_PLAN
    return linked


@router.delete("/{plan_id}/session", response_model=PlannedSessionRead)
async def unlink_planned_session(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlannedSessionRead:
    try:
        unlinked = await service.unlink_session(db, athlete, current_user, plan_id)
    except service.NotAllowed:
        raise _FORBIDDEN from None
    if unlinked is None:
        raise _NO_PLAN
    return unlinked


@router.get("/{plan_id}/comparison", response_model=PlanComparison)
async def planned_vs_ridden(
    athlete_id: uuid.UUID,
    plan_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> PlanComparison:
    """Each rep of the plan against the efforts of the session linked to it."""
    try:
        result = await service.comparison(db, athlete, plan_id)
    except service.NoLinkedSession:
        raise HTTPException(status.HTTP_409_CONFLICT, "This plan has no linked session") from None
    if result is None:
        raise _NO_PLAN
    return result
