"""The athlete's numbers a workout file is written with: the FTP in force on
the day (a plan's date; today, in the athlete's time zone, for a library
workout) and their best per event and start, which sets how long a track
step lasts on a trainer. Sqorz records and manual results only, so Strava
never enters. Without an athlete the exports fall back on % of FTP and the
simulated times.
"""

import uuid
from datetime import date, datetime, timezone

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.metrics_service import _ftp_on, _metric_rows, athlete_timezone, local_day
from app.athletes.models import Athlete
from app.auth.models import User
from app.planning.models import PlannedSession
from app.training.distances import STANDARD_EVENTS
from app.training.records_service import best_entry, get_records_board
from app.workouts import service
from app.workouts.cues import language
from app.workouts.export import ExportContext, ExportFile, ExportFormat, export_workout
from app.workouts.schemas import WorkoutItem

_ITEMS = TypeAdapter(list[WorkoutItem])


async def export_context(db: AsyncSession, viewer: User, athlete: Athlete | None, day: date | None) -> ExportContext:
    """`day` None: today for the athlete. Cues are in the viewer's language."""
    locale = language(viewer.locale)
    if athlete is None:
        return ExportContext(locale=locale)
    if day is None:
        day = local_day(datetime.now(timezone.utc), await athlete_timezone(db, athlete))
    board = await get_records_board(db, athlete.id)
    best = {
        (event.key, start): entry.time_ms
        for event in STANDARD_EVENTS
        for start in event.start_types
        if (entry := best_entry(board, event.key, start, None)) is not None
    }
    return ExportContext(ftp_w=_ftp_on(await _metric_rows(db, athlete.id), day), best_times_ms=best, locale=locale)


async def export_library_workout(
    db: AsyncSession, viewer: User, workout_id: uuid.UUID, fmt: ExportFormat, athlete: Athlete | None
) -> ExportFile | None:
    """None when the viewer can't see the workout. Raises `NeedsFtp`."""
    workout = await service.get_workout(db, viewer, workout_id)
    if workout is None:
        return None
    return export_workout(
        fmt,
        name=workout.name,
        description=workout.description,
        tags=workout.tags,
        items=workout.steps,
        context=await export_context(db, viewer, athlete, None),
        created=datetime.now(timezone.utc),
    )


async def export_plan(
    db: AsyncSession, viewer: User, athlete: Athlete, plan_id: uuid.UUID, fmt: ExportFormat
) -> ExportFile | None:
    """None when the plan isn't this athlete's or holds no workout. Raises `NeedsFtp`."""
    plan = await db.scalar(
        select(PlannedSession).where(PlannedSession.id == plan_id, PlannedSession.athlete_id == athlete.id)
    )
    if plan is None or not plan.workout:
        return None
    return export_workout(
        fmt,
        name=plan.title,
        description=plan.description,
        tags=[],
        items=_ITEMS.validate_python(plan.workout),
        context=await export_context(db, viewer, athlete, plan.planned_date),
        created=datetime.now(timezone.utc),
    )
