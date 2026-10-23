"""Taper and countdown arithmetic for the race calendar — pure."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Priority = Literal["A", "B", "C"]

# Days of reduced load before a race: the season's goal race gets the longest
# taper, a B race a short one, and a C race is trained through.
TAPER_DAYS: dict[str, int] = {"A": 10, "B": 5, "C": 0}

Phase = Literal["past", "race_day", "taper", "build"]


@dataclass(frozen=True)
class Countdown:
    days_until: int
    # The first day of the taper; null when the race has none (a C race).
    taper_starts_on: date | None
    # Days until the taper begins; null when there is none or it has started.
    days_to_taper: int | None
    phase: Phase


def countdown(race_date: date, priority: str, today: date) -> Countdown:
    days = (race_date - today).days
    taper_days = TAPER_DAYS.get(priority, 0)
    taper_start = race_date - timedelta(days=taper_days) if taper_days else None
    if days < 0:
        phase: Phase = "past"
    elif days == 0:
        phase = "race_day"
    elif taper_start is not None and today >= taper_start:
        phase = "taper"
    else:
        phase = "build"
    until_taper = (taper_start - today).days if taper_start is not None and phase != "past" else None
    return Countdown(
        days_until=days,
        taper_starts_on=taper_start,
        days_to_taper=until_taper if until_taper is not None and until_taper > 0 else None,
        phase=phase,
    )
