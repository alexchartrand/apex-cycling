import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.models import DataSourceConnection, DataSourceProvider, TransponderAssignment
from app.training.models import (
    EventClass,
    EventTrack,
    LapSegmentTime,
    Track,
    TrackLoop,
    TrackView,
    TrackViewLoop,
    TrainingEvent,
    TrainingLap,
)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _epoch_ms_to_datetime(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _resolve_athlete(assignments: list[TransponderAssignment], lap_date: date) -> uuid.UUID | None:
    for assignment in assignments:
        if assignment.start_date <= lap_date and (assignment.end_date is None or lap_date <= assignment.end_date):
            return assignment.athlete_id
    return None


async def _upsert_training_event(db: AsyncSession, athlete_id: uuid.UUID, account_id: str, detail: dict) -> TrainingEvent:
    external_event_id = detail["eventId"]
    event = await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.athlete_id == athlete_id,
            TrainingEvent.sqorz_account_id == account_id,
            TrainingEvent.external_event_id == external_event_id,
        )
    )
    if event is None:
        event = TrainingEvent(
            athlete_id=athlete_id,
            sqorz_account_id=account_id,
            external_event_id=external_event_id,
            name="",
            event_date=date.today(),
        )
        db.add(event)

    event.name = detail.get("eventName", external_event_id)
    event.event_date = date.fromisoformat(detail["eventDate"])
    event.sport_type = detail.get("sportType")
    event.start_timestamp = _parse_iso_datetime(detail.get("startTimestamp"))
    event.end_timestamp = _parse_iso_datetime(detail.get("endTimestamp"))
    await db.flush()
    return event


async def _upsert_event_classes(db: AsyncSession, event: TrainingEvent, classes_payload: list[dict]) -> None:
    for class_payload in classes_payload:
        class_code = class_payload.get("classCode")
        if class_code is None:
            continue
        existing = await db.scalar(
            select(EventClass).where(
                EventClass.training_event_id == event.id,
                EventClass.class_code == class_code,
            )
        )
        if existing is None:
            existing = EventClass(training_event_id=event.id, class_code=class_code)
            db.add(existing)
        existing.class_name = class_payload.get("className")
        existing.class_type = class_payload.get("classType")
    await db.flush()


async def _upsert_track(db: AsyncSession, cache: dict, account_id: str, track_payload: dict) -> Track:
    external_track_id = track_payload["trackId"]
    key = (account_id, external_track_id)
    track = cache.get(key)
    if track is None:
        track = await db.scalar(
            select(Track).where(Track.sqorz_account_id == account_id, Track.external_track_id == external_track_id)
        )
        if track is None:
            track = Track(sqorz_account_id=account_id, external_track_id=external_track_id, name="")
            db.add(track)
        cache[key] = track

    track.name = track_payload.get("trackName", external_track_id)
    track.track_type = track_payload.get("trackType")
    track.validation_method = track_payload.get("validationMethod")
    await db.flush()
    return track


async def _get_or_create_loop(
    db: AsyncSession,
    cache: dict,
    track: Track,
    external_loop_id: str,
    name: str | None = None,
    distance: float | None = None,
) -> TrackLoop:
    key = (track.id, external_loop_id)
    loop = cache.get(key)
    if loop is None:
        loop = await db.scalar(
            select(TrackLoop).where(TrackLoop.track_id == track.id, TrackLoop.external_loop_id == external_loop_id)
        )
        if loop is None:
            loop = TrackLoop(track_id=track.id, external_loop_id=external_loop_id, name=name or external_loop_id)
            db.add(loop)
            await db.flush()
        cache[key] = loop

    if name is not None:
        loop.name = name
    # sqorz only sometimes reports distance — never clobber a known value with a later null.
    if distance is not None:
        loop.distance_m = distance
    return loop


async def _upsert_track_loops(db: AsyncSession, cache: dict, track: Track, loops_payload: list[dict]) -> list[TrackLoop]:
    loops = []
    for loop_payload in loops_payload:
        loop = await _get_or_create_loop(
            db,
            cache,
            track,
            loop_payload["loopId"],
            name=loop_payload.get("loopName"),
            distance=loop_payload.get("distance"),
        )
        loops.append(loop)
    await db.flush()
    return loops


async def _upsert_track_views(
    db: AsyncSession, view_cache: dict, loop_cache: dict, track: Track, views_payload: list[dict]
) -> None:
    for view_payload in views_payload:
        external_view_id = view_payload["trackViewId"]
        key = (track.id, external_view_id)
        view = view_cache.get(key)
        if view is None:
            view = await db.scalar(
                select(TrackView).where(
                    TrackView.track_id == track.id, TrackView.external_track_view_id == external_view_id
                )
            )
            if view is None:
                view = TrackView(track_id=track.id, external_track_view_id=external_view_id, name="")
                db.add(view)
                await db.flush()
            view_cache[key] = view

        view.name = view_payload.get("trackViewName", external_view_id)
        view.circuit = bool(view_payload.get("circuit", False))
        await db.flush()

        # Rebuild the view's loop sequence from scratch each time — cheap at
        # this scale and avoids diffing reordered/added/removed loops.
        await db.execute(delete(TrackViewLoop).where(TrackViewLoop.track_view_id == view.id))
        for idx, loop_ref in enumerate(view_payload.get("trackViewLoops") or []):
            loop = await _get_or_create_loop(db, loop_cache, track, loop_ref["loopId"])
            db.add(TrackViewLoop(track_view_id=view.id, track_loop_id=loop.id, sequence_index=idx))
        await db.flush()


async def _upsert_event_track(db: AsyncSession, event: TrainingEvent, track: Track, track_payload: dict) -> EventTrack:
    event_track = await db.scalar(
        select(EventTrack).where(EventTrack.training_event_id == event.id, EventTrack.track_id == track.id)
    )
    if event_track is None:
        event_track = EventTrack(training_event_id=event.id, track_id=track.id)
        db.add(event_track)

    event_track.enabled = bool(track_payload.get("trackEnabled", True))
    event_track.gate = bool(track_payload.get("trackGate", False))
    event_track.start_from = track_payload.get("trackStartFrom")
    await db.flush()
    return event_track


async def _load_assignments_for_transponder(db: AsyncSession, transponder_code: str) -> list[TransponderAssignment]:
    connection = await db.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.provider == DataSourceProvider.SQORZ,
            DataSourceConnection.external_id == transponder_code,
        )
    )
    if connection is None:
        return []
    return list(
        (
            await db.scalars(
                select(TransponderAssignment).where(TransponderAssignment.data_source_connection_id == connection.id)
            )
        ).all()
    )


async def _upsert_training_lap(
    db: AsyncSession,
    event_track: EventTrack,
    loops_in_order: list[TrackLoop],
    athlete_id: uuid.UUID,
    transponder_code: str,
    lap_payload: dict,
) -> None:
    external_lap_id = lap_payload["lapId"]
    start_time = _epoch_ms_to_datetime(lap_payload["startTime"])

    lap = await db.scalar(
        select(TrainingLap).where(
            TrainingLap.event_track_id == event_track.id, TrainingLap.external_lap_id == external_lap_id
        )
    )
    if lap is None:
        lap = TrainingLap(event_track_id=event_track.id, transponder_code=transponder_code, external_lap_id=external_lap_id)
        db.add(lap)

    lap.athlete_id = athlete_id
    lap.class_code = lap_payload.get("classCode")
    lap.start_time = start_time
    lap.from_start = bool(lap_payload.get("fromStart", True))
    lap.start_number = lap_payload.get("startNumber")
    await db.flush()

    existing_segments = {
        segment.sequence_index: segment
        for segment in (
            await db.scalars(select(LapSegmentTime).where(LapSegmentTime.training_lap_id == lap.id))
        ).all()
    }
    for idx, time_ms in enumerate(lap_payload.get("lapTimes") or []):
        if idx >= len(loops_in_order):
            continue
        loop = loops_in_order[idx]
        segment = existing_segments.get(idx)
        if segment is None:
            segment = LapSegmentTime(training_lap_id=lap.id, sequence_index=idx, track_loop_id=loop.id)
            db.add(segment)
        else:
            segment.track_loop_id = loop.id
        segment.time_ms = time_ms
    await db.flush()


async def normalize_snapshot(db: AsyncSession, payload: dict) -> set[uuid.UUID]:
    """Upsert a raw sqorz payload (one transponder's full `eventTrainingDetails`
    history) into the normalized training tables.

    Each `trainingDetail` is owned by exactly one athlete, resolved from
    `TransponderAssignment` windows for this payload's transponder against
    `trainingDetail.eventDate` — entries with no covering assignment are
    dropped entirely (not stored unattributed), so a transponder with no
    assignment yet contributes nothing until one is created. Session/lap
    data (`TrainingEvent` and everything under it) is a private per-athlete
    copy, upserted by `(athlete_id, external_id)`, so re-running this against
    the same payload is idempotent and never duplicates rows.

    Returns the ids of the athletes whose data was written, so callers can
    refresh anything derived from it (e.g. personal records).
    """
    track_cache: dict[tuple[str, str], Track] = {}
    loop_cache: dict[tuple[uuid.UUID, str], TrackLoop] = {}
    view_cache: dict[tuple[uuid.UUID, str], TrackView] = {}

    transponder_code = payload.get("transponderCode")
    assignments = await _load_assignments_for_transponder(db, transponder_code) if transponder_code else []
    attributed_athlete_ids: set[uuid.UUID] = set()

    for event_entry in payload.get("eventTrainingDetails") or []:
        account_id = event_entry.get("accountId")
        detail = event_entry.get("trainingDetail") or {}
        event_date_str = detail.get("eventDate")
        if account_id is None or not detail.get("eventId") or not event_date_str:
            continue

        event_date = date.fromisoformat(event_date_str)
        athlete_id = _resolve_athlete(assignments, event_date)
        if athlete_id is None:
            continue

        attributed_athlete_ids.add(athlete_id)
        training_event = await _upsert_training_event(db, athlete_id, account_id, detail)
        await _upsert_event_classes(db, training_event, detail.get("classes") or [])

        tracks_by_external_id: dict[str, tuple[EventTrack, list[TrackLoop]]] = {}
        for track_payload in detail.get("tracks") or []:
            track = await _upsert_track(db, track_cache, account_id, track_payload)
            loops_in_order = await _upsert_track_loops(db, loop_cache, track, track_payload.get("trackLoops") or [])
            await _upsert_track_views(db, view_cache, loop_cache, track, track_payload.get("trackViews") or [])
            event_track = await _upsert_event_track(db, training_event, track, track_payload)
            tracks_by_external_id[track.external_track_id] = (event_track, loops_in_order)

        for member in detail.get("members") or []:
            if member.get("transponder") != transponder_code:
                continue  # this ingestion run only owns `transponder_code`'s data

            for lap_payload in member.get("trainingLaps") or []:
                entry = tracks_by_external_id.get(lap_payload.get("trackId"))
                if entry is None:
                    continue
                event_track, loops_in_order = entry
                await _upsert_training_lap(db, event_track, loops_in_order, athlete_id, transponder_code, lap_payload)

    return attributed_athlete_ids
