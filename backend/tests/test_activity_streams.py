import math

import pytest

from app.activities import streams


def test_round_trip_keeps_values_and_gaps():
    power = [0, 150, None, 320.5, 1200]
    assert streams.unpack("power_w", streams.pack("power_w", power)) == power


def test_time_and_distance_keep_double_precision():
    time_s = [0.0, 1.0, 10_799.0, 10_800.5]
    distance_m = [0.0, 8.123456, 99_999.123456]
    assert streams.unpack("time_s", streams.pack("time_s", time_s)) == time_s
    assert streams.unpack("distance_m", streams.pack("distance_m", distance_m)) == distance_m


def test_small_channels_are_float32():
    (value,) = streams.unpack("speed_mps", streams.pack("speed_mps", [11.1]))
    assert value == pytest.approx(11.1, abs=1e-5)
    assert value != 11.1  # float32, not float64


def test_empty_channel():
    assert streams.unpack("heart_rate", streams.pack("heart_rate", [])) == []


def test_three_hour_ride_is_compact():
    seconds = 3 * 3600
    blob = streams.pack("heart_rate", [round(140 + 20 * math.sin(i / 300)) for i in range(seconds)])  # whole bpm, as a head unit records
    assert len(blob) < seconds * 4 / 2  # well under the raw float32 size


def test_unknown_channel_is_rejected():
    with pytest.raises(KeyError):
        streams.pack("temperature", [20.0])
