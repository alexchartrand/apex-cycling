"""The step tree: validation, riding order, duration and TSS."""

import pytest
from pydantic import TypeAdapter, ValidationError

from app.workouts.schemas import WorkoutItem, WorkoutSteps, structure_size
from app.workouts.structure import DEFAULT_TRACK_LENGTH_M, estimate, expand, is_track

ITEMS = TypeAdapter(list[WorkoutItem])


def _items(*raw: dict):
    return ITEMS.validate_python(list(raw))


def test_repeats_unroll_in_riding_order_one_level_deep():
    items = _items(
        {"kind": "warmup", "duration_s": 600, "label": "wu"},
        {
            "type": "repeat",
            "count": 2,
            "steps": [
                {"type": "repeat", "count": 3, "steps": [{"label": "on", "duration_s": 30}, {"label": "off", "duration_s": 30}]},
                {"kind": "recovery", "label": "set rest", "duration_s": 300},
            ],
        },
    )
    labels = [s.label for s in expand(items)]
    assert labels == ["wu"] + (["on", "off"] * 3 + ["set rest"]) * 2
    assert structure_size(items) == 1 + 1 + (1 + 2) + 1  # steps and repeat markers, not reps
    assert estimate(items).duration_s == 600 + 2 * (3 * 60 + 300)


def test_nesting_stops_at_one_level():
    three_deep = {
        "type": "repeat",
        "count": 2,
        "steps": [{"type": "repeat", "count": 2, "steps": [{"type": "repeat", "count": 2, "steps": [{"duration_s": 1}]}]}],
    }
    with pytest.raises(ValidationError):
        _items(three_deep)


@pytest.mark.parametrize(
    "step",
    [
        {"duration_s": 60, "laps": 2},  # two lengths
        {"start_type": "standing"},  # a start goes with an event
        {"target_time_ms": 30_000},
        {"event_key": "marathon"},
        {"event_key": "f200", "start_type": "standing"},
        {"power": {"unit": "ftp_pct", "low": 120, "high": 100}},
        {"power": {"unit": "ftp_pct", "low": 400}},
        {"cadence": {"low": 110, "high": 90}},
        {"rpe": 11},
        {"gear": {"chainring_teeth": 50, "cog_teeth": 2}},
    ],
)
def test_a_bad_step_is_refused(step):
    with pytest.raises(ValidationError):
        _items(step)


def test_too_many_steps_are_refused():
    many = [{"duration_s": 10}] * 50
    assert WorkoutSteps(steps=many).steps
    with pytest.raises(ValidationError):  # 5 × (1 marker + 20 steps) = 105
        WorkoutSteps(steps=[{"type": "repeat", "count": 2, "steps": [{"duration_s": 1}] * 20}] * 5)


def test_track_steps_take_their_length_from_laps_or_the_event():
    items = _items(
        {"kind": "recovery", "laps": 4},  # 1000 m at the easy speed
        {"event_key": "500m", "start_type": "standing", "target_time_ms": 34_000},  # the target time
        {"event_key": "lap", "start_type": "flying"},  # one lap at the effort speed
        {"event_key": "f200", "laps": 3, "target_time_ms": 11_000},  # wind-up laps at the 200's speed
    )
    assert is_track(items)
    durations = [s.duration_s for s in estimate(items).segments]
    assert durations == pytest.approx([1000 / 10, 34.0, 250 / 14, 750 / (200 / 11)])
    # A known track changes what laps mean.
    assert estimate(items[:1], track_length_m=333.33).segments[0].duration_s == pytest.approx(333.33 * 4 / 10)
    assert DEFAULT_TRACK_LENGTH_M == 250


def test_a_generic_workout_isnt_track():
    assert not is_track(_items({"distance_m": 2000}, {"duration_s": 60, "gear": {"chainring_teeth": 50, "cog_teeth": 15}}))


def test_tss_counts_power_then_rpe_and_reports_the_rest():
    items = _items(
        {"duration_s": 3600, "power": {"unit": "ftp_pct", "low": 100}},  # 100 TSS
        {"duration_s": 1800, "power": {"unit": "ftp_pct", "low": 50, "high": 70}},  # IF 0.6 → 18
        {"duration_s": 600, "rpe": 5},  # IF 0.7 → 8.17
        {"duration_s": 300, "label": "spin"},  # no intensity
        {"label": "until ready"},  # open
    )
    result = estimate(items)
    assert result.duration_s == 3600 + 1800 + 600 + 300
    assert result.tss == pytest.approx(100 + 18 + 600 / 3600 * 0.7**2 * 100, abs=0.05)
    assert result.unrated_s == 300 and result.open_steps == 1
    assert [s.start_s for s in result.segments] == [0, 3600, 5400, 6000]
    second = result.segments[1]
    assert (second.power_low, second.power_high, second.intensity) == pytest.approx((0.5, 0.7, 0.6))


def test_watts_need_an_ftp():
    items = _items({"duration_s": 3600, "power": {"unit": "watts", "low": 200}})
    assert estimate(items).tss is None and estimate(items).unrated_s == 3600
    assert estimate(items, ftp_w=250).tss == pytest.approx(64.0)
