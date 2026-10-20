import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.auth.deps import require_athlete_access
from app.db.session import get_db
from app.training.efforts import StartType
from app.training.records_service import (
    UnknownTrackError,
    create_manual_result,
    delete_manual_result,
    get_record_history,
    get_records_board,
    list_manual_results,
    update_manual_result,
)
from app.training.schemas import ManualResultRead, ManualResultWrite, RecordEntry

router = APIRouter(prefix="/athletes/{athlete_id}", tags=["records"])


@router.get("/records", response_model=list[RecordEntry])
async def records_board(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[RecordEntry]:
    return await get_records_board(db, athlete.id)


@router.get("/records/history", response_model=list[RecordEntry])
async def record_history(
    athlete_id: uuid.UUID,
    event_key: str,
    start_type: StartType,
    track_id: uuid.UUID | None = None,
    venue: str | None = Query(default=None, max_length=255),
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[RecordEntry]:
    return await get_record_history(
        db, athlete.id, event_key=event_key, start_type=start_type, track_id=track_id, venue=venue
    )


@router.get("/manual-results", response_model=list[ManualResultRead])
async def manual_results(
    athlete_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[ManualResultRead]:
    return await list_manual_results(db, athlete.id)


@router.post("/manual-results", response_model=ManualResultRead, status_code=status.HTTP_201_CREATED)
async def add_manual_result(
    athlete_id: uuid.UUID,
    payload: ManualResultWrite,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> ManualResultRead:
    try:
        return await create_manual_result(db, athlete.id, payload)
    except UnknownTrackError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown track") from None


@router.put("/manual-results/{result_id}", response_model=ManualResultRead)
async def replace_manual_result(
    athlete_id: uuid.UUID,
    result_id: uuid.UUID,
    payload: ManualResultWrite,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> ManualResultRead:
    try:
        updated = await update_manual_result(db, athlete.id, result_id, payload)
    except UnknownTrackError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown track") from None
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result not found")
    return updated


@router.delete("/manual-results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_manual_result(
    athlete_id: uuid.UUID,
    result_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not await delete_manual_result(db, athlete.id, result_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
