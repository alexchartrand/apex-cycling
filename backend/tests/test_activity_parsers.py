from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.activities.parsers import ActivityParseError, parse_activity_file
from app.activities.parsers.base import MAX_SAMPLES, detect_format
from app.activities.summary import elevation_gain, summarize
from tests.fit_builder import build_fit

FIXTURES = Path(__file__).parent / "fixtures" / "activities"
START = datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc)


def _fit_records(seconds: int = 60, **overrides) -> list[dict]:
    return [
        {"t": t, "power": 200 + t, "heart_rate": 130, "cadence": 90, "speed": 10.0, "distance": 10.0 * t,
         "altitude": 100.0, **overrides}
        for t in range(seconds)
    ]  # fmt: skip


# --- FIT -------------------------------------------------------------------


def test_fit_channels_and_scaling():
    parsed = parse_activity_file(build_fit(START, _fit_records(5)))

    assert parsed.start_time == START
    assert parsed.time_s == [0, 1, 2, 3, 4]
    assert parsed.channels["power_w"] == [200, 201, 202, 203, 204]
    assert parsed.channels["heart_rate"] == [130] * 5
    assert parsed.channels["speed_mps"] == [10.0] * 5
    assert parsed.channels["distance_m"] == [0, 10, 20, 30, 40]
    assert parsed.channels["altitude_m"] == [100.0] * 5
    assert parsed.sport == "cycling"
    assert parsed.timer_s == 4
    assert parsed.extra["format"] == "fit"


def test_fit_dropouts_are_gaps_not_zeros():
    records = _fit_records(4)
    records[2]["power"] = None
    parsed = parse_activity_file(build_fit(START, records))
    assert parsed.channels["power_w"] == [200, 201, None, 203]


def test_fit_without_power_has_no_power_channel():
    records = [{k: v for k, v in r.items() if k != "power"} for r in _fit_records(5)]
    assert "power_w" not in parse_activity_file(build_fit(START, records)).channels


def test_fit_with_a_bad_crc_is_rejected():
    with pytest.raises(ActivityParseError, match="corrupt FIT"):
        parse_activity_file(build_fit(START, _fit_records(5), corrupt_crc=True))


def test_truncated_fit_is_rejected():
    with pytest.raises(ActivityParseError):
        parse_activity_file(build_fit(START, _fit_records(30))[:60])


def test_glitchy_readings_are_blanked():
    records = _fit_records(4)
    records[1]["power"] = 9000  # a power-meter spike
    records[2]["heart_rate"] = 0  # strap lost contact
    parsed = parse_activity_file(build_fit(START, records))
    assert parsed.channels["power_w"][1] is None
    assert parsed.channels["heart_rate"][2] is None


# --- TCX -------------------------------------------------------------------


def test_tcx():
    parsed = parse_activity_file((FIXTURES / "ride.tcx").read_bytes())

    assert parsed.start_time == datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc)
    assert parsed.time_s == [0, 1, 2, 4]
    assert parsed.channels["power_w"] == [0, 200, 400, 300]
    assert parsed.channels["heart_rate"] == [120, 124, 130, 134]
    assert parsed.channels["cadence"] == [80, 85, 0, 90]
    assert parsed.channels["speed_mps"] == [0, 5, 6, 6]
    assert parsed.channels["distance_m"] == [0, 5, 11, 23]
    assert parsed.sport == "Biking"
    assert parsed.timer_s == 4


# --- GPX -------------------------------------------------------------------


def test_gpx_derives_distance_and_speed_from_positions():
    parsed = parse_activity_file((FIXTURES / "ride.gpx").read_bytes())

    assert parsed.name == "Evening spin"
    assert parsed.sport == "cycling"
    assert parsed.time_s == [0, 10, 20]
    assert parsed.channels["power_w"] == [150, 250, 350]
    assert parsed.channels["heart_rate"] == [110, 115, 120]
    assert parsed.channels["cadence"] == [70, 75, 80]
    # 0.001 degrees of latitude is 111.2 m.
    assert parsed.channels["distance_m"] == pytest.approx([0, 111.19, 222.39], abs=0.1)
    assert parsed.channels["speed_mps"][1:] == pytest.approx([11.119, 11.119], abs=0.01)


def test_gpx_without_timestamps_is_rejected():
    with pytest.raises(ActivityParseError, match="fewer than two"):
        parse_activity_file((FIXTURES / "route-no-times.gpx").read_bytes())


def test_xml_entity_expansion_is_refused():
    with pytest.raises(ActivityParseError, match="invalid GPX"):
        parse_activity_file((FIXTURES / "billion-laughs.gpx").read_bytes())


# --- detection and limits --------------------------------------------------


def test_format_is_detected_from_content():
    assert detect_format(build_fit(START, _fit_records(3))) == "fit"
    assert detect_format((FIXTURES / "ride.tcx").read_bytes()) == "tcx"
    assert detect_format(b"\xef\xbb\xbf" + (FIXTURES / "ride.gpx").read_bytes()) == "gpx"
    assert detect_format(b"hello") is None


@pytest.mark.parametrize("content", [b"", b"hello world", b"<html></html>", b"\x00" * 64])
def test_unsupported_content_is_rejected(content):
    with pytest.raises(ActivityParseError, match="unsupported"):
        parse_activity_file(content)


def test_duplicate_timestamps_are_dropped():
    records = _fit_records(4)
    records.insert(2, {**records[1]})
    assert parse_activity_file(build_fit(START, records)).time_s == [0, 1, 2, 3]


def test_sample_count_is_capped():
    from app.activities.parsers.base import Sample, build_activity

    samples = [Sample(time=START.replace(microsecond=0)) for _ in range(MAX_SAMPLES + 1)]
    with pytest.raises(ActivityParseError, match="too many samples"):
        build_activity(samples)


# --- summary ---------------------------------------------------------------


def test_summary_of_a_steady_fit_ride():
    summary = summarize(parse_activity_file(build_fit(START, _fit_records(11))))

    assert summary.elapsed_s == 10
    assert summary.moving_s == 10  # the device's timer
    assert summary.distance_m == 100
    assert summary.avg_speed_mps == pytest.approx(10.0)
    assert summary.avg_power_w == pytest.approx(205.0)
    assert summary.max_power_w == 210
    assert summary.avg_heart_rate == 130
    assert summary.avg_cadence == 90
    assert summary.elevation_gain_m == 0


def test_summary_cadence_ignores_coasting_and_power_keeps_zeros():
    summary = summarize(parse_activity_file((FIXTURES / "ride.tcx").read_bytes()))

    # Weights are the seconds each sample stands for: 1, 1, 2, then 1 for the last.
    assert summary.avg_power_w == pytest.approx((0 * 1 + 200 * 1 + 400 * 2 + 300 * 1) / 5)
    assert summary.avg_cadence == pytest.approx((80 + 85 + 90) / 3)
    assert summary.elevation_gain_m == 4
    assert summary.distance_m == 23


def test_moving_time_without_a_device_timer_uses_speed():
    records = _fit_records(10)
    for record in records[4:8]:
        record["speed"] = 0.0  # stopped at a light
    parsed = parse_activity_file(build_fit(START, records))
    parsed.timer_s = None
    summary = summarize(parsed)
    assert summary.elapsed_s == 9
    assert summary.moving_s == 6  # samples 0-3 and 8-9 at one second each


def test_long_gaps_count_as_pauses_not_riding():
    records = [{"t": t, "power": 200} for t in (0, 1, 2, 600, 601)]
    parsed = parse_activity_file(build_fit(START, records))
    summary = summarize(parsed)
    assert summary.avg_power_w == 200
    assert summary.elapsed_s == 601


def test_elevation_gain_ignores_noise():
    assert elevation_gain([100, 100.8, 100.2, 101.1, 100.5]) == 0  # sensor jitter
    assert elevation_gain([100, 103, 101, 105]) == pytest.approx(3 + 4)  # ... the dip is walked back
    assert elevation_gain([None, None]) is None
