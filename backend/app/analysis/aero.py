"""CdA and rolling resistance from real laps — pure functions.

Over one track lap, what the rider puts in goes into drag, rolling resistance
and any change of speed:

    η·P·T = ½ρ·CdA·v²·L + Crr·m·g·L + ½·m_eff·(v_exit² − v_entry²)

where v = L/T is the lap's mean speed from sqorz timing (more trustworthy
than a wheel sensor) and P the head unit's mean power over the lap. Divided
by L, this is a straight line in v²:

    η·P/v − ½·m_eff·(v_exit² − v_entry²)/L = ½ρ·CdA·v² + Crr·m·g

so laps at several speeds give CdA (slope) and Crr (intercept) by least
squares. Laps all at one speed only pin down their sum, so then Crr is fixed
and CdA follows. The speed at a lap line is taken halfway between the laps on
either side of it, which is good enough because only steady laps are used.

The model is the one in `physics.py` (same constants and defaults); bends
and the rider's line are not modelled, so the CdA found here includes them —
which is what a prediction for the same track wants.
"""

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from app.analysis.physics import DEFAULT_CRR, DEFAULT_EFFICIENCY, DEFAULT_ROTATING_MASS_KG, G

# What makes a lap steady enough to use without being asked.
# Both neighbouring laps within this fraction of the lap's speed:
MAX_SPEED_CHANGE = 0.03
# Power's standard deviation within the lap, relative to its mean:
MAX_POWER_VARIATION = 0.25
# Slower than this is rolling around, where drag hardly shows (~29 km/h).
MIN_SPEED_MS = 8.0

# Fewer laps than this give no estimate at all.
MIN_LAPS = 3
# Fitting Crr as well needs more laps and a real spread of speeds (fastest
# lap this much faster than the slowest); otherwise the line's intercept is noise.
MIN_FIT_LAPS = 6
MIN_SPEED_SPREAD = 0.10
# A fitted Crr outside this range means the data can't separate it from drag.
PLAUSIBLE_CRR = (0.001, 0.01)
# A CdA outside this range (m²) is a bad pairing of power and laps (a
# mis-linked recording, an e-bike, a miscalibrated meter), not an aerodynamic
# result; the estimate gives no fit rather than a number nothing else can use.
PLAUSIBLE_CDA = (0.0, 1.0)

# Why a lap isn't used (`AeroPoint.issue`). Hard issues keep a lap out even
# when the athlete picks it by hand; the others only stop the automatic pick.
EXCLUDED = "excluded"  # the athlete excluded the lap from the session
NO_POWER = "no_power"  # no recording covers it, or it has no power
FIRST_LAP = "first_lap"  # the first lap of an effort is still accelerating
UNSTEADY_SPEED = "unsteady_speed"
UNSTEADY_POWER = "unsteady_power"
TOO_SLOW = "too_slow"
HARD_ISSUES = frozenset({EXCLUDED, NO_POWER})


@dataclass(frozen=True)
class AeroLap:
    """One timed lap. `previous_time_s` / `next_time_s` are the laps just
    before and after it in the same effort (None at its ends). `power_w` and
    `power_sd_w` are the mean and spread of the recording's power over the lap."""

    key: str
    length_m: float
    time_s: float
    power_w: float | None
    power_sd_w: float | None = None
    previous_time_s: float | None = None
    next_time_s: float | None = None
    excluded: bool = False

    @property
    def speed_ms(self) -> float:
        return self.length_m / self.time_s


@dataclass(frozen=True)
class AeroConditions:
    """`rho` in kg/m³ (`physics.air_density`), `mass_kg` rider + bike + kit."""

    rho: float
    mass_kg: float
    efficiency: float = DEFAULT_EFFICIENCY
    rotating_mass_kg: float = DEFAULT_ROTATING_MASS_KG


@dataclass(frozen=True)
class AeroPoint:
    key: str
    speed_ms: float
    power_w: float | None
    # The left-hand side above: the resistive force the lap's power overcame (N).
    resistance_n: float | None
    # This lap alone, with the estimate's Crr.
    cda_m2: float | None
    issue: str | None
    # Picked for the estimate (which still needs `MIN_LAPS` of them).
    used: bool


@dataclass(frozen=True)
class AeroFit:
    cda_m2: float
    crr: float
    # "fitted" from the laps, "given" by the caller, or the track "default".
    crr_source: str
    # Of the force line over the used laps; None when they are all one speed.
    r_squared: float | None
    # Standard error of CdA from the scatter of the laps around the line.
    cda_se_m2: float | None
    laps_used: int
    speed_ms: float
    power_w: float
    # Fastest used lap over the slowest, minus one.
    speed_spread: float


@dataclass(frozen=True)
class AeroEstimate:
    points: tuple[AeroPoint, ...]
    fit: AeroFit | None


def _issue(lap: AeroLap) -> str | None:
    if lap.excluded:
        return EXCLUDED
    if lap.power_w is None or lap.power_w <= 0:
        return NO_POWER
    if lap.previous_time_s is None:
        return FIRST_LAP
    if lap.speed_ms < MIN_SPEED_MS:
        return TOO_SLOW
    for neighbour in (lap.previous_time_s, lap.next_time_s):
        if neighbour is not None and abs(lap.time_s / neighbour - 1) > MAX_SPEED_CHANGE:
            return UNSTEADY_SPEED
    if lap.power_sd_w is not None and lap.power_sd_w > MAX_POWER_VARIATION * lap.power_w:
        return UNSTEADY_POWER
    return None


def resistance_n(lap: AeroLap, conditions: AeroConditions) -> float | None:
    """η·P/v less the share of the lap's energy that went into speeding up."""
    if lap.power_w is None:
        return None
    v = lap.speed_ms
    v_entry = (lap.length_m / lap.previous_time_s + v) / 2 if lap.previous_time_s else v
    v_exit = (v + lap.length_m / lap.next_time_s) / 2 if lap.next_time_s else v
    kinetic_j = 0.5 * (conditions.mass_kg + conditions.rotating_mass_kg) * (v_exit**2 - v_entry**2)
    return conditions.efficiency * lap.power_w / v - kinetic_j / lap.length_m


def lap_cda_m2(speed_ms: float, resistance: float, crr: float, conditions: AeroConditions) -> float:
    return (resistance - crr * conditions.mass_kg * G) / (0.5 * conditions.rho * speed_ms**2)


def _line(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float] | None:
    """Ordinary least squares y = a + b·x → (a, b, standard error of b)."""
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx <= 0:
        return None
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    a = mean_y - b * mean_x
    residual = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    return a, b, math.sqrt(residual / (n - 2) / sxx) if n > 2 else math.nan


def _r_squared(xs: Sequence[float], ys: Sequence[float], a: float, b: float) -> float | None:
    mean_y = sum(ys) / len(ys)
    total = sum((y - mean_y) ** 2 for y in ys)
    if total < 1e-9:
        return None
    return 1 - sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / total


def estimate(
    laps: Sequence[AeroLap],
    conditions: AeroConditions,
    *,
    crr: float | None = None,
    selected: Collection[str] | None = None,
) -> AeroEstimate:
    """CdA (and Crr when the laps allow) from the laps. By default the steady
    laps are used; `selected` (lap keys) replaces that pick, though excluded
    laps and laps without power never count. A given `crr` is held fixed;
    without one it is fitted when there are enough laps at varied speeds and
    the result is plausible, else `DEFAULT_CRR` is used."""
    issues = [_issue(lap) for lap in laps]
    forces = [resistance_n(lap, conditions) for lap in laps]
    if selected is None:
        used = [issue is None for issue in issues]
    else:
        used = [lap.key in selected and issue not in HARD_ISSUES for lap, issue in zip(laps, issues)]
    chosen = [i for i, flag in enumerate(used) if flag]

    fit = None
    if len(chosen) >= MIN_LAPS:
        xs = [laps[i].speed_ms ** 2 for i in chosen]
        ys = [forces[i] for i in chosen]
        speeds = [laps[i].speed_ms for i in chosen]
        spread = max(speeds) / min(speeds) - 1
        aero_k = 0.5 * conditions.rho
        weight_n = conditions.mass_kg * G

        fitted = None
        if crr is None and len(chosen) >= MIN_FIT_LAPS and spread >= MIN_SPEED_SPREAD:
            line = _line(xs, ys)
            if line is not None:
                a, b, se = line
                if PLAUSIBLE_CRR[0] <= a / weight_n <= PLAUSIBLE_CRR[1] and b > 0:
                    fitted = (a, b, se)
        if fitted is not None:
            a, b, se = fitted
            crr_value, crr_source = a / weight_n, "fitted"
        else:
            crr_value, crr_source = (crr, "given") if crr is not None else (DEFAULT_CRR, "default")
            a = crr_value * weight_n
            # Least squares through the fixed intercept.
            b = sum(x * (y - a) for x, y in zip(xs, ys)) / sum(x * x for x in xs)
            residual = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
            se = math.sqrt(residual / (len(xs) - 1) / sum(x * x for x in xs))
        cda = b / aero_k
        if PLAUSIBLE_CDA[0] < cda <= PLAUSIBLE_CDA[1]:
            fit = AeroFit(
                cda_m2=cda,
                crr=crr_value,
                crr_source=crr_source,
                r_squared=_r_squared(xs, ys, a, b),
                cda_se_m2=se / aero_k if math.isfinite(se) else None,
                laps_used=len(chosen),
                # Distance-weighted: total distance over total time.
                speed_ms=sum(laps[i].length_m for i in chosen) / sum(laps[i].time_s for i in chosen),
                power_w=sum(laps[i].power_w * laps[i].time_s for i in chosen) / sum(laps[i].time_s for i in chosen),
                speed_spread=spread,
            )

    point_crr = fit.crr if fit else (crr if crr is not None else DEFAULT_CRR)
    points = tuple(
        AeroPoint(
            key=lap.key,
            speed_ms=lap.speed_ms,
            power_w=lap.power_w,
            resistance_n=force,
            cda_m2=lap_cda_m2(lap.speed_ms, force, point_crr, conditions) if force is not None else None,
            issue=issue,
            used=flag,
        )
        for lap, issue, force, flag in zip(laps, issues, forces, used)
    )
    return AeroEstimate(points=points, fit=fit)
