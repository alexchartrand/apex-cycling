"""Predicting an event time from power and CdA. Pure: the physics lives in
`analysis/physics.py`, the inputs come from `goals/service.py`.

The rider's power is their best mean power over the duration closest to the
time they are aiming for (the power curve, from any ride), taken as the
*average* of the effort. The simulator's standing start spends more than the
race power at the beginning, so the race power is scaled until the simulated
average matches. The result is an estimate, a few percent either way: track
power often differs from road or trainer power, and the CdA depends on the
position it was measured in.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.analysis import physics


@dataclass(frozen=True)
class PowerPick:
    duration_s: int
    power_w: float


def pick_power(curve: Sequence[tuple[int, float]], target_s: float) -> PowerPick | None:
    """The (duration, power) of the curve whose duration is closest to
    `target_s` in ratio (a 70 s goal sits nearer 60 s than 120 s)."""
    if not curve or target_s <= 0:
        return None
    duration, power = min(curve, key=lambda point: abs(math.log(point[0] / target_s)))
    return PowerPick(duration, power)


def predict_time_s(
    distance_m: float, standing: bool, average_power_w: float, setup: physics.Setup
) -> float | None:
    """Time for `distance_m` at an *average* power of `average_power_w`."""
    if average_power_w <= 0 or distance_m <= 0:
        return None
    race_power = average_power_w
    ride = None
    for _ in range(3):  # the average is nearly proportional to the race power: two corrections settle it
        ride = physics.simulate(distance_m, race_power, setup, standing=standing)
        if ride is None or ride.average_power_w <= 0:
            return None
        race_power *= average_power_w / ride.average_power_w
    return ride.time_s
