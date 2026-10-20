"""Multi-lap distance windows and the standard track events.

A window is a run of consecutive finished laps inside one effort, so a
4 km pursuit on a 250 m track is the best 16-lap window. Pure functions over
`Effort`; the lap count comes from `Track.length_m`, so a track without a
known length (or a distance that isn't a whole number of laps) has no
multi-lap windows and callers fall back to the single-lap checkpoint search
in `service.find_best_distance_window`.
"""

from dataclasses import dataclass
import uuid

from app.training.efforts import Effort, StartType

# A distance counts as k laps when it's within this of k x track length —
# absorbs a 333.33 m track being entered as 333.3.
LAP_DISTANCE_TOLERANCE_M = 0.5


@dataclass(frozen=True)
class StandardEvent:
    """A distance track cyclists race and keep records for. `distance_m`
    None means one lap of whatever track it's ridden on. `view_name` marks
    an event timed by a track view (sqorz's own named checkpoint group)
    instead of whole laps. `start_types` are the starts records are kept
    for: a flying 200 or a single flying lap is only ever flying, while the
    longer distances are raced both from a standing start and rolling.
    """

    key: str
    distance_m: float | None
    view_name: str | None = None
    start_types: tuple[StartType, ...] = (StartType.STANDING, StartType.FLYING)


STANDARD_EVENTS: tuple[StandardEvent, ...] = (
    StandardEvent("f200", 200, view_name="200m", start_types=(StartType.FLYING,)),
    StandardEvent("lap", None, start_types=(StartType.FLYING,)),
    StandardEvent("500m", 500),
    StandardEvent("750m", 750),
    StandardEvent("1km", 1000),
    StandardEvent("2km", 2000),
    StandardEvent("3km", 3000),
    StandardEvent("4km", 4000),
)

STANDARD_EVENTS_BY_KEY: dict[str, StandardEvent] = {event.key: event for event in STANDARD_EVENTS}


def laps_for_distance(distance_m: float, track_length_m: float | None) -> int | None:
    """How many whole laps make `distance_m`, or None if the track length is
    unknown or the distance isn't a whole number of laps.
    """
    if not track_length_m or distance_m <= 0:
        return None
    lap_count = round(distance_m / track_length_m)
    if lap_count < 1 or abs(lap_count * track_length_m - distance_m) > LAP_DISTANCE_TOLERANCE_M:
        return None
    return lap_count


def event_lap_count(event: StandardEvent, track_length_m: float | None) -> int | None:
    """Laps in a lap-based standard event on this track; None for view-timed
    events and for distances the track can't be ridden as whole laps.
    """
    if event.view_name is not None:
        return None
    if event.distance_m is None:
        return 1
    return laps_for_distance(event.distance_m, track_length_m)


@dataclass(frozen=True)
class LapWindow:
    lap_ids: tuple[uuid.UUID, ...]
    first_lap_index: int  # position within the effort
    time_ms: int
    start_type: StartType


def lap_windows(effort: Effort, lap_count: int) -> list[LapWindow]:
    """Every run of `lap_count` consecutive finished, non-excluded laps in the
    effort. A
    window beginning on the effort's first lap starts the way the effort did
    (standing, flying or unknown); any later window is a rolling start, so
    flying.
    """
    windows = []
    for first in range(len(effort.laps) - lap_count + 1):
        times = effort.lap_times_ms[first : first + lap_count]
        if any(t is None for t in times) or any(lap.excluded for lap in effort.laps[first : first + lap_count]):
            continue
        windows.append(
            LapWindow(
                lap_ids=tuple(lap.lap_id for lap in effort.laps[first : first + lap_count]),
                first_lap_index=first,
                time_ms=sum(times),
                start_type=effort.start_type if first == 0 else StartType.FLYING,
            )
        )
    return windows


def best_lap_window(
    efforts: list[Effort], lap_count: int, start_type: StartType | None = None
) -> LapWindow | None:
    """The fastest window of `lap_count` laps across the efforts, optionally
    only those with the given start type. Earliest wins a tie.
    """
    candidates = [
        window
        for effort in efforts
        for window in lap_windows(effort, lap_count)
        if start_type is None or window.start_type == start_type
    ]
    return min(candidates, key=lambda w: w.time_ms, default=None)
