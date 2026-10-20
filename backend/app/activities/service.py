import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.activities import storage, streams
from app.activities.models import Activity, ActivitySource, ActivityStream
from app.activities.parsers import ActivityParseError, ParsedActivity, parse_activity_file
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
    """The athlete's activities this viewer may see. Strava's API terms only
    allow a user's Strava data to be shown to that user, so anyone else
    (coach, club admin) doesn't get Strava-sourced ones."""
    query = select(Activity).where(Activity.athlete_id == athlete.id)
    if athlete.user_id != viewer.id:
        query = query.where(Activity.source != ActivitySource.STRAVA)
    return query


async def _find_same_ride(db: AsyncSession, athlete_id: uuid.UUID, parsed: ParsedActivity) -> Activity | None:
    candidates = await db.scalars(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= parsed.start_time - _DUPLICATE_START_TOLERANCE,
            Activity.start_time <= parsed.start_time + _DUPLICATE_START_TOLERANCE,
        )
    )
    for candidate in candidates:
        if abs(candidate.elapsed_s - parsed.elapsed_s) <= _DUPLICATE_ELAPSED_TOLERANCE_S:
            return candidate
    return None


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
    same_ride = await _find_same_ride(db, athlete_id, parsed)
    if same_ride is not None:
        return ImportOutcome("duplicate", same_ride)

    file_format = parsed.extra["format"]
    activity, stream = _build_rows(
        athlete_id,
        parsed,
        source=source,
        external_id=external_id,
        data_source_connection_id=data_source_connection_id,
        file_format=file_format,
        file_sha256=sha256,
    )
    try:
        # A savepoint, so losing a race against the same file uploaded twice
        # at once doesn't undo the other files of this request.
        async with db.begin_nested():
            db.add(activity)
            await db.flush()
            stream.activity_id = activity.id
            db.add(stream)
            await db.flush()
    except IntegrityError:
        winner = await db.scalar(
            select(Activity).where(Activity.athlete_id == athlete_id, Activity.file_sha256 == sha256)
        )
        if winner is None:
            raise
        return ImportOutcome("duplicate", winner)

    activity.file_path = await asyncio.to_thread(storage.save_original, athlete_id, sha256, file_format, content)
    return ImportOutcome("created", activity)
