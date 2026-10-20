"""Linking recordings to sqorz sessions, and reading their data back lap by lap.

A session (`TrainingEvent`) is the athlete's private copy of a sqorz day; an
activity is a head-unit recording. They describe the same riding, so one can
carry the other's metrics: the lap table shows the power, heart rate and
cadence the recording holds over each lap. The maths is in `analysis/fusion.py`.
"""

import asyncio
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.activities import streams
from app.activities.metrics_service import visible_conditions
from app.activities.models import Activity, ActivityStream
from app.activities.schemas import SessionSuggestion
from app.analysis import fusion
from app.athletes.models import Athlete
from app.auth.models import User
from app.training.models import EventTrack, TrainingEvent, TrainingLap
from app.training.schemas import EffortDetail, LinkedActivity, SessionDetail
from app.training.service import _whole_lap_time_ms

# A session's window runs from just before its first lap to a lap length after
# its last (laps are recorded at their start).
_BEFORE_FIRST_LAP_S = 30.0
_AFTER_LAST_LAP_S = 90.0
# Offsets are re-estimated for recent rides as more laps arrive from sqorz.
_RECENT = timedelta(days=3)


def _ts(moment: datetime) -> float:
    """Epoch seconds; SQLite hands back naive datetimes that are UTC."""
    return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).timestamp()


# --- finding sessions --------------------------------------------------------


async def session_windows(db: AsyncSession, athlete_id: uuid.UUID) -> dict[uuid.UUID, tuple[float, float]]:
    """Per session, the span of the athlete's laps in epoch seconds."""
    rows = await db.execute(
        select(EventTrack.training_event_id, func.min(TrainingLap.start_time), func.max(TrainingLap.start_time))
        .join(EventTrack, TrainingLap.event_track_id == EventTrack.id)
        .where(TrainingLap.athlete_id == athlete_id)
        .group_by(EventTrack.training_event_id)
    )
    return {
        event_id: (_ts(first) - _BEFORE_FIRST_LAP_S, _ts(last) + _AFTER_LAST_LAP_S) for event_id, first, last in rows
    }


def _match(activity: Activity, windows: dict[uuid.UUID, tuple[float, float]]) -> uuid.UUID | None:
    start = _ts(activity.start_time)
    found = fusion.best_event_match((start, start + activity.elapsed_s), {str(k): v for k, v in windows.items()})
    return uuid.UUID(found) if found else None


async def _lap_windows(db: AsyncSession, athlete_id: uuid.UUID, event_id: uuid.UUID) -> list[tuple[float, float]]:
    """(epoch start, seconds) of each finished lap of a session."""
    laps = await db.scalars(
        select(TrainingLap)
        .join(EventTrack, TrainingLap.event_track_id == EventTrack.id)
        .where(
            EventTrack.training_event_id == event_id,
            TrainingLap.athlete_id == athlete_id,
            TrainingLap.excluded.is_(False),
        )
        .options(selectinload(TrainingLap.segment_times))
    )
    windows = []
    for lap in laps:
        milliseconds = _whole_lap_time_ms(lap.segment_times)
        if milliseconds:
            windows.append((_ts(lap.start_time), milliseconds / 1000))
    return sorted(windows)


async def estimate_offset(
    db: AsyncSession, activity: Activity, event_id: uuid.UUID
) -> fusion.OffsetEstimate | None:
    """How far the device clock is from sqorz's, judged from the speed trace."""
    stream = await db.get(ActivityStream, activity.id)
    if stream is None or stream.speed_mps is None:
        return None
    laps = await _lap_windows(db, activity.athlete_id, event_id)
    origin = _ts(activity.start_time)
    relative = [(start - origin, duration) for start, duration in laps]
    time_s, speed = streams.unpack("time_s", stream.time_s), streams.unpack("speed_mps", stream.speed_mps)
    return await asyncio.to_thread(fusion.estimate_clock_offset, relative, time_s, speed)


# --- linking -----------------------------------------------------------------


async def _auto_link(db: AsyncSession, activity: Activity, event_id: uuid.UUID) -> None:
    activity.training_event_id = event_id
    estimate = await estimate_offset(db, activity, event_id)
    activity.clock_offset_s = estimate.offset_s if estimate and estimate.confident else 0.0


async def auto_link_activity(db: AsyncSession, activity: Activity) -> bool:
    """Links a freshly imported activity to the session it overlaps, if any.
    Doesn't commit."""
    if activity.session_link_manual or activity.training_event_id is not None:
        return False
    event_id = _match(activity, await session_windows(db, activity.athlete_id))
    if event_id is None:
        return False
    await _auto_link(db, activity, event_id)
    return True


async def sync_session_links(db: AsyncSession, athlete_ids: Collection[uuid.UUID]) -> None:
    """After sqorz data arrived: link activities that now have a session, and
    re-estimate the clock offset of recent links (they were made when only
    part of the session had been synced). Never touches links the athlete
    set by hand. Doesn't commit."""
    recent = datetime.now(timezone.utc) - _RECENT
    for athlete_id in athlete_ids:
        windows = await session_windows(db, athlete_id)
        if not windows:
            continue
        pending = await db.scalars(
            select(Activity).where(
                Activity.athlete_id == athlete_id,
                Activity.session_link_manual.is_(False),
                (Activity.training_event_id.is_(None)) | (Activity.start_time >= recent),
            )
        )
        for activity in pending:
            if activity.training_event_id is None:
                event_id = _match(activity, windows)
                if event_id is not None:
                    await _auto_link(db, activity, event_id)
            else:
                estimate = await estimate_offset(db, activity, activity.training_event_id)
                if estimate and estimate.confident:
                    activity.clock_offset_s = estimate.offset_s


async def set_manual_link(
    db: AsyncSession, activity: Activity, event: TrainingEvent, clock_offset_s: float | None
) -> None:
    """The athlete's own choice: sticks until they change it. Doesn't commit."""
    activity.training_event_id = event.id
    activity.session_link_manual = True
    if clock_offset_s is not None:
        activity.clock_offset_s = clock_offset_s
    else:
        estimate = await estimate_offset(db, activity, event.id)
        activity.clock_offset_s = estimate.offset_s if estimate and estimate.confident else 0.0


def unlink(activity: Activity) -> None:
    """Also sticky: auto-linking won't bring it back."""
    activity.training_event_id = None
    activity.clock_offset_s = 0.0
    activity.session_link_manual = True


async def suggest(db: AsyncSession, activity: Activity) -> SessionSuggestion:
    event_id = activity.training_event_id
    if event_id is None:
        event_id = _match(activity, await session_windows(db, activity.athlete_id))
    if event_id is None:
        return SessionSuggestion(
            external_event_id=None, event_name=None, clock_offset_s=None, correlation=None, margin=None,
            laps_used=None, confident=False,
        )  # fmt: skip
    event = await db.get(TrainingEvent, event_id)
    estimate = await estimate_offset(db, activity, event_id)
    return SessionSuggestion(
        external_event_id=event.external_event_id,
        event_name=event.title_override or event.name,
        clock_offset_s=estimate.offset_s if estimate else None,
        correlation=estimate.correlation if estimate else None,
        margin=estimate.margin if estimate else None,
        laps_used=estimate.laps_used if estimate else None,
        confident=bool(estimate and estimate.confident),
    )


# --- reading back --------------------------------------------------------------


@dataclass
class _Recording:
    activity: Activity
    origin: float
    time_s: list[float]
    channels: dict[str, list[float | None]]

    def covers(self, start: float, end: float) -> bool:
        """`start`/`end` in sqorz epoch seconds, against this recording's own clock."""
        first = self.origin + self.activity.clock_offset_s  # sqorz time of the first sample
        return first - 1 <= start and end <= first + self.time_s[-1] + 1

    def mean(self, channel: str, start: float, end: float) -> float | None:
        if channel not in self.channels:
            return None
        shift = self.origin + self.activity.clock_offset_s
        return fusion.window_mean(self.time_s, self.channels[channel], start - shift, end - shift)


async def _recordings(db: AsyncSession, athlete: Athlete, viewer: User, event: TrainingEvent) -> list[_Recording]:
    """The viewer-visible activities linked to the session, with their samples."""
    activities = list(
        await db.scalars(
            select(Activity)
            .where(*visible_conditions(athlete, viewer), Activity.training_event_id == event.id)
            .order_by(Activity.start_time)
        )
    )
    recordings = []
    for activity in activities:
        stream = await db.get(ActivityStream, activity.id)
        if stream is None:
            continue
        channels = {
            name: streams.unpack(name, blob)
            for name in ("power_w", "heart_rate", "cadence")
            if (blob := getattr(stream, name)) is not None
        }
        recordings.append(_Recording(activity, _ts(activity.start_time), streams.unpack("time_s", stream.time_s), channels))
    return recordings


def _averages(recordings: list[_Recording], start: float, end: float) -> tuple[float | None, float | None, float | None]:
    for recording in recordings:
        if recording.covers(start, end):
            return (
                recording.mean("power_w", start, end),
                recording.mean("heart_rate", start, end),
                recording.mean("cadence", start, end),
            )
    return None, None, None


async def _event(db: AsyncSession, athlete: Athlete, external_event_id: str) -> TrainingEvent | None:
    return await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete.id, TrainingEvent.external_event_id == external_event_id
        )
    )


async def add_activity_metrics_to_session(
    db: AsyncSession, athlete: Athlete, viewer: User, detail: SessionDetail
) -> None:
    event = await _event(db, athlete, detail.external_event_id)
    recordings = await _recordings(db, athlete, viewer, event) if event else []
    detail.activities = [
        LinkedActivity(
            id=r.activity.id,
            name=r.activity.name,
            start_time=r.activity.start_time,
            elapsed_s=r.activity.elapsed_s,
            clock_offset_s=r.activity.clock_offset_s,
            has_power="power_w" in r.channels,
            has_heart_rate="heart_rate" in r.channels,
            has_cadence="cadence" in r.channels,
        )
        for r in recordings
    ]
    if not recordings:
        return
    for track in detail.tracks:
        for lap in track.laps:
            if lap.whole_lap_time_ms:
                start = _ts(lap.start_time)
                lap.avg_power_w, lap.avg_heart_rate, lap.avg_cadence = _averages(
                    recordings, start, start + lap.whole_lap_time_ms / 1000
                )


async def add_activity_metrics_to_efforts(
    db: AsyncSession, athlete: Athlete, viewer: User, external_event_id: str, efforts: list[EffortDetail]
) -> None:
    event = await _event(db, athlete, external_event_id)
    recordings = await _recordings(db, athlete, viewer, event) if event else []
    for effort in efforts:
        if recordings and effort.total_time_ms:
            start = _ts(effort.start_time)
            effort.avg_power_w, effort.avg_heart_rate, effort.avg_cadence = _averages(
                recordings, start, start + effort.total_time_ms / 1000
            )
