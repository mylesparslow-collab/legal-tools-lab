"""Buy America / BABA bill-of-materials audit engine.

Deterministic. No network, no model calls. Every threshold comes from
rules.json, which records the source and verification status of each number.

This is a personal portfolio demo that runs on synthetic data. It is not legal
advice and its output is a worksheet for a qualified reviewer, not a
compliance determination.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.json")

PASS, FAIL, REVIEW, NA = "PASS", "FAIL", "REVIEW", "N/A"
US = "US"
CATEGORIES = (
    "rolling_stock", "iron_steel", "manufactured_product",
    "construction_material", "section_70917c", "unclassified",
)
STAGES = ("pre_award", "contract_signed", "delivered", "title_transferred")


# ---------------------------------------------------------------- rules ----
class Rules:
    def __init__(self, path: Path | str = RULES_PATH):
        raw = json.loads(Path(path).read_text())
        self.entries = {r["id"]: r for r in raw["rules"]}

    def value(self, rule_id: str):
        return self.entries[rule_id]["value"]

    def cite(self, rule_id: str) -> str:
        return self.entries[rule_id]["source"]

    def rolling_stock_pct(self, fiscal_year: int) -> int:
        for band in self.value("rs_domestic_content_by_fy"):
            hi = band["fy_to"] if band["fy_to"] is not None else 9999
            if band["fy_from"] <= fiscal_year <= hi:
                return band["pct"]
        raise ValueError(
            f"No rolling stock threshold on file for FY{fiscal_year}. "
            "The statute's schedule starts at FY2016."
        )


def federal_fiscal_year(d: dt.date) -> int:
    """Federal fiscal year runs Oct. 1 to Sept. 30 and is named for the year it ends."""
    return d.year + 1 if d.month >= 10 else d.year


# ----------------------------------------------------------------- data ----
def _yes(v) -> bool:
    return str(v or "").strip().upper() in ("Y", "YES", "TRUE", "1")


def _money(v) -> float:
    s = str(v or "").replace(",", "").replace("$", "").strip()
    return float(s) if s else 0.0


@dataclass
class Line:
    project_id: str
    line_id: str
    parent_id: str
    tier: str                 # end_product | component | subcomponent
    category: str = ""        # end products only
    description: str = ""
    supplier: str = ""
    cost: float = 0.0
    mfg_country: str = ""
    all_processes_us: str = ""   # Y / N / blank (unknown)
    material_type: str = ""
    tariff_exempt_reexport: bool = False
    raw_material: bool = False
    waiver_ref: str = ""
    frame_or_shell: bool = False
    us_steel_iron_cost: float = 0.0
    cert_on_file: bool = False
    gwp: float | None = None
    epd_on_file: bool = False
    children: list["Line"] = field(default_factory=list)

    @property
    def us_made(self) -> bool:
        return self.mfg_country.strip().upper() == US

    @property
    def waived(self) -> bool:
        return bool(self.waiver_ref.strip())


def load_bom(path: Path | str) -> dict[str, list[Line]]:
    """Read bom.csv. Returns {project_id: [end product lines with children attached]}."""
    lines: list[Line] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            gwp = row.get("gwp", "").strip()
            lines.append(Line(
                project_id=row["project_id"].strip(),
                line_id=row["line_id"].strip(),
                parent_id=row.get("parent_id", "").strip(),
                tier=row["tier"].strip(),
                category=row.get("category", "").strip(),
                description=row.get("description", "").strip(),
                supplier=row.get("supplier", "").strip(),
                cost=_money(row.get("cost_usd")),
                mfg_country=row.get("mfg_country", "").strip().upper(),
                all_processes_us=row.get("all_processes_us", "").strip().upper(),
                material_type=row.get("material_type", "").strip(),
                tariff_exempt_reexport=_yes(row.get("tariff_exempt_reexport")),
                raw_material=_yes(row.get("raw_material")),
                waiver_ref=row.get("waiver_ref", "").strip(),
                frame_or_shell=_yes(row.get("frame_or_shell")),
                us_steel_iron_cost=_money(row.get("us_steel_iron_cost")),
                cert_on_file=_yes(row.get("cert_on_file")),
                gwp=float(gwp) if gwp else None,
                epd_on_file=_yes(row.get("epd_on_file")),
            ))
    by_id: dict[tuple[str, str], Line] = {}
    for ln in lines:
        key = (ln.project_id, ln.line_id)
        if key in by_id:
            raise ValueError(f"Duplicate line_id {ln.line_id} in project {ln.project_id}")
        by_id[key] = ln
    out: dict[str, list[Line]] = {}
    expected_parent = {"component": "end_product", "subcomponent": "component"}
    for ln in lines:
        if ln.tier == "end_product":
            if ln.category not in CATEGORIES:
                raise ValueError(f"{ln.line_id}: unknown category '{ln.category}'")
            out.setdefault(ln.project_id, []).append(ln)
            continue
        if ln.tier not in expected_parent:
            raise ValueError(f"{ln.line_id}: unknown tier '{ln.tier}'")
        parent = by_id.get((ln.project_id, ln.parent_id))
        if parent is None or parent.tier != expected_parent[ln.tier]:
            raise ValueError(
                f"{ln.line_id}: a {ln.tier} must sit under a {expected_parent[ln.tier]}"
            )
        parent.children.append(ln)
    return out


# -------------------------------------------------------- rolling stock ----
def _sub_counts_domestic(sub: Line) -> bool:
    """661.11(h): a subcomponent is domestic if manufactured in the US.
    661.7(f): a waived subcomponent is treated as domestic."""
    return sub.waived or sub.us_made


def audit_component(comp: Line, pct: int, frame_credit_allowed: bool, rules: Rules) -> dict:
    """Domestic cost a single rolling stock component contributes (49 CFR 661.11)."""
    subs = comp.children
    sub_total = sum(s.cost for s in subs)
    sub_domestic = sum(s.cost for s in subs if _sub_counts_domestic(s))
    sub_reexport = sum(
        s.cost for s in subs
        if s.us_made and s.tariff_exempt_reexport and not s.raw_material
    )
    share = (sub_domestic / sub_total * 100) if sub_total else None
    flags: list[str] = []

    if sub_total - comp.cost > 0.005:
        flags.append("Subcomponent costs add up to more than the component cost. Check the cost build-up.")

    if comp.waived:
        counted, basis = comp.cost, f"Waiver on file ({comp.waiver_ref}); treated as domestic. 49 CFR 661.7(f)"
        flags.append("Confirm the waiver covers this item and this procurement.")
    elif comp.us_made:
        if not subs:
            counted = comp.cost
            basis = "US-manufactured; no subcomponent breakdown supplied, so the subcomponent test was not run"
            flags.append(
                "No subcomponents listed. 49 CFR 661.11(g) needs the subcomponent share, and "
                "663.25(b)(1) expects component and subcomponent origin and cost."
            )
        elif sub_domestic * 100 > pct * sub_total:
            counted = comp.cost
            basis = f"US-manufactured and {share:.1f}% domestic subcomponents (needs more than {pct}%); full cost counts. 49 CFR 661.11(g)"
        else:
            counted = sub_domestic + max(comp.cost - sub_total, 0.0)
            basis = (
                f"US-manufactured but only {share:.1f}% domestic subcomponents (needs more than {pct}%); "
                "domestic subcomponents plus component manufacturing cost count. 49 CFR 661.11(l)"
            )
    else:
        counted = sub_reexport
        if sub_reexport:
            basis = "Foreign-manufactured; only tariff-exempt re-exported US subcomponents count. 49 CFR 661.11(i)"
            flags.append("Confirm the 19 CFR 10.11-10.24 entry papers and the f.o.b. valuation under 661.11(o).")
        else:
            basis = "Foreign-manufactured; nothing counts. 49 CFR 661.11(g), (j)"
        if not comp.mfg_country:
            flags.append("Country of manufacture is blank. Treated as foreign.")
        lost = sum(s.cost for s in subs if s.us_made and not (s.tariff_exempt_reexport and not s.raw_material))
        if lost:
            flags.append(f"${lost:,.0f} of US-made subcomponents or raw materials do not count because they sit in a foreign component without the tariff exemption. 49 CFR 661.11(j), (k)")

    frame_credit = 0.0
    if comp.frame_or_shell and not comp.us_made and not comp.waived and comp.us_steel_iron_cost:
        if frame_credit_allowed:
            frame_credit = min(comp.us_steel_iron_cost, comp.cost)
            basis += f"; plus ${frame_credit:,.0f} of US steel or iron in a non-US frame or car shell. 49 U.S.C. 5323(j)(5)"
        else:
            flags.append("US steel in a foreign frame or shell is not counted because the average vehicle cost is not above the 5323(j)(5) floor.")

    if not comp.cert_on_file:
        flags.append("No supplier origin certification on file for this component.")

    return {
        "line_id": comp.line_id, "description": comp.description, "supplier": comp.supplier,
        "mfg_country": comp.mfg_country, "cost": comp.cost,
        "sub_total": sub_total, "sub_domestic": sub_domestic, "sub_reexport": sub_reexport,
        "sub_share_pct": share, "waived": comp.waived, "frame_credit": frame_credit,
        "counted": counted + frame_credit, "basis": basis, "flags": flags,
    }


def audit_rolling_stock(end: Line, project: dict, rules: Rules) -> dict:
    delivery = dt.date.fromisoformat(project["scheduled_delivery_date"])
    fy = federal_fiscal_year(delivery)
    pct = rules.rolling_stock_pct(fy)
    floor = rules.value("rs_frame_shell_steel_credit_min_avg_cost")
    avg_cost = float(project.get("average_vehicle_cost", 0) or 0)
    frame_ok = avg_cost > floor

    comps = [audit_component(c, pct, frame_ok, rules) for c in end.children]
    total = sum(c["cost"] for c in comps)
    domestic = sum(c["counted"] for c in comps)
    share = domestic / total * 100 if total else 0.0
    final_us = str(project.get("final_assembly_country", "")).strip().upper() == US

    flags: list[str] = []
    if not end.children:
        flags.append("No components listed.")
    if not final_us:
        flags.append("Final assembly is not in the United States. 49 U.S.C. 5323(j)(2)(C)(ii)")
    content_ok = domestic * 100 > pct * total
    if end.waived:
        status = REVIEW
        flags.append(f"Vehicle-level waiver cited ({end.waiver_ref}). Confirm the FTA waiver letter. 49 CFR 663.25(a)")
    else:
        status = PASS if (content_ok and final_us and end.children) else FAIL
    shortfall = max(0.0, pct / 100 * total - domestic)
    return {
        "line_id": end.line_id, "description": end.description, "category": "rolling_stock",
        "governing_test": f"More than {pct}% domestic component cost and US final assembly (FY{fy} delivery)",
        "cite": "49 U.S.C. 5323(j)(2)(C); 49 CFR 661.11; 81 FR 60278",
        "fiscal_year": fy, "threshold_pct": pct, "total_component_cost": total,
        "domestic_cost": domestic, "domestic_pct": share, "final_assembly_us": final_us,
        "shortfall_usd": shortfall if not content_ok else 0.0,
        "status": status, "components": comps, "flags": flags,
    }


# ------------------------------------------------------- infrastructure ----
def _mp_tests(end: Line, rules: Rules) -> dict:
    """Run both manufactured-product tests on the same bill of materials."""
    comps = end.children
    total = sum(c.cost for c in comps)
    domestic = sum(c.cost for c in comps if c.us_made or c.waived)
    share = domestic / total * 100 if total else None
    foreign = [c for c in comps if not (c.us_made or c.waived)]
    baba_pct = rules.value("baba_manufactured_product_pct")
    made_us = end.us_made
    fta = PASS if (made_us and comps and not foreign) else FAIL
    baba = PASS if (made_us and total and domestic * 100 > baba_pct * total) else FAIL
    if not comps:
        fta = baba = REVIEW
    return {
        "component_total": total, "component_domestic": domestic, "component_share_pct": share,
        "foreign_components": [{"line_id": c.line_id, "description": c.description,
                                "mfg_country": c.mfg_country, "cost": c.cost} for c in foreign],
        "fta_661_5d": fta, "baba_184": baba, "baba_threshold_pct": baba_pct,
    }


def audit_infrastructure_item(end: Line, project: dict, rules: Rules) -> dict:
    funding = project.get("funding", "FTA")
    flags: list[str] = []
    res = {"line_id": end.line_id, "description": end.description, "category": end.category,
           "supplier": end.supplier, "cost": end.cost, "mfg_country": end.mfg_country,
           "fta_661_5d": NA, "baba_184": NA}
    cat = end.category

    if end.waived:
        flags.append(f"Waiver cited ({end.waiver_ref}). Confirm it covers this item, this award and this date.")

    if cat == "iron_steel":
        ok = end.us_made and end.all_processes_us == "Y"
        unknown = end.all_processes_us == ""
        if funding == "FTA":
            res["governing_test"] = "All steel and iron manufacturing processes in the US (refinement of steel additives excepted)"
            res["cite"] = rules.cite("fta_steel_iron_all_processes_us")
        else:
            res["governing_test"] = "All manufacturing processes from initial melting through application of coatings in the US"
            res["cite"] = rules.cite("baba_iron_steel_standard")
        status = REVIEW if unknown else (PASS if ok else FAIL)
        if unknown:
            flags.append("Mill certification does not say where every process took place.")
    elif cat == "manufactured_product":
        t = _mp_tests(end, rules)
        res.update(t)
        if funding == "FTA":
            res["governing_test"] = "All manufacturing processes in the US and every component US-manufactured (100%)"
            res["cite"] = rules.cite("fta_manufactured_product_all_components_us")
            status = t["fta_661_5d"]
        else:
            res["governing_test"] = f"Manufactured in the US and more than {t['baba_threshold_pct']}% US component cost"
            res["cite"] = rules.cite("baba_manufactured_product_pct")
            status = t["baba_184"]
        if t["fta_661_5d"] != t["baba_184"] and REVIEW not in (t["fta_661_5d"], t["baba_184"]):
            flags.append(
                f"The two tests disagree on this item: FTA 661.5(d) {t['fta_661_5d']}, BABA 55% {t['baba_184']}. "
                "Which one governs depends on the funding source (2 CFR 184.2(a))."
            )
        if not end.children:
            flags.append("No component list supplied. Neither test can be run.")
    elif cat == "construction_material":
        standards = rules.value("baba_construction_materials")
        res["governing_test"] = "All manufacturing processes for the listed material in the US"
        res["cite"] = rules.cite("baba_construction_materials")
        if end.material_type not in standards:
            status = REVIEW
            flags.append(f"Material type '{end.material_type}' is not one of the eight listed in 2 CFR 184.3.")
        else:
            res["standard"] = standards[end.material_type]
            if end.all_processes_us == "":
                status = REVIEW
                flags.append("Supplier certification does not address the 184.6 process standard.")
            else:
                status = PASS if (end.us_made and end.all_processes_us == "Y") else FAIL
    elif cat == "section_70917c":
        status = REVIEW
        res["governing_test"] = "Cement, aggregates and binding agents are their own category under BABA"
        res["cite"] = rules.cite("baba_section_70917c_materials")
        flags.append("Not tested as a manufactured product or construction material under 2 CFR 184. Treatment under FTA's Part 661 was not modeled.")
    elif cat == "rolling_stock":
        raise ValueError("rolling stock goes through audit_rolling_stock")
    else:
        status = REVIEW
        res["governing_test"] = "Not classified"
        res["cite"] = "2 CFR 184.4(e); 49 CFR 661.3"
        flags.append("Item has no category. Classification (steel, manufactured product, construction material, or part of a larger end product) is a judgment call for counsel.")

    if end.waived and status == FAIL:
        status = REVIEW
    if not end.cert_on_file:
        flags.append("No supplier Buy America certification on file.")
    res["status"] = status
    res["flags"] = flags
    res["buy_clean"] = _buy_clean(end, project, rules)
    return res


def _buy_clean(end: Line, project: dict, rules: Rules) -> dict | None:
    scope = rules.value("ca_buy_clean_scope")
    if end.material_type not in scope["eligible_materials"]:
        return None
    authority = project.get("awarding_authority_type", "local_agency")
    if authority not in scope["awarding_authorities"]:
        return {"status": NA, "note": "Buy Clean California covers state agencies, UC and CSU. This awarding authority is not one of them. Pub. Contract Code 3501(a)"}
    if not end.epd_on_file:
        return {"status": FAIL, "note": "No facility-specific Environmental Product Declaration on file. Pub. Contract Code 3503(a), (c)"}
    limit = rules.value("ca_buy_clean_gwp_limits").get(end.material_type)
    if not limit:
        return {"status": REVIEW, "note": "EPD on file, but no DGS limit is loaded in rules.json for this material."}
    if end.gwp is None:
        return {"status": REVIEW, "note": "EPD on file, but its GWP figure was not entered."}
    ok = end.gwp <= limit["limit"]
    return {"status": PASS if ok else FAIL,
            "note": f"GWP {end.gwp:g} against limit {limit['limit']:g} {limit.get('unit', '')}. Pub. Contract Code 3503(b)"}


# ------------------------------------------------------------ documents ----
def audit_documents(project: dict, has_rolling_stock: bool, rules: Rules) -> list[dict]:
    """Certificates under 49 CFR 661.6 / 661.12 and audits under Part 663."""
    docs = project.get("documents", {})
    stage = project.get("stage", "pre_award")
    if stage not in STAGES:
        raise ValueError(f"Unknown stage '{stage}'")
    at = STAGES.index(stage)
    out: list[dict] = []

    def need(key, label, cite, due_stage, required=True, why=""):
        have = bool(docs.get(key))
        if not required:
            status, note = NA, why
        elif have:
            status, note = PASS, "On file"
        elif at >= STAGES.index(due_stage):
            status, note = FAIL, f"Missing. Was due before '{due_stage.replace('_', ' ')}'."
        else:
            status, note = REVIEW, f"Not yet on file. Due before '{due_stage.replace('_', ' ')}'."
        out.append({"document": label, "cite": cite, "status": status, "note": note})

    if not has_rolling_stock:
        need("bidder_buy_america_certificate", "Bidder's Buy America certificate (steel, iron, manufactured products)",
             "49 CFR 661.6, 661.13(b)", "contract_signed")
        return out

    need("bidder_buy_america_certificate", "Bidder's Buy America rolling stock certificate",
         "49 CFR 661.12, 661.13(b)", "contract_signed")
    if not project.get("revenue_service", True):
        out.append({"document": "Part 663 audits", "cite": "49 CFR 663.3", "status": NA,
                    "note": "Part 663 covers rolling stock that carries passengers in revenue service."})
        return out

    motor = project.get("vehicle_type") in ("bus", "van")
    need("pre_award_buy_america_certification", "Pre-award Buy America certification",
         "49 CFR 663.23(a), 663.25", "contract_signed")
    need("pre_award_purchaser_requirements_certification", "Pre-award purchaser's requirements certification",
         "49 CFR 663.23(b), 663.27", "contract_signed")
    need("fmvss_pre_award", "Manufacturer's FMVSS information (pre-award)",
         "49 CFR 663.41, 663.43", "contract_signed", required=motor,
         why="Subpart D does not apply to rolling stock that is not a motor vehicle. 49 CFR 663.43(b)")
    need("post_delivery_buy_america_certification", "Post-delivery Buy America certification",
         "49 CFR 663.33(a), 663.35", "title_transferred")
    need("post_delivery_purchaser_requirements_certification", "Post-delivery purchaser's requirements certification",
         "49 CFR 663.33(b), 663.37", "title_transferred")

    ex = rules.value("p663_resident_inspector_exceptions")
    n = int(project.get("vehicle_count", 0) or 0)
    vtype = project.get("vehicle_type", "")
    small_area = project.get("service_area") == "rural_or_small_urbanized"
    why = ""
    if vtype == "bus" and n <= ex["max_buses"]:
        why = f"{n} buses is within the {ex['max_buses']}-bus exception. 49 CFR 663.37(c)(1)"
    elif small_area and n <= ex["max_vehicles_rural_or_small_urbanized"]:
        why = f"{n} vehicles for a rural or small urbanized area. 49 CFR 663.37(c)(2)"
    elif vtype == "van" and project.get("unmodified_standard_production"):
        why = "Unmodified standard-production vans. 49 CFR 663.37(c)(3)"
    need("resident_inspector_report", "Resident inspector's report",
         "49 CFR 663.37(a)", "title_transferred", required=not why, why=why)
    need("fmvss_post_delivery", "Manufacturer's FMVSS information (post-delivery)",
         "49 CFR 663.41, 663.43", "title_transferred", required=motor,
         why="Subpart D does not apply to rolling stock that is not a motor vehicle. 49 CFR 663.43(b)")
    return out


# -------------------------------------------------------------- project ----
def _de_minimis(project: dict, items: list[dict], rules: Rules) -> dict | None:
    w = rules.value("dot_de_minimis_waiver")
    applicable = float(project.get("total_applicable_cost", 0) or 0)
    federal = float(project.get("federal_assistance", 0) or 0)
    noncompliant = sum(i.get("cost", 0) for i in items if i["status"] == FAIL)
    if not noncompliant:
        return None
    cap = min(w["max_noncompliant_usd"], applicable * w["max_noncompliant_pct_of_applicable_cost"] / 100)
    fits = (applicable > 0 and noncompliant <= cap) or (0 < federal < w["small_grant_federal_usd_below"])
    return {
        "noncompliant_total": noncompliant, "cap": cap, "within_limits": fits,
        "note": ("Information only. The size limits come from FTA's summary of DOT's Aug. 16, 2023 waiver. "
                 "The waiver's scope and current status were not checked, and no status above was changed because of it."),
    }


def audit_project(project: dict, end_products: list[Line], rules: Rules) -> dict:
    rs, infra = [], []
    for end in end_products:
        if end.category == "rolling_stock":
            rs.append(audit_rolling_stock(end, project, rules))
        else:
            infra.append(audit_infrastructure_item(end, project, rules))
    docs = audit_documents(project, bool(rs), rules)
    statuses = [r["status"] for r in rs + infra] + [d["status"] for d in docs]
    overall = FAIL if FAIL in statuses else (REVIEW if REVIEW in statuses else PASS)
    return {
        "project_id": project["project_id"], "name": project.get("name", ""),
        "funding": project.get("funding", "FTA"), "stage": project.get("stage", ""),
        "overall": overall, "rolling_stock": rs, "infrastructure": infra,
        "documents": docs, "de_minimis": _de_minimis(project, infra, rules),
    }


def run(case_path: Path | str, bom_path: Path | str, rules: Rules | None = None) -> dict:
    rules = rules or Rules()
    case = json.loads(Path(case_path).read_text())
    bom = load_bom(bom_path)
    known = {p["project_id"] for p in case["projects"]}
    orphans = set(bom) - known
    if orphans:
        raise ValueError(f"BOM lines for projects not in case file: {sorted(orphans)}")
    return {
        "agency": case.get("agency", ""),
        "synthetic": case.get("synthetic", False),
        "generated_on": dt.date.today().isoformat(),
        "projects": [audit_project(p, bom.get(p["project_id"], []), rules) for p in case["projects"]],
    }
