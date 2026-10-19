"""UCI / Cycling Canada age categories, computed from a birthdate.

Cycling uses "race age": the age the rider turns during the calendar year
(year minus birth year), so a whole season is ridden in one category.
"""

from dataclasses import dataclass
from datetime import date

# (highest race age, code), checked in order; anything older is masters.
_YOUTH_TO_ELITE: tuple[tuple[int, str], ...] = (
    (10, "U11"),
    (12, "U13"),
    (14, "U15"),
    (16, "U17"),
    (18, "U19"),
    (22, "U23"),
    (29, "ELITE"),
)
MASTERS_FROM_AGE = 30
MASTERS_BAND_YEARS = 5


@dataclass(frozen=True)
class AgeCategory:
    """`code` is a stable, untranslated key (U11…U23, ELITE, or M30, M35…
    for the five-year masters bands); the frontend renders the label."""

    code: str
    race_age: int


def race_age(birthdate: date, on: date) -> int:
    return on.year - birthdate.year


def age_category(birthdate: date | None, on: date | None = None) -> AgeCategory | None:
    if birthdate is None:
        return None
    age = race_age(birthdate, on or date.today())
    if age < 0:
        return None
    for max_age, code in _YOUTH_TO_ELITE:
        if age <= max_age:
            return AgeCategory(code, age)
    band = MASTERS_FROM_AGE + (age - MASTERS_FROM_AGE) // MASTERS_BAND_YEARS * MASTERS_BAND_YEARS
    return AgeCategory(f"M{band}", age)
