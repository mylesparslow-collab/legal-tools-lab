import copy
import os
from datetime import date

import pytest

from baseline import ingest
from baseline.ingest import MappingError
from helpers import END, MAP_LONG, MAP_WIDE, START, make_roster, person, write_csv

PERIOD = (START, END)
A_HEAD = ["id", "ts", "email", "action"]
B_HEAD = ["Day", "User", "Docs", "Mail"]


def roster3(tmp_path):
    return make_roster(tmp_path, [person("P1"), person("P2"), person("P3", licence_assistant_a="no")])


def run_long(tmp_path, rows, mapping=MAP_LONG, period=PERIOD):
    path = write_csv(tmp_path, "a.csv", A_HEAD, rows)
    return ingest.ingest_file(path, mapping, roster3(tmp_path), period)


def run_wide(tmp_path, rows):
    path = write_csv(tmp_path, "b.csv", B_HEAD, rows, delimiter=";")
    return ingest.ingest_file(path, MAP_WIDE, roster3(tmp_path), PERIOD)


def test_long_export_becomes_canonical_rows(tmp_path):
    events, q, _ = run_long(tmp_path, [["1", "2026-09-08T09:00:00+00:00", "p1@firm.example", "chat"]])
    assert events == [{"person_id": "P1", "date": "2026-09-08", "tool": "Assistant A",
                       "feature": "chat", "interactions": 1}]
    assert q["rows_read"] == 1 and q["rows_kept"] == 1 and q["rows_dropped"] == 0


def test_wide_export_gives_one_row_per_feature_with_a_count(tmp_path):
    events, q, _ = run_wide(tmp_path, [["08/09/2026", "Person P1", "3", "2"]])
    assert {(e["feature"], e["interactions"]) for e in events} == {("documents", 3), ("email", 2)}
    assert q["interactions_kept"] == 5


def test_two_date_formats_in_one_file_are_both_read(tmp_path):
    events, q, _ = run_wide(tmp_path, [["08/09/2026", "Person P1", "1", "0"], ["09 Sep 2026", "Person P1", "1", "0"]])
    assert [e["date"] for e in events] == ["2026-09-08", "2026-09-09"]
    assert q["date_formats_used"] == {"%d %b %Y": 1, "%d/%m/%Y": 1}


def test_day_month_order_follows_the_mapping_not_a_guess(tmp_path):
    events, _, _ = run_wide(tmp_path, [["10/09/2026", "Person P1", "1", "0"]])
    assert events[0]["date"] == "2026-09-10"       # 10 September, not 9 October


@pytest.mark.parametrize("bad", ["", "not a date", "31/02/2026", "2026-09-08"])
def test_unreadable_dates_are_dropped_and_counted(tmp_path, bad):
    events, q, _ = run_wide(tmp_path, [[bad, "Person P1", "1", "0"]])
    assert events == [] and q["dropped"]["bad_date"] == 1


def test_timezone_as_given_keeps_the_date_as_written(tmp_path):
    events, _, _ = run_long(tmp_path, [["1", "2026-09-08T23:30:00-05:00", "p1@firm.example", "chat"]])
    assert events[0]["date"] == "2026-09-08"


def test_timezone_convert_moves_the_date(tmp_path):
    m = copy.deepcopy(MAP_LONG)
    m["date"].update({"timezone": "convert", "target_utc_offset_minutes": 0})
    events, _, _ = run_long(tmp_path, [["1", "2026-09-08T23:30:00-05:00", "p1@firm.example", "chat"]], m)
    assert events[0]["date"] == "2026-09-09"


def test_exact_duplicates_are_dropped_once_each(tmp_path):
    row = ["1", "2026-09-08T09:00:00+00:00", "p1@firm.example", "chat"]
    events, q, _ = run_long(tmp_path, [row, row, row])
    assert len(events) == 1 and q["dropped"]["duplicate"] == 2


def test_conflicting_duplicate_keeps_the_first_row(tmp_path):
    events, q, _ = run_wide(tmp_path, [["08/09/2026", "Person P1", "3", "0"], ["08 Sep 2026", "PERSON P1", "9", "0"]])
    assert [e["interactions"] for e in events] == [3]
    assert q["dropped"]["conflicting_duplicate"] == 1 and q["dropped"]["duplicate"] == 0


def test_user_missing_from_roster_is_counted_not_kept(tmp_path):
    events, q, unknown = run_long(tmp_path, [
        ["1", "2026-09-08T09:00:00+00:00", "stranger@firm.example", "chat"],
        ["2", "2026-09-09T09:00:00+00:00", "Stranger@firm.example", "chat"],
        ["3", "2026-09-09T09:00:00+00:00", "p1@firm.example", "chat"]])
    assert [e["person_id"] for e in events] == ["P1"]
    assert q["dropped"]["unknown_user"] == 2
    assert q["unknown_user_distinct_identifiers"] == 1 and q["unknown_user_interactions"] == 2
    assert unknown == {"stranger@firm.example": 2}


@pytest.mark.parametrize("raw", ["P1@FIRM.EXAMPLE", "  p1@firm.example ", "P1@Firm.Example"])
def test_email_case_and_spacing_are_repaired_and_counted(tmp_path, raw):
    events, q, _ = run_long(tmp_path, [["1", "2026-09-08T09:00:00+00:00", raw, "chat"]])
    assert events[0]["person_id"] == "P1" and q["repaired"]["identifier_repaired"] == 1


def test_name_case_and_spacing_are_repaired_and_counted(tmp_path):
    events, q, _ = run_wide(tmp_path, [["08/09/2026", "  PERSON   p1 ", "1", "0"], ["08/09/2026", "Person P2", "1", "0"]])
    assert sorted(e["person_id"] for e in events) == ["P1", "P2"]
    assert q["repaired"]["identifier_repaired"] == 1


def test_name_matching_two_roster_people_is_ambiguous_not_guessed(tmp_path):
    roster = make_roster(tmp_path, [person("P1", name="Same Name"), person("P2", name="same name")])
    path = write_csv(tmp_path, "b.csv", B_HEAD, [["08/09/2026", "Same Name", "1", "0"]], delimiter=";")
    events, q, _ = ingest.ingest_file(path, MAP_WIDE, roster, PERIOD)
    assert events == [] and q["dropped"]["ambiguous_user"] == 1


def test_bad_zero_and_blank_counts(tmp_path):
    events, q, _ = run_wide(tmp_path, [
        ["08/09/2026", "Person P1", "n/a", "0"], ["09/09/2026", "Person P1", "-2", "0"],
        ["10/09/2026", "Person P1", "1.5", "0"], ["11/09/2026", "Person P1", "0", ""],
        ["12/09/2026", "Person P1", "", "4"]])
    assert q["dropped"]["bad_count"] == 3 and q["dropped"]["zero_count"] == 1
    assert [(e["date"], e["interactions"]) for e in events] == [("2026-09-12", 4)]


def test_blank_user_and_blank_row_are_separate_counts(tmp_path):
    _, q, _ = run_long(tmp_path, [["1", "2026-09-08T09:00:00+00:00", "", "chat"], ["", "", "", ""]])
    assert q["dropped"]["missing_user"] == 1 and q["dropped"]["blank_row"] == 1


def test_rows_outside_the_period_are_dropped_and_counted(tmp_path):
    events, q, _ = run_long(tmp_path, [["1", "2026-09-06T09:00:00+00:00", "p1@firm.example", "chat"],
                                       ["2", "2026-10-05T09:00:00+00:00", "p1@firm.example", "chat"],
                                       ["3", "2026-10-04T09:00:00+00:00", "p1@firm.example", "chat"]])
    assert len(events) == 1 and q["dropped"]["outside_period"] == 2


def test_unmapped_feature_is_kept_as_other_and_listed(tmp_path):
    events, q, _ = run_long(tmp_path, [["1", "2026-09-08T09:00:00+00:00", "p1@firm.example", "new_thing"]])
    assert events[0]["feature"] == "other"
    assert q["repaired"]["unmapped_feature"] == 1 and q["unmapped_feature_values"] == ["new_thing"]


def test_use_without_a_licence_is_kept_and_flagged(tmp_path):
    events, q, _ = run_long(tmp_path, [["1", "2026-09-08T09:00:00+00:00", "p3@firm.example", "chat"]])
    assert len(events) == 1 and q["flagged_but_kept"]["usage_without_licence"] == 1


def test_mapping_naming_a_missing_column_fails_loudly(tmp_path):
    path = write_csv(tmp_path, "a.csv", ["id", "when", "email", "action"], [])
    with pytest.raises(MappingError) as exc:
        ingest.ingest_file(path, MAP_LONG, roster3(tmp_path), PERIOD)
    assert "ts" in str(exc.value) and "when" in str(exc.value)


@pytest.mark.parametrize("change", [
    lambda m: m.pop("tool"), lambda m: m.update(shape="pivot"),
    lambda m: m["user"].update(match_on="guess"), lambda m: m["date"].update(formats=[]),
    lambda m: m["date"].update(timezone="convert"), lambda m: m.pop("feature")])
def test_invalid_mappings_are_rejected(change):
    m = copy.deepcopy(MAP_LONG)
    change(m)
    with pytest.raises(MappingError):
        ingest.validate_mapping(m)


def test_day_table_sums_events_for_the_same_person_day_tool_feature():
    e = {"person_id": "P1", "date": "2026-09-08", "tool": "Assistant A", "feature": "chat", "interactions": 2}
    table = ingest.to_day_table([e, dict(e), dict(e, feature="other")])
    assert [(r["feature"], r["interactions"]) for r in table] == [("chat", 4), ("other", 2)]


def test_every_row_is_accounted_for_in_the_sample_exports(baseline):
    for q in baseline["data_quality"]["ingestion"]["sources"]:
        assert q["rows_read"] == q["rows_kept"] + sum(q["dropped"].values())
        assert q["rows_dropped"] == sum(q["dropped"].values())
        assert q["rows_read"] > 0


def test_missing_export_for_a_tool_is_reported(tmp_path):
    roster = roster3(tmp_path)
    path = write_csv(tmp_path, "a.csv", A_HEAD, [["1", "2026-09-08T09:00:00+00:00", "p1@firm.example", "chat"]])
    _, quality, _ = ingest.ingest_all([(path, MAP_LONG)], roster, PERIOD)
    assert quality["tools_with_no_rows"] == ["Assistant B"]


def test_shipped_mappings_do_not_claim_a_vendor_layout(root):
    for name in ("assistant_a_events.json", "assistant_b_daily.json"):
        m = ingest.load_mapping(os.path.join(root, "mappings", name))
        assert "invented for the demo" in m["description"]
