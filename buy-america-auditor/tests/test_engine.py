"""Engine tests. Run with: python -m pytest tests -q"""
import datetime as dt
import json
from pathlib import Path

import pytest

from buy_america.engine import (FAIL, NA, PASS, REVIEW, Line, Rules, audit_component, audit_documents,
                                audit_infrastructure_item, audit_rolling_stock, federal_fiscal_year, load_bom, run)

ROOT = Path(__file__).resolve().parents[1]
RULES = Rules()


def comp(cost, country, subs=(), **kw):
    c = Line("P", "C", "E", "component", cost=cost, mfg_country=country, cert_on_file=True, **kw)
    c.children = [Line("P", f"S{i}", "C", "subcomponent", cost=sc, mfg_country=sco, **(extra[0] if extra else {}))
                  for i, (sc, sco, *extra) in enumerate(subs)]
    return c


def vehicle(components, **project):
    end = Line("P", "E", "", "end_product", category="rolling_stock")
    end.children = components
    proj = {"scheduled_delivery_date": "2027-01-15", "final_assembly_country": "US", "average_vehicle_cost": 900000}
    proj.update(project)
    return audit_rolling_stock(end, proj, RULES)


# ---- rules data -----------------------------------------------------------
def test_every_rule_has_a_source_and_a_status():
    for r in RULES.entries.values():
        assert r["source"], r["id"]
        assert r["status"] in ("verified", "partially_verified", "not_loaded"), r["id"]
        if r["status"] != "not_loaded":
            assert r["verified_on"] and r["verified_how"], r["id"]


def test_engine_source_has_no_hard_coded_thresholds():
    """Every number in engine.py is structural (0, 1, 100, a rounding tolerance, an open-ended year)."""
    import io
    import tokenize
    src = (ROOT / "buy_america" / "engine.py").read_text()
    numbers = {t.string for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type == tokenize.NUMBER}
    assert numbers <= {"0", "1", "10", "100", "0.0", "0.005", "9999"}, numbers


def test_fiscal_year_boundaries():
    assert federal_fiscal_year(dt.date(2019, 9, 30)) == 2019
    assert federal_fiscal_year(dt.date(2019, 10, 1)) == 2020


@pytest.mark.parametrize("fy,pct", [(2016, 60), (2017, 60), (2018, 65), (2019, 65), (2020, 70), (2031, 70)])
def test_statutory_schedule(fy, pct):
    assert RULES.rolling_stock_pct(fy) == pct


def test_no_threshold_before_schedule_starts():
    with pytest.raises(ValueError):
        RULES.rolling_stock_pct(2015)


# ---- 49 CFR 661.11 component rules -----------------------------------------
def test_domestic_component_counts_in_full():
    r = audit_component(comp(100, "US", [(71, "US"), (29, "CN")]), 70, False, RULES)
    assert r["counted"] == 100


def test_exactly_at_threshold_is_not_more_than():
    r = audit_component(comp(120, "US", [(70, "US"), (30, "CN")]), 70, False, RULES)
    assert r["counted"] == 70 + 20  # 661.11(l): domestic subs plus manufacturing cost


def test_failed_subcomponent_test_gives_partial_credit_not_zero():
    r = audit_component(comp(310, "US", [(150, "KR"), (90, "US")]), 70, False, RULES)
    assert r["counted"] == 90 + 70
    assert "661.11(l)" in r["basis"]


def test_foreign_component_counts_nothing():
    r = audit_component(comp(100, "DE", [(40, "US"), (30, "DE")]), 70, False, RULES)
    assert r["counted"] == 0
    assert any("661.11(j)" in f for f in r["flags"])


def test_foreign_component_counts_tariff_exempt_us_subcomponent():
    r = audit_component(comp(100, "DE", [(40, "US", {"tariff_exempt_reexport": True}), (30, "DE")]), 70, False, RULES)
    assert r["counted"] == 40


def test_exported_raw_material_is_not_a_subcomponent():
    r = audit_component(comp(100, "DE", [(40, "US", {"tariff_exempt_reexport": True, "raw_material": True})]), 70, False, RULES)
    assert r["counted"] == 0


def test_waived_component_and_subcomponent_are_treated_as_domestic():
    assert audit_component(comp(100, "JP", waiver_ref="FTA letter"), 70, False, RULES)["counted"] == 100
    r = audit_component(comp(100, "US", [(60, "JP", {"waiver_ref": "FTA letter"}), (20, "US")]), 70, False, RULES)
    assert r["counted"] == 100


def test_component_without_subcomponents_is_flagged():
    r = audit_component(comp(100, "US"), 70, False, RULES)
    assert r["counted"] == 100 and any("No subcomponents" in f for f in r["flags"])


def test_frame_steel_credit_needs_average_cost_above_floor():
    shell = lambda: comp(600, "ES", frame_or_shell=True, us_steel_iron_cost=140)
    assert audit_component(shell(), 70, True, RULES)["counted"] == 140
    assert audit_component(shell(), 70, False, RULES)["counted"] == 0
    floor = RULES.value("rs_frame_shell_steel_credit_min_avg_cost")
    at_floor = vehicle([shell(), comp(400, "US")], average_vehicle_cost=floor)
    above = vehicle([shell(), comp(400, "US")], average_vehicle_cost=floor + 1)
    assert at_floor["domestic_cost"] == 400 and above["domestic_cost"] == 540


def test_us_made_frame_gets_no_extra_credit():
    r = audit_component(comp(600, "US", frame_or_shell=True, us_steel_iron_cost=140), 70, True, RULES)
    assert r["counted"] == 600


# ---- vehicle level ---------------------------------------------------------
def test_vehicle_needs_more_than_threshold():
    assert vehicle([comp(70, "US"), comp(30, "CN")])["status"] == FAIL      # exactly 70%
    assert vehicle([comp(70.01, "US"), comp(29.99, "CN")])["status"] == PASS


def test_foreign_final_assembly_fails_even_with_high_content():
    r = vehicle([comp(95, "US"), comp(5, "CN")], final_assembly_country="CA")
    assert r["domestic_pct"] == 95 and r["status"] == FAIL


def test_older_delivery_uses_older_percentage_for_vehicle_and_subcomponents():
    parts = lambda: [comp(66, "US", [(33, "US"), (17, "CN")]), comp(34, "CN")]   # 66% subs, 66% vehicle
    assert vehicle(parts(), scheduled_delivery_date="2019-06-01")["status"] == PASS   # FY2019: 65%
    late = vehicle(parts(), scheduled_delivery_date="2019-10-01")                      # FY2020: 70%
    assert late["status"] == FAIL and late["domestic_cost"] == 33 + 16


def test_shortfall_is_reported():
    r = vehicle([comp(60, "US"), comp(40, "CN")])
    assert r["shortfall_usd"] == pytest.approx(10)


# ---- infrastructure --------------------------------------------------------
def product(country, comps, funding="FTA", **kw):
    end = Line("P", "D", "", "end_product", category="manufactured_product", cost=1000, mfg_country=country,
               cert_on_file=True, **kw)
    end.children = [Line("P", f"K{i}", "D", "component", cost=c, mfg_country=co) for i, (c, co) in enumerate(comps)]
    return audit_infrastructure_item(end, {"funding": funding}, RULES)


def test_fta_and_baba_tests_disagree_on_the_same_product():
    fta = product("US", [(80, "US"), (20, "TW")])
    assert (fta["fta_661_5d"], fta["baba_184"], fta["status"]) == (FAIL, PASS, FAIL)
    assert any("disagree" in f for f in fta["flags"])
    assert product("US", [(80, "US"), (20, "TW")], funding="OTHER_FEDERAL_BABA")["status"] == PASS


def test_baba_needs_more_than_55_and_us_manufacture():
    assert product("US", [(55, "US"), (45, "CN")])["baba_184"] == FAIL
    assert product("US", [(55.1, "US"), (44.9, "CN")])["baba_184"] == PASS
    assert product("MX", [(90, "US"), (10, "MX")])["baba_184"] == FAIL


def test_product_without_component_list_is_review():
    assert product("US", [])["status"] == REVIEW


def item(category, funding="FTA", authority="local_agency", **kw):
    end = Line("P", "D", "", "end_product", category=category, cost=100, cert_on_file=True, **kw)
    return audit_infrastructure_item(end, {"funding": funding, "awarding_authority_type": authority}, RULES)


def test_steel_and_construction_materials():
    assert item("iron_steel", mfg_country="US", all_processes_us="Y")["status"] == PASS
    assert item("iron_steel", mfg_country="US", all_processes_us="N")["status"] == FAIL
    assert item("iron_steel", mfg_country="US")["status"] == REVIEW
    assert "661.5" in item("iron_steel", mfg_country="US", all_processes_us="Y")["cite"]
    assert "184.3" in item("iron_steel", funding="OTHER_FEDERAL_BABA", mfg_country="US", all_processes_us="Y")["cite"]
    assert item("construction_material", mfg_country="US", all_processes_us="Y", material_type="glass")["status"] == PASS
    assert item("construction_material", mfg_country="US", all_processes_us="N", material_type="optical_fiber")["status"] == FAIL
    assert item("construction_material", mfg_country="US", all_processes_us="Y", material_type="ceramic_tile")["status"] == REVIEW
    assert item("section_70917c", mfg_country="US")["status"] == REVIEW
    assert item("unclassified", mfg_country="US")["status"] == REVIEW


def test_buy_clean_only_reaches_state_awarding_authorities():
    kw = dict(mfg_country="US", all_processes_us="Y", material_type="structural_steel")
    assert item("iron_steel", **kw)["buy_clean"]["status"] == NA
    assert item("iron_steel", authority="state_agency", **kw)["buy_clean"]["status"] == FAIL          # no EPD
    assert item("iron_steel", authority="csu", epd_on_file=True, **kw)["buy_clean"]["status"] == REVIEW  # no limit loaded


def test_buy_clean_compares_gwp_when_a_limit_is_loaded(tmp_path):
    data = json.loads((ROOT / "buy_america" / "rules.json").read_text())
    for r in data["rules"]:
        if r["id"] == "ca_buy_clean_gwp_limits":
            r["value"] = {"structural_steel": {"limit": 1.0, "unit": "test units"}}
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(data))
    rules = Rules(p)
    def run_one(gwp):
        end = Line("P", "D", "", "end_product", category="iron_steel", mfg_country="US", all_processes_us="Y",
                   material_type="structural_steel", epd_on_file=True, gwp=gwp, cert_on_file=True)
        return audit_infrastructure_item(end, {"awarding_authority_type": "uc"}, rules)["buy_clean"]["status"]
    assert run_one(0.9) == PASS and run_one(1.1) == FAIL


# ---- documents -------------------------------------------------------------
def docs(stage, have=(), **project):
    p = {"stage": stage, "vehicle_type": "bus", "vehicle_count": 30, "service_area": "urbanized_over_200k",
         "documents": {k: True for k in have}}
    p.update(project)
    return {d["document"]: d["status"] for d in audit_documents(p, True, RULES)}


def test_pre_award_audit_is_due_before_contract():
    assert docs("pre_award")["Pre-award Buy America certification"] == REVIEW
    assert docs("contract_signed")["Pre-award Buy America certification"] == FAIL
    assert docs("contract_signed", ["pre_award_buy_america_certification"])["Pre-award Buy America certification"] == PASS


def test_post_delivery_audit_is_due_before_title_transfer():
    assert docs("delivered")["Post-delivery Buy America certification"] == REVIEW
    assert docs("title_transferred")["Post-delivery Buy America certification"] == FAIL


def test_resident_inspector_exceptions():
    key = "Resident inspector's report"
    assert docs("title_transferred")[key] == FAIL
    assert docs("title_transferred", vehicle_count=10)[key] == NA
    assert docs("title_transferred", vehicle_count=11)[key] == FAIL
    assert docs("title_transferred", vehicle_count=20, service_area="rural_or_small_urbanized")[key] == NA
    assert docs("title_transferred", vehicle_count=21, service_area="rural_or_small_urbanized")[key] == FAIL
    assert docs("title_transferred", vehicle_type="railcar", vehicle_count=4)[key] == FAIL


def test_fmvss_not_required_for_rail():
    assert docs("title_transferred", vehicle_type="railcar")["Manufacturer's FMVSS information (post-delivery)"] == NA


# ---- loader and sample data ------------------------------------------------
def test_loader_rejects_bad_hierarchy(tmp_path):
    p = tmp_path / "bom.csv"
    p.write_text("project_id,line_id,parent_id,tier,category,cost_usd\nP,E,,end_product,rolling_stock,\nP,S,E,subcomponent,,5\n")
    with pytest.raises(ValueError):
        load_bom(p)


def test_sample_data_results():
    audit = run(ROOT / "sample_data" / "case.json", ROOT / "sample_data" / "bom.csv")
    by = {p["project_id"]: p for p in audit["projects"]}
    bus = by["TB-BEB-40"]["rolling_stock"][0]
    assert bus["status"] == PASS and bus["domestic_cost"] == 566000 and round(bus["domestic_pct"], 2) == 71.83
    lrv = by["TB-LRV"]["rolling_stock"][0]
    assert lrv["status"] == FAIL and lrv["domestic_cost"] == 2100000 and lrv["shortfall_usd"] == pytest.approx(105000)
    depot = {r["line_id"]: r for r in by["TB-DEPOT"]["infrastructure"]}
    assert (depot["D03"]["fta_661_5d"], depot["D03"]["baba_184"]) == (FAIL, PASS)
    assert by["TB-DEPOT"]["de_minimis"]["within_limits"] is False
    assert [p["overall"] for p in audit["projects"]] == [REVIEW, FAIL, FAIL]


def test_report_misreading_would_flip_the_bus_result():
    """The source report said a component that fails the subcomponent test counts for nothing.
    Under 661.11(l) it gets partial credit, and on the sample bus that is the difference between pass and fail."""
    audit = run(ROOT / "sample_data" / "case.json", ROOT / "sample_data" / "bom.csv")
    bus = audit["projects"][0]["rolling_stock"][0]
    zeroed = sum(c["counted"] for c in bus["components"] if "661.11(l)" not in c["basis"])
    assert zeroed / bus["total_component_cost"] * 100 < bus["threshold_pct"] < bus["domestic_pct"]


def test_sample_data_is_marked_synthetic():
    assert json.loads((ROOT / "sample_data" / "case.json").read_text())["synthetic"] is True
