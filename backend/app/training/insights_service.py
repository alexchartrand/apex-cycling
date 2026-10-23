"""Loads the athlete's history and serves session insights (`insights.py`)."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.training.efforts import detect_efforts
from app.training.insights import EffortFacts, Insight, derive_insights
from app.training.models import Track, TrainingEvent
from app.training.records_service import load_session_inputs, results_of
from app.training.schemas import InsightRead


async def compute_insights(db: AsyncSession, athlete_id: uuid.UUID) -> list[Insight]:
    """Every insight across the athlete's sqorz history, newest first."""
    inputs = await load_session_inputs(db, athlete_id)
    efforts = [
        EffortFacts(item.training_event_id, item.track_id, item.event_date, effort)
        for item in inputs
        for effort in detect_efforts(item.laps, item.track_length_m)
    ]
    return derive_insights(results_of(inputs), efforts)


async def read_insights(db: AsyncSession, insights: list[Insight]) -> list[InsightRead]:
    """Adds the session and track names the screens show."""
    if not insights:
        return []
    events = {
        event.id: event
        for event in (
            await db.scalars(select(TrainingEvent).where(TrainingEvent.id.in_({i.training_event_id for i in insights})))
        ).all()
    }
    track_names = dict(
        (await db.execute(select(Track.id, Track.name).where(Track.id.in_({i.track_id for i in insights})))).all()
    )
    return [
        InsightRead(
            key=insight.key,
            kind=insight.kind.value,
            external_event_id=events[insight.training_event_id].external_event_id,
            session_name=events[insight.training_event_id].title_override or events[insight.training_event_id].name,
            event_date=insight.event_date,
            track_id=insight.track_id,
            track_name=track_names[insight.track_id],
            event_key=insight.event_key,
            start_type=insight.start_type,
            time_ms=insight.time_ms,
            previous_ms=insight.previous_ms,
            milestone_ms=insight.milestone_ms,
            lap_number=insight.lap_number,
            lap_count=insight.lap_count,
            cv_pct=insight.cv_pct,
            effort_start_type=insight.effort_start_type,
            first_lap_id=insight.first_lap_id,
        )
        for insight in insights
    ]


async def list_insights(
    db: AsyncSession,
    athlete_id: uuid.UUID,
    *,
    since: date | None = None,
    external_event_id: str | None = None,
    limit: int = 50,
) -> list[InsightRead]:
    """Newest first; narrowed to sessions on or after `since`, or to one session."""
    insights = await compute_insights(db, athlete_id)
    if external_event_id is not None:
        event_id = await db.scalar(
            select(TrainingEvent.id).where(
                TrainingEvent.athlete_id == athlete_id, TrainingEvent.external_event_id == external_event_id
            )
        )
        insights = [i for i in insights if i.training_event_id == event_id]
    if since is not None:
        insights = [i for i in insights if i.event_date >= since]
    return await read_insights(db, insights[:limit])
