import copy

import pytest

from baseline import compare as cmp
from baseline import targets
from baseline.suppress import cell, hidden
from helpers import make_analysis, person, use

DAYS = ["2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29"]
QUALITY = {"tools_with_no_rows": [], "totals": {"unknown_user_row_share": 0.0}}
SPEC = {"id": "t", "label": "T", "measure": "weekly_active", "basis": "last_4_weeks", "population": "lawyers",
        "threshold": 0.5, "due_month": 6}


def world(tmp_path, people, active):
    rows = [person("P%02d" % i) for i in range(people)]
    usage = [use("P%02d" % i, d) for i in range(active) for d in DAYS]
    return make_analysis(tmp_path, rows, usage)


def test_target_passes_at_exactly_the_threshold(tmp_path):
    r = targets.evaluate_one(world(tmp_path, 20, 10), SPEC, QUALITY, {})
    assert (r["status"], r["n"], r["d"], r["people"]) == ("pass", 40, 80, 20)


def test_target_below_the_threshold_is_not_yet(tmp_path):
    r = targets.evaluate_one(world(tmp_path, 20, 9), SPEC, QUALITY, {})
    assert r["status"] == "not yet" and r["rate"] == 0.45


def test_small_group_cannot_tell_even_if_everyone_is_active(tmp_path):
    r = targets.evaluate_one(world(tmp_path, 12, 12), SPEC, QUALITY, {"min_people": 20})
    assert r["status"] == "cannot tell" and "fewer than 20" in r["reason"]
    assert r["rate"] == 1.0          # shown, because 12 is above the suppression threshold


def test_group_under_the_suppression_threshold_shows_no_numbers(tmp_path):
    r = targets.evaluate_one(world(tmp_path, 3, 3), dict(SPEC, min_people=1), QUALITY, {})
    assert r["status"] == "cannot tell" and r["n"] is None and r["rate"] is None


def test_missing_export_or_many_unmatched_rows_cannot_tell(tmp_path):
    a = world(tmp_path, 20, 20)
    q1 = {"tools_with_no_rows": ["Assistant B"], "totals": {"unknown_user_row_share": 0.0}}
    q2 = {"tools_with_no_rows": [], "totals": {"unknown_user_row_share": 0.25}}
    assert targets.evaluate_one(a, SPEC, q1, {})["status"] == "cannot tell"
    r = targets.evaluate_one(a, SPEC, q2, {"max_unknown_user_row_share": 0.1})
    assert r["status"] == "cannot tell" and "25%" in r["reason"]


def test_too_few_weeks_cannot_tell(tmp_path):
    from datetime import date
    rows = [person("P%02d" % i) for i in range(20)]
    a = make_analysis(tmp_path, rows, [use("P%02d" % i, DAYS[0]) for i in range(20)], end=date(2026, 9, 20))
    assert targets.evaluate_one(a, SPEC, QUALITY, {})["status"] == "cannot tell"


def test_sample_targets_and_gates_have_the_expected_statuses(baseline):
    status = {t["id"]: t["status"] for t in baseline["targets"]["targets"] + baseline["targets"]["gates"]}
    assert status == {"weekly_active_lawyers_month_6": "not yet", "weekly_active_lawyers_month_12": "not yet",
                      "pilot_gate:Disputes": "pass", "pilot_gate:Employment": "not yet",
                      "pilot_gate:Competition": "cannot tell"}
    assert set(status.values()) == {"pass", "not yet", "cannot tell"}


def test_target_numbers_are_the_headline_numbers(baseline):
    t, h = baseline["targets"]["targets"][0], baseline["headline"]["weekly_active_last_4_weeks"]
    assert (t["n"], t["d"]) == (h["n"], h["d"])
    assert t["threshold"] == 0.5 and baseline["targets"]["targets"][1]["threshold"] == 0.7


@pytest.mark.parametrize("a,b,call", [
    (cell(30, 100), cell(40, 100), "up"),
    (cell(40, 100), cell(30, 100), "down"),
    (cell(30, 100), cell(34, 100), "no clear change"),
    (cell(2, 20), cell(12, 20), "too small to call"),          # +50 points on 20 people is still not called
    (cell(30, 100), cell(12, 20), "too small to call"),
    (cell(30, 100), hidden("small_group"), "suppressed"),
    (None, cell(30, 100), "not in both periods"),
])
def test_change_is_called_only_when_groups_are_big_enough(a, b, call):
    assert cmp.compare_cells(a, b, min_people=30, min_change_points=5)["call"] == call


def test_change_uses_people_not_person_weeks_for_the_size_test():
    a, b = cell(20, 80, people=20), cell(60, 80, people=20)
    assert cmp.compare_cells(a, b, 30, 5)["call"] == "too small to call"


def test_compare_shows_both_denominators(checkpoint, baseline):
    r = cmp.compare(checkpoint, baseline)["headline"]["weekly_active_last_4_weeks"]
    assert r["earlier"]["d"] == checkpoint["headline"]["weekly_active_last_4_weeks"]["d"]
    assert r["later"]["d"] == baseline["headline"]["weekly_active_last_4_weeks"]["d"]
    md = cmp.to_markdown(cmp.compare(checkpoint, baseline))
    assert "(%d of %d)" % (r["later"]["n"], r["later"]["d"]) in md


def test_compare_refuses_different_definition_versions(checkpoint, baseline):
    other = copy.deepcopy(checkpoint)
    other["definitions_version"] = "0.9"
    with pytest.raises(cmp.CompareError):
        cmp.compare(other, baseline)
