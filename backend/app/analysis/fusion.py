"""Joining a head-unit recording to sqorz timing — pure functions.

Both sides describe the same laps: sqorz knows when each lap started and how
long it took, the head unit knows what speed and power were happening. Times
here are seconds on the activity's own clock unless said otherwise; the
clock offset is what gets added to a device time to reach sqorz time.
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from app.analysis.metrics import MAX_SAMPLE_GAP_S

# The offset search covers a device whose clock is this far off either way.
MAX_OFFSET_S = 300.0
_COARSE_STEP_S = 2.0
_FINE_STEP_S = 0.25
# Fewer laps than this can't tell a clock offset from chance.
MIN_LAPS = 6
# Laps this far outside the session's typical lap time are timing glitches
# (a missed crossing leaves a 6 s "lap"), not riding the head unit could echo.
_TYPICAL_LAP_RANGE = (0.5, 2.5)
# Lap times that hardly vary (steady riding) carry no alignment information.
MIN_SPEED_VARIATION = 0.03
# Lap speeds change smoothly, so offsets near the best also correlate well:
# only offsets further away than this count as rivals for `margin`.
_PEAK_WIDTH_S = 30.0


def window_mean(
    time_s: Sequence[float],
    values: Sequence[float | None],
    start: float,
    end: float,
    *,
    min_coverage: float = 0.5,
) -> float | None:
    """Average of a sampled signal over [start, end), each reading held until
    the next (or for one second before a pause). Missing readings and uncovered
    time don't count; None when less than `min_coverage` of the window has data."""
    if end <= start or not time_s:
        return None
    n = len(time_s)
    total = covered = 0.0
    i = max(bisect_right(time_s, start) - 1, 0)
    while i < n and time_s[i] < end:
        gap = time_s[i + 1] - time_s[i] if i + 1 < n else 1.0
        hold = gap if gap <= MAX_SAMPLE_GAP_S else 1.0
        seconds = min(time_s[i] + hold, end) - max(time_s[i], start)
        if seconds > 0 and values[i] is not None:
            covered += seconds
            total += values[i] * seconds
        i += 1
    return total / covered if covered >= min_coverage * (end - start) else None


def best_event_match(
    activity: tuple[float, float],
    windows: dict[str, tuple[float, float]],
    *,
    tolerance_s: float = 300.0,
) -> str | None:
    """The session window the activity most overlaps, or None. `activity` and
    the windows are (start, end) on one time axis. The activity is widened by
    `tolerance_s` (clocks are never exact), and a session only counts if the
    ride covers at least half of its window."""
    start, end = activity[0] - tolerance_s, activity[1] + tolerance_s
    best_key, best_overlap = None, 0.0
    for key, (window_start, window_end) in windows.items():
        overlap = min(end, window_end) - max(start, window_start)
        if overlap >= 0.5 * (window_end - window_start) and overlap > best_overlap:
            best_key, best_overlap = key, overlap
    return best_key


@dataclass(frozen=True)
class OffsetEstimate:
    offset_s: float
    # Pearson r between the head unit's lap speeds and sqorz's at that offset.
    correlation: float
    # How far r beats the best offset more than 30 s away; small = ambiguous.
    margin: float
    laps_used: int

    @property
    def confident(self) -> bool:
        return self.correlation >= 0.9 and self.margin >= 0.1


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 1e-12 or var_y <= 1e-12:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / math.sqrt(var_x * var_y)


def estimate_clock_offset(
    laps: Sequence[tuple[float, float]],
    time_s: Sequence[float],
    speed_mps: Sequence[float | None],
) -> OffsetEstimate | None:
    """Finds the offset that makes the head unit's speed over each sqorz lap
    follow sqorz's lap speeds (1 / lap time — the track length cancels in a
    correlation). `laps` are (start, duration) in sqorz seconds measured from
    the activity's start. None when there are too few laps, their times hardly
    vary, or no offset lines up well enough to be worth proposing."""
    laps = [(start, duration) for start, duration in laps if duration > 0]
    if len(laps) < MIN_LAPS:
        return None
    durations = sorted(duration for _, duration in laps)
    typical = durations[len(durations) // 2]
    low, high = (typical * factor for factor in _TYPICAL_LAP_RANGE)
    laps = [(start, duration) for start, duration in laps if low <= duration <= high]
    if len(laps) < MIN_LAPS:
        return None
    sqorz_speed = [1 / duration for _, duration in laps]
    mean_speed = sum(sqorz_speed) / len(sqorz_speed)
    spread = math.sqrt(sum((v - mean_speed) ** 2 for v in sqorz_speed) / len(sqorz_speed))
    if spread / mean_speed < MIN_SPEED_VARIATION:
        return None
    needed = max(MIN_LAPS, math.ceil(0.8 * len(laps)))

    def correlation_at(offset: float) -> tuple[float, int] | None:
        measured, expected = [], []
        for (start, duration), wanted in zip(laps, sqorz_speed):
            mean = window_mean(time_s, speed_mps, start - offset, start - offset + duration, min_coverage=0.8)
            if mean is not None:
                measured.append(mean)
                expected.append(wanted)
        if len(measured) < needed:
            return None
        r = _pearson(measured, expected)
        return None if r is None else (r, len(measured))

    coarse: dict[float, tuple[float, int]] = {}
    offset = -MAX_OFFSET_S
    while offset <= MAX_OFFSET_S:
        result = correlation_at(offset)
        if result is not None:
            coarse[offset] = result
        offset += _COARSE_STEP_S
    if not coarse:
        return None
    centre = max(coarse, key=lambda o: coarse[o][0])

    best_offset, (best_r, used) = centre, coarse[centre]
    offset = centre - _COARSE_STEP_S
    while offset <= centre + _COARSE_STEP_S:
        result = correlation_at(offset)
        if result is not None and result[0] > best_r:
            best_offset, (best_r, used) = offset, result
        offset += _FINE_STEP_S

    rivals = [r for o, (r, _) in coarse.items() if abs(o - best_offset) > _PEAK_WIDTH_S]
    margin = best_r - max(rivals) if rivals else best_r
    return OffsetEstimate(offset_s=round(best_offset, 2), correlation=best_r, margin=margin, laps_used=used)
