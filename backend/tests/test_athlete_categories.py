from datetime import date

import pytest

from app.athletes.categories import age_category


@pytest.mark.parametrize(
    ("birth_year", "expected"),
    [
        (2016, "U11"),  # race age 10
        (2015, "U13"),
        (2014, "U13"),  # 12
        (2012, "U15"),
        (2010, "U17"),  # 16
        (2009, "U19"),  # 17: junior
        (2008, "U19"),
        (2007, "U23"),  # 19
        (2004, "U23"),  # 22
        (2003, "ELITE"),
        (1997, "ELITE"),  # 29
        (1996, "M30"),  # 30
        (1992, "M30"),  # 34
        (1991, "M35"),
        (1971, "M55"),
    ],
)
def test_category_uses_race_age_in_the_season(birth_year, expected):
    on = date(2026, 3, 1)
    assert age_category(date(birth_year, 12, 31), on).code == expected
    # Race age doesn't depend on the birthday: same category all season.
    assert age_category(date(birth_year, 1, 1), on).code == expected


def test_category_reports_race_age():
    assert age_category(date(1990, 11, 30), date(2026, 1, 15)).race_age == 36


def test_no_category_without_birthdate_or_for_future_birthdate():
    assert age_category(None) is None
    assert age_category(date(2030, 1, 1), date(2026, 1, 1)) is None
