"""The athlete's edits to their own copy of a session: title, notes, RPE,
tags, lap exclusion and labels, effort labels. Each function returns None
when the target isn't this athlete's, and commits on success.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.training.models import TrainingEvent, TrainingLap
from app.training.records_service import recompute_personal_records
from app.training.schemas import EffortLabel, LapEdit, LapUpdate, SessionMeta, SessionUpdate
from app.training.service import get_session_efforts


def _session_meta(event: TrainingEvent) -> SessionMeta:
    return SessionMeta(
        external_event_id=event.external_event_id,
        event_name=event.title_override or event.name,
        original_name=event.name,
        title_override=event.title_override,
        notes=event.notes,
        rpe=event.rpe,
        tags=event.tags or [],
        is_race=event.is_race,
    )


async def update_session(
    db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str, payload: SessionUpdate
) -> SessionMeta | None:
    event = await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete_id, TrainingEvent.external_event_id == external_event_id
        )
    )
    if event is None:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await db.commit()
    return _session_meta(event)


async def update_lap(
    db: AsyncSession, athlete_id: uuid.UUID, lap_id: uuid.UUID, payload: LapUpdate
) -> LapEdit | None:
    lap = await db.get(TrainingLap, lap_id)
    if lap is None or lap.athlete_id != athlete_id:
        return None
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(lap, field, value)
    if "excluded" in changes:
        await recompute_personal_records(db, athlete_id)
    await db.commit()
    return LapEdit(lap_id=lap.id, excluded=lap.excluded, label=lap.label)


async def set_effort_label(
    db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str, first_lap_id: uuid.UUID, label: str | None
) -> EffortLabel | None:
    """Names the effort that starts with `first_lap_id`. None if that lap
    doesn't begin an effort in this athlete's session.
    """
    efforts = await get_session_efforts(db, athlete_id, external_event_id)
    if efforts is None or not any(effort.lap_ids[0] == first_lap_id for effort in efforts):
        return None
    lap = await db.get(TrainingLap, first_lap_id)
    lap.effort_label = label
    await db.commit()
    return EffortLabel(first_lap_id=first_lap_id, label=label)
