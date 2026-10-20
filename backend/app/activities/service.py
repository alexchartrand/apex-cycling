import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.activities import storage, streams
from app.activities.fusion_service import auto_link_activity
from app.activities.metrics_service import apply_power_metrics, visible_conditions
from app.activities.models import Activity, ActivityPowerCurve, ActivitySource, ActivityStream
from app.activities.parsers import ActivityParseError, ParsedActivity, parse_activity_file
from app.activities.storage import delete_originals_after_commit
from app.activities.summary import summarize
from app.athletes.models import Athlete
from app.auth.models import User
from app.core.config import get_settings

# The same ride exported twice (FIT and TCX of one recording, or an upload
# followed by a sync) differs in bytes but not in when it started and how long it ran.
_DUPLICATE_START_TOLERANCE = timedelta(seconds=5)
_DUPLICATE_ELAPSED_TOLERANCE_S = 10.0


@dataclass
class ImportOutcome:
    status: Literal["created", "duplicate"]
    activity: Activity


def visible_activities(athlete: Athlete, viewer: User) -> Select[tuple[Activity]]:
    """The athlete's activities this viewer may see (see `visible_conditions`
    for the Strava rule)."""
    return select(Activity).where(*visible_conditions(athlete, viewer))


async def find_same_ride(
    db: AsyncSession, athlete_id: uuid.UUID, start_time: datetime, elapsed_s: float
) -> Activity | None:
    """An activity of the athlete that started when this one did and ran as
    long: the same ride, however it got here."""
    candidates = await db.scalars(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= start_time - _DUPLICATE_START_TOLERANCE,
            Activity.start_time <= start_time + _DUPLICATE_START_TOLERANCE,
        )
    )
    for candidate in candidates:
        if abs(candidate.elapsed_s - elapsed_s) <= _DUPLICATE_ELAPSED_TOLERANCE_S:
            return candidate
    return None


async def delete_activities(db: AsyncSession, activities: list[Activity]) -> None:
    """Removes activities with their samples, power curves and original files
    (the files once the transaction commits). Doesn't commit."""
    if not activities:
        return
    ids = [a.id for a in activities]
    delete_originals_after_commit(db, [a.file_path for a in activities if a.file_path])
    await db.execute(delete(ActivityPowerCurve).where(ActivityPowerCurve.activity_id.in_(ids)))
    await db.execute(delete(ActivityStream).where(ActivityStream.activity_id.in_(ids)))
    await db.execute(delete(Activity).where(Activity.id.in_(ids)))


async def _insert(db: AsyncSession, activity: Activity, stream: ActivityStream) -> bool:
    """Adds the rows inside a savepoint, so losing a race on a unique index
    (the same file or upstream activity arriving twice at once) doesn't undo
    the rest of the request. False when it lost."""
    try:
        async with db.begin_nested():
            db.add(activity)
            await db.flush()
            stream.activity_id = activity.id
            db.add(stream)
            await db.flush()
    except IntegrityError:
        return False
    return True


def _build_rows(athlete_id: uuid.UUID, parsed: ParsedActivity, **fields) -> tuple[Activity, ActivityStream]:
    summary = summarize(parsed)
    channels = parsed.channels
    activity = Activity(
        athlete_id=athlete_id,
        name=parsed.name,
        sport=parsed.sport,
        start_time=parsed.start_time,
        elapsed_s=summary.elapsed_s,
        moving_s=summary.moving_s,
        distance_m=summary.distance_m,
        elevation_gain_m=summary.elevation_gain_m,
        has_power="power_w" in channels,
        has_heart_rate="heart_rate" in channels,
        has_cadence="cadence" in channels,
        avg_power_w=summary.avg_power_w,
        max_power_w=summary.max_power_w,
        avg_heart_rate=summary.avg_heart_rate,
        max_heart_rate=summary.max_heart_rate,
        avg_cadence=summary.avg_cadence,
        avg_speed_mps=summary.avg_speed_mps,
        **fields,
    )
    stream = ActivityStream(
        sample_count=len(parsed.time_s),
        time_s=streams.pack("time_s", parsed.time_s),
        **{channel: streams.pack(channel, values) for channel, values in channels.items()},
    )
    return activity, stream


async def import_activity_file(
    db: AsyncSession,
    athlete_id: uuid.UUID,
    content: bytes,
    *,
    source: ActivitySource = ActivitySource.UPLOAD,
    external_id: str | None = None,
    data_source_connection_id: uuid.UUID | None = None,
    name: str | None = None,
) -> ImportOutcome:
    """Parses a FIT/TCX/GPX file and stores the activity, its samples and the
    original file. A file already imported, or another recording of the same
    ride, comes back as `duplicate` with the stored activity. Raises
    `ActivityParseError` for an unusable file. Doesn't commit."""
    if len(content) > get_settings().max_activity_file_bytes:
        raise ActivityParseError("file too large")
    sha256 = hashlib.sha256(content).hexdigest()

    existing = await db.scalar(select(Activity).where(Activity.athlete_id == athlete_id, Activity.file_sha256 == sha256))
    if existing is not None:
        return ImportOutcome("duplicate", existing)

    # Parsing is CPU-bound; keep the event loop free.
    parsed = await asyncio.to_thread(parse_activity_file, content)
    same_ride = await find_same_ride(db, athlete_id, parsed.start_time, parsed.elapsed_s)
    carried: dict = {}
    if same_ride is not None:
        if same_ride.source != ActivitySource.STRAVA or source == ActivitySource.STRAVA:
            return ImportOutcome("duplicate", same_ride)
        # Strava is the copy of last resort (owner-only, no original file): the
        # athlete's own file replaces it, keeping what they wrote on it.
        carried = {"rpe": same_ride.rpe, "notes": same_ride.notes}
        name = same_ride.name or name
        await delete_activities(db, [same_ride])

    parsed.name = parsed.name or name
    file_format = parsed.extra["format"]
    activity, stream = _build_rows(
        athlete_id,
        parsed,
        source=source,
        external_id=external_id,
        data_source_connection_id=data_source_connection_id,
        file_format=file_format,
        file_sha256=sha256,
        **carried,
    )
    if not await _insert(db, activity, stream):
        winner = await db.scalar(
            select(Activity).where(Activity.athlete_id == athlete_id, Activity.file_sha256 == sha256)
        )
        if winner is None:
            raise RuntimeError("activity insert hit a unique index but the conflicting row is gone")
        return ImportOutcome("duplicate", winner)

    activity.file_path = await asyncio.to_thread(storage.save_original, athlete_id, sha256, file_format, content)
    if "power_w" in parsed.channels:
        await apply_power_metrics(db, activity, parsed.time_s, parsed.channels["power_w"])
    await auto_link_activity(db, activity)
    return ImportOutcome("created", activity)


async def import_parsed_activity(
    db: AsyncSession,
    athlete_id: uuid.UUID,
    parsed: ParsedActivity,
    *,
    source: ActivitySource,
    external_id: str,
    data_source_connection_id: uuid.UUID,
) -> ImportOutcome:
    """Stores an activity that arrived as data rather than a file (Strava
    streams): no original is kept. A ride the athlete already has, from
    whichever source, is a duplicate. Doesn't commit."""
    same_ride = await find_same_ride(db, athlete_id, parsed.start_time, parsed.elapsed_s)
    if same_ride is not None:
        return ImportOutcome("duplicate", same_ride)
    activity, stream = _build_rows(
        athlete_id,
        parsed,
        source=source,
        external_id=external_id,
        data_source_connection_id=data_source_connection_id,
    )
    if not await _insert(db, activity, stream):
        winner = await db.scalar(
            select(Activity).where(
                Activity.athlete_id == athlete_id, Activity.source == source, Activity.external_id == external_id
            )
        )
        if winner is None:
            raise RuntimeError("activity insert hit a unique index but the conflicting row is gone")
        return ImportOutcome("duplicate", winner)
    if "power_w" in parsed.channels:
        await apply_power_metrics(db, activity, parsed.time_s, parsed.channels["power_w"])
    await auto_link_activity(db, activity)
    return ImportOutcome("created", activity)
