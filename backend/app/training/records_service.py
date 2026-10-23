"""Loads an athlete's laps, computes their results (`records.py`), and
persists / serves personal records and manual results.
"""

import re
import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.training.distances import STANDARD_EVENTS
from app.training.efforts import LapInput, StartType
from app.training.models import EventTrack, LapSegmentTime, ManualResult, PersonalRecord, Track, TrackView, TrainingEvent, TrainingLap
from app.training.records import Result, best_results, running_minimum, session_results
from app.training.schemas import ManualResultRead, ManualResultWrite, RecordEntry
from app.training.service import _lap_input, _view_time_ms

_EVENT_ORDER = {event.key: index for index, event in enumerate(STANDARD_EVENTS)}
_START_ORDER = {StartType.STANDING: 0, StartType.FLYING: 1}


def _normalized(name: str) -> str:
    return re.sub(r"\s+", "", name).casefold()


def _venue_key(venue: str) -> str:
    return venue.strip().casefold()


def _place_key(track_id: uuid.UUID | None, venue: str | None) -> str:
    return f"track:{track_id}" if track_id is not None else f"venue:{_venue_key(venue or '')}"


@dataclass(frozen=True)
class SessionInput:
    """One session's laps on one track, with what `records.session_results`
    needs to score them.
    """

    track_id: uuid.UUID
    track_length_m: float | None
    training_event_id: uuid.UUID
    event_date: date
    laps: list[LapInput]
    view_times_ms: dict[str, dict[uuid.UUID, int | None]]


def view_times_of(track: Track, laps: Iterable[TrainingLap]) -> dict[str, dict[uuid.UUID, int | None]]:
    """Each lap's time for the track view that defines a view-timed standard
    event (the flying 200), keyed by event key. Needs the track's views and
    the laps' segment times loaded.
    """
    laps = list(laps)
    view_times_ms: dict[str, dict[uuid.UUID, int | None]] = {}
    for standard_event in STANDARD_EVENTS:
        if standard_event.view_name is None:
            continue
        view = next((v for v in track.views if _normalized(v.name) == _normalized(standard_event.view_name)), None)
        if view is None:
            continue
        loop_ids = [vl.track_loop_id for vl in view.view_loops]
        view_times_ms[standard_event.key] = {lap.id: _view_time_ms(lap.segment_times, loop_ids) for lap in laps}
    return view_times_ms


async def load_session_inputs(db: AsyncSession, athlete_id: uuid.UUID) -> list[SessionInput]:
    """The athlete's laps grouped per session and track, ready to score."""
    laps = (
        await db.scalars(
            select(TrainingLap)
            .where(TrainingLap.athlete_id == athlete_id)
            .options(
                selectinload(TrainingLap.segment_times).selectinload(LapSegmentTime.track_loop),
                selectinload(TrainingLap.event_track).selectinload(EventTrack.training_event),
                selectinload(TrainingLap.event_track)
                .selectinload(EventTrack.track)
                .selectinload(Track.views)
                .selectinload(TrackView.view_loops),
            )
        )
    ).all()

    laps_by_event_track: dict[uuid.UUID, list[TrainingLap]] = {}
    for lap in laps:
        laps_by_event_track.setdefault(lap.event_track_id, []).append(lap)

    inputs: list[SessionInput] = []
    for event_track_laps in laps_by_event_track.values():
        event_track = event_track_laps[0].event_track
        track, event = event_track.track, event_track.training_event

        view_times_ms = view_times_of(track, event_track_laps)

        inputs.append(
            SessionInput(
                track_id=track.id,
                track_length_m=track.length_m,
                training_event_id=event.id,
                event_date=event.event_date,
                laps=[_lap_input(lap) for lap in event_track_laps],
                view_times_ms=view_times_ms,
            )
        )
    return inputs


def results_of(inputs: Iterable[SessionInput]) -> list[Result]:
    return [
        result
        for item in inputs
        for result in session_results(
            track_id=item.track_id,
            track_length_m=item.track_length_m,
            training_event_id=item.training_event_id,
            event_date=item.event_date,
            laps=item.laps,
            view_times_ms=item.view_times_ms,
        )
    ]


async def compute_results(db: AsyncSession, athlete_id: uuid.UUID) -> list[Result]:
    """Every session's best result per event, for all of the athlete's laps."""
    return results_of(await load_session_inputs(db, athlete_id))


async def recompute_personal_records(db: AsyncSession, athlete_id: uuid.UUID) -> None:
    """Rebuilds the athlete's `personal_records` from their laps: updates
    changed rows in place, adds new ones, drops records whose laps are gone.
    Doesn't commit.
    """
    best = {result.key: result for result in best_results(await compute_results(db, athlete_id))}
    existing = {
        (row.track_id, row.event_key, StartType(row.start_type)): row
        for row in (await db.scalars(select(PersonalRecord).where(PersonalRecord.athlete_id == athlete_id))).all()
    }

    for key, result in best.items():
        row = existing.pop(key, None)
        if row is None:
            row = PersonalRecord(
                athlete_id=athlete_id,
                track_id=result.track_id,
                event_key=result.event_key,
                start_type=result.start_type.value,
            )
            db.add(row)
        row.time_ms = result.time_ms
        row.achieved_on = result.event_date
        row.training_event_id = result.training_event_id
        row.training_lap_id = result.lap_id
    for stale in existing.values():
        await db.delete(stale)
    await db.flush()


async def recompute_many(db: AsyncSession, athlete_ids: Collection[uuid.UUID]) -> None:
    for athlete_id in athlete_ids:
        await recompute_personal_records(db, athlete_id)


def _manual_entry(row: ManualResult, track_name: str | None) -> RecordEntry:
    return RecordEntry(
        place=track_name or row.venue or "",
        track_id=row.track_id,
        event_key=row.event_key,
        start_type=StartType(row.start_type),
        time_ms=row.time_ms,
        achieved_on=row.achieved_on,
        source="manual",
        is_competition=row.is_competition,
        manual_result_id=row.id,
    )


async def _manual_entries(db: AsyncSession, athlete_id: uuid.UUID) -> list[RecordEntry]:
    rows = (
        await db.execute(
            select(ManualResult, Track.name)
            .outerjoin(Track, Track.id == ManualResult.track_id)
            .where(ManualResult.athlete_id == athlete_id)
        )
    ).all()
    return [_manual_entry(row, track_name) for row, track_name in rows]


def _entry_sort_key(entry: RecordEntry) -> tuple:
    return (entry.place.casefold(), _EVENT_ORDER.get(entry.event_key, 99), _START_ORDER[entry.start_type])


async def get_records_board(db: AsyncSession, athlete_id: uuid.UUID) -> list[RecordEntry]:
    """The athlete's best per place, event and start type, over computed
    records and manual results.
    """
    computed = (
        await db.execute(
            select(PersonalRecord, Track.name, TrainingEvent.external_event_id)
            .join(Track, Track.id == PersonalRecord.track_id)
            .join(TrainingEvent, TrainingEvent.id == PersonalRecord.training_event_id)
            .where(PersonalRecord.athlete_id == athlete_id)
        )
    ).all()
    entries = [
        RecordEntry(
            place=track_name,
            track_id=row.track_id,
            event_key=row.event_key,
            start_type=StartType(row.start_type),
            time_ms=row.time_ms,
            achieved_on=row.achieved_on,
            source="sqorz",
            external_event_id=external_event_id,
            lap_id=row.training_lap_id,
        )
        for row, track_name, external_event_id in computed
    ] + await _manual_entries(db, athlete_id)

    best: dict[tuple[str, str, StartType], RecordEntry] = {}
    for entry in sorted(entries, key=lambda e: e.achieved_on):
        key = (_place_key(entry.track_id, entry.place if entry.track_id is None else None), entry.event_key, entry.start_type)
        current = best.get(key)
        if current is None or entry.time_ms < current.time_ms:
            best[key] = entry
    return sorted(best.values(), key=_entry_sort_key)


async def get_record_history(
    db: AsyncSession,
    athlete_id: uuid.UUID,
    *,
    event_key: str,
    start_type: StartType,
    track_id: uuid.UUID | None,
    venue: str | None,
) -> list[RecordEntry]:
    """Every result that set a new best for the event and start type,
    oldest first. Scoped to one track or manual venue when given, otherwise
    across all places.
    """
    tracks_by_id: dict[uuid.UUID, str] = {}
    entries: list[RecordEntry] = []

    if venue is None:
        results = [
            r
            for r in await compute_results(db, athlete_id)
            if r.event_key == event_key and r.start_type == start_type and (track_id is None or r.track_id == track_id)
        ]
        if results:
            tracks_by_id = {
                t.id: t.name for t in (await db.scalars(select(Track).where(Track.id.in_({r.track_id for r in results})))).all()
            }
            external_ids = dict(
                (
                    await db.execute(
                        select(TrainingEvent.id, TrainingEvent.external_event_id).where(
                            TrainingEvent.id.in_({r.training_event_id for r in results})
                        )
                    )
                ).all()
            )
            entries += [
                RecordEntry(
                    place=tracks_by_id[r.track_id],
                    track_id=r.track_id,
                    event_key=r.event_key,
                    start_type=r.start_type,
                    time_ms=r.time_ms,
                    achieved_on=r.event_date,
                    source="sqorz",
                    external_event_id=external_ids[r.training_event_id],
                    lap_id=r.lap_id,
                )
                for r in sorted(results, key=lambda r: r.achieved_at)
            ]

    for entry in await _manual_entries(db, athlete_id):
        if entry.event_key != event_key or entry.start_type != start_type:
            continue
        if track_id is not None and entry.track_id != track_id:
            continue
        if venue is not None and (entry.track_id is not None or _venue_key(entry.place) != _venue_key(venue)):
            continue
        entries.append(entry)

    # Stable sort: within a day, computed results (already in lap order) stay before manual ones.
    entries.sort(key=lambda e: e.achieved_on)
    return running_minimum(entries, lambda e: e.time_ms)


async def _read_manual(db: AsyncSession, row: ManualResult) -> ManualResultRead:
    track_name = await db.scalar(select(Track.name).where(Track.id == row.track_id)) if row.track_id else None
    return ManualResultRead(
        id=row.id,
        event_key=row.event_key,
        start_type=StartType(row.start_type),
        time_ms=row.time_ms,
        achieved_on=row.achieved_on,
        track_id=row.track_id,
        venue=row.venue,
        place=track_name or row.venue or "",
        is_competition=row.is_competition,
        notes=row.notes,
    )


class UnknownTrackError(Exception):
    pass


async def _apply_manual(db: AsyncSession, row: ManualResult, payload: ManualResultWrite) -> None:
    if payload.track_id is not None and await db.get(Track, payload.track_id) is None:
        raise UnknownTrackError(str(payload.track_id))
    row.event_key = payload.event_key
    row.start_type = payload.start_type.value
    row.time_ms = payload.time_ms
    row.achieved_on = payload.achieved_on
    row.track_id = payload.track_id
    # A track names the place; a venue alongside it would only go stale.
    row.venue = None if payload.track_id is not None else payload.venue
    row.is_competition = payload.is_competition
    row.notes = payload.notes


async def list_manual_results(db: AsyncSession, athlete_id: uuid.UUID) -> list[ManualResultRead]:
    rows = (
        await db.scalars(
            select(ManualResult)
            .where(ManualResult.athlete_id == athlete_id)
            .order_by(ManualResult.achieved_on.desc(), ManualResult.created_at.desc())
        )
    ).all()
    return [await _read_manual(db, row) for row in rows]


async def create_manual_result(db: AsyncSession, athlete_id: uuid.UUID, payload: ManualResultWrite) -> ManualResultRead:
    row = ManualResult(athlete_id=athlete_id)
    await _apply_manual(db, row, payload)
    db.add(row)
    await db.commit()
    return await _read_manual(db, row)


async def update_manual_result(
    db: AsyncSession, athlete_id: uuid.UUID, result_id: uuid.UUID, payload: ManualResultWrite
) -> ManualResultRead | None:
    row = await db.get(ManualResult, result_id)
    if row is None or row.athlete_id != athlete_id:
        return None
    await _apply_manual(db, row, payload)
    await db.commit()
    return await _read_manual(db, row)


async def delete_manual_result(db: AsyncSession, athlete_id: uuid.UUID, result_id: uuid.UUID) -> bool:
    row = await db.get(ManualResult, result_id)
    if row is None or row.athlete_id != athlete_id:
        return False
    await db.delete(row)
    await db.commit()
    return True
