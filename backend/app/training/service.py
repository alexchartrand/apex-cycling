import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
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
    TrackLoopSummary,
    TrackSessionDetail,
    TrackSummary,
    TrackViewSummary,
    ViewTime,
)


def _whole_lap_time_ms(segments: list[LapSegmentTime]) -> int | None:
    """`time_ms` is cumulative elapsed time since lap start at that
    checkpoint (matches sqorz's `lapTimes` 1:1 — see `LapSegmentTime`), so
    the total is just the last checkpoint's (the finish line's) own value,
    not a sum. An earlier missed capture doesn't block this — only the
    last segment's own `time_ms` being null does.
    """
    if not segments:
        return None
    ordered = sorted(segments, key=lambda s: s.sequence_index)
    return ordered[-1].time_ms


def _view_time_ms(segments: list[LapSegmentTime], loop_ids: list[uuid.UUID]) -> int | None:
    """A view's elapsed time is a gate-to-gate subtraction, not a sum: the
    cumulative time at the view's last loop minus the cumulative time at
    the view's own first loop — both are checkpoints with their own
    directly-known cumulative-since-lap-start reading, the same way a
    stopwatch split works off two gate crossings. Uses list position
    rather than `sequence_index` arithmetic since `sequence_index` can be
    sparse.

    A single-loop view (first loop == last loop) has no second gate to
    subtract against, so it's treated as "elapsed since lap start to this
    one checkpoint" — its own raw cumulative value — rather than the
    otherwise-meaningless zero a literal gate-to-gate subtraction would give.

    If the view's first/last loop repeats within this lap (a circuit lap
    passing the same physical checkpoint twice), first-occurrence /
    last-occurrence is a deterministic but not fully disambiguated choice —
    a pre-existing ambiguity (the old loop_id-keyed dict had it too), not
    something this fixes.
    """
    if not loop_ids:
        return None
    ordered = sorted(segments, key=lambda s: s.sequence_index)

    first_loop_id, last_loop_id = loop_ids[0], loop_ids[-1]
    if first_loop_id == last_loop_id:
        pos = _last_index_of(ordered, first_loop_id)
        if pos is None:
            return None
        return ordered[pos].time_ms

    first_pos = _first_index_of(ordered, first_loop_id)
    last_pos = _last_index_of(ordered, last_loop_id)
    if first_pos is None or last_pos is None:
        return None

    start_segment = ordered[first_pos]
    end_segment = ordered[last_pos]
    if start_segment.time_ms is None or end_segment.time_ms is None:
        return None

    return end_segment.time_ms - start_segment.time_ms


def _first_index_of(ordered: list[LapSegmentTime], loop_id: uuid.UUID) -> int | None:
    for i, segment in enumerate(ordered):
        if segment.track_loop_id == loop_id:
            return i
    return None


def _last_index_of(ordered: list[LapSegmentTime], loop_id: uuid.UUID) -> int | None:
    for i in range(len(ordered) - 1, -1, -1):
        if ordered[i].track_loop_id == loop_id:
            return i
    return None


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
    """Converts each segment's raw cumulative `distance_m`/`time_ms` into a
    per-segment delta (this segment's own physical length / duration), via
    two independent running cumulative trackers. Each tracker resets to
    None the instant its underlying cumulative value is unknown for a
    segment, and recovers as soon as a later segment's value is known
    again — so one missing capture blanks exactly the deltas that needed
    it as an endpoint, without corrupting anything further down the lap.
    """
    ordered = sorted(segments, key=lambda s: s.sequence_index)
    result = []
    prev_distance: float | None = 0.0
    prev_time: float | None = 0.0
    for segment in ordered:
        loop_distance = segment.track_loop.distance_m
        cumulative_time = segment.time_ms

        distance_delta = (
            loop_distance - prev_distance
            if (prev_distance is not None and loop_distance is not None)
            else None
        )
        time_delta = (
            cumulative_time - prev_time
            if (prev_time is not None and cumulative_time is not None)
            else None
        )
        result.append(DistancedSegment(distance_m=distance_delta, time_ms=time_delta))
        prev_distance = loop_distance
        prev_time = cumulative_time
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
        ordered_segments = sorted(segments, key=lambda s: s.sequence_index)
        deltas = _segment_deltas(ordered_segments)
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
                    SegmentDetail(sequence_index=s.sequence_index, loop_name=s.track_loop.name, time_ms=d.time_ms)
                    for s, d in zip(ordered_segments, deltas)
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
    """Newest first, with per-session aggregates for list views. Two grouped
    queries (lap stats, track names) rather than loading every lap.
    """
    lap_stats = (
        await db.execute(
            select(
                TrainingEvent.id,
                TrainingEvent.external_event_id,
                TrainingEvent.name,
                TrainingEvent.event_date,
                func.count(TrainingLap.id),
                func.min(TrainingLap.start_time),
                func.max(TrainingLap.start_time),
            )
            .join(EventTrack, EventTrack.training_event_id == TrainingEvent.id)
            .join(TrainingLap, TrainingLap.event_track_id == EventTrack.id)
            .where(TrainingLap.athlete_id == athlete_id)
            .group_by(TrainingEvent.id)
            .order_by(TrainingEvent.event_date.desc(), func.min(TrainingLap.start_time).desc())
        )
    ).all()

    track_rows = (
        await db.execute(
            select(EventTrack.training_event_id, Track.name)
            .join(Track, Track.id == EventTrack.track_id)
            .join(TrainingLap, TrainingLap.event_track_id == EventTrack.id)
            .where(TrainingLap.athlete_id == athlete_id)
            .distinct()
            .order_by(Track.name)
        )
    ).all()
    tracks_by_event: dict[uuid.UUID, list[str]] = {}
    for event_id, track_name in track_rows:
        tracks_by_event.setdefault(event_id, []).append(track_name)

    return [
        SessionSummary(
            external_event_id=external_id,
            event_name=name,
            event_date=event_date,
            lap_count=lap_count,
            track_names=tracks_by_event.get(event_id, []),
            first_lap_at=first_lap_at,
            last_lap_at=last_lap_at,
        )
        for event_id, external_id, name, event_date, lap_count, first_lap_at, last_lap_at in lap_stats
    ]


async def list_athlete_tracks(db: AsyncSession, athlete_id: uuid.UUID) -> list[TrackSummary]:
    tracks = (
        await db.scalars(
            select(Track)
            .join(EventTrack, EventTrack.track_id == Track.id)
            .join(TrainingLap, TrainingLap.event_track_id == EventTrack.id)
            .where(TrainingLap.athlete_id == athlete_id)
            .options(selectinload(Track.views), selectinload(Track.loops))
            .distinct()
            .order_by(Track.name)
        )
    ).all()
    return [
        TrackSummary(
            id=t.id,
            name=t.name,
            views=[TrackViewSummary(id=v.id, name=v.name) for v in t.views],
            length_m=t.length_m,
            loops=sorted(
                (TrackLoopSummary(id=loop.id, name=loop.name, distance_m=loop.distance_m) for loop in t.loops),
                key=lambda loop: (loop.distance_m is None, loop.distance_m if loop.distance_m is not None else 0.0),
            ),
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
