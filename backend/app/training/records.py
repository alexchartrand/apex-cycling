"""Personal records, as pure functions.

A `Result` is an athlete's best performance of one standard event, on one
track, from one start type, within one session. An all-time record is the
best result across sessions; the record history is the chain of results that
each beat everything before them. `records_service.py` loads laps and
persists; the decisions about what counts live here.

Start types are only standing or flying here: a window whose start couldn't
be classified (see `efforts.StartType.UNKNOWN`) counts as flying, since a
rider is only called standing on positive evidence.
"""

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TypeVar

from app.training.distances import STANDARD_EVENTS, event_lap_count, lap_windows
from app.training.efforts import LapInput, StartType, detect_efforts

T = TypeVar("T")


@dataclass(frozen=True)
class Result:
    track_id: uuid.UUID
    event_key: str
    start_type: StartType  # STANDING or FLYING
    time_ms: int
    training_event_id: uuid.UUID
    event_date: date
    lap_id: uuid.UUID  # first lap of the performance
    achieved_at: datetime  # start of that lap, for ordering within a day

    @property
    def key(self) -> tuple[uuid.UUID, str, StartType]:
        return (self.track_id, self.event_key, self.start_type)


def session_results(
    *,
    track_id: uuid.UUID,
    track_length_m: float | None,
    training_event_id: uuid.UUID,
    event_date: date,
    laps: list[LapInput],
    view_times_ms: Mapping[str, Mapping[uuid.UUID, int | None]],
) -> list[Result]:
    """The athlete's best result per (standard event, start type) from one
    session's laps on one track.

    `view_times_ms[event_key][lap_id]` is each lap's time for the track view
    that defines a view-timed event (the flying 200), already computed by the
    caller. The first lap of a standing start never counts for the flying
    200 — it isn't flying. Excluded laps never count.
    """
    efforts = detect_efforts(laps, track_length_m)
    laps_by_id = {lap.lap_id: lap for lap in laps}
    best: dict[tuple[str, StartType], Result] = {}

    def offer(event_key: str, start_type: StartType, time_ms: int, first_lap: LapInput) -> None:
        if time_ms <= 0:
            return
        current = best.get((event_key, start_type))
        if current is None or time_ms < current.time_ms:
            best[(event_key, start_type)] = Result(
                track_id=track_id,
                event_key=event_key,
                start_type=start_type,
                time_ms=time_ms,
                training_event_id=training_event_id,
                event_date=event_date,
                lap_id=first_lap.lap_id,
                achieved_at=first_lap.start_time,
            )

    for event in STANDARD_EVENTS:
        if event.view_name is not None:
            lap_times = view_times_ms.get(event.key, {})
            for effort in efforts:
                for index, lap in enumerate(effort.laps):
                    time_ms = lap_times.get(lap.lap_id)
                    if time_ms is None or lap.excluded or (index == 0 and effort.start_type == StartType.STANDING):
                        continue
                    offer(event.key, StartType.FLYING, time_ms, lap)
            continue

        lap_count = event_lap_count(event, track_length_m)
        if lap_count is None:
            continue
        for effort in efforts:
            for window in lap_windows(effort, lap_count):
                start_type = StartType.FLYING if window.start_type == StartType.UNKNOWN else window.start_type
                if start_type in event.start_types:
                    offer(event.key, start_type, window.time_ms, laps_by_id[window.lap_ids[0]])

    return list(best.values())


def best_results(results: Sequence[Result]) -> list[Result]:
    """All-time best per (track, event, start type); the earliest wins a tie."""
    best: dict[tuple[uuid.UUID, str, StartType], Result] = {}
    for result in sorted(results, key=lambda r: r.achieved_at):
        current = best.get(result.key)
        if current is None or result.time_ms < current.time_ms:
            best[result.key] = result
    return list(best.values())


def running_minimum(chronological: Sequence[T], time_of: Callable[[T], int]) -> list[T]:
    """Of items in chronological order, the ones that each beat every earlier
    one — the step line of a record's history.
    """
    steps: list[T] = []
    best: int | None = None
    for item in chronological:
        time_ms = time_of(item)
        if best is None or time_ms < best:
            steps.append(item)
            best = time_ms
    return steps
