"""Critical power and W′ from a mean-maximal power curve, and an FTP suggestion
— pure functions over (duration, power) pairs.

The two-parameter model: work to exhaustion is linear in time, `W = CP·t + W′`,
so a least-squares line through (t, P·t) gives CP as its slope and W′ as its
intercept. It only holds for efforts of roughly 2–20 minutes (shorter ones draw
on the sprint reserve, longer ones on fatigue), so the fit uses the standard
durations in that band and needs efforts at both ends of it.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# The fit band, in seconds.
FIT_MIN_S = 180
FIT_MAX_S = 1200
# The efforts must reach down to short ones and up to long ones, or the slope
# and the intercept can't be told apart.
FIT_SHORTEST_NEEDED_S = 360
FIT_LONGEST_NEEDED_S = 720
MIN_FIT_POINTS = 3

# FTP ≈ 95 % of the best 20-minute power (the usual field-test rule).
FTP_FROM_20_MIN = 0.95
FTP_SOURCE_S = 1200
# A suggestion within this share of the current FTP isn't worth a prompt.
SUGGESTION_MARGIN = 0.02


@dataclass(frozen=True)
class CriticalPowerFit:
    cp_w: float
    w_prime_j: float
    r_squared: float
    points: int


def fit_critical_power(curve: Iterable[tuple[int, float]]) -> CriticalPowerFit | None:
    """Fits CP and W′ to the (duration s, best mean power W) pairs inside the
    fit band; None without enough spread or when the line isn't physical
    (a falling slope, or a negative W′ intercept). A loose fit is still returned
    with its R², for the caller to judge."""
    points = sorted((t, p) for t, p in curve if FIT_MIN_S <= t <= FIT_MAX_S and p > 0)
    if len(points) < MIN_FIT_POINTS:
        return None
    if points[0][0] > FIT_SHORTEST_NEEDED_S or points[-1][0] < FIT_LONGEST_NEEDED_S:
        return None

    times = [float(t) for t, _ in points]
    work = [t * p for t, p in points]
    n = len(points)
    mean_t, mean_w = sum(times) / n, sum(work) / n
    spread = sum((t - mean_t) ** 2 for t in times)
    slope = sum((t - mean_t) * (w - mean_w) for t, w in zip(times, work)) / spread
    intercept = mean_w - slope * mean_t
    if slope <= 0 or intercept < 0:
        return None

    residual = sum((w - (slope * t + intercept)) ** 2 for t, w in zip(times, work))
    total = sum((w - mean_w) ** 2 for w in work)
    return CriticalPowerFit(
        cp_w=slope, w_prime_j=intercept, r_squared=1 - residual / total if total else 1.0, points=n
    )


def predicted_power(fit: CriticalPowerFit, duration_s: float) -> float:
    """What the model says the rider can hold for `duration_s`."""
    return fit.cp_w + fit.w_prime_j / duration_s


def suggest_ftp(curve: Sequence[tuple[int, float]]) -> tuple[float, int] | None:
    """(suggested FTP, the duration it came from) — 95 % of the best 20-minute
    power. None without a 20-minute effort in the data."""
    for duration_s, power_w in curve:
        if duration_s == FTP_SOURCE_S and power_w > 0:
            return power_w * FTP_FROM_20_MIN, duration_s
    return None


def worth_suggesting(suggested_w: float, current_w: float | None) -> bool:
    """A suggestion is made when there is no FTP yet or the data moved it by
    more than the margin, either way."""
    if current_w is None or current_w <= 0:
        return True
    return abs(suggested_w - current_w) / current_w > SUGGESTION_MARGIN
