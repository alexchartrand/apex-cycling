import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.aero import service
from app.aero.models import AeroTest
from app.aero.schemas import (
    AeroEstimateRead,
    AeroEstimateRequest,
    AeroTestCreate,
    AeroTestDetail,
    AeroTestRead,
    AeroTestUpdate,
)
from app.athletes.models import Athlete
from app.auth.deps import get_current_user, require_athlete_access
from app.auth.models import User
from app.db.session import get_db

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["aero"])


@router.post("/sessions/{event_id}/aero", response_model=AeroEstimateRead)
async def estimate_session_aero(
    athlete_id: uuid.UUID,
    event_id: str,
    payload: AeroEstimateRequest,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AeroEstimateRead:
    """CdA (and Crr) from the session's laps and its linked recording's power.
    Computes only; nothing is saved."""
    data = await service.load_session(db, athlete, current_user, event_id)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    try:
        return service.estimate(data, payload, track_id=payload.track_id, lap_ids=payload.lap_ids)
    except service.TrackNotInSession:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Track not in this session") from None


# --- saved tests: the setups to compare. Results are computed on every read. ---


async def _test(test_id: uuid.UUID, athlete: Athlete, db: AsyncSession) -> AeroTest:
    test = await service.get_test(db, athlete, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aero test not found")
    return test


@router.get("/aero-tests", response_model=list[AeroTestRead])
async def list_aero_tests(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AeroTestRead]:
    return await service.list_tests(db, athlete, current_user)


@router.post("/aero-tests", response_model=AeroTestDetail, status_code=status.HTTP_201_CREATED)
async def create_aero_test(
    athlete_id: uuid.UUID,
    payload: AeroTestCreate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AeroTestDetail:
    try:
        created = await service.create_test(db, athlete, current_user, payload)
    except service.TrackNotInSession:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Track not in this session") from None
    if created is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return created


@router.get("/aero-tests/{test_id}", response_model=AeroTestDetail)
async def get_aero_test(
    athlete_id: uuid.UUID,
    test_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AeroTestDetail:
    return await service.read_test(db, athlete, current_user, await _test(test_id, athlete, db))


@router.patch("/aero-tests/{test_id}", response_model=AeroTestDetail)
async def update_aero_test(
    athlete_id: uuid.UUID,
    test_id: uuid.UUID,
    payload: AeroTestUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AeroTestDetail:
    return await service.update_test(db, athlete, current_user, await _test(test_id, athlete, db), payload)


@router.delete("/aero-tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_aero_test(
    athlete_id: uuid.UUID,
    test_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await db.delete(await _test(test_id, athlete, db))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
