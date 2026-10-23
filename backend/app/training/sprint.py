"""Sprint metrics from checkpoint times: top speed over the fastest stretch
between two checkpoints whose position is known, and the standing start's
launch (time to the first such checkpoint, average acceleration).

Pure functions over `LapInput`. Where a checkpoint sits comes from, in order:
the loop's own `distance_m` (cumulative from the start line, only sometimes
reported by sqorz), else its name — sqorz tracks name the sprint gates after
the distance left to the finish ("200m", "100m", "50m") and the last one is
the finish itself. Names alone give distances *relative to the finish*, which
is enough for a top speed; the launch needs the track's length to know how far
the first gate is from the start line.
"""

import re
import uuid
from dataclasses import dataclass

from app.training.efforts import CheckpointCrossing, Effort, LapInput, StartType

# Two gates closer than this make a speed too noisy to quote (±10 ms on 10 m
# is ±3 km/h at 70 km/h; on 50 m it is ±0.7).
MIN_SPEED_SEGMENT_M = 20.0
# Above this a reading is a capture error (a missed gate making two seem close).
MAX_PLAUSIBLE_SPEED_KMH = 120.0

_REMAINING_RE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*m\s*$", re.IGNORECASE)
_FINISH_RE = re.compile(r"^\s*(finish|arriv[ée]e|fin)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class SprintStats:
    peak_speed_kmh: float | None = None
    peak_speed_lap_id: uuid.UUID | None = None
    # Standing start only: time from the start to the first gate with a known
    # position, how far that is, and the constant acceleration from rest that
    # covers it (2·d/t²) — an average, not a peak.
    launch_time_ms: int | None = None
    launch_distance_m: float | None = None
    launch_accel_ms2: float | None = None


def _position_m(crossing: CheckpointCrossing, track_length_m: float | None) -> float | None:
    """Metres from the start line, or — with no track length and no recorded
    distance — metres relative to the finish line (≤ 0). `None` when the gate
    can't be placed. The two scales never mix inside one lap, which is all a
    difference between gates needs.
    """
    if crossing.distance_m is not None and track_length_m:
        return crossing.distance_m
    remaining = _REMAINING_RE.match(crossing.loop_name)
    if remaining:
        left = float(remaining.group(1).replace(",", "."))
        return track_length_m - left if track_length_m else -left
    if _FINISH_RE.match(crossing.loop_name):
        return track_length_m if track_length_m else 0.0
    return None


def positioned_crossings(lap: LapInput, track_length_m: float | None) -> list[tuple[float, int]]:
    """`(position_m, time_ms)` of the lap's gates that have both, in lap order."""
    found = []
    for crossing in lap.crossings:
        if crossing.time_ms is None:
            continue
        position = _position_m(crossing, track_length_m)
        if position is not None:
            found.append((position, crossing.time_ms))
    return found


def _fastest_stretch(lap: LapInput, track_length_m: float | None) -> float | None:
    """The lap's best speed in km/h between consecutive placed gates."""
    gates = positioned_crossings(lap, track_length_m)
    best = None
    for (from_m, from_ms), (to_m, to_ms) in zip(gates, gates[1:]):
        distance_m, time_s = to_m - from_m, (to_ms - from_ms) / 1000
        if distance_m < MIN_SPEED_SEGMENT_M or time_s <= 0:
            continue
        speed = distance_m / time_s * 3.6
        if speed <= MAX_PLAUSIBLE_SPEED_KMH and (best is None or speed > best):
            best = speed
    return best


def _launch(effort: Effort, track_length_m: float | None) -> tuple[int, float, float] | None:
    if effort.start_type != StartType.STANDING or not track_length_m:
        return None
    first = effort.laps[0]
    if not first.from_start:
        return None
    for position, time_ms in positioned_crossings(first, track_length_m):
        if 0 < position < track_length_m and time_ms > 0:
            time_s = time_ms / 1000
            return time_ms, position, 2 * position / time_s**2
    return None


def sprint_stats(effort: Effort, track_length_m: float | None) -> SprintStats:
    peak, peak_lap = None, None
    for lap in effort.laps:
        if lap.excluded:
            continue
        speed = _fastest_stretch(lap, track_length_m)
        if speed is not None and (peak is None or speed > peak):
            peak, peak_lap = speed, lap.lap_id
    launch = _launch(effort, track_length_m)
    return SprintStats(
        peak_speed_kmh=peak,
        peak_speed_lap_id=peak_lap,
        launch_time_ms=launch[0] if launch else None,
        launch_distance_m=launch[1] if launch else None,
        launch_accel_ms2=launch[2] if launch else None,
    )
