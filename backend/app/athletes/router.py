from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete
from app.athletes.schemas import AthleteRead
from app.auth.deps import get_current_user
from app.auth.models import User
from app.db.session import get_db

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.get("/me", response_model=AthleteRead)
async def get_my_athlete(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    # Every user gets a self-athlete row on signup (see auth/router.py), so
    # this should always resolve for an authenticated user.
    athlete = await db.scalar(select(Athlete).where(Athlete.user_id == current_user.id))
    if athlete is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No athlete profile for this user")
    return athlete
