"""Headline numbers of a parsed activity — pure functions."""

from dataclasses import dataclass

from app.activities.parsers.base import ParsedActivity

# A gap between samples longer than this is a pause (auto-pause, a stop),
# not riding: the sample before it counts for one second instead.
MAX_SAMPLE_GAP_S = 10.0
# Below this speed the rider is stopped.
MOVING_SPEED_MPS = 0.5
# Altitude changes smaller than this are sensor noise, not climbing.
ELEVATION_NOISE_M = 2.0


@dataclass
class ActivitySummary:
    elapsed_s: float
    moving_s: float
    distance_m: float | None
    elevation_gain_m: float | None
    avg_power_w: float | None
    max_power_w: float | None
    avg_heart_rate: float | None
    max_heart_rate: float | None
    avg_cadence: float | None
    avg_speed_mps: float | None


def sample_weights(time_s: list[float]) -> list[float]:
    """How many seconds each sample stands for: the time until the next one."""
    weights = []
    for i, moment in enumerate(time_s):
        gap = time_s[i + 1] - moment if i + 1 < len(time_s) else 1.0
        weights.append(gap if gap <= MAX_SAMPLE_GAP_S else 1.0)
    return weights


def _weighted_mean(values: list[float | None], weights: list[float], *, skip_zero: bool = False) -> float | None:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None and not (skip_zero and v == 0)]
    total = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total if total else None


def _max(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def elevation_gain(altitudes: list[float | None]) -> float | None:
    gain = 0.0
    reference: float | None = None
    seen = False
    for altitude in altitudes:
        if altitude is None:
            continue
        seen = True
        if reference is None or altitude < reference:
            reference = altitude
        elif altitude - reference >= ELEVATION_NOISE_M:
            gain += altitude - reference
            reference = altitude
    return gain if seen else None


def summarize(activity: ParsedActivity) -> ActivitySummary:
    weights = sample_weights(activity.time_s)
    channels = activity.channels
    speed = channels.get("speed_mps")

    if activity.timer_s:
        moving_s = min(activity.timer_s, activity.elapsed_s)
    elif speed is not None:
        moving_s = sum(w for v, w in zip(speed, weights) if v is not None and v >= MOVING_SPEED_MPS)
    else:
        moving_s = activity.elapsed_s

    distance = channels.get("distance_m")
    distance_m = _max(distance) if distance is not None else None
    return ActivitySummary(
        elapsed_s=activity.elapsed_s,
        moving_s=moving_s,
        distance_m=distance_m,
        elevation_gain_m=elevation_gain(channels["altitude_m"]) if "altitude_m" in channels else None,
        avg_power_w=_weighted_mean(channels["power_w"], weights) if "power_w" in channels else None,
        max_power_w=_max(channels["power_w"]) if "power_w" in channels else None,
        avg_heart_rate=_weighted_mean(channels["heart_rate"], weights) if "heart_rate" in channels else None,
        max_heart_rate=_max(channels["heart_rate"]) if "heart_rate" in channels else None,
        # Coasting (0 rpm) isn't pedalling cadence, so zeros are left out.
        avg_cadence=_weighted_mean(channels["cadence"], weights, skip_zero=True) if "cadence" in channels else None,
        avg_speed_mps=distance_m / moving_s if distance_m and moving_s else None,
    )
