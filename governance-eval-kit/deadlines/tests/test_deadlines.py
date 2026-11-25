"""Tests for the deadlines helper.

Three kinds:
  * the holiday table against the published schedule and the rule-based list
  * hand-worked examples (each one counted out in the comment)
  * a sweep of every hearing date and every service method in 2026-2027 against a
    second implementation that works from an indexed list of court days instead
    of stepping day by day
"""
import sys
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ca_deadlines import compute as c  # noqa: E402
from ca_deadlines import holidays as h  # noqa: E402
from ca_deadlines.__main__ import main  # noqa: E402

D = date


# ---------- holidays ----------

def test_official_years_have_fourteen_holidays_on_weekdays():
    for year in (2026, 2027):
        hol = h.judicial_holidays(year)
        assert len(hol) == 14
        assert all(d.weekday() < 5 and d.year == year for d in hol)
        assert h.holiday_source(year) == "official"


def test_excluded_days_are_court_days():
    # CCP 135 excludes these Gov. Code 6700 holidays from the judicial holidays.
    assert h.is_court_day(D(2026, 4, 24))   # Genocide Remembrance Day (Friday)
    assert h.is_court_day(D(2026, 9, 9))    # Admission Day (Wednesday)
    assert h.is_court_day(D(2026, 10, 12))  # Columbus Day (Monday)
    assert h.is_court_day(D(2027, 3, 31))   # not a court holiday in the published 2027 schedule


def test_rule_based_list_matches_published_2026():
    assert set(h.computed_holidays(2026)) == set(h.OFFICIAL[2026])


def test_rule_based_list_differs_from_published_2027_only_as_documented():
    computed, official = set(h.computed_holidays(2027)), set(h.OFFICIAL[2027])
    # Published: Farmworkers Day on April 9. Rule: March 31.
    # Rule also observes New Year's Day 2028 (a Saturday) on Dec 31, 2027; not in the published 2027 list.
    assert computed - official == {D(2027, 3, 31), D(2027, 12, 31)}
    assert official - computed == {D(2027, 4, 9)}


def test_computed_year_is_flagged():
    assert h.holiday_source(2029) == "computed"
    r = c.add_calendar_days(D(2029, 3, 1), 10)
    assert any("computed" in w for w in r.warnings)


def test_weekend_and_thanksgiving_friday_closed():
    assert not h.is_court_day(D(2026, 11, 27))
    assert not h.is_court_day(D(2026, 11, 28))
    assert h.why_closed(D(2026, 11, 29)) == "Sunday"


# ---------- hand-worked examples ----------

def test_motion_personal_service_across_thanksgiving():
    # Hearing Tue 2026-12-15. Court days back: Dec 14(1) 11(2) 10(3) 9(4) 8(5) 7(6) 4(7) 3(8)
    # 2(9) 1(10) Nov 30(11); Nov 27 and 26 are holidays; Nov 25(12) 24(13) 23(14) 20(15) 19(16).
    s = c.motion_schedule(D(2026, 12, 15), "personal")
    assert s["moving"].date == D(2026, 11, 19)
    assert s["opposition"].date == D(2026, 12, 2)
    assert s["reply"].date == D(2026, 12, 8)


def test_motion_mail_adds_five_calendar_days_counted_back():
    # Nov 19 less 5 calendar days is Sat Nov 14; the earlier court day is Fri Nov 13.
    m = c.motion_schedule(D(2026, 12, 15), "mail")["moving"]
    assert m.date == D(2026, 11, 14)
    assert m.safe_date == D(2026, 11, 13)


def test_motion_overnight_is_two_calendar_days_and_electronic_two_court_days():
    assert c.motion_schedule(D(2026, 12, 15), "overnight")["moving"].date == D(2026, 11, 17)
    assert c.motion_schedule(D(2026, 12, 15), "electronic")["moving"].date == D(2026, 11, 17)
    # Hearing Fri 2026-12-04. Court days back: Dec 3(1) 2(2) 1(3) Nov 30(4); Nov 27, 26 holidays;
    # Nov 25(5) 24(6) 23(7) 20(8) 19(9) 18(10) 17(11) 16(12) 13(13) 12(14); Nov 11 Veterans Day;
    # Nov 10(15) 9(16). So Mon Nov 9. Overnight: two calendar days back is Sat Nov 7 (safe Fri Nov 6).
    # Electronic: two court days back is Fri Nov 6(1), Thu Nov 5(2).
    s_over = c.motion_schedule(D(2026, 12, 4), "overnight")["moving"]
    s_elec = c.motion_schedule(D(2026, 12, 4), "electronic")["moving"]
    assert s_over.date == D(2026, 11, 7) and s_over.safe_date == D(2026, 11, 6)
    assert s_elec.date == D(2026, 11, 5) and s_elec.safe_date is None


def test_motion_hearing_must_be_court_day():
    with pytest.raises(ValueError):
        c.motion_schedule(D(2026, 11, 26))


def test_response_mail_and_electronic():
    # Served Mon 2026-11-02. 30 days: Wed Dec 2. Mail +5: Mon Dec 7. Electronic +2 court days: Fri Dec 4.
    assert c.response_deadline(D(2026, 11, 2), "interrogatories", "mail").date == D(2026, 12, 7)
    assert c.response_deadline(D(2026, 11, 2), "interrogatories", "electronic").date == D(2026, 12, 4)
    assert c.response_deadline(D(2026, 11, 2), "interrogatories", "personal").date == D(2026, 12, 2)


def test_response_rolls_off_weekend_and_holiday():
    # Served Thu 2026-11-05: 30 days is Sat Dec 5, so Mon Dec 7 (CCP 12a).
    assert c.response_deadline(D(2026, 11, 5), "interrogatories").date == D(2026, 12, 7)
    # Served Wed 2026-11-25: 30 days is Fri Dec 25 (holiday), then Sat, Sun, so Mon Dec 28.
    assert c.response_deadline(D(2026, 11, 25), "demurrer").date == D(2026, 12, 28)


def test_court_day_extension_counts_from_unrolled_day():
    # Served Thu 2026-11-05, electronic: day 30 is Sat Dec 5; two court days after it are Mon Dec 7, Tue Dec 8.
    r = c.response_deadline(D(2026, 11, 5), "interrogatories", "electronic")
    assert r.date == D(2026, 12, 8)
    assert any("earlier of the two readings" in s for s in r.steps)


def test_electronic_service_on_a_saturday_is_deemed_made_monday():
    # Sent Sat 2026-11-07: deemed served Mon Nov 9. 30 days: Wed Dec 9. Two court days: Fri Dec 11.
    r = c.response_deadline(D(2026, 11, 7), "interrogatories", "electronic")
    assert r.date == D(2026, 12, 11)
    assert "1010.6(a)(4)" in r.steps[0]


def test_new_trial_notice_not_extended_by_mail():
    # Served Mon 2026-11-02: 15 days is Tue Nov 17, with or without mail.
    assert c.response_deadline(D(2026, 11, 2), "new_trial_notice", "mail").date == D(2026, 11, 17)
    assert c.response_deadline(D(2026, 11, 2), "new_trial_notice", "electronic").date == D(2026, 11, 17)


def test_msj_dates():
    # Hearing Thu 2027-03-18. 81 days back: 18 (March) + 28 (Feb) + 31 (Jan) = 77, 4 more: Sun 2026-12-27.
    # Earlier court day: Dec 25 is a holiday, so Thu Dec 24.
    s = c.msj_schedule(D(2027, 3, 18), "personal", trial=D(2027, 4, 19))
    assert s["moving"].date == D(2026, 12, 27) and s["moving"].safe_date == D(2026, 12, 24)
    assert s["opposition"].date == D(2027, 2, 26)   # 18 + 2 = 20 days back
    assert s["reply"].date == D(2027, 3, 7) and s["reply"].safe_date == D(2027, 3, 5)
    assert s["latest_hearing"].date == D(2027, 3, 20)
    assert not [w for w in s["latest_hearing"].warnings if "less than 30 days" in w]
    late = c.msj_schedule(D(2027, 3, 18), "personal", trial=D(2027, 4, 12))
    assert any("less than 30 days" in w for w in late["latest_hearing"].warnings)
    # Mail adds 5 days: Tue Dec 22.
    assert c.msj_schedule(D(2027, 3, 18), "mail")["moving"].date == D(2026, 12, 22)


def test_msj_rejects_method_the_statute_does_not_list():
    with pytest.raises(ValueError):
        c.msj_schedule(D(2027, 3, 18), "mail_safe_at_home")


def test_farmworkers_day_2027_as_published():
    # One court day after Thu 2027-04-08 skips Fri Apr 9 (published holiday): Mon Apr 12.
    assert c.add_court_days(D(2027, 4, 8), 1).date == D(2027, 4, 12)
    assert c.add_court_days(D(2027, 3, 30), 1).date == D(2027, 3, 31)


# ---------- sweep against a second implementation ----------

START, END = D(2025, 6, 1), D(2028, 6, 30)
ALL = [START + timedelta(days=i) for i in range((END - START).days + 1)]
COURT = [d for d in ALL if h.is_court_day(d)]


def o_back(d, n):      # nth court day strictly before d
    return COURT[bisect_left(COURT, d) - n]


def o_fwd(d, n):       # nth court day strictly after d
    return COURT[bisect_right(COURT, d) + n - 1]


def o_roll(d):         # first court day on or after d
    return COURT[bisect_left(COURT, d)]


HEARINGS = [d for d in COURT if D(2026, 1, 1) <= d <= D(2027, 12, 31)]


def test_sweep_motion_schedule():
    checked = 0
    for hd in HEARINGS:
        base = o_back(hd, 16)
        for method, (n, unit, _) in c._MOTION_EXTENSION.items():
            exp = base - timedelta(days=n) if unit == "calendar" else o_back(base, n)
            s = c.motion_schedule(hd, method)
            assert s["moving"].date == exp, (hd, method)
            assert s["opposition"].date == o_back(hd, 9)
            assert s["reply"].date == o_back(hd, 5)
            assert s["moving"].date < s["opposition"].date < s["reply"].date < hd
            safe = s["moving"].safe_date
            assert (safe is None) == h.is_court_day(exp)
            if safe:
                assert safe < exp and h.is_court_day(safe)
            checked += 1
    assert checked == len(HEARINGS) * 8 and checked > 3900


def test_sweep_response_deadlines():
    checked = 0
    for served in ALL:
        if not D(2026, 1, 1) <= served <= D(2027, 12, 31):
            continue
        for days in (5, 10, 15, 30, 45, 60):
            for method, (_, (n, unit)) in c.SERVICE_METHODS.items():
                eff = o_roll(served) if method == "electronic" else served
                base = eff + timedelta(days=days)
                exp = o_roll(base + timedelta(days=n)) if unit == "calendar" else o_fwd(base, n)
                got = c.response_deadline(served, days, method).date
                assert got == exp, (served, days, method)
                assert h.is_court_day(got) and got >= base
                checked += 1
    assert checked == 730 * 6 * 8


def test_sweep_msj():
    for hd in HEARINGS:
        for method, (n, unit, _) in c._MSJ_EXTENSION.items():
            base = hd - timedelta(days=81)
            exp = base - timedelta(days=n) if unit == "calendar" else o_back(base, n)
            assert c.msj_schedule(hd, method)["moving"].date == exp, (hd, method)


# ---------- command line ----------

def test_cli_json(capsys):
    assert main(["motion", "--hearing", "2026-12-15", "--service", "mail", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"date": "2026-11-14"' in out and '"safe_date": "2026-11-13"' in out and "not legal advice" in out


def test_cli_rejects_closed_hearing_date(capsys):
    assert main(["motion", "--hearing", "2026-12-25"]) == 2
    assert "not a court day" in capsys.readouterr().err
