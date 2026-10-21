import json
import math

import pytest

from app.analysis.physics import (
    Setup,
    air_density,
    cadence_from_speed_rpm,
    development_m,
    gear_inches,
    power_for_time_w,
    power_required_w,
    pressure_at_elevation_pa,
    simulate,
    speed_from_cadence_ms,
    steady_speed_ms,
)
from tests.physics_vectors import VECTORS_PATH, build_vectors

PURSUITER = Setup(mass_kg=83, cda_m2=0.20, rho=1.2)


def test_air_density_matches_the_standard_atmosphere():
    # ISA sea level: 15 °C, 101 325 Pa, dry → 1.225 kg/m³.
    assert air_density(15) == pytest.approx(1.225, abs=5e-4)
    # ISA at 1000 m: 89 875 Pa.
    assert pressure_at_elevation_pa(1000) == pytest.approx(89_875, abs=5)
    assert air_density(15, elevation_m=1000) < air_density(15)


def test_humid_and_warm_air_is_lighter():
    assert air_density(20, humidity_pct=80) < air_density(20, humidity_pct=0)
    assert air_density(30) < air_density(15)
    # An explicit barometer reading wins over the elevation estimate.
    assert air_density(15, pressure_pa=101_325, elevation_m=2000) == pytest.approx(air_density(15))


def test_air_density_rejects_impossible_weather():
    with pytest.raises(ValueError, match="absolute zero"):
        air_density(-273.15)
    with pytest.raises(ValueError, match="humidity"):
        air_density(20, humidity_pct=150)
    with pytest.raises(ValueError, match="barometric formula"):
        pressure_at_elevation_pa(50_000)
    with pytest.raises(ValueError, match="barometric formula"):
        air_density(20, elevation_m=50_000)
    # An explicit barometer reading bypasses the elevation estimate.
    assert air_density(20, pressure_pa=90_000, elevation_m=50_000) > 0


def test_power_required_by_hand():
    setup = Setup(mass_kg=80, cda_m2=0.2, rho=1.2, crr=0.003, efficiency=1, rotating_mass_kg=0)
    # drag ½·1.2·0.2·10² = 12 N, rolling 0.003·80·9.80665 = 2.3536 N.
    assert power_required_w(10, setup) == pytest.approx(10 * (12 + 2.3535960))
    # +0.5 m/s² at 10 m/s adds m·a·v = 400 W.
    assert power_required_w(10, setup, 0.5) == pytest.approx(10 * (12 + 2.3535960) + 400)
    # Drivetrain losses scale it up.
    lossy = Setup(mass_kg=80, cda_m2=0.2, rho=1.2, crr=0.003, efficiency=0.95, rotating_mass_kg=0)
    assert power_required_w(10, lossy) == pytest.approx(power_required_w(10, setup) / 0.95)


@pytest.mark.parametrize("power", [1, 150, 450, 1500])
def test_steady_speed_inverts_the_power_equation(power):
    assert power_required_w(steady_speed_ms(power, PURSUITER), PURSUITER) == pytest.approx(power, rel=1e-9)


def test_steady_speed_of_no_power_is_zero():
    assert steady_speed_ms(0, PURSUITER) == 0


@pytest.mark.parametrize(
    "setup",
    [
        Setup(mass_kg=0, cda_m2=0.2, rho=1.2),
        Setup(mass_kg=83, cda_m2=0, rho=1.2),
        Setup(mass_kg=83, cda_m2=-0.05, rho=1.2),
        Setup(mass_kg=83, cda_m2=0.2, rho=0),
        Setup(mass_kg=83, cda_m2=0.2, rho=1.2, efficiency=0),
        Setup(mass_kg=83, cda_m2=0.2, rho=1.2, crr=-0.001),
        Setup(mass_kg=83, cda_m2=0.2, rho=1.2, rotating_mass_kg=-1),
    ],
)
def test_a_setup_that_is_not_a_rider_is_rejected(setup):
    with pytest.raises(ValueError):
        steady_speed_ms(450, setup)
    with pytest.raises(ValueError):
        power_required_w(10, setup)
    with pytest.raises(ValueError):
        simulate(4000, 450, setup)


def test_flying_effort_rides_at_steady_speed():
    ride = simulate(4000, 450, PURSUITER, standing=False, split_every_m=250)
    speed = steady_speed_ms(450, PURSUITER)
    assert ride.time_s == pytest.approx(4000 / speed, rel=1e-9)
    assert ride.average_power_w == pytest.approx(450)
    assert len(ride.split_times_s) == 15
    assert ride.split_times_s[0] == pytest.approx(250 / speed, rel=1e-9)


def test_standing_start_costs_time_on_the_first_lap_only():
    standing = simulate(4000, 450, PURSUITER, split_every_m=250)
    flying = simulate(4000, 450, PURSUITER, standing=False, split_every_m=250)
    laps = [b - a for a, b in zip((0, *standing.split_times_s), (*standing.split_times_s, standing.time_s))]
    flying_lap = flying.split_times_s[0]
    # Real 4:30 pursuits start with a ~20-22 s lap, then ride ~16.6 s laps.
    assert 20 < laps[0] < 22.5
    assert laps[2] == pytest.approx(flying_lap, rel=1e-3)
    assert 3 < standing.time_s - flying.time_s < 6
    # The start is ridden above race power, so the average is higher.
    assert standing.average_power_w > 450
    assert standing.final_speed_ms == pytest.approx(flying.final_speed_ms, rel=1e-6)


def test_start_power_and_force_cap_shape_the_start():
    constant = simulate(1000, 600, PURSUITER, start_power_ratio=1)
    surge = simulate(1000, 600, PURSUITER, start_power_ratio=2)
    assert surge.time_s < constant.time_s
    assert constant.average_power_w == pytest.approx(600)
    weak = simulate(1000, 600, PURSUITER, start_force_n=100)
    assert weak.time_s > surge.time_s


def test_a_rider_who_cannot_beat_rolling_resistance_never_finishes():
    # Rolling resistance is 0.0025·83·9.81 ≈ 2 N.
    assert simulate(250, 300, PURSUITER, start_force_n=1) is None


def test_no_power_means_no_ride():
    # The start force cap must not carry a rider who isn't pedalling.
    assert simulate(4000, 0, PURSUITER) is None
    assert simulate(4000, -100, PURSUITER) is None
    assert simulate(4000, 0, PURSUITER, standing=False) is None


def test_zero_distance():
    assert simulate(0, 300, PURSUITER).time_s == 0


@pytest.mark.parametrize(("distance", "target", "standing"), [(4000, 255, True), (1000, 66, True), (200, 11, False)])
def test_power_for_time_inverts_simulate(distance, target, standing):
    power = power_for_time_w(distance, target, PURSUITER, standing=standing)
    assert simulate(distance, power, PURSUITER, standing=standing).time_s == pytest.approx(target, abs=0.01)


def test_power_for_an_impossible_time_is_none():
    assert power_for_time_w(250, 2, PURSUITER) is None
    assert power_for_time_w(250, 0, PURSUITER) is None


def test_gearing_by_hand():
    # 52×14 on a 2.10 m rollout: 7.8 m per crank turn, ~97.7 gear inches.
    assert development_m(52, 14, 2.10) == pytest.approx(7.8)
    assert gear_inches(52, 14, 2.10) == pytest.approx(97.75, abs=0.01)
    assert speed_from_cadence_ms(110, 52, 14, 2.10) == pytest.approx(7.8 * 110 / 60)
    assert cadence_from_speed_rpm(7.8 * 110 / 60, 52, 14, 2.10) == pytest.approx(110)


def _assert_close(actual, expected, path="vectors"):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), path
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected)):
            _assert_close(a, e, f"{path}[{i}]")
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), path
    else:
        assert actual == expected, path


def test_shared_vectors_are_up_to_date():
    """The frontend checks its physics.ts against this file; if this fails,
    the Python model changed — regenerate with `python -m tests.physics_vectors`
    and make the same change in physics.ts."""
    stored = json.loads(VECTORS_PATH.read_text())
    _assert_close(json.loads(json.dumps(build_vectors())), stored)
