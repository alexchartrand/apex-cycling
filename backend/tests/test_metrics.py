import math
from datetime import date, timedelta

import pytest

from app.analysis import metrics


# --- resampling ------------------------------------------------------------


def test_one_hertz_data_comes_back_unchanged():
    assert metrics.resample_1hz([0, 1, 2, 3], [100, 200, None, 400]) == [100, 200, 0, 400]


def test_smart_recording_holds_the_last_reading():
    # Readings only when the value changes: 100 W for 3 s, then 300 W.
    assert metrics.resample_1hz([0, 3, 4], [100, 300, 300]) == [100, 100, 100, 300, 300]


def test_a_pause_is_zero_watts_or_left_out():
    time_s, power = [0, 1, 2, 62, 63], [200, 200, 200, 200, 200]
    zeroed = metrics.resample_1hz(time_s, power)
    assert len(zeroed) == 64
    assert zeroed[:3] == [200, 200, 200] and set(zeroed[3:62]) == {0.0} and zeroed[62:] == [200, 200]
    skipped = metrics.resample_1hz(time_s, power, pauses="skip")
    assert skipped == [200] * 5  # the stop itself is gone: 3 s before it, 2 s after


def test_empty_series():
    assert metrics.resample_1hz([], []) == []


# --- mean-maximal power ----------------------------------------------------


def test_mmp_finds_the_best_window():
    series = [100.0] * 10 + [300.0] * 5 + [100.0] * 10
    curve = metrics.mean_maximal_power(series, [1, 5, 10, 15, 30])
    assert curve[1] == 300
    assert curve[5] == 300
    assert curve[10] == pytest.approx((300 * 5 + 100 * 5) / 10)
    assert curve[15] == pytest.approx((300 * 5 + 100 * 10) / 15)
    assert 30 not in curve  # longer than the ride


def test_mmp_never_exceeds_the_peak_and_is_not_forced_monotone():
    series = [150 + 100 * math.sin(i / 7) ** 2 for i in range(600)]
    curve = metrics.mean_maximal_power(series)
    assert max(curve.values()) == pytest.approx(curve[1]) == pytest.approx(max(series))
    # Two spikes around a dip: the 3 s window beats the best 2 s one.
    assert metrics.mean_maximal_power([10.0, 0.0, 10.0], [2, 3]) == {2: 5.0, 3: pytest.approx(20 / 3)}


def test_mmp_of_constant_power_is_that_power():
    curve = metrics.mean_maximal_power([250.0] * 3600)
    assert set(curve.values()) == {250.0}
    assert max(curve) == 3600


# --- NP / IF / TSS ---------------------------------------------------------


def test_normalized_power_of_steady_riding_is_the_average():
    assert metrics.normalized_power([200.0] * 600) == pytest.approx(200)


def test_normalized_power_rewards_variability():
    alternating = [100.0] * 60 + [300.0] * 60
    alternating = alternating * 5
    average = sum(alternating) / len(alternating)
    assert average == 200
    assert metrics.normalized_power(alternating) > 220


def test_normalized_power_needs_a_full_window():
    assert metrics.normalized_power([300.0] * 29) is None
    assert metrics.normalized_power([300.0] * 30) == pytest.approx(300)


def test_normalized_power_hand_checked():
    # 30 s at 0 W then 30 s at 400 W: rolling means step 0 -> 400 in 30 steps
    # (window k holds k seconds of 400 W), 31 windows in all.
    series = [0.0] * 30 + [400.0] * 30
    rolling = [400 * k / 30 for k in range(31)]
    expected = (sum(r**4 for r in rolling) / 31) ** 0.25
    assert metrics.normalized_power(series) == pytest.approx(expected)


def test_one_hour_at_ftp_is_100_tss():
    assert metrics.training_stress_score(3600, 250, 250) == pytest.approx(100)
    assert metrics.intensity_factor(200, 250) == pytest.approx(0.8)
    assert metrics.training_stress_score(7200, 200, 250) == pytest.approx(2 * 0.64 * 100)


# --- sRPE ------------------------------------------------------------------


def test_srpe_matches_typical_sessions():
    assert metrics.srpe_training_stress(5, 3600) == pytest.approx(49, abs=0.5)  # an hour of tempo
    assert metrics.srpe_training_stress(3, 7200) == pytest.approx(58.3, abs=0.5)  # two easy hours
    assert metrics.srpe_training_stress(7, 3600) > metrics.srpe_training_stress(5, 3600)
    assert metrics.srpe_training_stress(5, 0) == 0


# --- zones -----------------------------------------------------------------


def test_power_zones_follow_coggan():
    limits = metrics.power_zone_limits(200)
    assert limits == pytest.approx([110, 150, 180, 210, 240, 300])
    seconds = metrics.time_in_zones([100, 110, 111, 190, 205, 400, 301], limits)
    assert seconds == [2, 1, 0, 2, 0, 0, 2]  # 110 W is still zone 1; 190 and 205 W are zone 4; 301 and 400 W zone 7


def test_hr_zones():
    limits = metrics.hr_zone_limits(190)
    assert limits == pytest.approx([114, 133, 152, 171])
    assert metrics.time_in_zones([100, 120, 150, 160, 180], limits) == [1, 1, 1, 1, 1]


# --- CTL / ATL / TSB -------------------------------------------------------


def test_load_with_one_hard_day_then_rest():
    days = metrics.training_load({date(2026, 6, 1): 100.0}, through=date(2026, 7, 1))

    assert days[0].day == date(2026, 6, 1) and days[-1].day == date(2026, 7, 1) and len(days) == 31
    first = days[0]
    assert first.tss == 100
    assert first.ctl == pytest.approx(100 * (1 - math.exp(-1 / 42)))
    assert first.atl == pytest.approx(100 * (1 - math.exp(-1 / 7)))
    assert first.tsb == 0  # nothing before the first day
    # Form going into a day is the day before's CTL - ATL: negative right
    # after the hard day, positive once fatigue (7-day) has faded below
    # fitness (42-day).
    assert days[1].tsb == pytest.approx(first.ctl - first.atl) and days[1].tsb < 0
    assert days[-1].atl < days[-1].ctl
    assert days[-1].tsb == pytest.approx(days[-2].ctl - days[-2].atl)
    assert days[-1].tsb > 0
    assert all(a.atl >= b.atl for a, b in zip(days, days[1:]))


def test_steady_daily_load_converges_to_that_load():
    first = date(2026, 1, 1)
    daily = {first + timedelta(days=i): 60.0 for i in range(400)}
    last = metrics.training_load(daily, through=first + timedelta(days=399))[-1]
    assert last.ctl == pytest.approx(60, abs=0.1)
    assert last.atl == pytest.approx(60, abs=0.01)
    assert last.tsb == pytest.approx(0, abs=0.2)


def test_gaps_decay_and_empty_input():
    days = metrics.training_load({date(2026, 6, 1): 80.0, date(2026, 6, 4): 80.0}, through=date(2026, 6, 4))
    assert [d.tss for d in days] == [80, 0, 0, 80]
    assert metrics.training_load({}, through=date(2026, 6, 4)) == []


def test_load_can_start_from_a_known_fitness():
    days = metrics.training_load({date(2026, 6, 1): 0.0}, through=date(2026, 6, 1), initial_ctl=50, initial_atl=50)
    assert days[0].ctl == pytest.approx(50 * math.exp(-1 / 42))
