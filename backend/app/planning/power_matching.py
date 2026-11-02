"""Planned vs ridden for a workout's power steps: where each step was ridden
in a recording, and whether its mean power (and cadence) was on target.

Pure functions over 1 Hz series (`metrics.resample_1hz`, seconds from the
start of the recording). A recording keeps no step markers, so the workout is
laid over the power trace: steps follow each other back to back — a timed
step lasts its time, a distance (or lap, or event) step until the recorded
distance has grown by it, else its nominal duration (`structure.step_duration_s`)
— and each run of steps between open steps (they end on the lap button, so
their length is unknown) is slid along the recording to where its power
targets fit best: least squares between the target's middle and the power
over the seconds that have a target, seconds past the end counting as 0 W.
The first run may start anywhere in the recording, a later one up to
`MAX_OPEN_STEP_S` after the run before it ends. An open step spans the gap
between its neighbours (from the start of the recording, or to its end,
when it opens or closes the workout). A run without a power target in watts
isn't searched: it starts where the previous one ended.

A pause in the middle of a run shifts every step after it, which this
doesn't follow; the steps' own figures then show it as a miss.
"""

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from app.workouts.export.fit import SINGLE_TARGET_SPREAD
from app.workouts.schemas import WorkoutStep
from app.workouts.structure import step_distance_m, step_duration_s

# The longest an open step (lap button) between two runs of steps is looked for.
MAX_OPEN_STEP_S = 30 * 60
# Step placements tried per run before refining around the best (keeps a long
# recording under a big unrolled workout to about a second).
_SEARCH_BUDGET = 300_000
# A step counts as ridden when the recording covers at least this much of it.
MIN_COVERAGE = 0.5


class StepStatus(str, Enum):
    HIT = "hit"  # the mean is inside the target
    UNDER = "under"
    OVER = "over"
    NOT_RIDDEN = "not_ridden"  # the step falls (mostly) outside the recording
    UNMEASURED = "unmeasured"  # a % FTP target without an FTP, or no such channel


@dataclass(frozen=True)
class StepOutcome:
    step_index: int  # position in riding order, repeats unrolled (0-based)
    step: WorkoutStep
    # The target in watts (low, high); None without one, or for % FTP without an FTP.
    power_target_w: tuple[float, float] | None
    # Seconds from the start of the recording; None when it couldn't be placed.
    start_s: int | None
    end_s: int | None
    avg_power_w: float | None
    avg_cadence: float | None
    # None when the step has no target of that kind.
    power_status: StepStatus | None
    cadence_status: StepStatus | None


def power_target_w(step: WorkoutStep, ftp_w: float | None) -> tuple[float, float] | None:
    if step.power is None:
        return None
    high = step.power.high if step.power.high is not None else step.power.low
    if step.power.unit == "watts":
        return step.power.low, high
    if ftp_w is None:
        return None
    return step.power.low / 100 * ftp_w, high / 100 * ftp_w


def _accepted(low: float, high: float | None) -> tuple[float, float]:
    """A range as written; a single value ± `SINGLE_TARGET_SPREAD`, as the
    head unit was given it (`export/fit.py`)."""
    if high is None or high == low:
        return low * (1 - SINGLE_TARGET_SPREAD), low * (1 + SINGLE_TARGET_SPREAD)
    return low, high


def _status(value: float | None, low: float, high: float) -> StepStatus:
    if value is None:
        return StepStatus.NOT_RIDDEN
    if value < low:
        return StepStatus.UNDER
    if value > high:
        return StepStatus.OVER
    return StepStatus.HIT


def cumulative_distance_1hz(time_s: Sequence[float], distance_m: Sequence[float | None]) -> list[float]:
    """Distance at each whole second, the latest reading held and never going
    back (a device resetting or dropping out doesn't undo distance ridden)."""
    if not time_s:
        return []
    series: list[float] = []
    i, latest = 0, 0.0
    for second in range(int(time_s[-1]) + 1):
        while i < len(time_s) and time_s[i] <= second:
            if distance_m[i] is not None:
                latest = max(latest, distance_m[i])
            i += 1
        series.append(latest)
    return series


class _Recording:
    def __init__(self, power: Sequence[float], distance: Sequence[float] | None):
        self.length = len(power)
        # A trainer without a speed sensor records a distance that never grows.
        self.distance = distance if distance and distance[-1] > 0 else None
        self.sums = [0.0]
        self.squares = [0.0]
        for value in power:
            self.sums.append(self.sums[-1] + value)
            self.squares.append(self.squares[-1] + value * value)

    def end_of(self, step: WorkoutStep, start: int, track_length_m: float) -> int:
        """The second the step ends when it starts at `start`."""
        if step.duration_s is not None:
            return start + step.duration_s
        nominal = max(round(step_duration_s(step, track_length_m)), 1)
        distance = step_distance_m(step, track_length_m)
        if not self.distance or start >= len(self.distance):
            return start + nominal
        goal = self.distance[start] + distance
        reached = bisect_left(self.distance, goal, lo=start)
        if reached < len(self.distance):
            return max(reached, start + 1)
        # Not reached by the end: the rest at the nominal pace.
        missing = (goal - self.distance[-1]) / distance
        return len(self.distance) + round(missing * nominal)

    def squared_error(self, start: int, end: int, target: float) -> float:
        """Σ (power − target)² over [start, end), 0 W past the end of the recording."""
        inside = min(end, self.length)
        error = 0.0
        if inside > start:
            total = self.sums[inside] - self.sums[start]
            squares = self.squares[inside] - self.squares[start]
            error = squares - 2 * target * total + (inside - start) * target * target
        return error + max(end - max(start, self.length), 0) * target * target


def _is_open(step: WorkoutStep) -> bool:
    return step.duration_s is None and step_distance_m(step, 1.0) is None


def _blocks(steps: Sequence[WorkoutStep]) -> list[list[int]]:
    """The indexes of steps, cut into runs at each open step (alone in its own run)."""
    blocks: list[list[int]] = []
    current: list[int] = []
    for index, step in enumerate(steps):
        if _is_open(step):
            if current:
                blocks.append(current)
            blocks.append([index])
            current = []
        else:
            current.append(index)
    if current:
        blocks.append(current)
    return blocks


def _walk(
    recording: _Recording, steps: Sequence[WorkoutStep], block: list[int], start: int, track_length_m: float
) -> list[tuple[int, int]]:
    windows = []
    for index in block:
        end = recording.end_of(steps[index], start, track_length_m)
        windows.append((start, end))
        start = end
    return windows


def _fit(
    recording: _Recording,
    steps: Sequence[WorkoutStep],
    block: list[int],
    targets: Sequence[tuple[float, float] | None],
    earliest: int,
    latest: int,
    track_length_m: float,
) -> int:
    """The start of the run in [earliest, latest] where its targets fit best:
    a grid coarse enough to stay within `_SEARCH_BUDGET` step placements,
    then halving steps around the best point of it."""
    if all(targets[index] is None for index in block):
        return earliest
    latest = max(latest, earliest)

    def error_at(start: int) -> float:
        error = seconds = 0.0
        for index, (a, b) in zip(block, _walk(recording, steps, block, start, track_length_m)):
            target = targets[index]
            if target is not None:
                error += recording.squared_error(a, b, (target[0] + target[1]) / 2)
                seconds += b - a
        return error / max(seconds, 1.0)

    stride = max(1, -(-(latest - earliest + 1) * len(block) // _SEARCH_BUDGET))
    best = min(range(earliest, latest + 1, stride), key=error_at)  # the earliest of equals
    best_error = error_at(best)
    while stride > 1:
        stride = (stride + 1) // 2
        for candidate in (best - stride, best + stride):
            if earliest <= candidate <= latest and (error := error_at(candidate)) < best_error:
                best, best_error = candidate, error
    return best


def place_steps(
    steps: Sequence[WorkoutStep],
    power: Sequence[float],
    distance: Sequence[float] | None,
    *,
    ftp_w: float | None,
    track_length_m: float,
) -> list[tuple[int, int] | None]:
    """[start, end) of each step in seconds of the recording, in riding order
    (`structure.expand`); None for an open step with no room between its
    neighbours."""
    recording = _Recording(power, distance)
    targets = [power_target_w(step, ftp_w) for step in steps]
    windows: list[tuple[int, int] | None] = [None] * len(steps)
    cursor = 0
    placed = False  # a run has been placed: the next one comes after it
    pending_open: int | None = None  # an open step waiting for the next run to start
    for block in _blocks(steps):
        if _is_open(steps[block[0]]):
            if pending_open is None:
                pending_open = block[0]
            continue  # a second open step in a row can't be told from the first
        latest = cursor + MAX_OPEN_STEP_S if placed else recording.length - 1
        start = _fit(recording, steps, block, targets, cursor, min(latest, recording.length - 1), track_length_m)
        if pending_open is not None and start > cursor:
            windows[pending_open] = (cursor, start)
        pending_open = None
        for index, window in zip(block, _walk(recording, steps, block, start, track_length_m)):
            windows[index] = window
        cursor, placed = windows[block[-1]][1], True
    if pending_open is not None and cursor < recording.length:
        windows[pending_open] = (cursor, recording.length)
    return windows


def _mean(series: Sequence[float], start: int, end: int, *, skip_zero: bool = False) -> float | None:
    """The mean over [start, end) when the recording covers enough of it."""
    inside = list(series[max(start, 0) : min(end, len(series))])
    if len(inside) < MIN_COVERAGE * (end - start):
        return None
    if skip_zero:
        inside = [v for v in inside if v > 0]
    return sum(inside) / len(inside) if inside else None


def score_steps(
    steps: Sequence[WorkoutStep],
    power: Sequence[float] | None,
    cadence: Sequence[float] | None,
    distance: Sequence[float] | None,
    *,
    ftp_w: float | None,
    track_length_m: float,
) -> list[StepOutcome]:
    """One outcome per step with a power or cadence target, in riding order.
    `power`, `cadence` and `distance` are 1 Hz series of the recording (None
    for a channel it lacks); without power the steps can't be placed."""
    windows = (
        place_steps(steps, power, distance, ftp_w=ftp_w, track_length_m=track_length_m)
        if power
        else [None] * len(steps)
    )
    outcomes = []
    for index, (step, window) in enumerate(zip(steps, windows)):
        if step.power is None and step.cadence is None:
            continue
        target_w = power_target_w(step, ftp_w)
        avg_power = _mean(power, *window) if window and power else None
        # Cadence while pedalling: coasting isn't a cadence.
        avg_cadence = _mean(cadence, *window, skip_zero=True) if window and cadence else None
        power_status = cadence_status = None
        if step.power is not None:
            if target_w is None or window is None:
                power_status = StepStatus.UNMEASURED
            else:
                written_high = None if step.power.high is None else target_w[1]
                power_status = _status(avg_power, *_accepted(target_w[0], written_high))
        if step.cadence is not None:
            if window is None or not cadence:
                cadence_status = StepStatus.UNMEASURED
            else:
                cadence_status = _status(avg_cadence, *_accepted(step.cadence.low, step.cadence.high))
        outcomes.append(
            StepOutcome(
                step_index=index,
                step=step,
                power_target_w=target_w,
                start_s=window[0] if window else None,
                end_s=window[1] if window else None,
                avg_power_w=avg_power,
                avg_cadence=avg_cadence,
                power_status=power_status,
                cadence_status=cadence_status,
            )
        )
    return outcomes
