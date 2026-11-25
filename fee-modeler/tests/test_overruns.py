"""Review round 2: one-sided upper-band judgement, back-test on the memo, drift sensitivity."""

import json
import os
from decimal import Decimal

from feemodel import backtest, memo, sensitivity, stats, synth
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
    assert more["text"] == "At the P90 figure, 10 of 41 back-tested matters cost more; the band implies about 4."
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


def test_the_example_from_review_now_reads_as_an_overrun_problem(bt):
    _records, summary, table = bt
    r = row(summary, "employment_single_plaintiff_defense")
    assert r["overruns"]["p90"] == {"band": "p90", "count": 10, "n": 41, "implied_pct": 10, "implied_count": 4,
                                    "judgement": "more", "text": r["overruns"]["p90"]["text"]}
    assert r["upper_band_status"] == "understated"
    assert r["verdict"].startswith("Bands understate overruns at P90 (n=41)")
    assert "At the P90 figure, 10 of 41 back-tested matters cost more; the band implies about 4." in r["verdict"]
    m = [x for x in table["rows"] if x["matter_type"] == "employment_single_plaintiff_defense"][0]
    assert m["verdict"] == "Modelable, bands understate overruns"
    assert any("10 of 41" in n for n in m["notes"])


def test_over_coverage_is_only_a_mild_note(bt):
    _records, summary, _table = bt
    r = row(summary, "contract_dispute_arbitration")           # 2 of 19 over P75, 0 of 19 over P90
    assert r["upper_band_status"] == "consistent"
    assert r["verdict"].startswith("Overruns at P75 and P90 are within what chance would explain at n=19.")
    assert "understate" not in r["verdict"]


def test_upper_band_statuses_on_the_synthetic_data(bt):
    _records, summary, _table = bt
    status = {r["matter_type"]: r["upper_band_status"] for r in summary["by_type"]}
    assert sorted(k for k, v in status.items() if v == "understated") == [
        "commercial_lease_review", "employment_single_plaintiff_defense", "facility_change_of_ownership",
        "internal_investigation", "paga_response"]
    assert status["election_law_advisory"] == "not_tested"
    assert summary["overall_upper_band_status"] == "understated"
    assert "64 of 385" in summary["overall_verdict"] and "about 39" in summary["overall_verdict"]


def test_same_wording_reaches_every_output(root):
    needle = "At the P90 figure, 10 of 41 back-tested matters cost more; the band implies about 4."
    for name in ("output/backtest.txt", "output/modelability.html", "output/modelability.json", "output/backtest.json",
                 "index.html"):
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            text = fh.read()
        assert needle in text, name
        assert "Bands held" not in text, name


def test_memo_carries_its_matter_types_backtest(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    b = r["backtest"]
    assert b["n_tested"] == 53 and b["usable"] and b["status"] == "consistent"
    assert b["statements"] == ["At the P75 figure, 15 of 53 back-tested matters cost more; the band implies about 13.",
                               "At the P90 figure, 9 of 53 back-tested matters cost more; the band implies about 5."]
    html = memo.render_memo(r)
    assert "Out-of-sample check: how these bands have held up for this matter type" in html
    for s in b["statements"]:
        assert s in html
    assert "Matched on matter type only (not this proposal&#x27;s selection rules)" in html
    assert html.index("Out-of-sample check") < html.index("Pricing scenarios against the comps")


def test_in_sample_share_and_out_of_sample_result_sit_side_by_side_and_are_labelled(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    fixed = r["scenarios"][0]
    assert fixed["under_fee"] == {"count": 29, "n": 43}                      # in sample
    oos = fixed["out_of_sample"]
    assert oos["available"] and oos["nearest_band"] == "p75" and oos["at_or_under"]["count"] == 38
    assert oos["at_or_under"]["n"] == 53 and oos["nominal_pct"] == 75
    assert "In sample" in fixed["in_sample_note"]
    phased = [s for s in r["scenarios"] if s["type"] == "phased"][0]
    assert phased["out_of_sample"]["available"] is False
    html = memo.render_memo(r)
    assert "In sample: comps at or under the fee" in html
    assert "Out of sample: walk-forward result at the nearest band" in html
    assert "In sample and out of sample are different things." in html
    assert "38 of 53 back-tested matters came in at or under their predicted P75; the band implies 75%." in html


def test_nearest_band_is_chosen_by_distance_to_the_fee():
    q = {"p25": D(100), "p50": D(200), "p75": D(300), "p90": D(400)}
    b = {"usable": True, "n_tested": 20,
         "under_band": {k: {"count": c, "n": 20, "nominal_pct": p} for k, c, p in
                        (("p25", 4, 25), ("p50", 9, 50), ("p75", 13, 75), ("p90", 16, 90))}}
    assert out_of_sample_for_fee(D(120), q, b)["nearest_band"] == "p25"
    assert out_of_sample_for_fee(D(390), q, b)["nearest_band"] == "p90"
    assert out_of_sample_for_fee(D(900), q, b)["at_or_under"] == {"count": 16, "n": 20, "nominal_pct": 90}
    assert out_of_sample_for_fee(None, q, b)["available"] is False


def test_memo_says_so_when_the_type_was_not_back_tested(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-004.json")))
    assert r["backtest"]["status"] == "not_tested" and r["backtest"]["usable"] is False
    assert "has not been back-tested" in memo.render_memo(r)
    assert out_of_sample_for_fee(D(100), {}, r["backtest"])["text"] == "No out-of-sample result: not back-tested."


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
    assert out_of_sample_for_fee(D(1), {}, b)["text"] == "No out-of-sample result: only 5 back-tested matters."


def test_drift_flag_rule_itself_is_unchanged(bt):
    # The one-sided overrun judgement was added beside the drift flag, not into it.
    _records, summary, _table = bt
    assert (backtest.DRIFT_RATIO, backtest.DRIFT_MAX_SHUFFLE_SHARE, backtest.DRIFT_SHUFFLES, backtest.DRIFT_MIN_N,
            backtest.COVERAGE_TOLERANCE_PTS, backtest.MIN_TESTED_TO_JUDGE) == (D("1.3"), D("0.02"), 1000, 16, 15, 10)
    assert [r["matter_type"] for r in summary["by_type"] if r["drift_flag"]] == [synth.DRIFT_TYPE]


def test_drift_sensitivity_is_pinned_at_the_shipped_setting(ws, bt, root):
    """Measured, not tuned: at the shipped 2.0x step the flag fires on 14 of 20 other seeds, so the
    recovery in the committed data is not guaranteed for every draw. Smaller steps are in the README."""
    assert synth.DRIFT_FACTOR == 2.0
    study = sensitivity.run_study(ws.code_map, ws.rate_card, steps=("2.0",))
    r = study["rows"][0]
    assert (r["drift_type_flagged"], r["seeds"]) == (14, 20)
    assert (r["other_types_flagged"], r["other_type_runs"]) == (2, 200)
    with open(os.path.join(root, "output", "drift_sensitivity.json"), encoding="utf-8") as fh:
        committed = json.load(fh)
    shipped = [x for x in committed["rows"] if x["planted_step"] == "2.0"][0]
    assert shipped["drift_type_flagged"] == 14 and shipped["other_types_flagged"] == 2
    assert [x["drift_type_flagged"] for x in committed["rows"]] == [0, 1, 6, 11, 14]       # steps 1.0, 1.3, 1.5, 1.7, 2.0
    # The committed data itself (seed 20260) is one of the draws where it fires, with little room to spare.
    _records, summary, _table = bt
    d = row(summary, synth.DRIFT_TYPE)["drift"]
    assert d["shifted"] and d["shuffles_as_extreme"] == 8 and d["n_shuffles"] == 1000


def test_in_memory_dataset_matches_the_loaded_export(ws):
    ds = synth.to_dataset(synth.generate())
    assert ds.matters == ws.dataset.matters and ds.invoices == ws.dataset.invoices
    key = lambda e: e.entry_id
    assert sorted(ds.entries, key=key) == sorted(ws.dataset.entries, key=key)
