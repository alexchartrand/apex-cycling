"""Planned vs ridden: which effort of the session answers which rep of the plan.

Pure functions. A plan's targets expand into reps in the order written ("3 ×
500 m standing" is three reps); the session's efforts are in the order ridden.
Each rep takes the first effort after the one the previous rep took that has a
result for its event and start — so a warm-up, or an effort that went wrong,
is passed over instead of shifting every rep after it. One effort answers at
most one rep; an effort holding several reps back to back is not split.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from app.training.efforts import StartType


class RepStatus(str, Enum):
    HIT = "hit"  # ridden, at or under the target time
    MISS = "miss"  # ridden, over the target time
    RIDDEN = "ridden"  # ridden, the plan gave no time to hit
    NOT_RIDDEN = "not_ridden"  # no effort of the session answers it
    FREE = "free"  # the plan named no event, so nothing can be measured


@dataclass(frozen=True)
class Rep:
    target_index: int  # position of the target in the plan
    rep: int  # 1-based within the target
    label: str
    event_key: str | None
    start_type: StartType | None
    target_time_ms: int | None


@dataclass(frozen=True)
class EffortResults:
    """What one ridden effort scored: its time per (event, start type)."""

    effort_index: int  # 1-based, as the session's effort list numbers them
    times_ms: Mapping[tuple[str, StartType], int]


@dataclass(frozen=True)
class RepOutcome:
    rep: Rep
    status: RepStatus
    effort_index: int | None = None
    start_type: StartType | None = None
    time_ms: int | None = None
    delta_ms: int | None = None  # time − target; negative = faster


def expand_reps(targets: Sequence[Mapping]) -> list[Rep]:
    """The plan's stored targets (dicts, as `PlannedSession.targets` keeps them) as one entry per rep."""
    reps = []
    for target_index, target in enumerate(targets):
        start = target.get("start_type")
        for rep in range(1, int(target.get("reps", 1)) + 1):
            reps.append(
                Rep(
                    target_index=target_index,
                    rep=rep,
                    label=target["label"],
                    event_key=target.get("event_key"),
                    start_type=StartType(start) if start else None,
                    target_time_ms=target.get("target_time_ms"),
                )
            )
    return reps


def _answer(rep: Rep, effort: EffortResults) -> tuple[StartType, int] | None:
    """The effort's time for the rep's event, the fastest of the starts the
    rep allows (all of them when the plan didn't say)."""
    candidates = [
        (start_type, time_ms)
        for (event_key, start_type), time_ms in effort.times_ms.items()
        if event_key == rep.event_key and (rep.start_type is None or start_type == rep.start_type)
    ]
    return min(candidates, key=lambda c: c[1], default=None)


def match_reps(reps: Sequence[Rep], efforts: Sequence[EffortResults]) -> list[RepOutcome]:
    """One outcome per rep, in plan order. `efforts` oldest first."""
    outcomes = []
    cursor = 0
    for rep in reps:
        if rep.event_key is None:
            outcomes.append(RepOutcome(rep, RepStatus.FREE))
            continue
        found = None
        for position in range(cursor, len(efforts)):
            answer = _answer(rep, efforts[position])
            if answer is not None:
                found = (position, answer)
                break
        if found is None:
            outcomes.append(RepOutcome(rep, RepStatus.NOT_RIDDEN))
            continue
        position, (start_type, time_ms) = found
        cursor = position + 1
        if rep.target_time_ms is None:
            status, delta = RepStatus.RIDDEN, None
        else:
            delta = time_ms - rep.target_time_ms
            status = RepStatus.HIT if delta <= 0 else RepStatus.MISS
        outcomes.append(RepOutcome(rep, status, efforts[position].effort_index, start_type, time_ms, delta))
    return outcomes
