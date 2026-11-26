from decimal import Decimal

import pytest

from feemodel import pricing
from feemodel.comps import SelectionRules, select_comps
from feemodel.cost import CostBook, build_cost, parse_reductions
from feemodel.pricing import CompEcon
from helpers import CODE_MAP, COSTS, RATES, d, mk_dataset, mk_entry, mk_matter

D = Decimal


def econ(pairs):
    return [CompEcon("M%d" % i, D(v), D(c)) for i, (v, c) in enumerate(pairs)]


COMPS = econ([(60, 20), (90, 30), (105, 35), (150, 50), (300, 100)])


def test_fixed_fee_share_under_and_margin_by_hand():
    r = pricing.evaluate_fixed(COMPS, "100")
    assert r["under_fee"] == {"count": 2, "n": 5}
    assert r["no_loss"] == {"count": 5, "n": 5}
    assert r["expected_revenue"] == D(100)
    assert r["expected_cost"] == D(47)                 # (20+30+35+50+100)/5
    assert r["expected_margin"] == D(53)
    assert r["margin_pct_of_revenue"] == D("53.0")
    assert r["n"] == 5 and len(r["per_comp"]) == 5


def test_fixed_fee_downside_is_fee_minus_p90_cost():
    r = pricing.evaluate_fixed(COMPS, "100")
    from feemodel import stats
    p90_cost = stats.quantile([c.cost for c in COMPS], D("0.90"))
    assert p90_cost == D(80)
    assert r["downside_p90_margin"] == D(100) - p90_cost


def test_fixed_fee_can_lose_money():
    r = pricing.evaluate_fixed(COMPS, "40")
    assert r["no_loss"] == {"count": 3, "n": 5}
    assert r["downside_p90_margin"] == D(-40)


def test_capped_fee_pays_hourly_up_to_the_cap():
    r = pricing.evaluate_capped(COMPS, "100")
    assert [pc["revenue"] for pc in r["per_comp"]] == [D(60), D(90), D(100), D(100), D(100)]
    assert r["under_fee"] == {"count": 2, "n": 5} and r["hit_cap"] == {"count": 3, "n": 5}
    assert r["expected_revenue"] == D(90)
    assert r["revenue_vs_standard_value_pct"] == D("63.8")     # 450 / 705


def test_collar_three_cases_by_hand():
    r = pricing.evaluate_collar(econ([(150, 50), (60, 20), (105, 35)]), "100", "10", "50")
    assert [pc["revenue"] for pc in r["per_comp"]] == [D(120), D(85), D(100)]   # above, below, inside the band
    assert r["above_band"]["count"] == 1 and r["below_band"]["count"] == 1 and r["inside_band"]["count"] == 1
    assert r["params"]["band_low"] == D(90) and r["params"]["band_high"] == D(110)


def test_collar_with_full_sharing_equals_hourly_outside_band_offsets():
    # 100% shared: revenue tracks value outside the band, shifted by the band width.
    r = pricing.evaluate_collar(econ([(200, 50)]), "100", "10", "100")
    assert r["per_comp"][0]["revenue"] == D(190)


def phased_comps():
    a = CompEcon("A", D(28), D(10), {"assessment": D(8), "drafting": D(20)}, {"assessment": D(3), "drafting": D(7)},
                 frozenset({"assessment", "drafting"}))
    b = CompEcon("B", D(108), D(40), {"assessment": D(8), "drafting": D(20), "hearing": D(80)},
                 {"assessment": D(3), "drafting": D(7), "hearing": D(30)}, frozenset({"assessment", "drafting", "hearing"}))
    return [a, b]


def test_phased_fee_charges_a_phase_only_when_it_happened():
    r = pricing.evaluate_phased(phased_comps(), {"assessment": "10", "hearing": "50"})
    assert [pc["revenue"] for pc in r["per_comp"]] == [D(30), D(80)]     # drafting billed hourly at 20
    assert r["params"]["hourly_phases"] == ["drafting", "discovery", "closing"]
    hearing = [p for p in r["by_phase"] if p["phase"] == "hearing"][0]
    assert hearing["n_occurred"] == 1 and hearing["under_fee"] == {"count": 0, "n": 1}
    assert hearing["no_loss"] == {"count": 1, "n": 1}
    assert r["under_fee"] == {"count": 1, "n": 2}


def test_unknown_scenario_or_phase_is_rejected():
    with pytest.raises(ValueError):
        pricing.evaluate_scenario(COMPS, {"type": "success_fee"})
    with pytest.raises(ValueError):
        pricing.evaluate_phased(phased_comps(), {"appeal": "10"})
    with pytest.raises(ValueError):
        pricing.evaluate_fixed([], "10")


def test_fee_for_target_meets_the_target_in_the_comps():
    t = pricing.fee_for_target(COMPS, D("0.80"))
    assert t["fee_no_loss_on_cost"] == D(50) and t["no_loss"] == {"count": 4, "n": 5}
    assert t["fee_covering_standard_value"] == D(150) and t["under_fee"] == {"count": 4, "n": 5}
    check = pricing.evaluate_fixed(COMPS, t["fee_no_loss_on_cost"])
    assert check["no_loss"]["count"] * 100 >= 80 * check["n"]
    with pytest.raises(ValueError):
        pricing.fee_for_target(COMPS, D("0"))


def test_target_fee_on_synthetic_comps_meets_target(ws):
    sel = select_comps(ws.dataset, "public_works_bid_protest", {}, SelectionRules(), d("2026-01-01"))
    costs = [ws.book.cost(m.matter_id) for m in sel.included]
    comps = pricing.comp_economics(costs, ws.rate_card, ws.cost_rates)
    for p in ("0.50", "0.80", "0.95"):
        t = pricing.fee_for_target(comps, D(p))
        assert t["no_loss"]["count"] >= D(p) * t["n"]
        lower = pricing.evaluate_fixed(comps, t["fee_no_loss_on_cost"] - D("0.01"))
        assert lower["no_loss"]["count"] < D(p) * t["n"]        # and it is the smallest such fee


def tiny_costs():
    m1, m2 = mk_matter("M1"), mk_matter("M2")
    e = [mk_entry("1", "M1", "2021-02-01", 10, code="DR10"), mk_entry("2", "M1", "2021-01-02", 2, level="partner", code="AS10"),
         mk_entry("3", "M2", "2021-02-01", 20, code="DR10")]
    book = CostBook(mk_dataset([m1, m2], e), CODE_MAP)
    return [book.cost("M1"), book.cost("M2")]


def test_ai_assumptions_default_to_zero_and_change_nothing():
    costs = tiny_costs()
    t = pricing.ai_before_after(costs, RATES, parse_reductions({}))
    assert t["any_applied"] is False
    assert "not predictions" in t["label"]
    assert t["total"]["median_value_before"] == t["total"]["median_value_after"]
    for row in t["rows"]:
        assert row["reduction_pct"] == 0 and row["median_hours_before"] == row["median_hours_after"]


def test_ai_assumptions_are_applied_transparently():
    costs = tiny_costs()
    red = parse_reductions({"drafting": "20"})
    t = pricing.ai_before_after(costs, RATES, red)
    drafting = [r for r in t["rows"] if r["phase"] == "drafting"][0]
    assert t["any_applied"] is True and drafting["reduction_pct"] == D(20)
    assert drafting["median_hours_before"] == D(15) and drafting["median_hours_after"] == D(12)
    assert drafting["median_value_after"] == drafting["median_value_before"] * D("0.8")
    comps = pricing.comp_economics(costs, RATES, COSTS, red)
    assert [c.value for c in comps] == [D("4400.0"), D("6400.0")]
    assert [c.cost for c in comps] == [D("1200.0"), D("1600.0")]


def test_scope_assumptions_cite_hearing_evidence():
    matters, entries = [], []
    for i in range(10):
        mid = "M%d" % i
        matters.append(mk_matter(mid, hearing_occurred=i < 4))
        entries.append(mk_entry("d%d" % i, mid, "2021-02-01", 10 + i, code="DR10"))
        if i < 4:
            entries.append(mk_entry("h%d" % i, mid, "2021-05-01", 40, level="partner", code="HR10"))
    ds = mk_dataset(matters, entries)
    book = CostBook(ds, CODE_MAP)
    sel = select_comps(ds, "widget_dispute", {}, SelectionRules(), d("2024-01-01"))
    out = pricing.scope_assumptions(sel, [book.cost(m.matter_id) for m in sel.included], RATES)
    hearing = [a for a in out if a["kind"] == "hearing"][0]
    assert hearing["evidence"]["n_with"] == 4 and hearing["evidence"]["n_without"] == 6
    assert hearing["evidence"]["matter_ids_with"] == ["M0", "M1", "M2", "M3"]
    assert "separate phase" in hearing["text"] and "n=4" in hearing["text"]
    overrun = [a for a in out if a["kind"] == "overrun_phase"][0]
    assert overrun["evidence"]["top_phase"] == "hearing"
    assert overrun["evidence"]["n_above_p75"] + overrun["evidence"]["n_rest"] == 10


def test_scope_assumptions_mention_write_downs_and_abnormal_exclusions():
    matters = [mk_matter("M%d" % i) for i in range(8)] + [mk_matter("S1", reason="settled_early")]
    entries = [mk_entry("e%d" % i, "M%d" % i, "2021-02-01", 10, billed=8, code="DR10") for i in range(8)]
    ds = mk_dataset(matters, entries)
    book = CostBook(ds, CODE_MAP)
    sel = select_comps(ds, "widget_dispute", {}, SelectionRules(), d("2024-01-01"))
    out = {a["kind"]: a for a in pricing.scope_assumptions(sel, [book.cost(m.matter_id) for m in sel.included], RATES)}
    assert out["write_downs"]["evidence"]["write_down_pct"] == D("20.0")
    assert out["abnormal_excluded"]["evidence"]["matter_ids"] == ["S1"]
    assert "hearing" not in out
