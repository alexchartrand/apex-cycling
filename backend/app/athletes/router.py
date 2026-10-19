import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete, AthleteMetric
from app.athletes.schemas import (
    AthleteMetricRead,
    AthleteMetricWrite,
    AthleteRead,
    AthleteUpdate,
    CurrentMetricsRead,
)
from app.athletes.service import metrics_at
from app.auth.deps import get_current_user, require_athlete_access
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


@router.get("/{athlete_id}", response_model=AthleteRead)
async def get_athlete(athlete: Athlete = Depends(require_athlete_access)) -> Athlete:
    return athlete


@router.patch("/{athlete_id}", response_model=AthleteRead)
async def update_athlete(
    payload: AthleteUpdate,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> Athlete:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(athlete, field, value)
    await db.commit()
    await db.refresh(athlete)
    return athlete


@router.get("/{athlete_id}/metrics", response_model=list[AthleteMetricRead])
async def list_metrics(
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> list[AthleteMetric]:
    rows = await db.scalars(
        select(AthleteMetric)
        .where(AthleteMetric.athlete_id == athlete.id)
        .order_by(AthleteMetric.effective_date.desc())
    )
    return list(rows)


@router.post("/{athlete_id}/metrics", response_model=AthleteMetricRead, status_code=status.HTTP_201_CREATED)
async def record_metrics(
    payload: AthleteMetricWrite,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> AthleteMetric:
    """Records measurements for a date. If that date already has a row, the
    values sent are merged into it (a null leaves the stored value alone),
    so a weigh-in and an FTP test on the same day end up in one row."""
    row = await db.scalar(
        select(AthleteMetric).where(
            AthleteMetric.athlete_id == athlete.id, AthleteMetric.effective_date == payload.effective_date
        )
    )
    if row is None:
        row = AthleteMetric(athlete_id=athlete.id, effective_date=payload.effective_date)
        db.add(row)
    for field, value in payload.model_dump(exclude={"effective_date"}).items():
        if value is not None:
            setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/{athlete_id}/metrics/current", response_model=CurrentMetricsRead)
async def current_metrics(
    on: date | None = Query(default=None, description="Defaults to today"),
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> CurrentMetricsRead:
    on = on or date.today()
    values = await metrics_at(db, athlete.id, on)
    return CurrentMetricsRead.model_validate({"on": on, **values})


@router.delete("/{athlete_id}/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    metric_id: uuid.UUID,
    athlete: Athlete = Depends(require_athlete_access),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(AthleteMetric, metric_id)
    if row is None or row.athlete_id != athlete.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Measurement not found")
    await db.delete(row)
    await db.commit()
