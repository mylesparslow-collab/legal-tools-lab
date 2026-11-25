"""Write the fictional sample data. Every name, number and date is invented.

The ledger is generated clean (exhibit totals and shares computed from the
deltas), then two drafting errors are seeded so the checks have something to
find. sample_data/ifoa_ledger_clean.json is the version without them.
"""
import copy
import csv
import json
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "sample_data"

ARCH, GC, SE = "Halvorsen Ito Architects", "Brightwater Builders", "Pallas Structural"
MECH, ELEC, CW = "Northspan Mechanical", "Kestrel Electric", "Sable Curtainwall"


def prov(doc, exhibit, page, quote):
    return {"document": doc, "exhibit": exhibit, "page": page, "quote": quote}


AMENDMENTS = [
    {"no": 0, "date": "2024-03-15", "type": "BASE", "title": "Integrated Form of Agreement",
     "base_members": [ARCH, GC, SE],
     "deltas": {"target_cost": 318000000, "shared_contingency": 11000000, "owner_contingency": 18000000, "emp": 372000000},
     "icl_changes": [{"member": ARCH, "delta": 4200000}, {"member": GC, "delta": 13300000}, {"member": SE, "delta": 1500000}],
     "provenance": prov("IFOA (executed)", "Exhibit 4 - Business Terms", 3, "The Target Cost is $318,000,000.")},
    {"no": 1, "date": "2024-06-03", "type": "JOINING", "title": "Joining Agreement - mechanical trade partner",
     "joining": {"member": MECH, "role": "Mechanical / plumbing trade partner", "counsel_status": "represented", "nonrep_notice_logged": False},
     "deltas": {"target_cost": 52000000, "emp": 57000000},
     "icl_changes": [{"member": MECH, "delta": 4400000}],
     "provenance": prov("Joining Agreement No. 1", "Exhibit A - Risk Pool Schedule", 2, "Northspan's ICL is $4,400,000.")},
    {"no": 2, "date": "2024-07-22", "type": "JOINING", "title": "Joining Agreement - electrical trade partner",
     "joining": {"member": ELEC, "role": "Electrical trade partner", "counsel_status": "unrepresented", "nonrep_notice_logged": True},
     "deltas": {"target_cost": 31000000, "emp": 34000000},
     "icl_changes": [{"member": ELEC, "delta": 2600000}],
     "provenance": prov("Joining Agreement No. 2", "Exhibit A - Risk Pool Schedule", 2, "Kestrel's ICL is $2,600,000.")},
    {"no": 3, "date": "2024-11-08", "type": "VALIDATION_GATE", "title": "Validation Gate Amendment",
     "deltas": {"target_cost": -6500000, "shared_contingency": 1500000, "emp": -5000000},
     "provenance": prov("Amendment No. 3", "Exhibit 4 (restated)", 1, "Target Cost is reduced by $6,500,000 following validation.")},
    {"no": 4, "date": "2025-04-17", "type": "TARGET_COST_ADJUSTMENT", "title": "Owner-directed scope: imaging suite",
     "deltas": {"target_cost": 9250000, "emp": 10000000},
     "icl_changes": [{"member": GC, "delta": 420000}, {"member": ARCH, "delta": 180000}, {"member": MECH, "delta": 150000}],
     "provenance": prov("Amendment No. 4", "Exhibit 4 (restated)", 2, "Target Cost is increased by $9,250,000 and ICL by $750,000.")},
    {"no": 5, "date": "2025-09-30", "type": "CONTINGENCY_DRAW", "title": "Shared contingency draw: unforeseen soil conditions",
     "draws": {"shared": 2300000},
     "provenance": prov("Amendment No. 5", "Contingency Log", 1, "Draw of $2,300,000 from Shared Contingency.")},
    {"no": 6, "date": "2026-02-12", "type": "JOINING", "title": "Joining Agreement - curtainwall trade partner",
     "joining": {"member": CW, "role": "Exterior envelope trade partner", "counsel_status": "unknown", "nonrep_notice_logged": False},
     "deltas": {"target_cost": 14600000, "emp": 15750000},
     "icl_changes": [{"member": CW, "delta": 1150000}],
     "provenance": prov("Joining Agreement No. 3", "Exhibit A - Risk Pool Schedule", 2, "Sable's ICL is $1,150,000.")},
    {"no": 7, "date": "2026-06-25", "type": "CONTINGENCY_DRAW", "title": "Contingency draws: steel escalation and owner equipment change",
     "draws": {"shared": 3100000, "owner": 1200000},
     "provenance": prov("Amendment No. 7", "Contingency Log", 1, "Draws of $3,100,000 (Shared) and $1,200,000 (Owner).")},
    {"no": 8, "date": "2026-10-09", "type": "TARGET_COST_ADJUSTMENT", "title": "Code-required changes from plan review comments",
     "deltas": {"target_cost": 3400000, "emp": 3400000},
     "provenance": prov("Amendment No. 8", "Exhibit 4 (restated)", 1, "Target Cost is increased by $3,400,000.")},
]


def largest_remainder_pct(icl):
    """Shares to 2 decimals that sum to exactly 100.00."""
    total = sum(icl.values())
    raw = {m: Decimal(v) * 10000 / total for m, v in icl.items()}
    floor = {m: int(r.to_integral_value(ROUND_FLOOR)) for m, r in raw.items()}
    short = 10000 - sum(floor.values())
    for m in sorted(raw, key=lambda m: raw[m] - floor[m], reverse=True)[:short]:
        floor[m] += 1
    return {m: float(Decimal(v) / 100) for m, v in floor.items()}


def build_ledger():
    run = {"target_cost": 0, "shared_contingency": 0, "owner_contingency": 0, "emp": 0}
    icl = {}
    ams = copy.deepcopy(AMENDMENTS)
    for am in ams:
        for k, v in am.get("deltas", {}).items():
            run[k] += v
        for ch in am.get("icl_changes", []):
            icl[ch["member"]] = icl.get(ch["member"], 0) + ch["delta"]
        am["stated"] = {**run, "icl_total": sum(icl.values()), "icl_shares": largest_remainder_pct(icl)}
    return {
        "project": "Calloway Ridge Medical Center - Replacement Patient Tower (fictional)",
        "owner": "Calloway Ridge Health Care District (fictional)",
        "as_of": "2026-11-25",
        "terms": {"owner_savings_pct": 50, "team_savings_pct": 50, "icl_cap_multiple": 2.0,
                  "tax_exempt_bond_financed": True, "post_occupancy_services_in_scope": False},
        "forecast_actual_cost": 441300000,
        "amendments": ams,
    }


FACILITY = {
    "facility": "Calloway Ridge Medical Center (fictional)", "owner": "Calloway Ridge Health Care District (fictional)",
    "perm_id": 990001, "as_of": "2026-11-25", "milestone_status_last_updated": "2026-08-14",
    "eligibility": {"licensed_beds": 118, "gac_beds": 96, "rural": "N", "critical_access": "N", "district": "Y",
                    "dhlp_recipient": "N", "integrated_system": "N", "system_bears_seismic_cost": "N",
                    "system_operated_by_district": "N", "system_in_financial_distress": "N",
                    "gac_revenue_2020": 212000000, "npc5_report_by_2025_01_01": "Y",
                    "compliance_plan_submitted": "2025-11-18"},
    "approved_delay_date": "2032-07-01", "additional_delay_granted": "N",
    "linked_project": {"name": "Replacement Patient Tower (IFOA)", "baseline_completion": "2031-03-31",
                       "forecast_completion": "2031-09-12", "scenario_extra_drift_days": 0},
    "buildings": [
        {"building_nbr": "BLD-90001", "name": "Main Hospital (1968)", "spc": "2", "npc": "2", "hcai_status": "OSHPD 1-In Service",
         "method": "Replace services to a new building", "linked_to_project": "Y", "forecast_compliance_date": "2031-08-15"},
        {"building_nbr": "BLD-90002", "name": "East Wing", "spc": "2", "npc": "3", "hcai_status": "OSHPD 1-In Service",
         "method": "SPC and NPC retrofit", "linked_to_project": "N", "forecast_compliance_date": "2032-04-20"},
        {"building_nbr": "BLD-90003", "name": "Diagnostic Pavilion", "spc": "4", "npc": "4", "hcai_status": "OSHPD 1-In Service",
         "method": "NPC retrofit", "linked_to_project": "N", "forecast_compliance_date": "2029-10-30"},
        {"building_nbr": "BLD-90005", "name": "Central Plant", "spc": "5", "npc": "5", "hcai_status": "OSHPD 1-In Service",
         "method": "Building is already compliant", "linked_to_project": "N", "forecast_compliance_date": None},
    ],
    "milestones": [
        {"id": "M01", "building": "BLD-90001", "type": "Construction Project Submittal", "description": "Tower increment 1 documents", "critical": "N", "approved_date": "2025-12-15", "forecast_or_actual_date": "2025-12-09", "status": "Completed"},
        {"id": "M02", "building": "BLD-90001", "type": "Permit Issuance", "description": "Tower increment 1 permit", "critical": "Y", "approved_date": "2026-06-30", "forecast_or_actual_date": "2026-07-21", "status": "Completed"},
        {"id": "M03", "building": "BLD-90001", "type": "Construction Commencement", "description": "Tower foundations", "critical": "Y", "approved_date": "2026-09-15", "forecast_or_actual_date": "2026-12-18", "status": "In Progress"},
        {"id": "M04", "building": "BLD-90001", "type": "Construction Milestone", "description": "Tower structure topped out", "critical": "Y", "approved_date": "2028-11-30", "forecast_or_actual_date": "2029-03-15", "status": "Not Started"},
        {"id": "M05", "building": "BLD-90001", "type": "Construction Final", "description": "Tower construction final", "critical": "Y", "approved_date": "2031-03-31", "forecast_or_actual_date": "2031-09-12", "status": "Not Started"},
        {"id": "M06", "building": "BLD-90001", "type": "Compliant Building", "description": "Acute services moved out of Main Hospital", "critical": "Y", "approved_date": "2031-08-15", "forecast_or_actual_date": "2032-01-27", "status": "Not Started"},
        {"id": "M07", "building": "BLD-90002", "type": "Evaluation Report Submittal", "description": "SPC 4D evaluation", "critical": "N", "approved_date": "2026-05-01", "forecast_or_actual_date": "2026-04-22", "status": "Completed"},
        {"id": "M08", "building": "BLD-90002", "type": "Material Testing Report Submittal", "description": "Material testing results", "critical": "Y", "approved_date": "2026-11-02", "forecast_or_actual_date": "2026-11-20", "status": "In Progress"},
        {"id": "M09", "building": "BLD-90002", "type": "Permit Issuance", "description": "SPC 4D retrofit permit", "critical": "Y", "approved_date": "2028-06-30", "forecast_or_actual_date": "2028-06-30", "status": "Not Started"},
        {"id": "M10", "building": "BLD-90002", "type": "Construction Final", "description": "SPC 4D and NPC 5 retrofit final", "critical": "Y", "approved_date": "2032-04-20", "forecast_or_actual_date": "2032-04-20", "status": "Not Started"},
        {"id": "M11", "building": "BLD-90003", "type": "Construction Project Submittal", "description": "NPC 5 documents", "critical": "N", "approved_date": "2026-03-01", "forecast_or_actual_date": "2026-02-20", "status": "Completed"},
        {"id": "M12", "building": "BLD-90003", "type": "Permit Issuance", "description": "NPC 5 permit", "critical": "Y", "approved_date": "2028-03-01", "forecast_or_actual_date": "2028-02-01", "status": "Not Started"},
        {"id": "M13", "building": "BLD-90003", "type": "Construction Final", "description": "NPC 5 retrofit final", "critical": "Y", "approved_date": "2029-10-30", "forecast_or_actual_date": "2029-10-30", "status": "Not Started"},
    ],
}

HCAI_ROWS = [  # same columns as the CalHHS "Hospital Building Data" CSV; all values invented
    ["99 - Example", 990001, "Calloway Ridge Medical Center", "Calloway Ridge", "BLD-90001", "Main Hospital", "OSHPD 1-In Service", "2", "", 62, 5, "1964 Uniform Building Code (UBC)", 1964, 1968, "This building does not significantly jeopardize life, but may not be repairable or functional following an earthquake.", 0, 0, 1],
    ["99 - Example", 990001, "Calloway Ridge Medical Center", "Calloway Ridge", "BLD-90002", "East Wing", "OSHPD 1-In Service", "2", "", 44, 3, "1970 Uniform Building Code (UBC)", 1970, 1974, "This building does not significantly jeopardize life, but may not be repairable or functional following an earthquake.", 0, 0, 1],
    ["99 - Example", 990001, "Calloway Ridge Medical Center", "Calloway Ridge", "BLD-90003", "Diagnostic Pavilion", "OSHPD 1-In Service", "3", "", 30, 2, "1988 Uniform Building Code (UBC)", 1988, 1991, "", 0, 0, 1],
    ["99 - Example", 990001, "Calloway Ridge Medical Center", "Calloway Ridge", "BLD-90004", "Annex", "OSHPD 1-In Service", "2", "", 18, 1, "1970 Uniform Building Code (UBC)", 1970, 1975, "This building does not significantly jeopardize life, but may not be repairable or functional following an earthquake.", 0, 0, 1],
    ["99 - Example", 990001, "Calloway Ridge Medical Center", "Calloway Ridge", "BLD-90005", "Central Plant", "OSHPD 1-In Service", "5", "", 24, 1, "2010 California Building Code (CBC)", 2010, 2014, "", 0, 0, 1],
    ["99 - Example", 990002, "Other Example Hospital", "Elsewhere", "BLD-90100", "Main", "OSHPD 1-In Service", "4", "", 40, 3, "1995 California Building Code (CBC)", 1995, 1999, "", 0, 0, 1],
]


def main():
    from engine.seismic import HCAI_COLUMNS
    OUT.mkdir(exist_ok=True)
    clean = build_ledger()
    (OUT / "ifoa_ledger_clean.json").write_text(json.dumps(clean, indent=2))
    seeded = copy.deepcopy(clean)
    # Seeded error 1: Amendment 6 exhibit was not re-based after the new member joined.
    a6 = seeded["amendments"][6]["stated"]["icl_shares"]
    a6["Brightwater Builders"] = round(a6["Brightwater Builders"] - 0.5, 2)
    # Seeded error 2: Amendment 8 restates the target cost $250,000 low.
    seeded["amendments"][8]["stated"]["target_cost"] -= 250000
    seeded["seeded_errors"] = ["Amendment 6: stated ICL shares sum to 99.50%", "Amendment 8: restated target cost is $250,000 low"]
    (OUT / "ifoa_ledger.json").write_text(json.dumps(seeded, indent=2))
    (OUT / "seismic_campus.json").write_text(json.dumps(FACILITY, indent=2))
    with open(OUT / "hcai_buildings_sample.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HCAI_COLUMNS)
        w.writerows(HCAI_ROWS)
    print("sample data written to", OUT)


if __name__ == "__main__":
    main()
