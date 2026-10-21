import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import require_athlete_access
from app.db.session import get_db
from app.equipment import service
from app.equipment.schemas import (
    BikeRead,
    BikeUpdate,
    BikeWrite,
    GearAssignment,
    GearRead,
    GearUpdate,
    GearWrite,
)

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["equipment"])

_NO_BIKE = HTTPException(status.HTTP_404_NOT_FOUND, "Bike not found")
_NO_GEAR = HTTPException(status.HTTP_404_NOT_FOUND, "Gear not found")


@router.get("/bikes", response_model=list[BikeRead])
async def list_bikes(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[BikeRead]:
    return await service.list_bikes(db, athlete.id)


@router.post("/bikes", response_model=BikeRead, status_code=status.HTTP_201_CREATED)
async def create_bike(
    athlete_id: uuid.UUID,
    payload: BikeWrite,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> BikeRead:
    return await service.create_bike(db, athlete.id, payload)


@router.patch("/bikes/{bike_id}", response_model=BikeRead)
async def update_bike(
    athlete_id: uuid.UUID,
    bike_id: uuid.UUID,
    payload: BikeUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> BikeRead:
    updated = await service.update_bike(db, athlete.id, bike_id, payload)
    if updated is None:
        raise _NO_BIKE
    return updated


@router.delete("/bikes/{bike_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bike(
    athlete_id: uuid.UUID,
    bike_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not await service.delete_bike(db, athlete.id, bike_id):
        raise _NO_BIKE
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bikes/{bike_id}/gears", response_model=GearRead, status_code=status.HTTP_201_CREATED)
async def create_gear(
    athlete_id: uuid.UUID,
    bike_id: uuid.UUID,
    payload: GearWrite,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> GearRead:
    created = await service.create_gear(db, athlete.id, bike_id, payload)
    if created is None:
        raise _NO_BIKE
    return created


@router.patch("/gears/{gear_id}", response_model=GearRead)
async def update_gear(
    athlete_id: uuid.UUID,
    gear_id: uuid.UUID,
    payload: GearUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> GearRead:
    updated = await service.update_gear(db, athlete.id, gear_id, payload)
    if updated is None:
        raise _NO_GEAR
    return updated


@router.delete("/gears/{gear_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gear(
    athlete_id: uuid.UUID,
    gear_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not await service.delete_gear(db, athlete.id, gear_id):
        raise _NO_GEAR
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/sessions/{event_id}/gear", status_code=status.HTTP_204_NO_CONTENT)
async def set_session_gear(
    athlete_id: uuid.UUID,
    event_id: str,
    payload: GearAssignment,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        found = await service.set_session_gear(db, athlete.id, event_id, payload.gear_setup_id)
    except service.UnknownGear:
        raise _NO_GEAR from None
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/sessions/{event_id}/efforts/{first_lap_id}/gear", status_code=status.HTTP_204_NO_CONTENT)
async def set_effort_gear(
    athlete_id: uuid.UUID,
    event_id: str,
    first_lap_id: uuid.UUID,
    payload: GearAssignment,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        found = await service.set_effort_gear(db, athlete.id, event_id, first_lap_id, payload.gear_setup_id)
    except service.UnknownGear:
        raise _NO_GEAR from None
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Effort not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
