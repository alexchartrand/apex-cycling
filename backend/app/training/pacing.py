"""Pacing of one effort: how even the laps were and whether the rider faded.

Pure functions over an `Effort`. The reference laps are the finished,
non-excluded ones, minus the first lap of a standing start (it is slow by
construction, so it would read as a fade in reverse and swamp the spread).
Percentages are signed the way a rider reads them: positive = slower.
"""

import statistics
from dataclasses import dataclass

from app.training.efforts import Effort, StartType

# Fewer reference laps than this and a spread or a fade says nothing.
MIN_LAPS_FOR_SPREAD = 3
MIN_LAPS_FOR_FADE = 4


@dataclass(frozen=True)
class Pacing:
    reference_lap_count: int
    # Mean of the reference laps: the "even pace" every lap is compared to.
    even_pace_ms: float
    # Coefficient of variation of the reference laps, in percent.
    cv_pct: float | None
    # Last third of the reference laps against the first third, in percent.
    fade_pct: float | None
    # Per lap of the effort (same order as `lap_times_ms`): its time against
    # the even pace, in percent. Null for an unfinished lap. The standing
    # start's first lap is included (it just wasn't used for the reference).
    deviations_pct: tuple[float | None, ...]
    # The first lap was a standing start and is left out of the reference.
    start_lap_skipped: bool


def pacing(effort: Effort) -> Pacing | None:
    """None when the effort has too few comparable laps to speak of pace."""
    skip_first = effort.start_type == StartType.STANDING
    reference = [
        time_ms
        for index, (time_ms, lap) in enumerate(zip(effort.lap_times_ms, effort.laps))
        if time_ms is not None and not lap.excluded and not (skip_first and index == 0)
    ]
    if len(reference) < 2:
        return None
    even = statistics.fmean(reference)

    cv = statistics.pstdev(reference) / even * 100 if len(reference) >= MIN_LAPS_FOR_SPREAD else None

    fade = None
    if len(reference) >= MIN_LAPS_FOR_FADE:
        third = max(1, len(reference) // 3)
        first, last = statistics.fmean(reference[:third]), statistics.fmean(reference[-third:])
        fade = (last - first) / first * 100

    return Pacing(
        reference_lap_count=len(reference),
        even_pace_ms=even,
        cv_pct=cv,
        fade_pct=fade,
        deviations_pct=tuple(None if t is None else (t - even) / even * 100 for t in effort.lap_times_ms),
        start_lap_skipped=skip_first,
    )
