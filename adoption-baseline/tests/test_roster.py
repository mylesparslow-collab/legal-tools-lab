from datetime import date

import pytest

from baseline.roster import ELIGIBLE, LEFT, NOT_STARTED, ON_LEAVE, RosterError, load_roster
from helpers import MONDAYS, TOOLS, make_analysis, make_roster, person, use, write_csv

W1, W2, W3, W4 = MONDAYS


def one(tmp_path, **kw):
    return make_roster(tmp_path, [person("P1", **kw)]).people["P1"]


def test_not_started_until_the_week_containing_the_start_date(tmp_path):
    p = one(tmp_path, start_date="2026-09-17")          # a Thursday in week 2
    assert p.week_status(W1) == NOT_STARTED
    assert p.week_status(W2) == ELIGIBLE
    assert p.week_status(W3) == ELIGIBLE


def test_start_on_sunday_counts_for_that_week(tmp_path):
    assert one(tmp_path, start_date="2026-09-13").week_status(W1) == ELIGIBLE
    assert one(tmp_path, start_date="2026-09-14").week_status(W1) == NOT_STARTED


def test_leave_covering_monday_to_friday_excludes_the_week(tmp_path):
    p = one(tmp_path, leave_periods="2026-09-14/2026-09-18")
    assert [p.week_status(w) for w in MONDAYS] == [ELIGIBLE, ON_LEAVE, ELIGIBLE, ELIGIBLE]


def test_partial_leave_does_not_exclude_the_week(tmp_path):
    p = one(tmp_path, leave_periods="2026-09-14/2026-09-17")     # Monday to Thursday
    assert p.week_status(W2) == ELIGIBLE


def test_two_leave_periods_that_together_cover_the_week_exclude_it(tmp_path):
    p = one(tmp_path, leave_periods="2026-09-16/2026-09-18;2026-09-14/2026-09-15")
    assert p.week_status(W2) == ON_LEAVE


def test_long_leave_excludes_every_week_it_covers(tmp_path):
    p = one(tmp_path, leave_periods="2026-09-01/2026-12-31")
    assert all(p.week_status(w) == ON_LEAVE for w in MONDAYS)


def test_left_only_after_the_week_containing_the_end_date(tmp_path):
    p = one(tmp_path, end_date="2026-09-15")
    assert [p.week_status(w) for w in MONDAYS] == [ELIGIBLE, ELIGIBLE, LEFT, LEFT]


def test_practice_change_takes_effect_on_its_date(tmp_path):
    roster = make_roster(tmp_path, [person("P1", practice="Old"),
                                    person("P1", practice="New", effective_from="2026-09-21")])
    p = roster.people["P1"]
    assert len(roster) == 1 and p.changed_practice()
    assert p.assignment_on(date(2026, 9, 20)).practice == "Old"
    assert p.assignment_on(date(2026, 9, 21)).practice == "New"


def test_unreadable_roster_rows_are_skipped_and_counted(tmp_path):
    roster = make_roster(tmp_path, [person("P1"), person("P2", role="wizard"), person("P3", start_date="soon"),
                                    person("P4", licence_assistant_a="maybe"), person("P1")])
    assert sorted(roster.people) == ["P1"]
    assert roster.issues["rows_skipped_invalid"] == 3
    assert roster.issues["duplicate_assignment_rows"] == 1


def test_roster_missing_a_licence_column_fails_loudly(tmp_path):
    path = write_csv(tmp_path, "r.csv", ["person_id", "name", "email", "role", "practice", "office", "start_date"], [])
    with pytest.raises(RosterError) as exc:
        load_roster(path, TOOLS)
    assert "licence_assistant_a" in str(exc.value)


def test_roster_people_with_no_usage_count_as_zero_not_missing(tmp_path):
    a = make_analysis(tmp_path, [person("P%d" % i) for i in range(1, 11)], [use("P1", "2026-09-08")])
    c = a.weekly_active([W1])
    assert (c["n"], c["d"]) == (1, 10)
    assert a.roster_quality()["people_with_no_usage_counted_as_zero"] == 9


def test_denominator_drops_people_on_leave_or_not_started_for_that_week_only(tmp_path):
    rows = [person("P1"), person("P2", leave_periods="2026-09-14/2026-09-18"),
            person("P3", start_date="2026-09-21"), person("P4", end_date="2026-09-10")]
    a = make_analysis(tmp_path, rows, [])
    assert [w["d"] for w in a.weekly_trend()] == [3, 1, 3, 3]
    assert a.weekly_trend()[1]["excluded"] == {"not_started": 1, "on_leave": 1, "left": 1}


def test_usage_during_a_week_of_full_leave_is_not_counted_but_is_reported(tmp_path):
    rows = [person("P1", leave_periods="2026-09-14/2026-09-18"), person("P2")]
    a = make_analysis(tmp_path, rows, [use("P1", "2026-09-16")])
    c = a.weekly_active([W2])
    assert (c["n"], c["d"]) == (0, 1)
    assert a.roster_quality()["person_weeks_with_usage_during_full_leave"] == 1
