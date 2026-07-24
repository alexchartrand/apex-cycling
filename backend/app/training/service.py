import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.training.models import EventTrack, LapSegmentTime, Track, TrackView, TrainingEvent, TrainingLap
from app.training.schemas import (
    LapDetail,
    ProgressionMetric,
    ProgressionPoint,
    SegmentDetail,
    SessionDetail,
    SessionSummary,
    TrackSessionDetail,
    TrackSummary,
    TrackViewSummary,
    ViewTime,
)


def _whole_lap_time_ms(segments: list[LapSegmentTime]) -> int | None:
    times = [segment.time_ms for segment in segments]
    if not times or any(t is None for t in times):
        return None
    return sum(times)


def _view_time_ms(segments: list[LapSegmentTime], loop_ids: list[uuid.UUID]) -> int | None:
    if not loop_ids:
        return None
    times_by_loop = {segment.track_loop_id: segment.time_ms for segment in segments}
    total = 0
    for loop_id in loop_ids:
        time_ms = times_by_loop.get(loop_id)
        if time_ms is None:
            return None
        total += time_ms
    return total


@dataclass
class DistancedSegment:
    """One lap segment with its physical length, when knowable. `distance_m`
    is None if either boundary checkpoint's cumulative distance is unknown
    — sqorz only sometimes reports it (see normalizer.py TrackLoop notes).
    """

    distance_m: float | None
    time_ms: int | None


@dataclass
class DistanceWindowResult:
    distance_m: float
    time_ms: int
    start_index: int
    end_index: int


def _segment_deltas(segments: list[LapSegmentTime]) -> list[DistancedSegment]:
    result = []
    prev_cumulative: float | None = 0.0
    for segment in segments:
        loop_distance = segment.track_loop.distance_m
        delta = (
            loop_distance - prev_cumulative
            if (prev_cumulative is not None and loop_distance is not None)
            else None
        )
        result.append(DistancedSegment(distance_m=delta, time_ms=segment.time_ms))
        prev_cumulative = loop_distance
    return result


def find_best_distance_window(
    segments: list[DistancedSegment], target_distance_m: float
) -> DistanceWindowResult | None:
    """Find the contiguous run of segments whose summed distance is closest
    to `target_distance_m`, minimizing summed time among ties. A segment
    with unknown distance or time can't be crossed by any window (see plan
    Data Model, "custom distance").

    Scoped to a single lap's segments (not concatenated across laps): sqorz
    doesn't report a track's total circuit length, so there's no reliable
    way to carry cumulative distance across a lap boundary. Distances
    longer than one lap (e.g. a velodrome pursuit) aren't supported yet.
    """
    best: DistanceWindowResult | None = None
    n = len(segments)
    for start in range(n):
        cum_distance = 0.0
        cum_time = 0
        for end in range(start, n):
            seg = segments[end]
            if seg.distance_m is None or seg.time_ms is None:
                break
            cum_distance += seg.distance_m
            cum_time += seg.time_ms
            diff = abs(cum_distance - target_distance_m)
            if best is None:
                best = DistanceWindowResult(cum_distance, cum_time, start, end)
                continue
            best_diff = abs(best.distance_m - target_distance_m)
            if diff < best_diff or (diff == best_diff and cum_time < best.time_ms):
                best = DistanceWindowResult(cum_distance, cum_time, start, end)
    return best


async def get_session_detail(db: AsyncSession, athlete_id: uuid.UUID, external_event_id: str) -> SessionDetail | None:
    event = await db.scalar(
        select(TrainingEvent).where(
            TrainingEvent.external_event_id == external_event_id, TrainingEvent.athlete_id == athlete_id
        )
    )
    if event is None:
        return None

    laps = (
        await db.scalars(
            select(TrainingLap)
            .join(EventTrack, TrainingLap.event_track_id == EventTrack.id)
            .where(EventTrack.training_event_id == event.id, TrainingLap.athlete_id == athlete_id)
            .options(
                selectinload(TrainingLap.event_track)
                .selectinload(EventTrack.track)
                .selectinload(Track.views)
                .selectinload(TrackView.view_loops),
                selectinload(TrainingLap.segment_times).selectinload(LapSegmentTime.track_loop),
            )
            .order_by(TrainingLap.start_time)
        )
    ).all()

    laps_by_track: dict[uuid.UUID, TrackSessionDetail] = {}
    for lap in laps:
        track = lap.event_track.track
        track_detail = laps_by_track.get(track.id)
        if track_detail is None:
            track_detail = TrackSessionDetail(track_id=track.id, track_name=track.name, laps=[])
            laps_by_track[track.id] = track_detail

        segments = lap.segment_times
        views = [
            ViewTime(
                track_view_id=view.id,
                name=view.name,
                time_ms=_view_time_ms(segments, [vl.track_loop_id for vl in view.view_loops]),
            )
            for view in track.views
        ]
        track_detail.laps.append(
            LapDetail(
                lap_id=lap.id,
                start_time=lap.start_time,
                class_code=lap.class_code,
                start_number=lap.start_number,
                whole_lap_time_ms=_whole_lap_time_ms(segments),
                segments=[
                    SegmentDetail(sequence_index=s.sequence_index, loop_name=s.track_loop.name, time_ms=s.time_ms)
                    for s in segments
                ],
                views=views,
            )
        )

    return SessionDetail(
        external_event_id=event.external_event_id,
        event_name=event.name,
        event_date=event.event_date,
        tracks=list(laps_by_track.values()),
    )


async def list_athlete_sessions(db: AsyncSession, athlete_id: uuid.UUID) -> list[SessionSummary]:
    events = (
        await db.scalars(
            select(TrainingEvent)
            .join(EventTrack, EventTrack.training_event_id == TrainingEvent.id)
            .join(TrainingLap, TrainingLap.event_track_id == EventTrack.id)
            .where(TrainingLap.athlete_id == athlete_id)
            .distinct()
            .order_by(TrainingEvent.event_date.desc())
        )
    ).all()
    return [
        SessionSummary(external_event_id=e.external_event_id, event_name=e.name, event_date=e.event_date)
        for e in events
    ]


async def list_athlete_tracks(db: AsyncSession, athlete_id: uuid.UUID) -> list[TrackSummary]:
    tracks = (
        await db.scalars(
            select(Track)
            .join(EventTrack, EventTrack.track_id == Track.id)
            .join(TrainingLap, TrainingLap.event_track_id == EventTrack.id)
            .where(TrainingLap.athlete_id == athlete_id)
            .options(selectinload(Track.views))
            .distinct()
            .order_by(Track.name)
        )
    ).all()
    return [
        TrackSummary(
            id=t.id,
            name=t.name,
            views=[TrackViewSummary(id=v.id, name=v.name) for v in t.views],
        )
        for t in tracks
    ]


async def _athlete_laps_for_track(
    db: AsyncSession,
    athlete_id: uuid.UUID,
    track_id: uuid.UUID,
    from_date: date | None,
    to_date: date | None,
) -> list[TrainingLap]:
    stmt = (
        select(TrainingLap)
        .join(EventTrack, TrainingLap.event_track_id == EventTrack.id)
        .join(TrainingEvent, EventTrack.training_event_id == TrainingEvent.id)
        .where(TrainingLap.athlete_id == athlete_id, EventTrack.track_id == track_id)
        .options(
            selectinload(TrainingLap.segment_times).selectinload(LapSegmentTime.track_loop),
            selectinload(TrainingLap.event_track).selectinload(EventTrack.training_event),
        )
        .order_by(TrainingLap.start_time)
    )
    if from_date is not None:
        stmt = stmt.where(TrainingEvent.event_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(TrainingEvent.event_date <= to_date)
    return list((await db.scalars(stmt)).all())


async def get_progression(
    db: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    metric: ProgressionMetric,
    track_id: uuid.UUID | None,
    track_view_id: uuid.UUID | None,
    distance_m: float | None,
    from_date: date | None,
    to_date: date | None,
) -> list[ProgressionPoint]:
    """One point per session (`training_event`), taking the best (lowest)
    value achieved that day — see plan Data Model: "a progression view is
    the same metric computed per session and plotted across a date range."
    """
    loop_ids: list[uuid.UUID] = []
    if metric == ProgressionMetric.VIEW:
        view = await db.get(TrackView, track_view_id, options=[selectinload(TrackView.view_loops)])
        if view is None:
            return []
        track_id = view.track_id
        loop_ids = [vl.track_loop_id for vl in view.view_loops]

    laps = await _athlete_laps_for_track(db, athlete_id, track_id, from_date, to_date)

    laps_by_event: dict[uuid.UUID, list[TrainingLap]] = {}
    for lap in laps:
        laps_by_event.setdefault(lap.event_track.training_event_id, []).append(lap)

    points: list[ProgressionPoint] = []
    for event_laps in laps_by_event.values():
        event = event_laps[0].event_track.training_event
        best: ProgressionPoint | None = None

        for lap in event_laps:
            if metric == ProgressionMetric.LAP_TIME:
                candidate_time = _whole_lap_time_ms(lap.segment_times)
                candidate_distance = None
            elif metric == ProgressionMetric.VIEW:
                candidate_time = _view_time_ms(lap.segment_times, loop_ids)
                candidate_distance = None
            else:
                window = find_best_distance_window(_segment_deltas(lap.segment_times), distance_m)
                candidate_time = window.time_ms if window is not None else None
                candidate_distance = window.distance_m if window is not None else None

            if candidate_time is None:
                continue
            if best is None or candidate_time < best.time_ms:
                best = ProgressionPoint(
                    external_event_id=event.external_event_id,
                    event_date=event.event_date,
                    best_lap_id=lap.id,
                    time_ms=candidate_time,
                    achieved_distance_m=candidate_distance,
                )

        if best is not None:
            points.append(best)

    points.sort(key=lambda p: p.event_date)
    return points
