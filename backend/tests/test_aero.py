import random
from dataclasses import replace

import pytest

from app.analysis import aero, fusion, physics

RHO = 1.18
MASS = 82.0
CDA = 0.215
CRR = 0.0028
TRACK = 250.0
CONDITIONS = aero.AeroConditions(rho=RHO, mass_kg=MASS)


def steady_power(speed_ms: float, cda: float = CDA, crr: float = CRR) -> float:
    setup = physics.Setup(mass_kg=MASS, cda_m2=cda, rho=RHO, crr=crr)
    return physics.power_required_w(speed_ms, setup)


def effort(prefix: str, speeds: list[float], *, noise_w: float = 0.0, rng=None, **power_kw) -> list[aero.AeroLap]:
    """Consecutive laps of one effort, power from the physics model (+ noise)."""
    times = [TRACK / v for v in speeds]
    laps = []
    for i, (speed, time_s) in enumerate(zip(speeds, times)):
        power = steady_power(speed, **power_kw) + (rng.gauss(0, noise_w) if rng else 0.0)
        laps.append(
            aero.AeroLap(
                key=f"{prefix}{i}",
                length_m=TRACK,
                time_s=time_s,
                power_w=power,
                power_sd_w=power * 0.05,
                previous_time_s=times[i - 1] if i else None,
                next_time_s=times[i + 1] if i + 1 < len(times) else None,
            )
        )
    return laps


def test_recovers_cda_and_crr_from_laps_at_several_speeds():
    # A warm-up lap, then efforts at 40, 46 and 52 km/h.
    laps = effort("a", [11.1] * 5) + effort("b", [12.8] * 5) + effort("c", [14.4] * 5)
    result = aero.estimate(laps, CONDITIONS)
    assert result.fit is not None
    assert result.fit.crr_source == "fitted"
    assert result.fit.cda_m2 == pytest.approx(CDA, rel=1e-9)
    assert result.fit.crr == pytest.approx(CRR, rel=1e-9)
    assert result.fit.r_squared == pytest.approx(1.0)
    assert result.fit.laps_used == 12  # the first lap of each effort is left out
    assert [p.issue for p in result.points if not p.used] == [aero.FIRST_LAP] * 3
    assert all(p.cda_m2 == pytest.approx(CDA) for p in result.points if p.used)


def test_one_speed_holds_crr_and_still_finds_cda():
    laps = effort("a", [15.0] * 8, crr=physics.DEFAULT_CRR)
    result = aero.estimate(laps, CONDITIONS)
    assert result.fit.crr_source == "default"
    assert result.fit.crr == physics.DEFAULT_CRR
    assert result.fit.cda_m2 == pytest.approx(CDA, rel=1e-9)
    assert result.fit.r_squared is None  # every lap the same speed: no line to explain
    assert result.fit.speed_spread == pytest.approx(0)


def test_a_given_crr_is_held_even_when_it_could_be_fitted():
    laps = effort("a", [11.1] * 5) + effort("b", [14.4] * 5)
    result = aero.estimate(laps, CONDITIONS, crr=0.004)
    assert result.fit.crr_source == "given"
    assert result.fit.crr == 0.004
    # The wrong Crr pushes CdA off: the extra rolling force is put on drag.
    assert result.fit.cda_m2 < CDA


def test_noisy_power_still_lands_close():
    rng = random.Random(7)
    laps = []
    for i, speed in enumerate([10.5, 11.5, 12.5, 13.5, 14.5, 15.5]):
        laps += effort(f"e{i}", [speed] * 6, noise_w=4, rng=rng)
    result = aero.estimate(laps, CONDITIONS)
    assert result.fit.crr_source == "fitted"
    assert result.fit.cda_m2 == pytest.approx(CDA, abs=0.01)
    assert result.fit.cda_m2 - 3 * result.fit.cda_se_m2 < CDA < result.fit.cda_m2 + 3 * result.fit.cda_se_m2
    assert result.fit.r_squared > 0.95


def test_an_implausible_fitted_crr_falls_back_to_the_default():
    # Power that doesn't grow with speed as drag would: the free line's
    # intercept comes out negative: a 5 N push on top of the drag at every speed.
    laps = effort("a", [11.0] * 4, crr=0.0) + effort("b", [14.0] * 4, crr=0.0)
    laps = [replace(lap, power_w=lap.power_w - 5 * lap.speed_ms / physics.DEFAULT_EFFICIENCY) for lap in laps]
    result = aero.estimate(laps, CONDITIONS)
    assert result.fit.crr_source == "default"
    assert 0 < result.fit.cda_m2 < 1


def test_speeding_up_is_not_counted_as_drag():
    # Each lap 1% faster than the last: the power also paid for the speed gained.
    speeds = [13.0 * 1.01**i for i in range(8)]
    times = [TRACK / v for v in speeds]
    mass = MASS + physics.DEFAULT_ROTATING_MASS_KG
    laps = []
    for i, (v, t) in enumerate(zip(speeds, times)):
        v_in = (speeds[i - 1] + v) / 2 if i else v
        v_out = (v + speeds[i + 1]) / 2 if i + 1 < len(speeds) else v
        kinetic = 0.5 * mass * (v_out**2 - v_in**2)
        power = steady_power(v) + kinetic / t / physics.DEFAULT_EFFICIENCY
        previous = times[i - 1] if i else None
        following = times[i + 1] if i + 1 < len(times) else None
        laps.append(aero.AeroLap(f"l{i}", TRACK, t, power, None, previous, following))
    with_correction = aero.estimate(laps, CONDITIONS, crr=CRR)
    assert with_correction.fit.cda_m2 == pytest.approx(CDA, rel=1e-9)
    # Ignoring the speed change would overstate CdA noticeably.
    naive = [p.power_w * physics.DEFAULT_EFFICIENCY / p.speed_ms for p in with_correction.points[1:]]
    corrected = [p.resistance_n for p in with_correction.points[1:]]
    assert all(n > c for n, c in zip(naive, corrected))


def test_unsteady_laps_are_skipped_automatically():
    laps = effort("a", [12.0, 12.0, 12.0, 13.0, 13.0, 13.0, 13.0])
    laps.append(aero.AeroLap("slow", TRACK, TRACK / 7.0, 60.0, None, TRACK / 13.0, None))
    laps.append(aero.AeroLap("surgy", TRACK, TRACK / 13.0, 400.0, 150.0, TRACK / 13.0, TRACK / 13.0))
    laps.append(aero.AeroLap("blank", TRACK, TRACK / 13.0, None, None, TRACK / 13.0, TRACK / 13.0))
    laps.append(aero.AeroLap("cut", TRACK, TRACK / 13.0, 400.0, None, TRACK / 13.0, None, excluded=True))
    issues = {p.key: p.issue for p in aero.estimate(laps, CONDITIONS).points}
    assert issues == {
        "a0": aero.FIRST_LAP,
        "a1": None,
        "a2": aero.UNSTEADY_SPEED,  # the next lap is 8% faster
        "a3": aero.UNSTEADY_SPEED,
        "a4": None,
        "a5": None,
        "a6": None,
        "slow": aero.TOO_SLOW,
        "surgy": aero.UNSTEADY_POWER,
        "blank": aero.NO_POWER,
        "cut": aero.EXCLUDED,
    }


def test_a_hand_picked_selection_replaces_the_automatic_one():
    laps = effort("a", [12.0] * 3 + [13.0] * 3)
    picked = {"a0", "a2", "a3", "a5"}
    result = aero.estimate(laps, CONDITIONS, selected=picked)
    assert {p.key for p in result.points if p.used} == picked
    assert result.fit.laps_used == 4
    # Excluded and power-less laps stay out even when picked.
    laps[1] = replace(laps[1], excluded=True)
    laps[4] = replace(laps[4], power_w=None)
    result = aero.estimate(laps, CONDITIONS, selected={"a1", "a4", "a5"})
    assert [p.key for p in result.points if p.used] == ["a5"]
    assert result.fit is None  # one lap isn't enough


def test_power_below_rolling_resistance_gives_no_fit_instead_of_a_negative_cda():
    # A meter reading far too low (or a recording from another ride): at one
    # speed Crr is held, so the fit would otherwise come out with CdA <= 0.
    laps = [replace(lap, power_w=lap.power_w * 0.05, power_sd_w=lap.power_w * 0.01) for lap in effort("a", [15.0] * 8)]
    result = aero.estimate(laps, CONDITIONS)
    assert result.fit is None
    assert sum(p.used for p in result.points) >= aero.MIN_LAPS  # lap count isn't the reason


def test_power_far_above_the_physics_gives_no_fit_instead_of_a_huge_cda():
    laps = [replace(lap, power_w=lap.power_w * 6, power_sd_w=lap.power_w * 0.01) for lap in effort("a", [15.0] * 8)]
    assert aero.estimate(laps, CONDITIONS).fit is None


def test_too_few_laps_give_points_but_no_estimate():
    result = aero.estimate(effort("a", [13.0] * 3), CONDITIONS)  # first lap skipped → 2 usable
    assert result.fit is None
    assert [p.used for p in result.points] == [False, True, True]
    assert result.points[1].cda_m2 == pytest.approx(
        aero.lap_cda_m2(13.0, result.points[1].resistance_n, physics.DEFAULT_CRR, CONDITIONS)
    )


def test_window_stats_gives_the_spread_of_power_over_a_lap():
    mean, sd = fusion.window_stats([0, 1, 2, 3], [100, 300, 100, 300], 0, 4)
    assert mean == pytest.approx(200)
    assert sd == pytest.approx(100)
    assert fusion.window_stats([0, 1], [None, None], 0, 2) is None
