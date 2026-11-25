"""California judicial holidays.

Two sources, in this order:

1. OFFICIAL: the Judicial Council's published court holiday schedules for 2026
   and 2027, copied from https://courts.ca.gov/about/court-holidays as read on
   2026-11-25. These are used as written.

2. COMPUTED: for any other year, a rule-based list built from Code Civ. Proc.
   § 135 and Gov. Code §§ 6700-6701 (text read on leginfo 2026-11-25). A computed
   year is an estimate. The Judicial Council may designate a different day when a
   holiday falls on a weekend (§ 135), so check the published schedule before
   relying on a computed year. Every result that touches a computed year says so.

Section 135 makes every full-day holiday in Gov. Code § 6700 a judicial holiday
except Lunar New Year, Diwali, Genocide Remembrance Day (April 24), Admission Day
(September 9) and Columbus Day, and adds every Saturday and the day after
Thanksgiving. Good Friday (noon to 3 p.m.) is not a full day and is not included.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

OFFICIAL_SOURCE = "courts.ca.gov/about/court-holidays, read 2026-11-25"

OFFICIAL: dict[int, dict[date, str]] = {
    2026: {
        date(2026, 1, 1): "New Year's Day",
        date(2026, 1, 19): "Dr. Martin Luther King, Jr. Day",
        date(2026, 2, 12): "Lincoln's Birthday",
        date(2026, 2, 16): "Presidents' Day",
        date(2026, 3, 31): "Farmworkers Day",
        date(2026, 5, 25): "Memorial Day",
        date(2026, 6, 19): "Juneteenth",
        date(2026, 7, 3): "Independence Day (observed)",
        date(2026, 9, 7): "Labor Day",
        date(2026, 9, 25): "Native American Day",
        date(2026, 11, 11): "Veterans Day",
        date(2026, 11, 26): "Thanksgiving Day",
        date(2026, 11, 27): "Day after Thanksgiving",
        date(2026, 12, 25): "Christmas Day",
    },
    2027: {
        date(2027, 1, 1): "New Year's Day",
        date(2027, 1, 18): "Dr. Martin Luther King, Jr. Day",
        date(2027, 2, 12): "Lincoln's Birthday",
        date(2027, 2, 15): "Washington's Birthday",
        # The published 2027 schedule lists Farmworkers Day (formerly Cesar Chavez
        # Day) on Friday, April 9, not March 31. Copied as published.
        date(2027, 4, 9): "Farmworkers Day (as published)",
        date(2027, 5, 31): "Memorial Day",
        date(2027, 6, 18): "Juneteenth (observed)",
        date(2027, 7, 5): "Independence Day (observed)",
        date(2027, 9, 6): "Labor Day",
        date(2027, 9, 24): "Native American Day",
        date(2027, 11, 11): "Veterans Day",
        date(2027, 11, 25): "Thanksgiving Day",
        date(2027, 11, 26): "Day after Thanksgiving",
        date(2027, 12, 24): "Christmas Day (observed)",
    },
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    """Weekend rule assumed for computed years: Saturday to Friday, Sunday to Monday."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def computed_holidays(year: int) -> dict[date, str]:
    """Rule-based judicial holidays whose observed date falls in the given year."""
    out: dict[date, str] = {}
    for y in (year, year + 1):
        thanksgiving = _nth_weekday(y, 11, 3, 4)
        named = [
            (date(y, 1, 1), "New Year's Day"),
            (_nth_weekday(y, 1, 0, 3), "Dr. Martin Luther King, Jr. Day"),
            (date(y, 2, 12), "Lincoln Day"),
            (_nth_weekday(y, 2, 0, 3), "Third Monday in February"),
            (date(y, 3, 31), "Farmworkers Day"),
            (_last_weekday(y, 5, 0), "Memorial Day"),
            (date(y, 6, 19), "Juneteenth"),
            (date(y, 7, 4), "Independence Day"),
            (_nth_weekday(y, 9, 0, 1), "Labor Day"),
            (_nth_weekday(y, 9, 4, 4), "Native American Day"),
            (date(y, 11, 11), "Veterans Day"),
            (thanksgiving, "Thanksgiving Day"),
            (thanksgiving + timedelta(days=1), "Day after Thanksgiving"),
            (date(y, 12, 25), "Christmas Day"),
        ]
        for actual, name in named:
            obs = _observed(actual)
            if obs.year == year:
                out[obs] = name if obs == actual else f"{name} (observed)"
    return out


@lru_cache(maxsize=None)
def judicial_holidays(year: int) -> dict[date, str]:
    """Judicial holidays (other than Saturdays and Sundays) for a year."""
    return dict(OFFICIAL[year]) if year in OFFICIAL else computed_holidays(year)


def holiday_source(year: int) -> str:
    return "official" if year in OFFICIAL else "computed"


def is_court_day(d: date) -> bool:
    """True if courts are open: not a Saturday, Sunday or judicial holiday."""
    return d.weekday() < 5 and d not in judicial_holidays(d.year)


def why_closed(d: date) -> str | None:
    if d.weekday() == 5:
        return "Saturday"
    if d.weekday() == 6:
        return "Sunday"
    return judicial_holidays(d.year).get(d)
