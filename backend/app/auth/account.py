"""Whole-account operations: "export my data" and "delete my account".

Both walk every table holding a user's or their athlete's rows. **Any new
table with a user_id/athlete_id (or hanging off one) must be added to both
`build_export` and `delete_account`** — `tests/test_account.py` checks the
deletion leaves no row pointing at the user or athlete.
"""

import csv
import io
import json
import uuid
import zipfile
from collections.abc import Sequence
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.athletes.models import Athlete, AthleteMetric, CoachAthlete
from app.auth.models import PasswordResetToken, User
from app.clubs.models import ClubMembership
from app.connections.models import DataSourceConnection, IngestionRun, RawSnapshot, TransponderAssignment
from app.db.base import Base
from app.training.models import (
    EventClass,
    EventTrack,
    LapSegmentTime,
    ManualResult,
    PersonalRecord,
    Track,
    TrackLoop,
    TrainingEvent,
    TrainingLap,
)

# Never exported: secrets, and other people's/opaque bookkeeping.
_EXCLUDED_COLUMNS = {"hashed_password", "credentials", "credentials_changed_at"}


def _plain(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "value"):  # enums
        return value.value
    if isinstance(value, list):  # e.g. session tags
        return json.dumps(value, ensure_ascii=False)
    return value


def _row_dict(row: Base) -> dict[str, Any]:
    return {
        column.key: _plain(getattr(row, column.key))
        for column in row.__table__.columns
        if column.key not in _EXCLUDED_COLUMNS
    }


def _csv(model: type[Base], rows: Sequence[Base]) -> str:
    columns = [c.key for c in model.__table__.columns if c.key not in _EXCLUDED_COLUMNS]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow(_row_dict(row))
    return buffer.getvalue()


async def _self_athlete(db: AsyncSession, user: User) -> Athlete | None:
    return await db.scalar(select(Athlete).where(Athlete.user_id == user.id))


async def build_export(db: AsyncSession, user: User) -> bytes:
    """A zip with account.json (user + athlete profile) and one CSV per
    table of the athlete's data, plus the track/loop definitions it
    references so lap splits are readable on their own."""
    athlete = await _self_athlete(db, user)
    files: dict[str, str] = {}

    account = {"exported_at": datetime.now(timezone.utc).isoformat(), "user": _row_dict(user)}
    account["athlete"] = _row_dict(athlete) if athlete else None
    files["account.json"] = json.dumps(account, indent=2, ensure_ascii=False)

    if athlete is not None:
        events = list(await db.scalars(select(TrainingEvent).where(TrainingEvent.athlete_id == athlete.id)))
        event_ids = [e.id for e in events]
        event_tracks = list(await db.scalars(select(EventTrack).where(EventTrack.training_event_id.in_(event_ids))))
        laps = list(await db.scalars(select(TrainingLap).where(TrainingLap.athlete_id == athlete.id)))
        segments = list(
            await db.scalars(
                select(LapSegmentTime).where(LapSegmentTime.training_lap_id.in_([lap.id for lap in laps]))
            )
        )
        track_ids = {et.track_id for et in event_tracks}
        tables: list[tuple[str, type[Base], Sequence[Base]]] = [
            (
                "metrics.csv",
                AthleteMetric,
                list(
                    await db.scalars(
                        select(AthleteMetric)
                        .where(AthleteMetric.athlete_id == athlete.id)
                        .order_by(AthleteMetric.effective_date)
                    )
                ),
            ),
            ("sessions.csv", TrainingEvent, events),
            (
                "session_classes.csv",
                EventClass,
                list(await db.scalars(select(EventClass).where(EventClass.training_event_id.in_(event_ids)))),
            ),
            ("session_tracks.csv", EventTrack, event_tracks),
            ("laps.csv", TrainingLap, laps),
            ("lap_splits.csv", LapSegmentTime, segments),
            (
                "records.csv",
                PersonalRecord,
                list(await db.scalars(select(PersonalRecord).where(PersonalRecord.athlete_id == athlete.id))),
            ),
            (
                "manual_results.csv",
                ManualResult,
                list(
                    await db.scalars(
                        select(ManualResult)
                        .where(ManualResult.athlete_id == athlete.id)
                        .order_by(ManualResult.achieved_on)
                    )
                ),
            ),
            ("tracks.csv", Track, list(await db.scalars(select(Track).where(Track.id.in_(track_ids))))),
            (
                "track_loops.csv",
                TrackLoop,
                list(await db.scalars(select(TrackLoop).where(TrackLoop.track_id.in_(track_ids)))),
            ),
            (
                "transponders.csv",
                TransponderAssignment,
                list(
                    await db.scalars(
                        select(TransponderAssignment).where(TransponderAssignment.athlete_id == athlete.id)
                    )
                ),
            ),
        ]
        for filename, model, rows in tables:
            files[filename] = _csv(model, rows)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


async def delete_account(db: AsyncSession, user: User) -> None:
    """Deletes the user, their own athlete profile and all of its data.
    Shared rows stay (sqorz transponder connections and their snapshots,
    tracks); rows other people own that merely reference this user lose
    that reference instead (e.g. a transponder assignment this user entered
    for another athlete). Doesn't commit."""
    athlete = await _self_athlete(db, user)

    if athlete is not None:
        event_ids = select(TrainingEvent.id).where(TrainingEvent.athlete_id == athlete.id)
        lap_ids = select(TrainingLap.id).where(TrainingLap.athlete_id == athlete.id)
        await db.execute(delete(PersonalRecord).where(PersonalRecord.athlete_id == athlete.id))
        await db.execute(delete(ManualResult).where(ManualResult.athlete_id == athlete.id))
        await db.execute(delete(LapSegmentTime).where(LapSegmentTime.training_lap_id.in_(lap_ids)))
        await db.execute(delete(TrainingLap).where(TrainingLap.athlete_id == athlete.id))
        await db.execute(delete(EventTrack).where(EventTrack.training_event_id.in_(event_ids)))
        await db.execute(delete(EventClass).where(EventClass.training_event_id.in_(event_ids)))
        await db.execute(delete(TrainingEvent).where(TrainingEvent.athlete_id == athlete.id))
        await db.execute(delete(AthleteMetric).where(AthleteMetric.athlete_id == athlete.id))
        await db.execute(delete(TransponderAssignment).where(TransponderAssignment.athlete_id == athlete.id))

        # Personal (non-sqorz) connections belong to the athlete outright.
        connection_ids = select(DataSourceConnection.id).where(DataSourceConnection.athlete_id == athlete.id)
        run_ids = select(IngestionRun.id).where(IngestionRun.data_source_connection_id.in_(connection_ids))
        await db.execute(delete(RawSnapshot).where(RawSnapshot.ingestion_run_id.in_(run_ids)))
        await db.execute(delete(IngestionRun).where(IngestionRun.data_source_connection_id.in_(connection_ids)))
        await db.execute(delete(DataSourceConnection).where(DataSourceConnection.athlete_id == athlete.id))

    athlete_filter = [CoachAthlete.athlete_id == athlete.id] if athlete is not None else []
    await db.execute(delete(CoachAthlete).where(or_(CoachAthlete.coach_user_id == user.id, *athlete_filter)))
    await db.execute(
        update(CoachAthlete).where(CoachAthlete.initiated_by_user_id == user.id).values(initiated_by_user_id=None)
    )
    await db.execute(delete(ClubMembership).where(ClubMembership.user_id == user.id))
    await db.execute(
        update(TransponderAssignment)
        .where(TransponderAssignment.created_by_user_id == user.id)
        .values(created_by_user_id=None)
    )
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.created_by_user_id == user.id)
        .values(created_by_user_id=None)
    )
    if athlete is not None:
        await db.execute(delete(Athlete).where(Athlete.id == athlete.id))
    await db.execute(delete(User).where(User.id == user.id))
