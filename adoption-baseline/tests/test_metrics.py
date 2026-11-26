from datetime import date

from baseline.metrics import complete_weeks, distribution, quantile, week_label
from helpers import MONDAYS, make_analysis, person, use

W1, W2, W3, W4 = MONDAYS
DAYS = ["2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29"]     # one Tuesday per week


def test_complete_weeks_ignores_part_weeks():
    assert complete_weeks(date(2026, 9, 9), date(2026, 9, 27)) == [date(2026, 9, 14), date(2026, 9, 21)]
    assert week_label(date(2026, 9, 7)) == "2026-W37"


def test_one_interaction_in_the_iso_week_makes_someone_active(tmp_path):
    a = make_analysis(tmp_path, [person("P1"), person("P2")], [use("P1", "2026-09-13")])     # the Sunday
    assert a.weekly_active([W1])["n"] == 1
    assert a.weekly_active([W2])["n"] == 0


def test_last_four_weeks_pools_person_weeks_and_counts_distinct_people(tmp_path):
    a = make_analysis(tmp_path, [person("P1"), person("P2")], [use("P1", d) for d in DAYS[:3]])
    c = a.weekly_active(a.last_weeks)
    assert (c["n"], c["d"], c["people"]) == (3, 8, 2)


def test_regular_use_needs_three_of_the_last_four_weeks(tmp_path):
    usage = [use("P1", d) for d in DAYS[:3]] + [use("P2", d) for d in DAYS[:2]] + [use("P3", d) for d in DAYS]
    a = make_analysis(tmp_path, [person("P1"), person("P2"), person("P3"), person("P4")], usage)
    c = a.regular_use()
    assert (c["n"], c["d"]) == (2, 4)


def test_regular_use_leaves_out_people_who_could_not_meet_the_test(tmp_path):
    rows = [person("P1"), person("P2", start_date="2026-09-21")]        # P2 eligible in 2 of 4 weeks
    a = make_analysis(tmp_path, rows, [use("P2", DAYS[2]), use("P2", DAYS[3])])
    c = a.regular_use()
    assert (c["n"], c["d"]) == (0, 1)


def test_per_tool_rate_uses_people_licensed_for_that_tool(tmp_path):
    rows = [person("P1"), person("P2", licence_assistant_a="no"), person("P3", licence_assistant_a="no")]
    usage = [use("P1", DAYS[0]), use("P2", DAYS[0], tool="Assistant A")]
    a = make_analysis(tmp_path, rows, usage)
    tool = a.weekly_active([W1], "lawyers", "Assistant A")
    anyt = a.weekly_active([W1])
    assert (tool["n"], tool["d"]) == (1, 1)         # unlicensed user is outside the per-tool rate
    assert (anyt["n"], anyt["d"]) == (2, 3)         # but did use an approved tool


def test_lawyer_population_excludes_paralegals_and_staff(tmp_path):
    rows = [person("P1", role="partner"), person("P2", role="paralegal"), person("P3", role="staff")]
    a = make_analysis(tmp_path, rows, [use("P2", DAYS[0])])
    assert a.weekly_active([W1])["d"] == 1
    assert a.weekly_active([W1], "all")["d"] == 3


def test_practice_change_counts_each_week_under_the_practice_in_effect(tmp_path):
    rows = [person("P1", practice="Old"), person("P1", practice="New", effective_from="2026-09-21")]
    a = make_analysis(tmp_path, rows, [use("P1", d) for d in DAYS], {"suppression_threshold": 1})
    old = a.weekly_active(a.weeks, where=lambda r: r["practice"] == "Old")
    new = a.weekly_active(a.weeks, where=lambda r: r["practice"] == "New")
    assert (old["n"], old["d"]) == (2, 2) and (new["n"], new["d"]) == (2, 2)
    assert a.roster_quality()["people_who_changed_practice"] == 1


def test_unused_licences_in_the_last_30_days(tmp_path):
    rows = [person("P1"), person("P2"), person("P3", licence_assistant_a="no"),
            person("P4", leave_periods="2026-08-01/2026-12-31")]
    usage = [use("P1", "2026-09-29"), use("P2", "2026-09-01"), use("P3", "2026-09-29", tool="Assistant B")]
    a = make_analysis(tmp_path, rows, usage, {"suppression_threshold": 1}, start=date(2026, 8, 31))
    t = {r["tool"]: r for r in a.tools_table()}["Assistant A"]
    assert t["licensed"] == 3
    assert (t["cells"]["unused_licences"]["n"], t["cells"]["unused_licences"]["d"]) == (2, 3)   # P2 too old, P4 none
    assert t["cells"]["unused_licences_absent_throughout"]["n"] == 1                             # P4 on leave
    assert t["cells"]["activated"]["n"] == 2


def test_quartiles_use_linear_interpolation():
    assert quantile([1, 2, 3, 4], 0.5) == 2.5
    assert quantile([1, 2, 3, 4, 5], 0.25) == 2
    assert quantile([7], 0.75) == 7
    assert quantile([], 0.5) is None


def test_intensity_reports_median_and_quartiles_and_the_heavy_tail():
    d = distribution([1, 2, 2, 3, 3, 3, 4, 4, 5, 100], 5)
    assert (d["p25"], d["median"], d["p75"]) == (2.25, 3.0, 4.0)
    assert d["mean"] == 12.7 and d["median"] < d["mean"]
    assert d["top_decile_people"] == 1 and round(d["top_decile_share"], 3) == round(100 / 127, 3)
    assert "max" not in d


def test_intensity_is_withheld_for_a_small_group():
    d = distribution([3, 4, 5], 5)
    assert d["suppressed"] == "small_group" and d["median"] is None and d["people"] is None


def test_breadth_counts_distinct_features_per_person(tmp_path):
    rows = [person("P%d" % i) for i in range(1, 7)]
    usage = [use("P%d" % i, DAYS[3]) for i in range(1, 7)] + [use("P1", DAYS[3], feature="upload"),
                                                              use("P1", DAYS[2], tool="Assistant B", feature="email")]
    a = make_analysis(tmp_path, rows, usage)
    b = a.breadth()["by_tool"]
    assert b["any approved tool"]["people"] == 6
    assert b["any approved tool"]["two_or_more_features"]["n"] == 1
    assert b["Assistant B"]["suppressed"] == "small_group"


# ---- per-tool populations: licence holders only ---------------------------

def unlicensed_world(tmp_path):
    """Six licensed Assistant A users and one heavy user (P7) with no Assistant A licence."""
    rows = [person("P%d" % i) for i in range(1, 7)] + [person("P7", licence_assistant_a="no")]
    usage = [use("P%d" % i, DAYS[3], n=i) for i in range(1, 7)]
    usage += [use("P7", DAYS[3], n=500), use("P7", DAYS[3], feature="upload", n=1)]
    return make_analysis(tmp_path, rows, usage)


def test_unlicensed_use_is_in_the_any_tool_intensity_and_not_the_per_tool_one(tmp_path):
    by = unlicensed_world(tmp_path).intensity()["by_tool"]
    assert by["Assistant A"]["people"] == 6 and by["any approved tool"]["people"] == 7
    assert by["Assistant A"]["median"] == 3.5 and by["Assistant A"]["mean"] == 3.5       # 1..6 only
    assert by["any approved tool"]["mean"] == (21 + 501) / 7
    assert by["any approved tool"]["top_decile_share"] == 501 / 522


def test_unlicensed_use_is_in_the_any_tool_breadth_and_not_the_per_tool_one(tmp_path):
    b = unlicensed_world(tmp_path).breadth()
    assert b["by_tool"]["Assistant A"]["people"] == 6
    assert b["by_tool"]["Assistant A"]["two_or_more_features"]["n"] == 0                 # P7's two features left out
    assert b["by_tool"]["any approved tool"]["people"] == 7
    assert b["by_tool"]["any approved tool"]["two_or_more_features"]["n"] == 1
    feats = {(f["tool"], f["feature"]): f for f in b["features"]}
    assert feats[("Assistant A", "chat")]["people"] == 6
    assert ("Assistant A", "upload") not in feats                                       # only the unlicensed user used it


def test_every_per_tool_measure_leaves_out_the_unlicensed_user(tmp_path):
    a = unlicensed_world(tmp_path)
    tool = "Assistant A"
    assert a.tool_population(tool) == ["P%d" % i for i in range(1, 7)]
    assert len(a.tool_population("any approved tool")) == 7
    assert a.activated("all", tool)["d"] == 6 and a.activated("all", tool)["n"] == 6
    assert a.weekly_active([W4], "all", tool)["d"] == 6
    assert a.regular_use("all", tool)["d"] == 6
    t = {r["tool"]: r for r in a.tools_table()}[tool]
    assert t["licensed"] == 6 and t["cells"]["unused_licences"]["d"] == 6
    col = a.breakdown("practice", "lawyers")["total"]["cells"]["weekly_active_last_4_weeks:" + tool]
    assert col["people"] == 6
    assert a.activated("all")["n"] == 7 and a.weekly_active([W4], "all")["n"] == 7       # any tool counts P7
