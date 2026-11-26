import datetime as dt

from desk.util import (business_days_between, count_value, find_dates, find_time, load_holidays, sentences,
                       shift_business_days)


def test_dates_in_three_written_forms():
    assert find_dates("Proposals due December 18, 2026 at 4:00 p.m.")[0]["date"] == "2026-12-18"
    assert find_dates("Fri., Dec. 11, 2026 - 12:00 noon")[0]["date"] == "2026-12-11"
    assert find_dates("Board approval: 01/26/2027")[0]["date"] == "2027-01-26"


def test_date_range_keeps_both_ends():
    d = find_dates("Oral presentations January 26-27, 2027")[0]
    assert (d["date"], d["end"]) == ("2027-01-26", "2027-01-27")


def test_impossible_date_is_reported_not_guessed():
    d = find_dates("Proposals due February 30, 2027")[0]
    assert d["valid"] is False and d["date"] is None


def test_times():
    assert find_time("at 5:00 p.m.") == "17:00"
    assert find_time("(by 4 PM)") == "16:00"
    assert find_time("12:00 noon") == "12:00"
    assert find_time("12:30 a.m.") == "00:30"
    assert find_time("no time here, 2026") is None


def test_counts_as_words_digits_and_both():
    assert count_value("ten (10)") == (10, True)
    assert count_value("twenty-five") == (25, True)
    assert count_value("15") == (15, True)
    assert count_value("ten (12)") == (12, False)      # word and number disagree


def test_business_days_skip_weekends():
    thu = dt.date(2026, 12, 17)
    assert shift_business_days(thu, -3) == dt.date(2026, 12, 14)
    assert shift_business_days(thu, -4) == dt.date(2026, 12, 11)      # back over a weekend
    assert shift_business_days(dt.date(2026, 12, 19), 0) == dt.date(2026, 12, 18)  # Saturday -> Friday
    assert business_days_between(dt.date(2026, 11, 25), thu) == 16


def test_holidays_only_count_when_supplied(tmp_path):
    d = dt.date(2026, 12, 28)   # Monday
    assert shift_business_days(d, -1) == dt.date(2026, 12, 25)
    p = tmp_path / "h.txt"
    p.write_text("2026-12-25  # closed\n2026-12-24\n")
    hol = load_holidays(str(p))
    assert shift_business_days(d, -1, hol) == dt.date(2026, 12, 23)
    assert load_holidays(None) == frozenset()


def test_sentence_split_keeps_abbreviations_together():
    s = sentences("The dispute with Granite Spur Constructors, Inc. over claims continues. Proposals are due at 2:00 p.m. on Friday.")
    assert len(s) == 2
