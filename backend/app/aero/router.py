import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.aero import service
from app.aero.schemas import AeroEstimateRead, AeroEstimateRequest
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
