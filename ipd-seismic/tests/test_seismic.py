import copy
from datetime import date
from pathlib import Path

from engine import seismic

ROOT = Path(__file__).resolve().parent.parent


def test_deadline_and_limits(campus, params):
    d, f = seismic.facility_deadline(campus, params)
    assert d == date(2032, 7, 1) and f == []
    c = copy.deepcopy(campus)
    c["approved_delay_date"] = None
    assert seismic.facility_deadline(c, params)[0] == date(2030, 1, 1)
    c["approved_delay_date"] = "2034-06-30"
    assert [x.code for x in seismic.facility_deadline(c, params)[1]] == ["S1"]
    c["additional_delay_granted"] = "Y"
    assert seismic.facility_deadline(c, params)[1] == []
    c["approved_delay_date"] = "2035-01-02"
    assert [x.code for x in seismic.facility_deadline(c, params)[1]] == ["S1"]


def test_eligibility_screen(campus, params):
    assert seismic.eligibility_screen(campus, params)["passes_screen"]
    c = copy.deepcopy(campus)
    e = c["eligibility"]
    e["district"] = "N"                                   # 118 beds, no category
    assert not seismic.eligibility_screen(c, params)["passes_screen"]
    e["licensed_beds"] = 50                               # small hospital
    assert seismic.eligibility_screen(c, params)["passes_screen"]
    e["integrated_system"] = "Y"                          # system hospital, no exception
    assert not seismic.eligibility_screen(c, params)["passes_screen"]
    e.update(rural="Y", gac_beds=79, gac_revenue_2020=75_000_000)   # exception (c)(2)(A)
    assert seismic.eligibility_screen(c, params)["exception_a"]
    assert seismic.eligibility_screen(c, params)["passes_screen"]
    e["gac_beds"] = 80
    assert not seismic.eligibility_screen(c, params)["passes_screen"]
    e["system_in_financial_distress"] = "Y"
    assert seismic.eligibility_screen(c, params)["passes_screen"]
    e["compliance_plan_submitted"] = "2026-01-02"         # one day late
    assert not seismic.eligibility_screen(c, params)["passes_screen"]


def test_district_with_cost_shifting_is_barred(campus, params):
    c = copy.deepcopy(campus)
    c["eligibility"]["system_bears_seismic_cost"] = "Y"
    r = seismic.eligibility_screen(c, params)
    assert r["system_bar"] and not r["exception_c"] and not r["passes_screen"]


def test_building_float_and_drift(campus, params):
    rows = {r["building_nbr"]: r for r in seismic.building_rows(campus, params)}
    assert rows["BLD-90001"]["drift_applied"] == 165 and rows["BLD-90001"]["float_days"] == 156
    assert rows["BLD-90002"]["float_days"] == 72 and rows["BLD-90002"]["status"] == "Tight"
    assert rows["BLD-90003"]["status"] == "On track"
    assert rows["BLD-90005"]["status"] == "Compliant" and rows["BLD-90005"]["notice"] == ""
    assert rows["BLD-90001"]["notice"].startswith("The State of California has determined that this building does not")
    c = copy.deepcopy(campus)
    c["linked_project"]["scenario_extra_drift_days"] = 157
    rows = {r["building_nbr"]: r for r in seismic.building_rows(c, params)}
    assert rows["BLD-90001"]["float_days"] == -1 and rows["BLD-90001"]["status"] == "Past deadline"
    assert rows["BLD-90002"]["float_days"] == 72          # not linked, unaffected


def test_spc_alone_is_not_compliance(campus, params):
    rows = {r["building_nbr"]: r for r in seismic.building_rows(campus, params)}
    assert rows["BLD-90003"]["spc"] == "4" and not rows["BLD-90003"]["compliant"]   # NPC 4, needs NPC 5


def test_milestone_lateness_and_fines(campus, params):
    m = {r["id"]: r for r in seismic.milestone_rows(campus, params)}
    assert (m["M02"]["accrued_late_days"], m["M03"]["accrued_late_days"], m["M08"]["accrued_late_days"]) == (21, 71, 23)
    assert m["M03"]["projected_late_days"] == 94 and m["M04"]["accrued_late_days"] == 0
    assert m["M04"]["adjustment_request_due"] == date(2028, 10, 31)
    fx = seismic.fine_exposure(list(m.values()), params)
    a = fx["accrued"]
    # M02 6/30-7/21 (21 days); M03 9/15-11/25 and M08 11/2-11/25 overlap (71 days)
    assert a["union_days"] == 92 and a["max_days"] == 71 and a["sum_days"] == 115
    assert a["per_facility"] == 460_000 and a["low"] <= a["per_facility"] <= a["high"]
    p = fx["projected"]
    assert p["max_days"] <= p["union_days"] <= p["sum_days"]


def test_non_critical_milestones_carry_no_fine(campus, params):
    c = copy.deepcopy(campus)
    for m in c["milestones"]:
        m["critical"] = "N"
    fx = seismic.fine_exposure(seismic.milestone_rows(c, params), params)
    assert fx["accrued"]["per_facility"] == 0 and fx["projected"]["per_facility"] == 0


def test_plan_findings(campus, params):
    b, m = seismic.building_rows(campus, params), seismic.milestone_rows(campus, params)
    f = seismic.plan_findings(campus, params, b, m)
    assert "S9" in [x.code for x in f]                    # permit hold
    assert "S5" not in [x.code for x in f]                # exactly 10 critical milestones
    c = copy.deepcopy(campus)
    c["milestones"] = [x for x in c["milestones"] if x["building"] != "BLD-90003"]
    c["milestones"][0]["type"] = "Ribbon Cutting"
    c["milestone_status_last_updated"] = "2025-10-01"
    b, m = seismic.building_rows(c, params), seismic.milestone_rows(c, params)
    got = [x.code for x in seismic.plan_findings(c, params, b, m)]
    assert {"S2", "S3", "S5", "S6"} <= set(got)


def test_hcai_crosscheck(campus):
    f = seismic.hcai_crosscheck(campus, ROOT / "sample_data" / "hcai_buildings_sample.csv")
    assert sorted((x.code, x.where) for x in f) == [("H1", "BLD-90004"), ("H2", "BLD-90003")]


def test_every_legal_param_has_citation_and_status(params):
    for pid, p in params.items():
        assert p["status"] in ("verified", "secondary", "assumption"), pid
        assert p["citation"], pid
        if p["status"] != "assumption":
            assert p["source_url"].startswith("https://"), pid
