"""The analyser must recover what generate_synthetic.py planted (see ANSWER_KEY.md)."""
import os

from baseline import compare as cmp


def visible(rows, measure="weekly_active_last_4_weeks"):
    return {r["group"]: r["cells"][measure] for r in rows if not r["cells"][measure]["suppressed"]}


def source(baseline, name):
    return [q for q in baseline["data_quality"]["ingestion"]["sources"] if q["source"] == name][0]


def test_weekly_active_counts_match_the_clean_truth_every_week(baseline, key):
    got = [(w["week"], w["n"], w["d"]) for w in baseline["weekly_trend"]]
    want = [(w["week"], w["active"], w["eligible"]) for w in key["weekly_active_lawyers"]]
    assert got == want and len(got) == 13


def test_licence_counts_match_the_truth(baseline, key):
    for t in baseline["tools"]:
        truth = key["licences"][t["tool"]]
        assert t["licensed"] == truth["licensed"]
        assert t["cells"]["activated"]["n"] == truth["activated"]
        assert t["cells"]["unused_licences"]["n"] == truth["unused_30_days"]


def test_many_licensed_non_users(baseline):
    unused = {t["tool"]: t["cells"]["unused_licences"]["rate"] for t in baseline["tools"]}
    assert unused["Assistant B"] > 0.6 and unused["Assistant A"] > 0.4


def test_heavy_users_are_the_top_eight_and_dominate_volume(analysis, baseline, key):
    totals = analysis.person_totals()
    top = sorted(sorted(totals, key=totals.get, reverse=True)[:8])
    assert top == key["heavy_users"]
    a = baseline["intensity"]["by_tool"]["Assistant A"]
    assert a["top_decile_share"] > 0.5 and a["mean"] > 2 * a["median"]
    assert sum(totals.values()) == key["total_interactions"]


def test_overclaim_practice_has_the_largest_survey_gap(baseline, key):
    rows = [r for r in baseline["survey"]["by_practice"] if r["gap_points"] is not None]
    top = max(rows, key=lambda r: r["gap_points"])
    assert top["group"] == key["overclaim_practice"]
    assert top["gap_points"] > 40
    assert top["gap_points"] > 2 * sorted(r["gap_points"] for r in rows)[-2]


def test_overclaim_practice_is_low_in_the_logs(baseline, key):
    rates = {g: c["rate"] for g, c in visible(baseline["breakdowns"]["practice"]["rows"]).items()}
    assert min(rates, key=rates.get) == key["overclaim_practice"]


def test_new_office_is_the_lowest_office_shown(baseline, key):
    rates = {g: c["rate"] for g, c in visible(baseline["breakdowns"]["office"]["rows"]).items()}
    assert min(rates, key=rates.get) == key["new_office"]
    assert rates[key["new_office"]] < 0.5 * baseline["headline"]["weekly_active_last_4_weeks"]["rate"]


def test_new_office_is_outside_the_denominator_before_it_opens(baseline, key):
    trend = baseline["weekly_trend"]
    before = [w for w in trend if w["week_start"] < "2026-10-05"]
    after = [w for w in trend if w["week_start"] >= "2026-10-05"]
    assert len(before) == 4
    assert all(w["excluded"]["not_started"] >= key["new_office_lawyers"] for w in before)
    assert all(w["excluded"]["not_started"] < key["new_office_lawyers"] for w in after)


def test_holiday_week_is_the_lowest_week(baseline, key):
    low = min(baseline["weekly_trend"], key=lambda w: w["rate"])
    assert low["week"] == key["holiday_week"]
    assert low["excluded"]["on_leave"] == max(w["excluded"]["on_leave"] for w in baseline["weekly_trend"])


def test_rising_adoption_is_called_as_an_increase(checkpoint, baseline):
    r = cmp.compare(checkpoint, baseline)
    assert r["headline"]["weekly_active_last_4_weeks"]["call"] == "up"
    assert r["headline"]["regular_use"]["call"] == "up"
    calls = {row["group"]: row["measures"]["weekly_active_last_4_weeks"]["call"] for row in r["breakdowns"]["office"]}
    assert calls["Lakeshore"] == "too small to call" and calls["Midvale"] == "suppressed"


def test_survey_overstates_use_firm_wide(baseline):
    o = baseline["survey"]["overall"]
    assert o["claimed"]["rate"] > o["logged"]["rate"] and o["gap_points"] > 5


def test_small_practice_and_office_are_suppressed_with_one_complementary_each(baseline, key):
    for dim, name in (("practice", key["small_practice"]["name"]), ("office", key["small_office"]["name"])):
        marks = {r["group"]: r["cells"]["weekly_active_last_4_weeks"]["suppressed"] for r in baseline["breakdowns"][dim]["rows"]}
        assert marks[name] == "small_group"
        assert sorted(v for v in marks.values() if v) == ["complementary", "small_group"]
    assert key["small_practice"]["lawyers"] < 5 and key["small_office"]["lawyers"] < 5


def test_injected_mess_in_the_event_export_is_counted_exactly(baseline, key):
    q, k = source(baseline, "assistant_a_events"), key["exports"]["assistant_a_events"]
    assert q["rows_read"] == k["rows_read"] and q["rows_kept"] == k["rows_kept"]
    for reason in ("duplicate", "unknown_user", "bad_date", "missing_user", "outside_period"):
        assert q["dropped"][reason] == k[reason], reason
    assert q["repaired"]["identifier_repaired"] == k["identifier_repaired"]
    assert q["repaired"]["unmapped_feature"] == k["unmapped_feature"]
    assert q["flagged_but_kept"]["usage_without_licence"] == k["usage_without_licence"]
    assert q["unknown_user_distinct_identifiers"] == 3


def test_injected_mess_in_the_daily_export_is_counted_exactly(baseline, key):
    q, k = source(baseline, "assistant_b_daily"), key["exports"]["assistant_b_daily"]
    assert q["rows_read"] == k["rows_read"] and q["rows_kept"] == k["rows_kept"]
    for reason in ("duplicate", "conflicting_duplicate", "unknown_user", "bad_date", "bad_count", "zero_count"):
        assert q["dropped"][reason] == k[reason], reason
    assert q["repaired"]["identifier_repaired"] == k["identifier_repaired"]
    assert q["date_formats_used"]["%d %b %Y"] == k["alternate_date_format"]


def test_roster_facts_are_recovered(baseline, key):
    ro = baseline["data_quality"]["roster"]
    assert ro["people_on_roster"] == key["people"] == 320
    assert ro["people_who_changed_practice"] == len(key["practice_changers"]) == 3
    assert ro["person_weeks_with_usage_during_full_leave"] == key["usage_in_full_leave_weeks"]
    assert ro["people_with_no_usage_counted_as_zero"] == key["roster_people_with_no_usage"]


def test_top_blocker_and_response_count(baseline, key):
    s = baseline["survey"]
    counts = {k: v for k, v in s["tallies"]["blockers"]["counts"].items() if v and k != "nothing"}
    assert max(counts, key=counts.get) == key["survey"]["top_blocker"]
    assert s["responses"] == key["survey"]["responses"]


def test_sample_shape_ten_practices_eight_offices_thirteen_weeks(analysis, baseline):
    people = analysis.roster.people.values()
    assert len({a.practice for p in people for a in p.assignments}) == 10
    assert len({a.office for p in people for a in p.assignments}) == 8
    assert len(baseline["meta"]["weeks"]) == 13


def test_generator_is_seeded_and_reproduces_the_committed_files(root, tmp_path, monkeypatch):
    import importlib.util
    import hashlib
    spec = importlib.util.spec_from_file_location("gen", os.path.join(root, "generate_synthetic.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", str(tmp_path))
    monkeypatch.setattr(gen, "HERE", str(tmp_path))
    gen.main()
    digest = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    for name in ("roster.csv", "assistant_a_events.csv", "assistant_b_daily.csv", "survey_responses.csv", "answer_key.json"):
        assert digest(os.path.join(str(tmp_path), name)) == digest(os.path.join(root, "sample_data", name)), name
    assert digest(os.path.join(str(tmp_path), "ANSWER_KEY.md")) == digest(os.path.join(root, "ANSWER_KEY.md"))


def test_sub_window_user_counts_never_exceed_any_use_in_period_for_each_tool(baseline, analysis):
    """A 4-week window cannot hold more users of a tool than the whole period, on the same population."""
    for t in baseline["tools"]:
        tool, period_users = t["tool"], t["cells"]["activated"]["n"]
        assert baseline["intensity"]["by_tool"][tool]["people"] <= period_users
        assert baseline["breadth"]["by_tool"][tool]["people"] <= period_users
        assert baseline["intensity"]["by_tool"][tool]["people"] == baseline["breadth"]["by_tool"][tool]["people"]
        assert t["cells"]["regular_use"]["n"] <= period_users
        assert t["cells"]["weekly_active_last_4_weeks"]["people"] <= t["licensed"]
        for f in baseline["breadth"]["features"]:
            if f["tool"] == tool and f["people"] is not None:
                assert f["people"] <= period_users
        for monday in analysis.weeks:
            assert analysis.weekly_active([monday], "all", tool)["n"] <= period_users
    anyt = baseline["intensity"]["by_tool"]["any approved tool"]["people"]
    assert anyt >= max(baseline["intensity"]["by_tool"][t["tool"]]["people"] for t in baseline["tools"])


def test_unlicensed_users_are_outside_per_tool_figures_but_inside_any_tool_and_data_quality(baseline, analysis, key):
    tool = "Assistant A"
    first, last = analysis.last_weeks[0], analysis.end
    planted = key["unlicensed_assistant_a_users"]
    assert len(planted) == 2
    in_window = [p for p in planted if analysis.usage.interactions(p, first, last, tool) > 0]
    assert in_window                                             # the case is live in the sample
    assert not set(planted) & set(analysis.tool_population(tool))
    assert set(planted) <= set(analysis.tool_population("any approved tool"))
    licensed_users = sum(1 for p in analysis.tool_population(tool) if analysis.usage.interactions(p, first, last, tool) > 0)
    assert baseline["intensity"]["by_tool"][tool]["people"] == licensed_users
    everyone = sum(1 for p in analysis.in_scope if analysis.usage.interactions(p, first, last) > 0)
    assert baseline["intensity"]["by_tool"]["any approved tool"]["people"] == everyone
    q = [s for s in baseline["data_quality"]["ingestion"]["sources"] if s["tool"] == tool][0]
    assert q["flagged_but_kept"]["usage_without_licence"] == key["exports"]["assistant_a_events"]["usage_without_licence"] == 39
