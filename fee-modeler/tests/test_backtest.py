from datetime import date, timedelta
from decimal import Decimal

import pytest

from feemodel import backtest
from feemodel.cost import CostBook
from helpers import CODE_MAP, RATES, d, mk_dataset, mk_entry, mk_matter, simple_history

D = Decimal


def run(ds, min_comps=3):
    book = CostBook(ds, CODE_MAP)
    return backtest.walk_forward(ds, book, RATES, min_comps=min_comps), book


def test_bands_and_coverage_by_hand():
    # Three earlier matters worth 100, 200 and 300 hours x 400; the fourth is tested against them.
    ds = simple_history([100, 200, 300, 240])
    records, _ = run(ds)
    assert [r["tested"] for r in records] == [False, False, False, True]
    r = records[3]
    assert (r["p25"], r["p50"], r["p75"], r["p90"]) == (D(60000), D(80000), D(100000), D(112000))
    assert r["actual"] == D(96000)
    assert r["inside_p25_p75"] and r["at_or_under_p75"] and r["at_or_under_p90"]
    assert r["actual_over_p50"] == D("1.20")
    assert r["comp_ids"] == ["H-00", "H-01", "H-02"]


def test_only_matters_closed_before_the_target_opened_are_used(ws, bt):
    records, _summary, _table = bt
    matters = ws.dataset.matters
    tested = [r for r in records if r["tested"]]
    assert len(tested) > 300
    for r in tested:
        assert r["latest_comp_close"] < r["open_date"]
        assert r["data_cutoff"] < r["open_date"]
        assert r["matter_id"] not in r["comp_ids"]
        for cid in r["comp_ids"]:
            assert matters[cid].close_date < r["open_date"]
            assert matters[cid].matter_type == r["matter_type"]
            assert not matters[cid].is_abnormal_close


def test_lookahead_guard_fails_loudly_on_a_tampered_record(ws, bt):
    records, _summary, _table = bt
    r = dict([x for x in records if x["tested"]][0])
    future = [m for m in ws.dataset.matters.values() if m.is_closed and m.close_date > r["open_date"]][0]
    r["comp_ids"] = r["comp_ids"] + [future.matter_id]
    with pytest.raises(backtest.LookAheadError):
        backtest.verify_no_lookahead([r], ws.dataset)


def test_a_later_matter_cannot_change_earlier_predictions():
    base = simple_history([100, 200, 300, 240, 180])
    before, _ = run(base)
    plus = simple_history([100, 200, 300, 240, 180])
    plus.matters["Z-99"] = mk_matter("Z-99", open_="2030-01-10", close="2030-06-30")
    plus.entries.append(mk_entry("Z-E", "Z-99", "2030-02-01", 99999))
    after, _ = run(plus)
    by_id = {r["matter_id"]: r for r in after}
    for r in before:
        assert by_id[r["matter_id"]] == r


def test_matter_closing_the_day_the_target_opens_is_not_used():
    ds = simple_history([100, 200, 300])
    ds.matters["SAME"] = mk_matter("SAME", open_="2018-01-01", close="2019-01-10")
    ds.entries.append(mk_entry("S-E", "SAME", "2018-02-01", 5000))
    ds.matters["T"] = mk_matter("T", open_="2019-01-10", close="2019-03-01")
    ds.entries.append(mk_entry("T-E", "T", "2019-02-01", 150))
    records, _ = run(ds)
    t = [r for r in records if r["matter_id"] == "T"][0]
    assert t["tested"] and "SAME" not in t["comp_ids"]
    assert t["p50"] == D(80000)


def test_time_posted_after_the_target_opened_is_hidden_from_its_prediction():
    ds = simple_history([100, 200, 300, 240])
    # Late time on the first matter, dated after the fourth matter opened (2018-01-10).
    ds.entries.append(mk_entry("LATE", "H-00", "2018-03-01", 1000))
    records, book = run(ds)
    assert book.cost("H-00").value_total(RATES) == D(440000)          # full record includes the late time
    r = [x for x in records if x["matter_id"] == "H-03"][0]
    assert (r["p25"], r["p50"], r["p75"]) == (D(60000), D(80000), D(100000))   # prediction does not


def test_abnormally_closed_matters_are_neither_comps_nor_tested():
    ds = simple_history([100, 200, 300, 240])
    ds.matters["S"] = mk_matter("S", open_="2014-01-01", close="2014-03-01", reason="settled_early")
    ds.entries.append(mk_entry("S-E", "S", "2014-02-01", 1))
    records, _ = run(ds)
    assert "S" not in {r["matter_id"] for r in records}
    assert all("S" not in r["comp_ids"] for r in records)


def test_drift_check_flags_a_clear_step_and_ignores_noise():
    start = date(2020, 1, 1)
    flat = [(start + timedelta(days=30 * i), D(100 + (i * 37) % 23)) for i in range(40)]
    step = [(day, v * (2 if i >= 20 else 1)) for i, (day, v) in enumerate(flat)]
    assert backtest.drift_check(flat)["shifted"] is False
    out = backtest.drift_check(step)
    assert out["shifted"] is True and out["late_over_early"] >= D("1.8")
    assert out["n_early"] == 20 and out["n_late"] == 20 and out["shuffles_as_extreme"] == 0
    assert backtest.drift_check(step) == out                          # seeded: same answer every run
    assert backtest.drift_check(step[15:25])["shifted"] is False      # too few to call


def test_summary_counts_and_nominal_shares(ws, bt):
    records, summary, _table = bt
    assert summary["n_tested"] == sum(1 for r in records if r["tested"])
    for row in summary["by_type"]:
        recs = [r for r in records if r["matter_type"] == row["matter_type"]]
        assert row["n_tested"] + row["n_skipped"] == len(recs) == row["n_clean_closed"]
        for key, nominal in (("inside_p25_p75", 50), ("at_or_under_p75", 75), ("at_or_under_p90", 90)):
            c = row["coverage"][key]
            assert c["n"] == row["n_tested"] and c["nominal_pct"] == nominal and 0 <= c["count"] <= c["n"]
        assert row["coverage"]["inside_p25_p75"]["count"] <= row["coverage"]["at_or_under_p75"]["count"] \
            <= row["coverage"]["at_or_under_p90"]["count"]
        assert row["verdict"]


def test_min_comps_is_respected(ws):
    records = backtest.walk_forward(ws.dataset, ws.book, ws.rate_card, min_comps=20)
    assert all(r["n_comps"] >= 20 for r in records if r["tested"])
    assert all(r["n_comps"] < 20 for r in records if not r["tested"])
