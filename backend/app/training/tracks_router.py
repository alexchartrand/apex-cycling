import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.training.schemas import TrackSummary, TrackUpdate
from app.training.tracks_service import InvalidTrackSettings, get_track, track_edit_rights, update_track

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.patch("/{track_id}", response_model=TrackSummary)
async def edit_track(
    track_id: uuid.UUID,
    payload: TrackUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrackSummary:
    track = await get_track(db, track_id)
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Track not found")
    if not (await track_edit_rights(db, current_user)).can_edit(track):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to edit this track")
    try:
        return await update_track(db, track, payload, can_edit=True)
    except InvalidTrackSettings as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
