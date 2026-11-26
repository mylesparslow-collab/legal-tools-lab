"""One-sided upper-band judgement and the back-test on the memo, for planning bands and comp quantiles."""

import os
from decimal import Decimal

from feemodel import backtest, memo, stats, synth
from feemodel.cost import CostBook
from feemodel.engine import backtest_for_type, out_of_sample_for_fee, price_proposal
from feemodel.loader import load_json
from helpers import CODE_MAP, RATES, simple_history

D = Decimal


def row(summary, mtype):
    return [r for r in summary["by_type"] if r["matter_type"] == mtype][0]


def test_exact_binomial_tail_by_hand():
    # Two fair coins: P(X >= 2) = 1/4, P(X <= 0) = 1/4.
    assert stats.binomial_tail_at_most(2, 2, 1, 2, 1, 4, upper=True) is True
    assert stats.binomial_tail_at_most(2, 2, 1, 2, 1, 5, upper=True) is False
    assert stats.binomial_tail_at_most(0, 2, 1, 2, 1, 4, upper=False) is True
    assert stats.binomial_tail_at_most(1, 2, 1, 2, 1, 2, upper=True) is False     # P(X >= 1) = 3/4
    assert stats.binomial_tail_at_most(0, 0, 1, 10) is False                       # no data, no judgement


def test_overrun_check_is_one_sided_and_states_counts():
    more = backtest.overrun_check(10, 41, "p90", 10)
    assert more["judgement"] == "more" and more["implied_count"] == 4
    assert more["text"] == "At the planning P90, 10 of 41 back-tested matters cost more; the band implies about 4."
    assert backtest.overrun_check(10, 41, "p90", 10, "descriptive")["text"] == (
        "At the comp P90 (descriptive), 10 of 41 back-tested matters cost more; the band implies about 4.")
    assert backtest.overrun_check(4, 41, "p90", 10)["judgement"] == "consistent"
    assert backtest.overrun_check(7, 41, "p90", 10)["judgement"] == "consistent"   # 7 against about 4: not beyond chance at n=41
    fewer = backtest.overrun_check(2, 40, "p75", 25)
    assert fewer["judgement"] == "fewer" and fewer["implied_count"] == 10
    assert backtest.overrun_check(0, 0, "p90", 10)["judgement"] == "consistent"


def test_more_overruns_than_implied_is_never_reported_as_held(bt):
    _records, summary, _table = bt
    for r in summary["by_type"] + [{"verdict": summary["overall_verdict"], "n_tested": summary["n_tested"],
                                    "overruns": summary["overall_overruns"], "upper_band_status": summary["overall_upper_band_status"]}]:
        assert "held" not in r["verdict"].lower()
        if r["n_tested"] >= backtest.MIN_TESTED_TO_JUDGE:
            over = [b for b in ("p75", "p90") if r["overruns"][b]["judgement"] == "more"]
            assert (r["upper_band_status"] == "understated") == bool(over)
            for b in ("p75", "p90"):
                o = r["overruns"][b]
                assert "%d of %d back-tested matters cost more" % (o["count"], o["n"]) in r["verdict"]
                assert "implies about %d" % o["implied_count"] in r["verdict"]


def test_the_example_from_review_reads_as_an_overrun_problem_for_the_comp_quantiles(bt):
    _records, summary, _table = bt
    r = row(summary, "employment_single_plaintiff_defense")["descriptive"]
    assert r["overruns"]["p90"] == {"band": "p90", "count": 10, "n": 41, "implied_pct": 10, "implied_count": 4,
                                    "judgement": "more", "text": r["overruns"]["p90"]["text"]}
    assert r["upper_band_status"] == "understated"
    assert r["verdict"].startswith("Comp quantiles understate overruns at P90 (n=41)")
    assert "At the comp P90 (descriptive), 10 of 41 back-tested matters cost more; the band implies about 4." in r["verdict"]


def test_over_coverage_is_only_a_mild_note(bt):
    _records, summary, _table = bt
    r = row(summary, "contract_dispute_arbitration")           # planning: 1 of 19 over P75, 0 of 19 over P90
    assert r["upper_band_status"] == "consistent"
    assert r["verdict"].startswith("Overruns at P75 and P90 are within what chance would explain at n=19.")
    assert "Fewer overruns than implied at P75" in r["verdict"] and "understate" not in r["verdict"]


def test_upper_band_statuses_old_and_new_on_the_synthetic_data(bt):
    _records, summary, _table = bt
    old = {r["matter_type"]: r["descriptive"]["upper_band_status"] for r in summary["by_type"]}
    new = {r["matter_type"]: r["upper_band_status"] for r in summary["by_type"]}
    assert sorted(k for k, v in old.items() if v == "understated") == [
        "employment_single_plaintiff_defense", "facility_change_of_ownership", "internal_investigation",
        "ordinance_drafting", "paga_response"]
    assert [k for k, v in new.items() if v == "understated"] == []
    assert new["election_law_advisory"] == old["election_law_advisory"] == "not_tested"
    d = summary["overall_descriptive"]
    assert d["upper_band_status"] == "understated"
    assert (d["overruns"]["p75"]["count"], d["overruns"]["p90"]["count"], d["n_tested"]) == (114, 60, 385)
    assert summary["overall_upper_band_status"] == "consistent"
    assert (summary["overall_overruns"]["p75"]["count"], summary["overall_overruns"]["p90"]["count"],
            summary["n_tested"]) == (88, 32, 385)
    assert "32 of 385" in summary["overall_verdict"] and "about 39" in summary["overall_verdict"]


def test_same_wording_reaches_every_output(root):
    new = "At the planning P90, 7 of 41 back-tested matters cost more; the band implies about 4."
    old = "At the comp P90 (descriptive), 10 of 41 back-tested matters cost more; the band implies about 4."
    for name in ("output/backtest.txt", "output/modelability.html", "output/modelability.json", "output/backtest.json",
                 "index.html"):
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            text = fh.read()
        assert new in text, name
        assert "Bands held" not in text, name
    for name in ("output/backtest.txt", "output/backtest.json"):
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            assert old in fh.read(), name


def test_memo_carries_its_matter_types_backtest(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    b = r["backtest"]
    assert b["n_tested"] == 53 and b["usable"] and b["status"] == "consistent"
    assert b["statements"] == ["At the planning P75, 13 of 53 back-tested matters cost more; the band implies about 13.",
                               "At the planning P90, 4 of 53 back-tested matters cost more; the band implies about 5."]
    assert b["descriptive_statements"] == [
        "At the comp P75 (descriptive), 16 of 53 back-tested matters cost more; the band implies about 13.",
        "At the comp P90 (descriptive), 9 of 53 back-tested matters cost more; the band implies about 5."]
    html = memo.render_memo(r)
    assert "Out-of-sample check: how the planning bands have held up for this matter type" in html
    for s in b["statements"] + b["descriptive_statements"]:
        assert s in html
    assert "Matched on matter type only (not this proposal&#x27;s selection rules)" in html
    assert html.index("Out-of-sample check") < html.index("Pricing scenarios against the comps")


def test_in_sample_share_and_out_of_sample_result_sit_side_by_side_and_are_labelled(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    fixed = r["scenarios"][0]
    assert fixed["under_fee"] == {"count": 29, "n": 43}                      # in sample
    oos = fixed["out_of_sample"]
    assert oos["available"] and oos["position"] == {"at_or_above": "p50", "below": "p75"}
    assert oos["bands"]["p75"] == {"count": 40, "n": 53, "nominal_pct": 75}
    assert "In sample" in fixed["in_sample_note"]
    phased = [s for s in r["scenarios"] if s["type"] == "phased"][0]
    assert phased["out_of_sample"]["available"] is False and phased["at_planning"] is None
    html = memo.render_memo(r)
    assert "In sample: comps at or under the fee" in html
    assert "Against the planning figures, and how those held up out of sample" in html
    assert "40 of 53 at or under their planning P75 (the band implies 75%)" in html


def test_fee_is_placed_between_the_planning_bands_either_side():
    q = {"p25": D(100), "p50": D(200), "p75": D(300), "p90": D(400)}
    b = {"usable": True, "n_tested": 20,
         "under_band": {k: {"count": c, "n": 20, "nominal_pct": p} for k, c, p in
                        (("p25", 4, 25), ("p50", 9, 50), ("p75", 13, 75), ("p90", 16, 90))}}
    assert out_of_sample_for_fee(D(120), q, b)["position"] == {"at_or_above": "p25", "below": "p50"}
    assert out_of_sample_for_fee(D(50), q, b)["position"] == {"at_or_above": None, "below": "p25"}
    top = out_of_sample_for_fee(D(900), q, b)
    assert top["position"] == {"at_or_above": "p90", "below": None}
    assert top["bands"] == {"p90": {"count": 16, "n": 20, "nominal_pct": 90}}
    assert "16 of 20 at or under their planning P90 (the band implies 90%)" in top["text"]
    assert out_of_sample_for_fee(None, q, b)["available"] is False


def test_memo_says_so_when_the_type_was_not_back_tested(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-004.json")))
    assert r["backtest"]["status"] == "not_tested" and r["backtest"]["usable"] is False
    assert "has not been back-tested" in memo.render_memo(r)
    q = {"p25": D(1), "p50": D(2), "p75": D(3), "p90": D(4)}
    assert out_of_sample_for_fee(D(100), q, r["backtest"])["text"].endswith("No out-of-sample result: not back-tested.")


def test_memo_says_so_when_fewer_than_ten_matters_were_back_tested():
    class TinyWorkspace:
        def __init__(self):
            self.dataset = simple_history([100 + 7 * i for i in range(13)])     # 13 matters, 5 back-tested
            self.book = CostBook(self.dataset, CODE_MAP)

        def backtest(self):
            records = backtest.walk_forward(self.dataset, self.book, RATES)
            return records, backtest.summarize_backtest(records, self.dataset, self.book, RATES)

    b = backtest_for_type(TinyWorkspace(), "widget_dispute")
    assert b["n_tested"] == 5 and b["usable"] is False and b["status"] == "too_few"
    assert b["headline"].startswith("Only 5 matters of this type could be back-tested; at least 10 are needed")
    q = {"p25": D(1), "p50": D(2), "p75": D(3), "p90": D(4)}
    assert out_of_sample_for_fee(D(1), q, b)["text"].endswith("No out-of-sample result: only 5 back-tested matters.")


def test_old_drift_rule_is_kept_unchanged_for_comparison(bt):
    _records, summary, _table = bt
    assert (backtest.DRIFT_RATIO, backtest.DRIFT_MAX_SHUFFLE_SHARE, backtest.DRIFT_SHUFFLES, backtest.DRIFT_MIN_N,
            backtest.COVERAGE_TOLERANCE_PTS, backtest.MIN_TESTED_TO_JUDGE) == (D("1.3"), D("0.02"), 1000, 16, 15, 10)
    # At the shipped 1.7x step the old rule misses the planted type on this seed; the new check finds it.
    assert [r["matter_type"] for r in summary["by_type"] if r["drift_flag_old"]] == []
    assert row(summary, synth.DRIFT_TYPE)["drift_flag"] is True


def test_in_memory_dataset_matches_the_loaded_export(ws):
    ds = synth.to_dataset(synth.generate())
    assert ds.matters == ws.dataset.matters and ds.invoices == ws.dataset.invoices
    key = lambda e: e.entry_id
    assert sorted(ds.entries, key=key) == sorted(ws.dataset.entries, key=key)
