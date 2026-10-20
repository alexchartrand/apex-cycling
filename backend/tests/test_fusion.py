import random

import pytest

from app.analysis import fusion


# --- window_mean -----------------------------------------------------------


def test_window_mean_over_one_hertz_samples():
    time_s = [0, 1, 2, 3, 4, 5]
    power = [100, 200, 300, 400, 500, 600]
    assert fusion.window_mean(time_s, power, 1, 4) == pytest.approx(300)  # samples at 1, 2, 3
    assert fusion.window_mean(time_s, power, 0.5, 2.5) == pytest.approx((100 * 0.5 + 200 + 300 * 0.5) / 2)


def test_window_mean_holds_a_reading_until_the_next():
    # Smart recording: 100 W from t=0, 300 W from t=4.
    assert fusion.window_mean([0, 4, 5], [100, 300, 300], 2, 6) == pytest.approx((100 * 2 + 300 * 2) / 4)


def test_window_mean_skips_missing_readings_and_needs_enough_data():
    values = [100, None, None, None, 500]
    assert fusion.window_mean([0, 1, 2, 3, 4], values, 0, 5) is None  # 40% covered
    assert fusion.window_mean([0, 1, 2, 3, 4], [100, 200, None, 400, 500], 0, 5) == pytest.approx(300)


def test_window_mean_outside_the_recording_or_across_a_pause():
    assert fusion.window_mean([0, 1, 2], [1, 1, 1], 100, 110) is None
    assert fusion.window_mean([0, 1, 2], [1, 1, 1], 5, 5) is None
    # A 60 s pause: the last reading before it stands for one second only.
    assert fusion.window_mean([0, 1, 61, 62], [100, 100, 500, 500], 0, 62, min_coverage=0.0) == pytest.approx(
        (100 * 2 + 500 * 1) / 3
    )


# --- best_event_match ------------------------------------------------------


def test_picks_the_session_the_ride_covers():
    windows = {"morning": (0, 3600), "evening": (50_000, 53_000)}
    assert fusion.best_event_match((49_000, 56_000), windows) == "evening"
    assert fusion.best_event_match((100, 4000), windows) == "morning"


def test_a_brief_touch_is_not_a_match():
    windows = {"session": (1000, 4600)}
    assert fusion.best_event_match((0, 1200), windows, tolerance_s=0) is None  # 200 of 3600 s
    assert fusion.best_event_match((0, 1200), windows) is None  # even with 5 min of clock slack


def test_clock_slack_lets_a_shifted_ride_match_a_short_window():
    # One flying lap, ride recorded 4 minutes "late" on a bad clock.
    assert fusion.best_event_match((1240, 2000), {"s": (1000, 1090)}) == "s"
    assert fusion.best_event_match((1500, 2000), {"s": (1000, 1090)}) is None


def test_the_larger_overlap_wins():
    windows = {"a": (0, 1000), "b": (500, 1500)}
    assert fusion.best_event_match((400, 1600), windows, tolerance_s=0) == "b"


# --- estimate_clock_offset -------------------------------------------------


def _scenario(true_offset: float, *, noise: float = 0.0, seed: int = 1, hz: float = 1.0):
    """A track session: laps with varying times (a warm-up, then efforts),
    and the head unit's speed trace recorded `true_offset` seconds behind
    sqorz's clock (device time + offset = sqorz time)."""
    rng = random.Random(seed)
    lap_times = [24, 22, 20, 19, 18, 17.5, 17.2, 17, 18, 21, 25, 28, 26, 22, 19, 17.8, 17.3, 17.1, 17, 17.4, 19, 23, 27, 30]
    laps, sqorz_clock = [], 100.0  # sqorz time of the first lap's start
    for duration in lap_times:
        laps.append((sqorz_clock, duration))
        sqorz_clock += duration
    session_end = sqorz_clock

    def speed_at(sqorz_time: float) -> float | None:
        for start, duration in laps:
            if start <= sqorz_time < start + duration:
                return 250 / duration * 3.6 + rng.gauss(0, noise)
        return 3.0  # rolling around before/after

    count = int((session_end + 200) * hz)
    # Device time t is sqorz time t + true_offset.
    time_s = [i / hz for i in range(count)]
    speed = [speed_at(t + true_offset) for t in time_s]
    return laps, time_s, speed


@pytest.mark.parametrize("true_offset", [0.0, 7.0, -13.5, 62.0, -140.25])
def test_recovers_a_known_clock_offset(true_offset):
    laps, time_s, speed = _scenario(true_offset)
    # Laps are positioned on the activity timeline in sqorz time.
    estimate = fusion.estimate_clock_offset(laps, time_s, speed)

    assert estimate is not None
    # 1 Hz sample-and-hold lags the true signal by half a sample: within a second.
    assert estimate.offset_s == pytest.approx(true_offset, abs=1.0)
    assert estimate.correlation > 0.95
    assert estimate.confident
    assert estimate.laps_used >= 19


def test_survives_sensor_noise_and_slow_sampling():
    laps, time_s, speed = _scenario(11.0, noise=1.5, hz=0.5)
    estimate = fusion.estimate_clock_offset(laps, time_s, speed)
    assert estimate is not None and estimate.offset_s == pytest.approx(11.0, abs=1.5)


def test_steady_laps_carry_no_information():
    laps = [(100.0 + 20 * i, 20.0 + (i % 2) * 0.1) for i in range(20)]
    time_s = [float(i) for i in range(600)]
    assert fusion.estimate_clock_offset(laps, time_s, [10.0] * 600) is None


def test_too_few_laps_or_no_speed_data():
    laps, time_s, speed = _scenario(0.0)
    assert fusion.estimate_clock_offset(laps[:5], time_s, speed) is None
    assert fusion.estimate_clock_offset(laps, time_s, [None] * len(time_s)) is None


def test_unrelated_speed_is_not_confident():
    laps, time_s, _ = _scenario(0.0)
    rng = random.Random(7)
    noise = [8 + rng.random() * 6 for _ in time_s]
    estimate = fusion.estimate_clock_offset(laps, time_s, noise)
    assert estimate is None or not estimate.confident


def test_timing_glitches_do_not_throw_the_alignment_off():
    # Real sqorz data holds the odd 6 s "lap" (a missed crossing) that no
    # speed sensor ever shows: the rider kept riding at the neighbours' pace.
    laps, time_s, speed = _scenario(9.0)
    glitched = list(laps)
    for index in (4, 11, 17):
        start, _ = glitched[index]
        glitched[index] = (start, 6.0)

    estimate = fusion.estimate_clock_offset(glitched, time_s, speed)

    assert estimate is not None and estimate.confident
    assert estimate.offset_s == pytest.approx(9.0, abs=1.0)
    assert estimate.laps_used == len(laps) - 3
