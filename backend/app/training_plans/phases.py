"""The broad shape of a plan — pure.

`suggest_phases` is the default periodization offered by the plan builder
(and the rule the AI coach is told): the time before the taper split into
base, build and peak in whole weeks counted from the plan's start, then the
taper (`seasons/planning.TAPER_DAYS` by the race's priority) and the race day.
"""

from datetime import date, timedelta

from app.seasons.planning import TAPER_DAYS
from app.training_plans.schemas import Phase, PlanState

# Share of the weeks before the taper: base, build; peak takes the rest.
BASE_SHARE = 0.5
BUILD_SHARE = 0.35
# Under this many weeks there's no room to periodize: it's all build.
MIN_PERIODIZED_WEEKS = 4


def suggest_phases(start: date, end: date, race_priority: str | None = None) -> list[Phase]:
    phases: list[Phase] = []
    last = end
    race: Phase | None = None
    taper: Phase | None = None
    if race_priority is not None and end > start:
        race = Phase(kind="race", start=end, end=end)
        last = end - timedelta(days=1)
        taper_days = TAPER_DAYS.get(race_priority, 0)
        if taper_days and (last - start).days + 1 > taper_days + 7:
            taper = Phase(kind="taper", start=end - timedelta(days=taper_days), end=last)
            last = taper.start - timedelta(days=1)

    days = (last - start).days + 1
    weeks = days // 7
    if weeks < MIN_PERIODIZED_WEEKS:
        phases.append(Phase(kind="build", start=start, end=last))
    else:
        base_weeks = max(1, round(weeks * BASE_SHARE))
        build_weeks = max(1, round(weeks * BUILD_SHARE))
        if base_weeks + build_weeks >= weeks:
            build_weeks = weeks - base_weeks - 1
        base_end = start + timedelta(weeks=base_weeks) - timedelta(days=1)
        build_end = base_end + timedelta(weeks=build_weeks)
        phases.append(Phase(kind="base", start=start, end=base_end))
        phases.append(Phase(kind="build", start=base_end + timedelta(days=1), end=build_end))
        phases.append(Phase(kind="peak", start=build_end + timedelta(days=1), end=last))
    if taper is not None:
        phases.append(taper)
    if race is not None:
        phases.append(race)
    return phases


def current_phase(phases: list[Phase], today: date) -> int | None:
    for index, phase in enumerate(phases):
        if phase.start <= today <= phase.end:
            return index
    return None


def plan_state(start: date, end: date, today: date) -> PlanState:
    if today < start:
        return "upcoming"
    return "finished" if today > end else "active"
