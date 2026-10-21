"""Cycling physics: air density, the power equation and its solvers.

Pure functions, mirrored one for one in `frontend/src/features/tools/physics.ts`
(same names in camelCase, same algorithms and constants). Both are checked
against `shared/physics-test-vectors.json`, so change them together and
regenerate the vectors with `python -m tests.physics_vectors` (from `backend/`).

The model is a rider on flat ground in still air:

    P = (v·(½ρ·CdA·v² + Crr·m·g) + m_eff·a·v) / η

with m_eff = m + the wheels' rotational inertia expressed as an equivalent
mass. Track bends (lean, the longer path of the centre of mass) are ignored:
on a 250 m track they cost well under 1% and CdA fitted from real laps
(Phase 8) absorbs them anyway.
"""

import math
from dataclasses import dataclass

G = 9.80665  # m/s²
R_DRY_AIR = 287.058  # J/(kg·K)
R_WATER_VAPOR = 461.495  # J/(kg·K)
SEA_LEVEL_PRESSURE_PA = 101_325.0
ZERO_CELSIUS_K = 273.15

# Typical values the tools start from; every one is a parameter.
DEFAULT_CRR = 0.0025  # wooden indoor track, good tubulars
DEFAULT_EFFICIENCY = 0.98  # fixed-gear chain drivetrain
# Two track wheels: I ≈ 0.14 kg·m² at r ≈ 0.335 m → I/r² ≈ 1.2 kg.
DEFAULT_ROTATING_MASS_KG = 1.2
# Standing start: riders accelerate far above their race power, then settle.
# The model rides at `start_power_ratio` × race power until reaching race
# pace (the steady speed for race power), then holds race power. 2× gives a
# ~21 s first lap for a 4:30 4 km pursuit on a 250 m track and a 19.6 s first
# lap for a kilo, both in line with real races.
DEFAULT_START_POWER_RATIO = 2.0
# Cap on the propulsive force at the wheel, where P/v would otherwise be
# unbounded at v = 0: torque, not power, limits the first pedal strokes.
DEFAULT_START_FORCE_N = 300.0

# Integration step for the effort simulation (fixed, so Python and TS agree).
SIMULATION_STEP_S = 0.02
# Hard stop for a simulation that will never finish (a force cap too small
# to overcome rolling resistance…).
MAX_SIMULATION_S = 3600.0


@dataclass(frozen=True)
class Setup:
    """A rider on a bike. `mass_kg` is rider + bike + kit; `rho` is the air
    density in kg/m³ (`air_density`)."""

    mass_kg: float
    cda_m2: float
    rho: float
    crr: float = DEFAULT_CRR
    efficiency: float = DEFAULT_EFFICIENCY
    rotating_mass_kg: float = DEFAULT_ROTATING_MASS_KG


@dataclass(frozen=True)
class Ride:
    """The result of `simulate`. `split_times_s[i]` is the elapsed time at
    (i + 1) × `split_every_m`, for the splits that fall strictly inside the
    distance; `time_s` is the finish. `average_power_w` includes the start,
    so it is above the race power after a standing start."""

    time_s: float
    final_speed_ms: float
    average_power_w: float
    split_times_s: tuple[float, ...]


# --- Air ---------------------------------------------------------------------


def saturation_vapor_pressure_pa(temp_c: float) -> float:
    """Tetens' formula, good to ~0.1% between 0 and 50 °C."""
    return 610.78 * 10 ** (7.5 * temp_c / (temp_c + 237.3))


def pressure_at_elevation_pa(elevation_m: float) -> float:
    """Standard-atmosphere station pressure at an elevation, for when no
    barometer reading is available."""
    base = 1 - 2.25577e-5 * elevation_m
    if base <= 0:
        # Beyond ~44.3 km the base goes negative and a fractional power of it
        # would silently come back complex.
        raise ValueError(f"elevation_m is beyond the barometric formula's domain: {elevation_m}")
    return SEA_LEVEL_PRESSURE_PA * base**5.25588


def air_density(
    temp_c: float,
    *,
    pressure_pa: float | None = None,
    elevation_m: float = 0.0,
    humidity_pct: float = 0.0,
) -> float:
    """Density of moist air in kg/m³. `pressure_pa` is the actual (station,
    not sea-level-corrected) pressure; without it the pressure is estimated
    from `elevation_m`. Humid air is lighter than dry air."""
    temp_k = temp_c + ZERO_CELSIUS_K
    if temp_k <= 0:
        raise ValueError(f"temp_c must be above absolute zero: {temp_c}")
    if not 0 <= humidity_pct <= 100:
        raise ValueError(f"humidity_pct must be within 0..100: {humidity_pct}")
    pressure = pressure_pa if pressure_pa is not None else pressure_at_elevation_pa(elevation_m)
    vapor = humidity_pct / 100 * saturation_vapor_pressure_pa(temp_c)
    return (pressure - vapor) / (R_DRY_AIR * temp_k) + vapor / (R_WATER_VAPOR * temp_k)


# --- Power equation -----------------------------------------------------------


def _check_setup(setup: Setup) -> None:
    """The model needs a real rider in real air. Anything else is a caller bug
    (a zeroed field, a negative CdA from a bad aero fit) and would otherwise
    surface as a math domain error or a nonsensical speed deep inside a solve."""
    if setup.mass_kg <= 0:
        raise ValueError(f"mass_kg must be positive: {setup.mass_kg}")
    if setup.cda_m2 <= 0:
        raise ValueError(f"cda_m2 must be positive: {setup.cda_m2}")
    if setup.rho <= 0:
        raise ValueError(f"rho must be positive: {setup.rho}")
    if setup.efficiency <= 0:
        raise ValueError(f"efficiency must be positive: {setup.efficiency}")
    if setup.crr < 0:
        raise ValueError(f"crr must not be negative: {setup.crr}")
    if setup.rotating_mass_kg < 0:
        raise ValueError(f"rotating_mass_kg must not be negative: {setup.rotating_mass_kg}")


def resistive_force_n(speed_ms: float, setup: Setup) -> float:
    """Aerodynamic drag + rolling resistance at a speed."""
    return 0.5 * setup.rho * setup.cda_m2 * speed_ms**2 + setup.crr * setup.mass_kg * G


def power_required_w(speed_ms: float, setup: Setup, accel_ms2: float = 0.0) -> float:
    """Pedal power to hold (or, with `accel_ms2`, change) a speed."""
    _check_setup(setup)
    effective_mass = setup.mass_kg + setup.rotating_mass_kg
    wheel_power = speed_ms * resistive_force_n(speed_ms, setup) + effective_mass * accel_ms2 * speed_ms
    return wheel_power / setup.efficiency


def steady_speed_ms(power_w: float, setup: Setup) -> float:
    """The speed a constant power holds, solving ½ρCdA·v³ + Crr·m·g·v = η·P
    (one real root, by Cardano: the cubic has no v² term and p > 0)."""
    _check_setup(setup)
    if power_w <= 0:
        return 0.0
    a = 0.5 * setup.rho * setup.cda_m2
    p = setup.crr * setup.mass_kg * G / a
    q = -setup.efficiency * power_w / a
    root = math.sqrt(q * q / 4 + p**3 / 27)
    return math.cbrt(-q / 2 + root) + math.cbrt(-q / 2 - root)


# --- Efforts ------------------------------------------------------------------


def _rider_power_w(speed_ms: float, power_w: float, race_speed_ms: float, start_power_ratio: float) -> float:
    return power_w * start_power_ratio if speed_ms < race_speed_ms else power_w


def _acceleration(speed_ms: float, rider_power_w: float, setup: Setup, start_force_n: float) -> float:
    drive_power = setup.efficiency * rider_power_w
    # min(F_max, ηP/v), written so v = 0 never divides. No drive power means
    # no drive force: the cap must not push a rider who isn't pedalling.
    if drive_power <= 0:
        drive_force = 0.0
    elif speed_ms <= 0 or speed_ms * start_force_n <= drive_power:
        drive_force = start_force_n
    else:
        drive_force = drive_power / speed_ms
    if speed_ms <= 0 and drive_force <= resistive_force_n(0, setup):
        return 0.0  # rolling resistance only opposes motion: a stalled rider stays put
    return (drive_force - resistive_force_n(speed_ms, setup)) / (setup.mass_kg + setup.rotating_mass_kg)


def simulate(
    distance_m: float,
    power_w: float,
    setup: Setup,
    *,
    standing: bool = True,
    split_every_m: float | None = None,
    start_power_ratio: float = DEFAULT_START_POWER_RATIO,
    start_force_n: float = DEFAULT_START_FORCE_N,
) -> Ride | None:
    """Ride `distance_m` at race power `power_w`, from a standing start (from
    v = 0 at `start_power_ratio` × race power, propulsion capped at
    `start_force_n`, until reaching the race-power steady speed) or flying
    (already at that speed). Fixed-step RK4 in time; split and finish times
    are interpolated linearly inside the step that crosses them. None if the
    rider can't finish within `MAX_SIMULATION_S` or has no power to ride with."""
    race_speed = steady_speed_ms(power_w, setup)
    if distance_m <= 0:
        return Ride(0.0, 0.0 if standing else race_speed, 0.0, ())
    if power_w <= 0:
        return None  # no power, no ride: the force cap must not carry a stopped rider
    dt = SIMULATION_STEP_S
    marks: list[float] = []
    if split_every_m and split_every_m > 0:
        count = math.ceil(distance_m / split_every_m) - 1
        marks = [split_every_m * (i + 1) for i in range(count)]
    splits: list[float] = []

    def accel(v: float) -> float:
        rider_power = _rider_power_w(v, power_w, race_speed, start_power_ratio)
        return _acceleration(v, rider_power, setup, start_force_n)

    t, x, energy = 0.0, 0.0, 0.0
    v = 0.0 if standing else race_speed
    while t < MAX_SIMULATION_S:
        k1v = accel(v)
        k1x = v
        k2v = accel(v + dt / 2 * k1v)
        k2x = v + dt / 2 * k1v
        k3v = accel(v + dt / 2 * k2v)
        k3x = v + dt / 2 * k2v
        k4v = accel(v + dt * k3v)
        k4x = v + dt * k3v
        next_x = x + dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
        next_v = max(0.0, v + dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v))
        step_power = _rider_power_w(v, power_w, race_speed, start_power_ratio)
        while len(splits) < len(marks) and next_x >= marks[len(splits)]:
            mark = marks[len(splits)]
            splits.append(t + dt * (mark - x) / (next_x - x))
        if next_x >= distance_m:
            fraction = (distance_m - x) / (next_x - x)
            time = t + dt * fraction
            energy += step_power * dt * fraction
            return Ride(time, v + (next_v - v) * fraction, energy / time, tuple(splits))
        t, x, v = t + dt, next_x, next_v
        energy += step_power * dt
    return None


def power_for_time_w(
    distance_m: float,
    time_s: float,
    setup: Setup,
    *,
    standing: bool = True,
    start_power_ratio: float = DEFAULT_START_POWER_RATIO,
    start_force_n: float = DEFAULT_START_FORCE_N,
) -> float | None:
    """The race power that rides `distance_m` in `time_s` (bisection on
    `simulate`, to 0.01 W). None when even 3000 W can't make it."""
    low, high = 0.0, 3000.0

    def finish(power: float) -> float:
        ride = simulate(
            distance_m,
            power,
            setup,
            standing=standing,
            start_power_ratio=start_power_ratio,
            start_force_n=start_force_n,
        )
        return math.inf if ride is None else ride.time_s

    if time_s <= 0 or finish(high) > time_s:
        return None
    while high - low > 0.01:
        mid = (low + high) / 2
        if finish(mid) > time_s:
            low = mid
        else:
            high = mid
    return high


# --- Gearing ------------------------------------------------------------------


def development_m(chainring: int, cog: int, rollout_m: float) -> float:
    """Distance covered per crank revolution."""
    return chainring / cog * rollout_m


GEAR_INCHES_WHEEL_IN = 27.0


def gear_inches(chainring: int, cog: int) -> float:
    """The traditional gear size: ratio × a nominal 27-inch wheel, whatever the
    real tire, so it matches published gear tables (58×16 = 97.9)."""
    return chainring / cog * GEAR_INCHES_WHEEL_IN


def speed_from_cadence_ms(cadence_rpm: float, chainring: int, cog: int, rollout_m: float) -> float:
    return cadence_rpm / 60 * development_m(chainring, cog, rollout_m)


def cadence_from_speed_rpm(speed_ms: float, chainring: int, cog: int, rollout_m: float) -> float:
    return speed_ms / development_m(chainring, cog, rollout_m) * 60
