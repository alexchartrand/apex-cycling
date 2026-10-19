"""Effort detection: groups an athlete's laps into continuous efforts and
describes each one (start type, distance, speed, pursuit half-lap splits).

Pure functions over plain dataclasses — no SQLAlchemy, no I/O — so the logic
is unit-testable on synthetic laps and on the real sqorz fixture. The
service layer (`app/training/service.py`) adapts ORM rows into `LapInput`.

Facts about sqorz data this relies on (verified on `tests/fixtures/LS-03407.json`):
- Within a run, sqorz sets each lap's start to the previous lap's finish, so
  consecutive laps of one effort have a gap of exactly 0 ms; the smallest
  real pause between efforts in that data is ~16 s.
- A lap whose last checkpoint is null never reached the finish (the rider
  stopped mid-lap, or the capture was missed). Its true end is unknown, so
  nothing can be chained after it: it always ends its effort.
- `from_start` is True on every lap in that fixture, so on its own it can't
  tell standing from flying starts; the first-lap time profile does.
"""

import re
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Laps are "continuous" when the next lap starts within this many ms of the
# previous lap's end. Real data is either exactly 0 or >= ~16 s, so this only
# needs to absorb rounding from other timing sources.
CONTINUITY_TOLERANCE_MS = 1500

# A first lap this much slower than the laps that follow it is a standing
# start. Lap-to-lap noise in training is ~2-3%; real standing starts on a
# 250 m track cost ~10-15% on the first lap.
STANDING_START_MIN_RATIO = 1.08
# How many following laps form the reference pace for that comparison.
STANDING_REFERENCE_LAPS = 3

_PURSUIT_LINE_RE = re.compile(r"^\s*(?:p|poursuite|pursuit)\s*([12])\b", re.IGNORECASE)


class StartType(str, Enum):
    STANDING = "standing"
    FLYING = "flying"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CheckpointCrossing:
    """One checkpoint of a lap. `time_ms` is cumulative since lap start (as
    stored in `LapSegmentTime`), null when the capture was missed.
    """

    loop_id: uuid.UUID
    loop_name: str
    time_ms: int | None


@dataclass(frozen=True)
class LapInput:
    lap_id: uuid.UUID
    start_time: datetime
    from_start: bool
    crossings: tuple[CheckpointCrossing, ...]  # in lap order (sequence_index)

    @property
    def total_time_ms(self) -> int | None:
        """The finish line's cumulative time — see `_whole_lap_time_ms`."""
        return self.crossings[-1].time_ms if self.crossings else None


@dataclass(frozen=True)
class HalfLapSplit:
    """Time between two consecutive pursuit-line crossings. `time_ms` is
    null when either crossing was missed.
    """

    index: int
    from_line: str  # "P1" | "P2"
    to_line: str
    time_ms: int | None


@dataclass(frozen=True)
class Effort:
    laps: tuple[LapInput, ...]
    start_type: StartType
    completed_lap_count: int
    lap_times_ms: tuple[int | None, ...]  # one per lap; null for an unfinished lap
    total_time_ms: int | None  # sum of the finished laps
    distance_m: float | None  # finished laps x track length, if the length is known
    avg_speed_kmh: float | None
    best_lap_ms: int | None
    half_lap_splits: tuple[HalfLapSplit, ...]

    @property
    def start_time(self) -> datetime:
        return self.laps[0].start_time


def pursuit_line(loop_name: str) -> str | None:
    """"P1"/"P2" for a pursuit-line checkpoint (`P1`, `Poursuite 2`…), else None."""
    match = _PURSUIT_LINE_RE.match(loop_name)
    return f"P{match.group(1)}" if match else None


def group_continuous_laps(laps: list[LapInput], tolerance_ms: int = CONTINUITY_TOLERANCE_MS) -> list[list[LapInput]]:
    """Splits laps (any order, one track) into time-ordered runs where each
    lap starts when the previous one ended.
    """
    groups: list[list[LapInput]] = []
    for lap in sorted(laps, key=lambda lap: lap.start_time):
        if groups:
            previous = groups[-1][-1]
            previous_total = previous.total_time_ms
            if previous_total is not None:
                gap_ms = (lap.start_time - previous.start_time).total_seconds() * 1000 - previous_total
                if abs(gap_ms) <= tolerance_ms:
                    groups[-1].append(lap)
                    continue
        groups.append([lap])
    return groups


def classify_start(laps: list[LapInput]) -> StartType:
    """Standing when the first lap is clearly slower than the laps after it.
    A lap that doesn't begin at the start can't be a standing start. With no
    comparable following lap there's nothing to judge by: unknown.
    """
    first = laps[0]
    if not first.from_start:
        return StartType.FLYING
    first_total = first.total_time_ms
    if first_total is None:
        return StartType.UNKNOWN
    reference = [
        lap.total_time_ms for lap in laps[1 : 1 + STANDING_REFERENCE_LAPS] if lap.total_time_ms is not None
    ]
    if not reference:
        return StartType.UNKNOWN
    return StartType.STANDING if first_total >= STANDING_START_MIN_RATIO * statistics.median(reference) else StartType.FLYING


def half_lap_splits(laps: list[LapInput]) -> list[HalfLapSplit]:
    """Times between consecutive pursuit-line (P1/P2) crossings across the
    whole effort, laps chained into one timeline. A missed crossing stays in
    the sequence (so the P1/P2 alternation holds) and blanks the two splits
    that touch it.
    """
    effort_start = laps[0].start_time
    crossings: list[tuple[str, int | None]] = []
    for lap in laps:
        lap_offset_ms = round((lap.start_time - effort_start).total_seconds() * 1000)
        for crossing in lap.crossings:
            line = pursuit_line(crossing.loop_name)
            if line is None:
                continue
            crossings.append((line, None if crossing.time_ms is None else lap_offset_ms + crossing.time_ms))

    splits = []
    for index, ((from_line, from_ms), (to_line, to_ms)) in enumerate(zip(crossings, crossings[1:])):
        known = from_ms is not None and to_ms is not None and from_line != to_line
        splits.append(HalfLapSplit(index, from_line, to_line, to_ms - from_ms if known else None))
    return splits


def build_effort(laps: list[LapInput], track_length_m: float | None) -> Effort:
    lap_times = tuple(lap.total_time_ms for lap in laps)
    finished = [t for t in lap_times if t is not None]
    total_time_ms = sum(finished) if finished else None
    distance_m = track_length_m * len(finished) if track_length_m and finished else None
    avg_speed_kmh = distance_m / (total_time_ms / 1000) * 3.6 if distance_m and total_time_ms else None
    return Effort(
        laps=tuple(laps),
        start_type=classify_start(laps),
        completed_lap_count=len(finished),
        lap_times_ms=lap_times,
        total_time_ms=total_time_ms,
        distance_m=distance_m,
        avg_speed_kmh=avg_speed_kmh,
        best_lap_ms=min(finished) if finished else None,
        half_lap_splits=tuple(half_lap_splits(laps)),
    )


def detect_efforts(
    laps: list[LapInput],
    track_length_m: float | None = None,
    tolerance_ms: int = CONTINUITY_TOLERANCE_MS,
) -> list[Effort]:
    """All efforts among one track's laps, oldest first."""
    return [build_effort(group, track_length_m) for group in group_continuous_laps(laps, tolerance_ms)]
