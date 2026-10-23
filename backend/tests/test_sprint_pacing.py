import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.training.efforts import CheckpointCrossing, LapInput, StartType, build_effort
from app.training.pacing import pacing
from app.training.sprint import sprint_stats

_T0 = datetime(2026, 7, 7, 13, 0, 0, tzinfo=timezone.utc)
_SPRINT_NAMES = ("Courbe 1", "200m", "100m", "50m", "Finish")


def _lap(start_ms: int, times: list[int | None], names=_SPRINT_NAMES, excluded=False, distances=None) -> LapInput:
    distances = distances or [None] * len(times)
    return LapInput(
        lap_id=uuid.uuid4(),
        start_time=_T0 + timedelta(milliseconds=start_ms),
        from_start=True,
        excluded=excluded,
        crossings=tuple(CheckpointCrossing(uuid.uuid4(), n, t, d) for n, t, d in zip(names, times, distances)),
    )


def _chain(laps_times: list[list[int | None]], **kwargs) -> list[LapInput]:
    laps, cursor = [], 0
    for times in laps_times:
        laps.append(_lap(cursor, times, **kwargs))
        cursor += times[-1] or 0
    return laps


def _effort(totals: list[int | None], **kwargs):
    laps, cursor = [], 0
    for total in totals:
        laps.append(_lap(cursor, [total], names=("Finish",), **kwargs))
        cursor += total or 0
    return build_effort(laps, 250.0)


# --- sprint -----------------------------------------------------------------


def test_peak_speed_is_the_fastest_gate_to_gate_stretch():
    # 250 m track: 200m gate = 50 m from the start; stretches 100m→50m = 50 m, 50m→Finish = 50 m.
    lap = _lap(0, [3000, 6000, 10_000, 12_700, 15_000])
    stats = sprint_stats(build_effort([lap], 250.0), 250.0)
    # 200m→100m: 100 m in 4.0 s = 90 km/h; 100m→50m: 50 m in 2.7 s = 66.7; 50m→Finish: 50 m in 2.3 s = 78.3
    assert stats.peak_speed_kmh == pytest.approx(90.0)
    assert stats.peak_speed_lap_id == lap.lap_id


def test_peak_speed_needs_no_track_length():
    lap = _lap(0, [3000, 6000, 10_000, 12_700, 15_000])
    assert sprint_stats(build_effort([lap], None), None).peak_speed_kmh == pytest.approx(90.0)


def test_peak_speed_ignores_short_stretches_and_implausible_readings():
    # 100m→50m→Finish only 50 m apart is fine, but 5 m apart gates are skipped and a
    # missed capture in between just widens the stretch.
    lap = _lap(0, [3000, 6000, None, 9000, 12_000], names=("Courbe 1", "200m", "100m", "50m", "Finish"))
    stats = sprint_stats(build_effort([lap], 250.0), 250.0)
    # 200m→50m: 150 m in 3.0 s = 180 km/h → implausible; 50m→Finish: 50 m / 3 s = 60 km/h.
    assert stats.peak_speed_kmh == pytest.approx(60.0)


def test_peak_speed_skips_excluded_laps():
    slow = _lap(0, [3000, 6000, 12_000, 15_000, 18_000])
    fast = _lap(18_000, [3000, 6000, 10_000, 12_700, 15_000], excluded=True)
    stats = sprint_stats(build_effort([slow, fast], 250.0), 250.0)
    assert stats.peak_speed_lap_id == slow.lap_id


def test_recorded_distance_is_used_when_present():
    lap = _lap(0, [4000, 8000], names=("A", "B"), distances=[30.0, 130.0])
    stats = sprint_stats(build_effort([lap], 250.0), 250.0)
    assert stats.peak_speed_kmh == pytest.approx(90.0)


def test_no_placed_gates_gives_nothing():
    lap = _lap(0, [5000, 10_000], names=("Poursuite 1", "Finish"))
    # Finish alone cannot make a stretch.
    assert sprint_stats(build_effort([lap], 250.0), 250.0).peak_speed_kmh is None


def test_standing_start_launch():
    first = _lap(0, [5000, 8000, 12_000, 14_000, 16_000])  # slow first lap → standing
    later = [_lap(16_000 + i * 11_000, [2500, 4500, 7000, 9000, 11_000]) for i in range(3)]
    effort = build_effort([first, *later], 250.0)
    assert effort.start_type == StartType.STANDING
    stats = sprint_stats(effort, 250.0)
    # Courbe 1 has no position; 200m is 50 m from the start, reached at 8.0 s.
    assert stats.launch_time_ms == 8000
    assert stats.launch_distance_m == 50.0
    assert stats.launch_accel_ms2 == pytest.approx(2 * 50 / 8.0**2)


def test_flying_start_has_no_launch():
    laps = _chain([[2500, 4500, 7000, 9000, 11_000]] * 4)
    effort = build_effort(laps, 250.0)
    assert effort.start_type == StartType.FLYING
    assert sprint_stats(effort, 250.0).launch_time_ms is None


def test_launch_needs_the_track_length():
    first = _lap(0, [5000, 8000, 12_000, 14_000, 16_000])
    later = [_lap(16_000 + i * 11_000, [2500, 4500, 7000, 9000, 11_000]) for i in range(3)]
    effort = build_effort([first, *later], None)
    assert sprint_stats(effort, None).launch_accel_ms2 is None


# --- pacing -----------------------------------------------------------------


def test_even_laps_have_no_spread_or_fade():
    result = pacing(_effort([20_000, 20_000, 20_000, 20_000, 20_000, 20_000]))
    assert result is not None
    assert result.cv_pct == pytest.approx(0)
    assert result.fade_pct == pytest.approx(0)
    assert result.even_pace_ms == 20_000
    assert result.deviations_pct == (0, 0, 0, 0, 0, 0)


def test_fade_compares_the_last_third_to_the_first():
    result = pacing(_effort([20_000, 20_000, 20_500, 20_500, 21_000, 21_000]))
    assert result is not None
    assert result.fade_pct == pytest.approx(5.0)
    assert result.deviations_pct[0] < 0 < result.deviations_pct[-1]


def test_standing_start_first_lap_is_left_out_of_the_reference():
    effort = _effort([26_000, 20_000, 20_000, 20_000, 20_000])
    assert effort.start_type == StartType.STANDING
    result = pacing(effort)
    assert result is not None
    assert result.start_lap_skipped
    assert result.reference_lap_count == 4
    assert result.even_pace_ms == 20_000
    assert result.cv_pct == pytest.approx(0)
    assert result.deviations_pct[0] == pytest.approx(30.0)


def test_excluded_and_unfinished_laps_do_not_count():
    laps = []
    cursor = 0
    for total, excluded in ((20_000, False), (30_000, True), (20_000, False), (20_000, False), (None, False)):
        laps.append(_lap(cursor, [total], names=("Finish",), excluded=excluded))
        cursor += total or 0
    result = pacing(build_effort(laps, 250.0))
    assert result is not None
    assert result.reference_lap_count == 3
    assert result.even_pace_ms == 20_000
    assert result.deviations_pct[1] == pytest.approx(50.0)
    assert result.deviations_pct[-1] is None


def test_few_laps_give_deviations_without_spread_or_fade():
    result = pacing(_effort([20_000, 21_000]))
    assert result is not None
    assert result.cv_pct is None
    assert result.fade_pct is None


def test_a_single_lap_has_no_pacing():
    assert pacing(_effort([20_000])) is None


async def test_the_efforts_endpoint_carries_pacing_and_sprint_fields(client, db_session):
    from tests.test_aero_api import _setup

    athlete_id = await _setup(client, db_session, upload=False)
    efforts = (await client.get(f"/athletes/{athlete_id}/sessions/evt-aero/efforts")).json()
    assert len(efforts) == 3
    first = efforts[0]
    # Six even laps: no spread, no fade. The test track's gates carry distances (80, 150, 200 m):
    # Loop A → Loop B is 70 m in 0.35 × 20 s = 36 km/h; the flying start has no launch.
    assert first["pacing"]["reference_lap_count"] == 6
    assert first["pacing"]["cv_pct"] == pytest.approx(0, abs=0.01)
    assert first["pacing"]["fade_pct"] == pytest.approx(0, abs=0.01)
    assert len(first["pacing"]["deviations_pct"]) == 6
    assert first["peak_speed_kmh"] == pytest.approx(36.0)
    assert first["launch_accel_ms2"] is None
