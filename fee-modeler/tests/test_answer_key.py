"""The tool must recover the truths planted by the synthetic generator (see ANSWER_KEY.md)."""

import filecmp
import os
from collections import Counter
from decimal import Decimal

from feemodel import pricing, stats, synth
from feemodel.backtest import clean_closed
from feemodel.comps import InsufficientComps, SelectionRules, require_min, select_comps
from feemodel.engine import price_proposal
from helpers import d

D = Decimal
AS_OF = d("2026-01-01")


def test_generator_is_deterministic_and_matches_committed_files(tmp_path, root):
    synth.write_all(str(tmp_path))
    for sub, names in (("export_a", ["matters.csv", "timekeepers.csv", "time_entries.csv", "invoices.csv"]),
                       ("export_b", ["MATTER_MASTER.csv", "WIP_DETAIL.csv", "AR_SUMMARY.csv"])):
        for name in names:
            assert filecmp.cmp(os.path.join(tmp_path, sub, name), os.path.join(root, "data", sub, name), shallow=False), name
    assert filecmp.cmp(os.path.join(tmp_path, "rate_card.json"), os.path.join(root, "data", "rate_card.json"), shallow=False)


def test_shape_of_the_synthetic_firm(ws):
    matters = list(ws.dataset.matters.values())
    assert sum(1 for m in matters if m.is_closed) == 600
    assert sum(1 for m in matters if m.status == "open") == synth.N_OPEN == 40
    assert len({m.matter_type for m in matters}) == 12
    years = {m.close_date.year for m in matters if m.is_closed}
    assert years == {2020, 2021, 2022, 2023, 2024, 2025}


def test_thin_matter_type_is_refused(ws):
    sel = select_comps(ws.dataset, synth.THIN_TYPE, {}, SelectionRules(), AS_OF)
    assert sel.n == 5
    try:
        require_min(sel)
        raise AssertionError("should have refused")
    except InsufficientComps as exc:
        assert "5 comparable closed matters" in str(exc) and "8 required" in str(exc) and "3 more are needed" in str(exc)
    result = price_proposal(ws, {"matter_type": synth.THIN_TYPE, "as_of": "2026-01-01",
                                 "scenarios": [{"type": "fixed", "fee": "15000"}], "target_probability": "0.8"})
    assert result["status"] == "refused"
    for key in ("distribution", "scenarios", "target"):
        assert key not in result            # no number without enough comps


def test_drifting_type_is_the_only_one_flagged_in_the_backtest(bt):
    _records, summary, table = bt
    flagged = [r["matter_type"] for r in summary["by_type"] if r["drift_flag"]]
    assert flagged == [synth.DRIFT_TYPE]
    row = [r for r in summary["by_type"] if r["matter_type"] == synth.DRIFT_TYPE][0]
    assert row["drift"]["late_over_early"] >= D("1.3")
    c = row["coverage"]["at_or_under_p75"]
    assert c["count"] * 100 < 60 * c["n"]                       # bands from older matters missed badly
    assert "shifted" in row["verdict"]
    verdicts = {r["matter_type"]: r["verdict"] for r in table["rows"]}
    assert verdicts[synth.DRIFT_TYPE] == "Modelable with care"
    assert verdicts[synth.THIN_TYPE] == "Not modelable"
    assert sum(1 for v in verdicts.values() if v.startswith("Modelable")) == 11


def test_thin_type_is_never_backtested(bt):
    _records, summary, _table = bt
    row = [r for r in summary["by_type"] if r["matter_type"] == synth.THIN_TYPE][0]
    assert row["n_tested"] == 0 and "Not back-tested" in row["verdict"]


def test_pricing_the_drifting_type_warns_and_recent_comps_cost_more(ws):
    base = {"matter_type": synth.DRIFT_TYPE, "as_of": "2026-01-01"}
    all_hist = price_proposal(ws, base)
    assert all_hist["drift"]["shifted"] is True
    assert any("later half" in w for w in all_hist["warnings"])
    recent = price_proposal(ws, dict(base, selection_rules={"closed_within_years": 3}))
    assert recent["distribution"]["normalized"]["quantiles"]["p50"] > all_hist["distribution"]["normalized"]["quantiles"]["p50"]


def test_hearing_multiplier_recovered_and_turned_into_a_scope_assumption(ws):
    sel = select_comps(ws.dataset, synth.HEARING_TYPE, {}, SelectionRules(), AS_OF)
    costs = [ws.book.cost(m.matter_id) for m in sel.included]
    out = pricing.scope_assumptions(sel, costs, ws.rate_card)
    hearing = [a for a in out if a["kind"] == "hearing"][0]
    assert D("1.6") <= hearing["evidence"]["ratio"] <= D("3.0")      # planted: hearing adds about 0.9x the base hours
    assert "Quote the hearing as a separate phase" in hearing["text"]
    overrun = [a for a in out if a["kind"] == "overrun_phase"][0]
    assert overrun["evidence"]["top_phase"] == "hearing"


def test_timekeeper_level_change_is_respected_in_both_exports(ws, ws_b):
    tk, eff = synth.LEVEL_CHANGE["timekeeper_id"], synth.LEVEL_CHANGE["effective"]
    for dataset in (ws.dataset, ws_b.dataset):
        mine = [e for e in dataset.entries if e.timekeeper_id == tk]
        before = {e.level for e in mine if e.work_date < eff}
        after = {e.level for e in mine if e.work_date >= eff}
        assert before == {"associate"} and after == {"senior_associate"}
        assert len(mine) > 50
    levels = {}
    for e in ws.dataset.entries:
        levels.setdefault(e.timekeeper_id, set()).add(e.level)
    assert [k for k, v in levels.items() if len(v) > 1] == [tk]


def test_type_without_task_codes_gets_low_confidence_phases(ws, bt):
    _records, _summary, table = bt
    for m in clean_closed(ws.dataset, synth.NO_TASK_CODE_TYPE):
        assert ws.book.cost(m.matter_id).phase_confidence == "date_window"
    row = [r for r in table["rows"] if r["matter_type"] == synth.NO_TASK_CODE_TYPE][0]
    assert row["task_coded_hours_pct"] == 0
    assert any("low confidence" in n for n in row["notes"])
    other = [r for r in table["rows"] if r["matter_type"] == "public_works_bid_protest"][0]
    assert 80 <= other["task_coded_hours_pct"] <= 95               # about 10% blank plus 1% unmapped


def test_heaviest_write_downs_are_in_the_planted_type(ws):
    shares = {}
    for mtype in {m.matter_type for m in ws.dataset.matters.values()}:
        costs = [ws.book.cost(m.matter_id) for m in clean_closed(ws.dataset, mtype)]
        worked = sum(c.raw_worked for c in costs)
        shares[mtype] = (worked - sum(c.raw_billed for c in costs)) / worked
    assert max(shares, key=shares.get) == synth.HEAVY_WRITE_DOWN_TYPE
    assert D("0.09") <= shares[synth.HEAVY_WRITE_DOWN_TYPE] <= D("0.15")         # planted 12%
    assert all(v < D("0.09") for k, v in shares.items() if k != synth.HEAVY_WRITE_DOWN_TYPE)


def test_rate_increases_recovered_and_normalization_undoes_them(ws):
    for year in (2020, 2023, 2025):
        rates = Counter(e.rate for e in ws.dataset.entries if e.work_date.year == year and e.level == "partner")
        assert set(rates) == {D(synth.rate_for("partner", year))}
    assert ws.rate_card["partner"] == synth.rate_for("partner", 2026)
    assert D("1.26") < ws.rate_card["partner"] / synth.rate_for("partner", 2020) < D("1.27")    # 1.04 ** 6
    all_2020 = [m for m in clean_closed(ws.dataset) if m.close_date.year == 2020
                and ws.book.cost(m.matter_id).last_entry_date.year == 2020]
    assert len(all_2020) > 10
    for m in all_2020:
        c = ws.book.cost(m.matter_id)
        assert D("1.25") < c.value_total(ws.rate_card) / c.raw_worked < D("1.31")
    late = [m for m in clean_closed(ws.dataset) if m.open_date.year == 2025]
    for m in late:
        c = ws.book.cost(m.matter_id)
        assert D("1.03") < c.value_total(ws.rate_card) / c.raw_worked < D("1.05")


def test_abnormal_closes_cost_far_less_which_is_why_they_are_excluded(ws):
    mtype = synth.HEAVY_WRITE_DOWN_TYPE
    normal = [ws.book.cost(m.matter_id).total_hours for m in clean_closed(ws.dataset, mtype)]
    early = [ws.book.cost(m.matter_id).total_hours for m in ws.dataset.matters.values()
             if m.matter_type == mtype and m.close_reason == "settled_early"]
    assert len(early) >= 3
    assert stats.quantile(early, D("0.5")) < D("0.6") * stats.quantile(normal, D("0.5"))


def test_cost_rises_with_number_of_facilities(ws):
    costs = [ws.book.cost(m.matter_id) for m in clean_closed(ws.dataset, synth.UNITS_TYPE)]
    one = [c.total_hours for c in costs if c.matter.num_units == 1]
    many = [c.total_hours for c in costs if c.matter.num_units >= 3]
    assert len(one) >= 8 and len(many) >= 8
    assert stats.quantile(many, D("0.5")) > D("1.4") * stats.quantile(one, D("0.5"))
