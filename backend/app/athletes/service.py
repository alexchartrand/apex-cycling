import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import AthleteMetric

METRIC_FIELDS = ("weight_kg", "ftp_w", "max_hr", "resting_hr")


@dataclass(frozen=True)
class DatedValue:
    value: float | int
    effective_date: date


def metrics_as_of(rows: list[AthleteMetric], on: date) -> dict[str, DatedValue | None]:
    """Per field, the latest non-null value on or before `on` (fields are
    tracked independently: a weigh-in row doesn't reset FTP)."""
    result: dict[str, DatedValue | None] = dict.fromkeys(METRIC_FIELDS)
    for row in sorted(rows, key=lambda r: r.effective_date):
        if row.effective_date > on:
            break
        for field in METRIC_FIELDS:
            value = getattr(row, field)
            if value is not None:
                result[field] = DatedValue(value, row.effective_date)
    return result


async def metrics_at(db: AsyncSession, athlete_id: uuid.UUID, on: date) -> dict[str, DatedValue | None]:
    rows = await db.scalars(
        select(AthleteMetric).where(AthleteMetric.athlete_id == athlete_id, AthleteMetric.effective_date <= on)
    )
    return metrics_as_of(list(rows), on)
