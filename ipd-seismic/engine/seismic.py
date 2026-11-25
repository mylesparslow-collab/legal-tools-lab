"""Hospital seismic compliance tracker (HSC §§ 130065, 130065.1; HCAI PIN 80).

Date and count arithmetic only. The eligibility result is a screen of the
statutory conditions against recorded facts, not a determination; HCAI decides.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from .common import Finding, parse_date, pval

MILESTONE_TYPES = [  # HCAI PIN 80 p. 8
    "Compliant Building", "Material Testing Report Submittal", "Evaluation Report Submittal",
    "Construction Project Submittal", "Permit Issuance", "Construction Commencement",
    "Construction Milestone", "Construction Final",
]
MILESTONE_STATUSES = ["Completed", "In Progress", "Not Started"]
COMPLIANCE_METHODS = [  # HCAI PIN 80 pp. 7-8
    "Building is already compliant", "Building will be demolished",
    "Relocate services to another existing compliant building",
    "Replace services to a new building", "SPC retrofit", "NPC retrofit", "SPC and NPC retrofit",
]


def yes(v) -> bool:
    return str(v).strip().upper() in ("Y", "YES", "TRUE")


def eligibility_screen(f: dict, params: dict) -> dict:
    """Screen § 130065.1(b)-(d) conditions against the facility's recorded facts."""
    e = f["eligibility"]
    category = {
        "small hospital": e["licensed_beds"] <= pval(params, "small_hospital_beds"),
        "rural hospital": yes(e["rural"]),
        "critical access hospital": yes(e["critical_access"]),
        "health care district hospital": yes(e["district"]),
        "Distressed Hospital Loan Program recipient": yes(e["dhlp_recipient"]),
    }
    in_category = any(category.values())
    system_bar = yes(e["integrated_system"]) or (yes(e["district"]) and yes(e["system_bears_seismic_cost"]))
    exc_a = (yes(e["rural"]) and e["gac_beds"] < pval(params, "rural_exception_gac_beds")
             and e["gac_revenue_2020"] <= pval(params, "rural_exception_revenue_2020"))
    exc_b = yes(e["system_operated_by_district"])
    exc_c = yes(e["district"]) and not yes(e["system_bears_seismic_cost"])
    bar_lifted = yes(e["system_in_financial_distress"]) or exc_a or exc_b or exc_c
    npc5_ok = str(e["npc5_report_by_2025_01_01"]).strip().upper() in ("Y", "NOT NEEDED")
    plan_date = parse_date(e.get("compliance_plan_submitted"))
    plan_ok = plan_date is not None and plan_date <= parse_date(pval(params, "compliance_plan_due"))
    passes = in_category and (not system_bar or bar_lifted) and npc5_ok and plan_ok
    return {
        "categories_met": [k for k, v in category.items() if v], "in_category": in_category,
        "system_bar": system_bar, "exception_a": exc_a, "exception_b": exc_b, "exception_c": exc_c,
        "bar_lifted": bar_lifted, "npc5_ok": npc5_ok, "plan_ok": plan_ok, "passes_screen": passes,
    }


def facility_deadline(f: dict, params: dict):
    base = parse_date(pval(params, "seismic_base_deadline"))
    approved = parse_date(f.get("approved_delay_date"))
    findings = []
    if approved is None:
        return base, findings
    limit = parse_date(pval(params, "ab869_max_delay"))
    outer = parse_date(pval(params, "ab869_outer_limit"))
    if yes(f.get("additional_delay_granted", "N")):
        limit = outer
    if approved > limit:
        findings.append(Finding("S1", "error", "Facility",
                                f"Approved delay date {approved} is after the limit of {limit}."))
    return approved, findings


def project_drift(f: dict) -> int:
    p = f["linked_project"]
    return (parse_date(p["forecast_completion"]) - parse_date(p["baseline_completion"])).days \
        + int(p.get("scenario_extra_drift_days", 0))


def building_rows(f: dict, params: dict) -> list[dict]:
    deadline, _ = facility_deadline(f, params)
    drift = project_drift(f)
    tight = pval(params, "tight_float_days")
    ok_spc, ok_npc = set(pval(params, "compliant_spc")), set(pval(params, "compliant_npc"))
    rows = []
    for b in f["buildings"]:
        compliant = str(b["spc"]) in ok_spc and str(b["npc"]) in ok_npc
        base = parse_date(b.get("forecast_compliance_date"))
        applied = drift if yes(b.get("linked_to_project", "N")) else 0
        adj = base + timedelta(days=applied) if base else None
        flt = None if compliant or adj is None else (deadline - adj).days
        if compliant:
            status = "Compliant"
        elif adj is None:
            status = "No forecast date"
        elif flt < 0:
            status = "Past deadline"
        elif flt < tight:
            status = "Tight"
        else:
            status = "On track"
        notice = "" if compliant else (
            pval(params, "ab1882_notice_spc2") if str(b["spc"]) == "2" else pval(params, "ab1882_notice_other"))
        rows.append({**b, "compliant": compliant, "drift_applied": applied, "adjusted_forecast": adj,
                     "deadline": deadline, "float_days": flt, "status": status, "notice": notice})
    return rows


def _late_interval(m: dict, as_of: date, projected: bool):
    """Days (start, end] during which a milestone is past its approved date and unmet."""
    start = parse_date(m["approved_date"])
    when = parse_date(m["forecast_or_actual_date"])
    if m["status"] == "Completed":
        end = when
    else:
        end = max(when, as_of) if projected else as_of
    return (start, end) if end > start else None


def _union_days(intervals) -> int:
    total, cur_s, cur_e = 0, None, None
    for s, e in sorted(i for i in intervals if i):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).days
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += (cur_e - cur_s).days
    return total


def milestone_rows(f: dict, params: dict) -> list[dict]:
    as_of = parse_date(f["as_of"])
    lead = pval(params, "adjustment_request_lead_days")
    rows = []
    for m in f["milestones"]:
        acc = _late_interval(m, as_of, projected=False)
        proj = _late_interval(m, as_of, projected=True)
        approved = parse_date(m["approved_date"])
        when = parse_date(m["forecast_or_actual_date"])
        rows.append({**m, "slip_days": max(0, (when - approved).days),
                     "accrued_late_days": (acc[1] - acc[0]).days if acc else 0,
                     "projected_late_days": (proj[1] - proj[0]).days if proj else 0,
                     "adjustment_request_due": approved - timedelta(days=lead),
                     "_acc": acc, "_proj": proj})
    return rows


def fine_exposure(rows: list[dict], params: dict) -> dict:
    """$ per calendar day while a critical milestone is unmet.

    PIN 80 applies the fine per facility, so the main figure counts each late
    calendar day once (union of late periods). The longest single period and
    the stacked sum are reported as lower and upper bounds.
    """
    rate = pval(params, "milestone_fine_per_day")
    out = {"rate": rate}
    for key, col, iv in (("accrued", "accrued_late_days", "_acc"), ("projected", "projected_late_days", "_proj")):
        crit = [r for r in rows if yes(r["critical"])]
        days = [r[col] for r in crit]
        union = _union_days([r[iv] for r in crit])
        out[key] = {"union_days": union, "max_days": max(days, default=0), "sum_days": sum(days),
                    "per_facility": union * rate, "low": max(days, default=0) * rate, "high": sum(days) * rate}
    return out


def plan_findings(f: dict, params: dict, brows: list[dict], mrows: list[dict]) -> list[Finding]:
    out: list[Finding] = []
    as_of = parse_date(f["as_of"])
    by_bldg: dict[str, list] = {}
    for m in mrows:
        by_bldg.setdefault(m["building"], []).append(m)
        if m["type"] not in MILESTONE_TYPES:
            out.append(Finding("S2", "error", m["id"], f"Milestone type {m['type']!r} is not on the PIN 80 list."))
        if m["status"] not in MILESTONE_STATUSES:
            out.append(Finding("S2", "error", m["id"], f"Status {m['status']!r} is not on the PIN 80 list."))
    cap = pval(params, "max_milestones_per_building")
    for b in brows:
        n = len(by_bldg.get(b["building_nbr"], []))
        if not b["compliant"] and n == 0:
            out.append(Finding("S3", "error", b["building_nbr"], "Noncompliant building has no milestone (PIN 80 requires at least one)."))
        if n > cap:
            out.append(Finding("S3", "error", b["building_nbr"], f"{n} milestones; PIN 80 allows at most {cap} per building."))
        if b["method"] not in COMPLIANCE_METHODS:
            out.append(Finding("S2", "error", b["building_nbr"], f"Compliance method {b['method']!r} is not on the PIN 80 list."))
        if b["status"] == "Past deadline":
            out.append(Finding("S4", "error", b["building_nbr"],
                               f"{b['name']}: forecast compliance {b['adjusted_forecast']} is {-b['float_days']} days after the {b['deadline']} deadline."))
        elif b["status"] == "Tight":
            out.append(Finding("S4", "warn", b["building_nbr"],
                               f"{b['name']}: {b['float_days']} days of float to the {b['deadline']} deadline."))
        elif b["status"] == "No forecast date":
            out.append(Finding("S4", "error", b["building_nbr"], f"{b['name']}: no forecast compliance date."))
    need = pval(params, "critical_milestones_per_facility")
    ncrit = sum(1 for m in mrows if yes(m["critical"]))
    if ncrit != need:
        out.append(Finding("S5", "warn", "Facility", f"{ncrit} critical milestones; PIN 80 calls for {need} per facility."))
    months = pval(params, "milestone_status_update_months")
    last = parse_date(f.get("milestone_status_last_updated"))
    if last is None or (as_of - last).days > 365 * months // 12:
        out.append(Finding("S6", "warn", "Facility", f"Milestone status last updated {last}; PIN 80 requires an update at least once a year."))
    late_now = [m for m in mrows if m["status"] != "Completed" and m["accrued_late_days"] > 0]
    for m in mrows:
        if m["slip_days"] > 0:
            crit = " critical" if yes(m["critical"]) else ""
            out.append(Finding("S7", "error" if yes(m["critical"]) else "warn", m["id"],
                               f"{m['building']} {m['type']} ({m['description']}):{crit} milestone runs {m['slip_days']} days past its approved date of {m['approved_date']}."))
        if m["status"] != "Completed" and m["slip_days"] > 0 and as_of <= m["adjustment_request_due"]:
            out.append(Finding("S8", "info", m["id"],
                               f"A schedule adjustment request for this milestone is due by {m['adjustment_request_due']}."))
        elif m["status"] != "Completed" and m["slip_days"] > 0 and m["accrued_late_days"] == 0:
            out.append(Finding("S8", "warn", m["id"],
                               f"The {m['adjustment_request_due']} date for requesting a schedule adjustment has passed."))
    if late_now:
        out.append(Finding("S9", "error", "Facility",
                           f"{len(late_now)} approved milestone(s) are unmet and overdue. Under § 130065.1(i) no building permit issues "
                           "for the facility except seismic compliance, maintenance, and emergency repair work until they are met."))
    if f.get("approved_delay_date") and not eligibility_screen(f, params)["passes_screen"]:
        out.append(Finding("S10", "warn", "Facility", "A delay date is recorded but the recorded facts do not pass the § 130065.1 screen."))
    return out


HCAI_COLUMNS = ["County Code", "Perm ID", "Facility Name", "City", "Building Nbr", "Building Name",
                "Building Status", "SPC Rating *", "Building URL", "Height (ft)", "Stories",
                "Building Code", "Building Code Year", "Year Completed", "AB 1882 Notice",
                "Latitude", "Longitude", "Count"]


def hcai_crosscheck(f: dict, csv_path: Path) -> list[Finding]:
    """Compare the campus file with a CalHHS 'Hospital Building Data' CSV export."""
    out = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in ("Perm ID", "Building Nbr", "SPC Rating *") if c not in reader.fieldnames]
        if missing:
            return [Finding("H0", "error", "HCAI export", f"Export is missing column(s): {missing}.")]
        rows = [r for r in reader if str(r["Perm ID"]).strip() == str(f["perm_id"])]
    ours = {b["building_nbr"]: b for b in f["buildings"]}
    theirs = {r["Building Nbr"]: r for r in rows}
    for nbr, r in theirs.items():
        if nbr not in ours:
            if "In Service" in r.get("Building Status", ""):
                out.append(Finding("H1", "warn", nbr, f"{r['Building Name']} is in the HCAI export (SPC {r['SPC Rating *']}) but not in the campus plan."))
        elif str(ours[nbr]["spc"]) != r["SPC Rating *"].strip():
            out.append(Finding("H2", "error", nbr, f"SPC rating is {ours[nbr]['spc']} in the campus plan and {r['SPC Rating *']} in the HCAI export."))
    for nbr in ours:
        if nbr not in theirs:
            out.append(Finding("H3", "warn", nbr, "Building is in the campus plan but not in the HCAI export."))
    return out
