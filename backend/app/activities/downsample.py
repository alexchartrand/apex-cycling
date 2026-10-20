"""Thinning a recording for a chart — pure."""

import math
from collections.abc import Sequence

# Channels averaged over a bucket; the cumulative ones (time, distance,
# altitude) are better represented by where the bucket ends.
_AVERAGED = {"power_w", "heart_rate", "cadence", "speed_mps"}


def bucket_size(sample_count: int, max_points: int) -> int:
    return max(1, math.ceil(sample_count / max_points))


def downsample(channel: str, values: Sequence[float | None], size: int) -> list[float | None]:
    """One value per `size` samples: the mean of the readings present for
    power, heart rate, cadence and speed (a power spike inside a bucket is
    smoothed, as on any chart), the last reading for time, distance and altitude."""
    if size <= 1:
        return list(values)
    out: list[float | None] = []
    for start in range(0, len(values), size):
        chunk = values[start : start + size]
        present = [v for v in chunk if v is not None]
        if not present:
            out.append(None)
        elif channel in _AVERAGED:
            out.append(sum(present) / len(present))
        else:
            out.append(present[-1])
    return out
