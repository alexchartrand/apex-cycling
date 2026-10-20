"""Power and training-load metrics — pure functions over plain lists.

Conventions (Coggan / TrainingPeaks, as Intervals.icu and WKO use them):
- Power is analysed as a 1 Hz series (`resample_1hz`). A dropout inside a
  recording counts as 0 W.
- Normalized power: 30 s rolling mean, ^4, mean, ^(1/4).
- IF = NP / FTP. TSS = hours x IF^2 x 100.
- CTL / ATL are exponentially weighted daily TSS (42 and 7 days); TSB, the
  "form" going into a day, is the previous day's CTL - ATL.
"""

import math
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

# A longer gap between samples is a stop, not riding (same threshold as
# app/activities/summary.py).
MAX_SAMPLE_GAP_S = 10.0

# Every second up to 10, then the durations riders compare: track efforts
# (15 s, 30 s, 1 min, 4 min pursuit) and road/threshold ones (5, 20, 60 min…).
STANDARD_DURATIONS_S: tuple[int, ...] = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300, 360, 420, 480, 600,
    720, 900, 1200, 1800, 2400, 3600, 5400, 7200, 10800, 14400, 18000,
)  # fmt: skip

CTL_DAYS = 42
ATL_DAYS = 7

# Upper bounds of Coggan power zones 1-6 as a share of FTP (zone 7 is above).
POWER_ZONE_LIMITS = (0.55, 0.75, 0.90, 1.05, 1.20, 1.50)
# Upper bounds of heart-rate zones 1-4 as a share of max HR (zone 5 is above).
HR_ZONE_LIMITS = (0.60, 0.70, 0.80, 0.90)


def resample_1hz(
    time_s: Sequence[float],
    values: Sequence[float | None],
    *,
    pauses: Literal["zero", "skip"] = "zero",
) -> list[float]:
    """One value per whole second from 0 to the last sample, each the latest
    reading held until the next one (smart recording). A missing reading is 0.
    Where the recorder paused (a gap over `MAX_SAMPLE_GAP_S`) the seconds are
    0 W (`pauses="zero"`, so an effort can't be stitched across a stop) or
    left out (`"skip"`, so a stop doesn't dilute averages)."""
    if not time_s:
        return []
    n = len(time_s)
    # Seconds each sample stands for: until the next one, or 1 s before a pause.
    cover = [
        (time_s[i + 1] - time_s[i]) if i + 1 < n and time_s[i + 1] - time_s[i] <= MAX_SAMPLE_GAP_S else 1.0
        for i in range(n)
    ]
    series: list[float] = []
    i = 0
    for second in range(math.floor(time_s[-1]) + 1):
        while i + 1 < n and time_s[i + 1] <= second:
            i += 1
        if time_s[i] <= second < time_s[i] + cover[i]:
            value = values[i]
            series.append(0.0 if value is None else float(value))
        elif pauses == "zero":
            series.append(0.0)
    return series


def _prefix_sums(series: Sequence[float]) -> list[float]:
    sums = [0.0]
    for value in series:
        sums.append(sums[-1] + value)
    return sums


def mean_maximal_power(
    power_1hz: Sequence[float], durations: Sequence[int] = STANDARD_DURATIONS_S
) -> dict[int, float]:
    """The best average power over each duration; durations longer than the
    series are left out."""
    sums = _prefix_sums(power_1hz)
    n = len(power_1hz)
    curve: dict[int, float] = {}
    for duration in durations:
        if duration > n:
            continue
        best = max(sums[start + duration] - sums[start] for start in range(n - duration + 1))
        curve[duration] = best / duration
    return curve


def normalized_power(power_1hz: Sequence[float]) -> float | None:
    """None when there are fewer than 30 s of data (no full rolling window)."""
    window = 30
    if len(power_1hz) < window:
        return None
    sums = _prefix_sums(power_1hz)
    fourth_powers = [((sums[i + window] - sums[i]) / window) ** 4 for i in range(len(power_1hz) - window + 1)]
    return (sum(fourth_powers) / len(fourth_powers)) ** 0.25


def intensity_factor(normalized_power_w: float, ftp_w: float) -> float:
    return normalized_power_w / ftp_w


def training_stress_score(duration_s: float, normalized_power_w: float, ftp_w: float) -> float:
    return duration_s / 3600 * intensity_factor(normalized_power_w, ftp_w) ** 2 * 100


def srpe_training_stress(rpe: int, duration_s: float) -> float:
    """A TSS-sized load for a session known only by its duration and the
    rider's 1-10 effort rating. The intensity factor is a line through typical
    cases (RPE 3 ~ endurance, 5 ~ tempo, 7 ~ threshold, 10 ~ all-out hour):
    IF = 0.30 + 0.08 x RPE."""
    intensity = 0.30 + 0.08 * rpe
    return duration_s / 3600 * intensity**2 * 100


def power_zone_limits(ftp_w: float) -> list[float]:
    return [share * ftp_w for share in POWER_ZONE_LIMITS]


def hr_zone_limits(max_hr: float) -> list[float]:
    return [share * max_hr for share in HR_ZONE_LIMITS]


def time_in_zones(series_1hz: Sequence[float], limits: Sequence[float]) -> list[int]:
    """Seconds in each zone: zone i holds values up to and including
    `limits[i]`; the last zone is everything above."""
    seconds = [0] * (len(limits) + 1)
    for value in series_1hz:
        seconds[bisect_left(limits, value)] += 1
    return seconds


@dataclass(frozen=True)
class LoadDay:
    day: date
    tss: float
    ctl: float
    atl: float
    tsb: float


def training_load(
    daily_tss: Mapping[date, float], through: date, *, initial_ctl: float = 0.0, initial_atl: float = 0.0
) -> list[LoadDay]:
    """Fitness (CTL), fatigue (ATL) and form (TSB) for every day from the first
    day with load up to `through`. Days without training decay both."""
    if not daily_tss:
        return []
    ctl, atl = initial_ctl, initial_atl
    ctl_gain, atl_gain = 1 - math.exp(-1 / CTL_DAYS), 1 - math.exp(-1 / ATL_DAYS)
    days: list[LoadDay] = []
    day = min(daily_tss)
    while day <= through:
        tss = daily_tss.get(day, 0.0)
        form = ctl - atl
        ctl += (tss - ctl) * ctl_gain
        atl += (tss - atl) * atl_gain
        days.append(LoadDay(day=day, tss=tss, ctl=ctl, atl=atl, tsb=form))
        day += timedelta(days=1)
    return days
