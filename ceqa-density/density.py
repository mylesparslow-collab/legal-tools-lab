"""Density bonus calculator: Gov. Code 65915 (incl. the AB 1287 additional bonus in subd. (v)),
with SB 4 (Gov. Code 65913.16) and AB 130 (Pub. Resources Code 21080.66) eligibility checklists.

Deterministic. Every legal number comes from legal_data.json. Fictional sample data only.
Not legal advice; built by a non-attorney as a portfolio demo.

Run: python3 density.py sample_data/site.json -o output/Density_Model.xlsx
"""
from __future__ import annotations
import argparse, json, math, sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGAL = json.loads((ROOT / "legal_data.json").read_text())
DB = LEGAL["density_bonus"]
TABLE_PATHS = ("LI", "VLI", "MOD_SALE", "STUDENT")
PATHS = TABLE_PATHS + ("SENIOR", "SPECIAL", "AFF100")
PATH_LABEL = {"LI": "Lower income (b)(1)(A)", "VLI": "Very low income (b)(1)(B)", "MOD_SALE": "Moderate income for-sale (b)(1)(D)",
              "STUDENT": "Lower income students (b)(1)(F)", "SENIOR": "Senior housing (b)(1)(C)",
              "SPECIAL": "Foster youth / disabled veterans / homeless (b)(1)(E)", "AFF100": "100% affordable (b)(1)(G)"}


def v(node):
    return node["value"]


def ceil_units(x: float) -> int:
    """Round up to the next whole number (65915(q)). The 6-decimal round removes float noise
    (0.1 * 30 is 3.0000000000000004 in floating point) and matches ROUNDUP(ROUND(x,6),0) in the workbook."""
    return int(math.ceil(round(x, 6)))


def lookup(table, pct):
    """Largest row at or below pct; 0 below the first row. Same as VLOOKUP(pct, table, 2, TRUE)
    on a table that starts with a 0 -> 0 row."""
    out = 0
    for p, val in table:
        if pct >= p:
            out = val
    return out


def calculate(inp: dict) -> dict:
    """inp keys: site_acres, zoning_density_du_ac, sb4_applies (bool), sb4_density_du_ac,
    base_path, base_affordable_units, aff100_moderate_units, add_path (NONE|VLI|MOD), add_units,
    near_major_transit (bool), share_0_1_br, share_2_3_br, share_4plus_br, avg_bedrooms_per_unit."""
    path = inp["base_path"]
    if path not in PATHS:
        raise ValueError(f"base_path must be one of {PATHS}")
    add_path = inp.get("add_path") or "NONE"
    if add_path not in ("NONE", "VLI", "MOD"):
        raise ValueError("add_path must be NONE, VLI or MOD")
    sb4 = bool(inp.get("sb4_applies"))
    flags = []
    density = max(inp["zoning_density_du_ac"], inp.get("sb4_density_du_ac", 0)) if sb4 else inp["zoning_density_du_ac"]
    base = ceil_units(inp["site_acres"] * density)
    if base < 1:
        raise ValueError("site area times density gives no base units")
    aff = int(inp.get("base_affordable_units", 0))
    mod100 = int(inp.get("aff100_moderate_units", 0))
    add_units = int(inp.get("add_units", 0)) if add_path != "NONE" else 0
    pct = aff * 100 // base  # whole percent actually provided (floor)
    if sb4 and path != "AFF100":
        flags.append("SB 4 requires a 100% affordable project (65913.16(c)(9)); set base_path to AFF100.")

    bonus_pct = 0.0
    if path in TABLE_PATHS:
        bonus_pct = lookup(v(DB["tables"][path]), pct)
        bonus = ceil_units(base * bonus_pct / 100)
    elif path == "SENIOR":
        bonus_pct = v(DB["flat"]["SENIOR_pct_of_senior_units"])
        bonus = ceil_units(base * bonus_pct / 100)
    elif path == "SPECIAL":
        ok = pct >= v(DB["flat"]["SPECIAL_min_pct"])
        bonus_pct = v(DB["flat"]["SPECIAL_pct_of_qualifying_units"]) if ok else 0.0
        bonus = ceil_units(aff * bonus_pct / 100)
    else:  # AFF100
        ok = mod100 * 100 <= v(DB["flat"]["AFF100_max_moderate_pct"]) * base
        bonus_pct = v(DB["flat"]["AFF100_pct_of_lower_income_units"]) if ok else 0.0
        bonus = ceil_units((base - mod100) * bonus_pct / 100)
        if not ok:
            flags.append("More than 20% moderate income units: not a (b)(1)(G) project.")
        if inp.get("near_major_transit"):
            flags.append("Within 1/2 mile of a major transit stop: no maximum density applies (65915(f)(3)(D)(ii)). "
                         "The unit count shown is the 80% bonus only; the real ceiling is set by height and other standards.")
    if path in TABLE_PATHS and bonus_pct == 0:
        flags.append(f"{pct}% is below the minimum for this category; no bonus.")

    # AB 1287 additional bonus, 65915(v)
    gate = DB["additional_bonus_gate"]
    add_pct_units = add_units * 100 // base
    restricted = aff + add_units
    add_bonus_pct, add_reason = 0.0, ""
    if add_path != "NONE":
        if path not in ("LI", "VLI", "MOD_SALE"):
            add_reason = "Additional bonus is only for (b)(1)(A), (B) or (D) projects (65915(v)(1))."
        elif pct < v(gate[path]):
            add_reason = f"Base project must first provide {v(gate[path])}% in its category; it provides {pct}%."
        elif restricted * 100 > v(gate["max_restricted_pct_of_total_units"]) * base:
            add_reason = (f"{restricted} restricted units is more than 50% of {base} total units; "
                          "no additional bonus (65915(v)(1)).")
        else:
            add_bonus_pct = lookup(v(DB["tables"]["ADD_" + add_path]), add_pct_units)
            if add_bonus_pct == 0:
                add_reason = f"Additional units are {add_pct_units}% of total units; the table starts at 5%."
        if add_reason:
            flags.append(add_reason)
    add_bonus = ceil_units(base * add_bonus_pct / 100)
    total = base + bonus + add_bonus

    concessions = lookup(v(DB["concessions"]).get(path, []), pct) if path != "AFF100" else 5
    if path == "AFF100" and bonus_pct == 0:
        concessions = 0

    # parking maximum a city may require, 65915(p)
    pk = DB["parking"]
    s01, s23, s4 = inp.get("share_0_1_br", 1.0), inp.get("share_2_3_br", 0.0), inp.get("share_4plus_br", 0.0)
    blended = s01 * v(pk["per_unit_0_1_br"]) + s23 * v(pk["per_unit_2_3_br"]) + s4 * v(pk["per_unit_4plus_br"])
    transit = bool(inp.get("near_major_transit"))
    tmin = v(pk["transit_min_pct"])
    if path == "AFF100" and transit and bonus_pct > 0:
        ratio, basis = v(pk["aff100_transit"]), pk["aff100_transit"]["cite"]
    elif transit and path in tmin and pct >= tmin[path]:
        ratio, basis = v(pk["transit_per_unit"]), pk["transit_per_unit"]["cite"]
    elif transit and path == "MOD_SALE" and pct >= v(pk["transit_mod_min_pct"]):
        ratio = v(pk["transit_mod_per_bedroom"]) * inp.get("avg_bedrooms_per_unit", 1.0)
        basis = pk["transit_mod_per_bedroom"]["cite"] + " (0.5 per bedroom)"
    else:
        ratio, basis = blended, pk["per_unit_0_1_br"]["cite"]
    if sb4:
        sb4_ratio = 0.0 if transit else v(LEGAL["sb4"]["parking_max_per_unit"])
        if sb4_ratio < ratio:
            ratio, basis = sb4_ratio, LEGAL["sb4"]["parking_max_per_unit"]["cite"] + ", (k)(2)"
    parking = ceil_units(total * ratio)

    return {"density_used": density, "base_units": base, "base_affordable_pct": pct, "bonus_pct": bonus_pct,
            "bonus_units": bonus, "add_units_pct": add_pct_units, "restricted_units": restricted,
            "add_bonus_pct": add_bonus_pct, "add_bonus_units": add_bonus, "total_units": total,
            "total_bonus_pct_of_base": int((total - base) * 10000 / base + 0.5) / 100, "concessions": concessions,
            "parking_ratio": round(ratio, 6), "parking_basis": basis, "max_required_parking": parking, "flags": flags}


def units_needed(base_units: int, pct: int) -> int:
    """Smallest whole number of units that is at least pct percent of base_units."""
    return -(-base_units * pct // 100)


def scenario_grid(inp: dict) -> list[dict]:
    """Every base tier, alone and with every additional-bonus tier the 50% cap allows."""
    out = []
    base = calculate(dict(inp, base_path="LI", base_affordable_units=0, add_path="NONE"))["base_units"]
    for path in ("VLI", "LI", "MOD_SALE"):
        for pct, _ in v(DB["tables"][path]):
            n = units_needed(base, pct)
            combos = [("NONE", 0)]
            if pct >= v(DB["additional_bonus_gate"][path]):
                combos += [(ap, apct) for ap in ("VLI", "MOD") for apct, _ in v(DB["tables"]["ADD_" + ap])]
            for ap, apct in combos:
                na = units_needed(base, apct) if ap != "NONE" else 0
                r = calculate(dict(inp, base_path=path, base_affordable_units=n, add_path=ap, add_units=na))
                if ap != "NONE" and r["add_bonus_pct"] == 0:
                    continue
                out.append({"base_path": path, "base_pct": pct, "base_aff_units": n, "add_path": ap, "add_pct": apct,
                            "add_units": na, **{k: r[k] for k in ("base_units", "bonus_units", "add_bonus_units",
                                                                    "total_units", "total_bonus_pct_of_base", "concessions")}})
    return out


# ---------------------------------------------------------------- eligibility checklists
def _chk(cid, label, ok, cite, detail=""):
    return {"id": cid, "check": label, "result": "PASS" if ok is True else "FAIL" if ok is False else "NEEDS REVIEW",
            "cite": cite, "detail": detail}


def sb4_gate(site: dict) -> list[dict]:
    L, s = LEGAL["sb4"], site
    cut = date.fromisoformat(v(L["ownership_cutoff"]))
    acq = date.fromisoformat(s["owner_acquired"])
    out = [
        _chk("owner_type", "Owner is a religious institution or independent institution of higher education",
             s["owner_type"] in ("religious_institution", "independent_higher_ed"), "Gov. Code 65913.16(b)(6), (b)(10), (c)(1)", s["owner_type"]),
        _chk("owned_by", f"Land owned on or before {cut:%b %d, %Y}".replace(" 0", " "), acq <= cut, L["ownership_cutoff"]["cite"], f"acquired {acq}"),
        _chk("lower_income", "100% of units (excluding manager units) for lower income households", s["pct_lower_or_below"] + s["pct_moderate"] + s["pct_staff"] >= 100,
             "Gov. Code 65913.16(c)(9)"),
        _chk("moderate_cap", f"Moderate income units at most {v(L['max_moderate_pct'])}%", s["pct_moderate"] <= v(L["max_moderate_pct"]), L["max_moderate_pct"]["cite"], f"{s['pct_moderate']}%"),
        _chk("staff_cap", f"Staff units at most {v(L['max_staff_pct'])}%", s["pct_staff"] <= v(L["max_staff_pct"]), L["max_staff_pct"]["cite"], f"{s['pct_staff']}%"),
        _chk("light_industrial", "Does not adjoin a site with more than one-third light industrial use", not s["adjoins_light_industrial"], L["light_industrial_adjoining_share"]["cite"]),
        _chk("heavy_industrial", f"At least {v(L['heavy_industrial_ft']):,} ft from heavy industrial use", s["ft_to_heavy_industrial"] >= v(L["heavy_industrial_ft"]), L["heavy_industrial_ft"]["cite"], f"{s['ft_to_heavy_industrial']:,} ft"),
        _chk("title_v", f"At least {v(L['title_v_ft']):,} ft from a Title V industrial use", s["ft_to_title_v"] >= v(L["title_v_ft"]), L["title_v_ft"]["cite"], f"{s['ft_to_title_v']:,} ft"),
        _chk("oil_gas", f"At least {v(L['oil_gas_ft']):,} ft from oil or gas extraction or refining (where multifamily is not already permitted)",
             s["multifamily_permitted"] or s["ft_to_oil_gas"] >= v(L["oil_gas_ft"]), L["oil_gas_ft"]["cite"], f"{s['ft_to_oil_gas']:,} ft"),
        _chk("sunset", f"Statute still in effect (repealed {v(L['sunset'])})", date.fromisoformat(s["as_of"]) < date.fromisoformat(v(L["sunset"])), L["sunset"]["cite"]),
        _chk("site_criteria", "Site criteria cross-referenced from Gov. Code 65913.4(a)(2), (a)(6)(B)-(K), (a)(7)", None,
             "Gov. Code 65913.16(c)(2)-(4)", "cross-referenced text was not read; attorney to confirm"),
    ]
    return out


def sb4_density(site: dict) -> tuple[float, str]:
    L = LEGAL["sb4"]
    if site["zone_allows_residential"]:
        d = v(L["default_density_du_ac"])[site["jurisdiction_type"]]
        return d, f"{L['residential_zone_density']['cite']} ({site['jurisdiction_type']}: {d} du/ac, UNVERIFIED figure)"
    return v(L["nonresidential_zone_du_ac"]), L["nonresidential_zone_du_ac"]["cite"]


def ab130_gate(site: dict) -> list[dict]:
    L, s = LEGAL["ab130"], site
    cap = v(L["max_acres_builders_remedy"]) if s["builders_remedy"] else v(L["max_acres"])
    urban = (s["previously_urban_use"] or s["perimeter_urban_pct"] >= v(L["perimeter_urban_pct"])
             or s["quarter_mile_urban_pct"] >= v(L["quarter_mile_urban_pct"]))
    floor = v(L["min_density_fraction"]) * v(LEGAL["sb4"]["default_density_du_ac"])[s["jurisdiction_type"]]
    return [
        _chk("acres", f"Site not more than {cap} acres" + (" (builder's remedy)" if s["builders_remedy"] else ""), s["site_acres"] <= cap,
             L["max_acres_builders_remedy" if s["builders_remedy"] else "max_acres"]["cite"], f"{s['site_acres']} acres"),
        _chk("location", "In an incorporated city or a Census urban area", s["in_city_or_urban_area"], "Pub. Resources Code 21080.66(a)(2)"),
        _chk("urban_use", "Previously urban use, or 75% of perimeter / quarter-mile area urban", urban, "Pub. Resources Code 21080.66(a)(3)",
             f"perimeter {s['perimeter_urban_pct']}%, quarter mile {s['quarter_mile_urban_pct']}%"),
        _chk("consistency", "Consistent with general plan and zoning (density bonus does not count against it)", s["consistent_with_plan_zoning"], "Pub. Resources Code 21080.66(a)(4)"),
        _chk("min_density", f"Density at least half the Gov. Code 65583.2(c)(3)(B) density ({floor:g} du/ac here; base figure UNVERIFIED)",
             s["proposed_density_du_ac"] >= floor, L["min_density_fraction"]["cite"], f"{s['proposed_density_du_ac']} du/ac"),
        _chk("excluded_sites", "Meets Gov. Code 65913.4(a)(6) site exclusions", None, "Pub. Resources Code 21080.66(a)(6)", "cross-referenced text was not read; attorney to confirm"),
        _chk("historic", "No demolition of a listed historic structure", not s["demolishes_historic"], "Pub. Resources Code 21080.66(a)(7)"),
        _chk("lodging", "No hotel, motel or other transient lodging", not s["includes_transient_lodging"], "Pub. Resources Code 21080.66(a)(8)"),
    ]


def tribal_clock(application_complete: str, tribe_accepted: str | None = None, extension: bool = False) -> list[dict]:
    """Outside dates for the AB 130 tribal consultation steps. Calendar days, no weekend adjustment."""
    L = LEGAL["ab130"]
    d0 = date.fromisoformat(application_complete)
    notice = d0 + timedelta(days=v(L["tribal_notice_days"]))
    rows = [{"step": "Application deemed complete", "date": d0, "cite": ""},
            {"step": "Send notice to affiliated tribes by", "date": notice, "cite": L["tribal_notice_days"]["cite"]},
            {"step": "Tribe response window ends (if notice sent on the last day)", "date": notice + timedelta(days=v(L["tribal_response_days"])), "cite": L["tribal_response_days"]["cite"]}]
    if tribe_accepted:
        acc = date.fromisoformat(tribe_accepted)
        start = acc + timedelta(days=v(L["consult_start_days"]))
        end = start + timedelta(days=v(L["consult_conclude_days"]) + (v(L["consult_extension_days"]) if extension else 0))
        rows += [{"step": "Tribe accepted consultation", "date": acc, "cite": ""},
                 {"step": "Begin consultation by", "date": start, "cite": L["consult_start_days"]["cite"]},
                 {"step": "Conclude consultation by (if begun on the last day" + (", with 15-day extension)" if extension else ")"), "date": end, "cite": L["consult_conclude_days"]["cite"]}]
    return rows


# ---------------------------------------------------------------- workbook
def write_workbook(site: dict, out: Path) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation

    inp = dict(site["calc"])
    if inp.get("sb4_applies"):
        inp["sb4_density_du_ac"], sb4_basis = sb4_density(site["site"])
    else:
        inp.setdefault("sb4_density_du_ac", 0); sb4_basis = ""
    res = calculate(inp)
    wb = Workbook()
    bold, head = Font(bold=True), PatternFill("solid", fgColor="DDE3EA")
    inputfill = PatternFill("solid", fgColor="FFF7D6")

    def header(ws, row, cols):
        for i, c in enumerate(cols, 1):
            cell = ws.cell(row=row, column=i, value=c); cell.font = bold; cell.fill = head

    # --- Tables (legal numbers; formulas read from here)
    wt = wb.active; wt.title = "Tables"
    wt["A1"] = "Legal numbers used by the Calc tab. Source and status for each table are on the Sources tab."; wt["A1"].font = bold
    ranges, col = {}, 1
    tabs = {k: v(DB["tables"][k]) for k in DB["tables"]}
    for k, rows in v(DB["concessions"]).items():
        if rows and k != "AFF100":
            tabs["CON_" + k] = rows
    for name, rows in tabs.items():
        wt.cell(row=3, column=col, value=name).font = bold
        wt.cell(row=4, column=col, value="min %"); wt.cell(row=4, column=col + 1, value="value")
        full = [[0, 0]] + rows
        for i, (p, val) in enumerate(full):
            wt.cell(row=5 + i, column=col, value=p); wt.cell(row=5 + i, column=col + 1, value=val)
        a, b = wt.cell(row=5, column=col).column_letter, wt.cell(row=5, column=col + 1).column_letter
        ranges[name] = f"Tables!${a}$5:${b}${4 + len(full)}"
        col += 3
    consts = [("SENIOR_PCT", v(DB["flat"]["SENIOR_pct_of_senior_units"])), ("SPECIAL_PCT", v(DB["flat"]["SPECIAL_pct_of_qualifying_units"])),
              ("SPECIAL_MIN", v(DB["flat"]["SPECIAL_min_pct"])), ("AFF100_PCT", v(DB["flat"]["AFF100_pct_of_lower_income_units"])),
              ("AFF100_MAX_MOD", v(DB["flat"]["AFF100_max_moderate_pct"])), ("GATE_LI", v(DB["additional_bonus_gate"]["LI"])),
              ("GATE_VLI", v(DB["additional_bonus_gate"]["VLI"])), ("GATE_MOD_SALE", v(DB["additional_bonus_gate"]["MOD_SALE"])),
              ("MAX_RESTRICTED", v(DB["additional_bonus_gate"]["max_restricted_pct_of_total_units"])),
              ("PK_01", v(DB["parking"]["per_unit_0_1_br"])), ("PK_23", v(DB["parking"]["per_unit_2_3_br"])), ("PK_4", v(DB["parking"]["per_unit_4plus_br"])),
              ("PK_TRANSIT", v(DB["parking"]["transit_per_unit"])), ("PK_T_LI", v(DB["parking"]["transit_min_pct"])["LI"]),
              ("PK_T_VLI", v(DB["parking"]["transit_min_pct"])["VLI"]), ("PK_T_MOD", v(DB["parking"]["transit_mod_min_pct"])),
              ("PK_MOD_BR", v(DB["parking"]["transit_mod_per_bedroom"])), ("SB4_PK", v(LEGAL["sb4"]["parking_max_per_unit"]))]
    crow0 = 60
    wt.cell(row=crow0 - 1, column=1, value="Constants").font = bold
    C = {}
    for i, (k, val) in enumerate(consts):
        wt.cell(row=crow0 + i, column=1, value=k); wt.cell(row=crow0 + i, column=2, value=val)
        C[k] = f"Tables!$B${crow0 + i}"

    # --- Inputs
    wi = wb.create_sheet("Inputs", 0)
    wi["A1"] = f"Density inputs: {site['site']['name']} (fictional)"; wi["A1"].font = Font(bold=True, size=13)
    rows_in = [("Site area (acres)", inp["site_acres"], ""), ("Zoning / general plan base density (du/ac)", inp["zoning_density_du_ac"], "65915(o)(6): greatest density allowed"),
               ("SB 4 project? (YES/NO)", "YES" if inp.get("sb4_applies") else "NO", "Gov. Code 65913.16"),
               ("SB 4 density (du/ac)", inp["sb4_density_du_ac"], sb4_basis),
               ("Base bonus category", inp["base_path"], " | ".join(PATHS)),
               ("Affordable units in base category", inp.get("base_affordable_units", 0), "count, out of base units (bonus units excluded)"),
               ("Moderate units (100% affordable projects only)", inp.get("aff100_moderate_units", 0), "at most 20%"),
               ("Additional bonus category (AB 1287)", inp.get("add_path") or "NONE", "NONE | VLI | MOD"),
               ("Additional affordable units", inp.get("add_units", 0), "count"),
               ("Within 1/2 mile of major transit stop? (YES/NO)", "YES" if inp.get("near_major_transit") else "NO", "unobstructed access"),
               ("Share of units with 0-1 bedrooms", inp.get("share_0_1_br", 1.0), ""), ("Share of units with 2-3 bedrooms", inp.get("share_2_3_br", 0.0), ""),
               ("Share of units with 4+ bedrooms", inp.get("share_4plus_br", 0.0), ""), ("Average bedrooms per unit", inp.get("avg_bedrooms_per_unit", 1.0), "used only for the moderate for-sale transit ratio")]
    header(wi, 2, ["Input", "Value", "Note"])
    for i, (a, b, c) in enumerate(rows_in, 3):
        wi.cell(row=i, column=1, value=a); cell = wi.cell(row=i, column=2, value=b); cell.fill = inputfill; wi.cell(row=i, column=3, value=c)
    for cellref, opts in (("B5", "YES,NO"), ("B7", ",".join(PATHS)), ("B10", "NONE,VLI,MOD"), ("B12", "YES,NO")):
        dv = DataValidation(type="list", formula1=f'"{opts}"', allow_blank=False); wi.add_data_validation(dv); dv.add(cellref)
    wi["A18"] = "Yellow cells are inputs. Change them and the Calc tab recalculates. Fictional data. Not legal advice."
    I = {k: f"Inputs!$B${r}" for k, r in zip(("acres", "zden", "sb4", "sb4den", "path", "aff", "mod100", "apath", "aunits", "transit", "s01", "s23", "s4", "avgbr"), range(3, 17))}

    # --- Calc (live formulas)
    wc = wb.create_sheet("Calc", 1)
    wc["A1"] = "Density bonus calculation (live formulas)"; wc["A1"].font = Font(bold=True, size=13)
    header(wc, 2, ["Step", "Result", "Rule"])
    R = {}
    def put(key, label, formula, rule):
        r = 3 + len(R); R[key] = f"$B${r}"
        wc.cell(row=r, column=1, value=label); wc.cell(row=r, column=2, value=formula); wc.cell(row=r, column=3, value=rule)
    up = lambda x: f"ROUNDUP(ROUND({x},6),0)"
    put("density", "Density used (du/ac)", f'=IF({I["sb4"]}="YES",MAX({I["zden"]},{I["sb4den"]}),{I["zden"]})', "65915(o)(6); SB 4: 65913.16(j)")
    put("base", "Base units", f'={up(I["acres"] + "*" + R["density"])}', "65915(q): round up")
    put("pct", "Affordable share of base units (whole %)", f'=INT({I["aff"]}*100/{R["base"]})', "65915(o)(9)(A): bonus units excluded")
    tl = lambda name, x: f"VLOOKUP({x},{ranges[name]},2,TRUE)"
    p = I["path"]
    put("bpct", "Base bonus %", f'=IF({p}="LI",{tl("LI", R["pct"])},IF({p}="VLI",{tl("VLI", R["pct"])},IF({p}="MOD_SALE",{tl("MOD_SALE", R["pct"])},'
        f'IF({p}="STUDENT",{tl("STUDENT", R["pct"])},IF({p}="SENIOR",{C["SENIOR_PCT"]},IF({p}="SPECIAL",IF({R["pct"]}>={C["SPECIAL_MIN"]},{C["SPECIAL_PCT"]},0),'
        f'IF({I["mod100"]}*100<={C["AFF100_MAX_MOD"]}*{R["base"]},{C["AFF100_PCT"]},0)))))))', "65915(f)(1)-(4)")
    put("bonus", "Base bonus units", f'=IF({p}="SPECIAL",{up(I["aff"] + "*" + R["bpct"] + "/100")},IF({p}="AFF100",{up("(" + R["base"] + "-" + I["mod100"] + ")*" + R["bpct"] + "/100")},{up(R["base"] + "*" + R["bpct"] + "/100")}))',
        "65915(f), (q)")
    ap = I["apath"]
    put("aunits", "Additional affordable units counted", f'=IF({ap}="NONE",0,{I["aunits"]})', "")
    put("apct", "Additional units share of base units (whole %)", f'=INT({R["aunits"]}*100/{R["base"]})', "65915(v)(4)")
    put("restricted", "Restricted units (base + additional)", f'={I["aff"]}+{R["aunits"]}', "")
    put("gate", "Additional bonus allowed?", f'=IF({ap}="NONE","n/a",IF(AND(OR(AND({p}="LI",{R["pct"]}>={C["GATE_LI"]}),AND({p}="VLI",{R["pct"]}>={C["GATE_VLI"]}),AND({p}="MOD_SALE",{R["pct"]}>={C["GATE_MOD_SALE"]})),'
        f'{R["restricted"]}*100<={C["MAX_RESTRICTED"]}*{R["base"]}),"YES","NO"))', "65915(v)(1): base at maximum tier; no more than 50% of total units restricted")
    put("abpct", "Additional bonus %", f'=IF({R["gate"]}="YES",IF({ap}="VLI",{tl("ADD_VLI", R["apct"])},{tl("ADD_MOD", R["apct"])}),0)', "65915(v)(2)")
    put("abonus", "Additional bonus units", f'={up(R["base"] + "*" + R["abpct"] + "/100")}', "65915(v)(4), (q)")
    put("total", "Total units", f'={R["base"]}+{R["bonus"]}+{R["abonus"]}', "")
    put("totpct", "Total bonus as % of base units", f'=ROUND(({R["total"]}-{R["base"]})*100/{R["base"]},2)', "")
    put("conc", "Incentives or concessions", f'=IF({p}="AFF100",IF({R["bpct"]}>0,5,0),IF({p}="LI",{tl("CON_LI", R["pct"])},IF({p}="VLI",{tl("CON_VLI", R["pct"])},IF({p}="MOD_SALE",{tl("CON_MOD_SALE", R["pct"])},IF({p}="STUDENT",{tl("CON_STUDENT", R["pct"])},0)))))',
        "65915(d)(2)")
    put("blend", "Parking: blended ratio by bedroom mix", f'={I["s01"]}*{C["PK_01"]}+{I["s23"]}*{C["PK_23"]}+{I["s4"]}*{C["PK_4"]}', "65915(p)(1)")
    t = f'{I["transit"]}="YES"'
    put("ratio0", "Parking: ratio under 65915(p)", f'=IF(AND({p}="AFF100",{t},{R["bpct"]}>0),0,IF(AND({t},OR(AND({p}="LI",{R["pct"]}>={C["PK_T_LI"]}),AND({p}="VLI",{R["pct"]}>={C["PK_T_VLI"]}))),{C["PK_TRANSIT"]},'
        f'IF(AND({t},{p}="MOD_SALE",{R["pct"]}>={C["PK_T_MOD"]}),{C["PK_MOD_BR"]}*{I["avgbr"]},{R["blend"]})))', "65915(p)(1)-(3)")
    put("ratio", "Parking: ratio after SB 4", f'=ROUND(IF({I["sb4"]}="YES",MIN({R["ratio0"]},IF({t},0,{C["SB4_PK"]})),{R["ratio0"]}),6)', "65913.16(k)")
    put("parking", "Most parking a city may require (spaces)", f'={up(R["total"] + "*" + R["ratio"])}', "65915(p)(4): round up")
    for r in range(3, 3 + len(R)):
        wc.cell(row=r, column=2).font = bold

    # --- Engine Check
    we = wb.create_sheet("Engine Check")
    header(we, 1, ["Item", "Workbook formula", "Python engine", "Match"])
    pairs = [("density", "density_used"), ("base", "base_units"), ("pct", "base_affordable_pct"), ("bpct", "bonus_pct"), ("bonus", "bonus_units"),
             ("abpct", "add_bonus_pct"), ("abonus", "add_bonus_units"), ("total", "total_units"), ("totpct", "total_bonus_pct_of_base"),
             ("conc", "concessions"), ("ratio", "parking_ratio"), ("parking", "max_required_parking")]
    for i, (k, rk) in enumerate(pairs, 2):
        we.cell(row=i, column=1, value=rk); we.cell(row=i, column=2, value=f"=Calc!{R[k]}"); we.cell(row=i, column=3, value=res[rk])
        we.cell(row=i, column=4, value=f'=IF(ABS(B{i}-C{i})<0.0001,"YES","NO")')
    n = len(pairs) + 2
    we.cell(row=n, column=1, value="All checks match?").font = bold
    we.cell(row=n, column=2, value=f'=IF(COUNTIF(D2:D{n - 1},"YES")={len(pairs)},"YES","NO")')
    we.cell(row=n + 1, column=1, value="The Python column is fixed at the values for the inputs this file was generated with. After you edit an input, a NO here is expected.")

    # --- Scenarios (engine output)
    wsn = wb.create_sheet("Scenarios")
    wsn["A1"] = "Every qualifying mixed-income combination at this site and density, computed by the Python engine (static values). Not SB 4 scenarios."; wsn["A1"].font = bold
    cols = ["base_path", "base_pct", "base_aff_units", "add_path", "add_pct", "add_units", "base_units", "bonus_units", "add_bonus_units", "total_units", "total_bonus_pct_of_base", "concessions"]
    header(wsn, 2, cols)
    grid = scenario_grid({**inp, "sb4_applies": False, "zoning_density_du_ac": res["density_used"]})
    for i, g in enumerate(grid, 3):
        for j, c in enumerate(cols, 1):
            wsn.cell(row=i, column=j, value=g[c])

    # --- Gates
    wg = wb.create_sheet("Eligibility")
    r = 1
    for title, checks in (("SB 4 checklist (Gov. Code 65913.16)", sb4_gate(site["site"])), ("AB 130 infill CEQA exemption checklist (Pub. Resources Code 21080.66)", ab130_gate(site["site"]))):
        wg.cell(row=r, column=1, value=title).font = Font(bold=True, size=12); r += 1
        header(wg, r, ["Check", "Result", "Cite", "Detail"]); r += 1
        for c in checks:
            for j, k in enumerate(("check", "result", "cite", "detail"), 1):
                wg.cell(row=r, column=j, value=c[k])
            r += 1
        r += 1
    wg.cell(row=r, column=1, value="AB 130 tribal consultation outside dates").font = Font(bold=True, size=12); r += 1
    header(wg, r, ["Step", "Date", "Cite"]); r += 1
    for row in tribal_clock(site["site"]["application_complete"], site["site"].get("tribe_accepted"), site["site"].get("tribal_extension", False)):
        wg.cell(row=r, column=1, value=row["step"]); wg.cell(row=r, column=2, value=row["date"]).number_format = "yyyy-mm-dd"; wg.cell(row=r, column=3, value=row["cite"]); r += 1
    wg.cell(row=r + 1, column=1, value="A checklist is a screening aid. NEEDS REVIEW items were not evaluated. Fictional site.")

    # --- Sources
    wsrc = wb.create_sheet("Sources")
    header(wsrc, 1, ["Item", "Value", "Cite", "Source read", "Status", "Read on", "Note"])
    r = 2
    def walk(prefix, node):
        nonlocal r
        if isinstance(node, dict) and "status" in node and "cite" in node:
            val = node["value"]
            for j, x in enumerate((prefix, json.dumps(val) if isinstance(val, (list, dict)) else val, node["cite"], node["source"], node["status"], node["read_on"], node["note"]), 1):
                wsrc.cell(row=r, column=j, value=x)
            if node["status"] == "unverified":
                for j in range(1, 8):
                    wsrc.cell(row=r, column=j).fill = PatternFill("solid", fgColor="FFE0E0")
            r += 1
        elif isinstance(node, dict):
            for k, x in node.items():
                if not k.startswith("_"):
                    walk(f"{prefix}.{k}" if prefix else k, x)
    walk("", {k: LEGAL[k] for k in ("density_bonus", "sb4", "ab130")})

    # --- Attorney Review
    wr = wb.create_sheet("Attorney Review")
    header(wr, 1, ["#", "Open question", "How the tool handles it now"])
    for i, (q, a) in enumerate(ATTORNEY_REVIEW, 2):
        wr.cell(row=i, column=1, value=i - 1); wr.cell(row=i, column=2, value=q); wr.cell(row=i, column=3, value=a)

    for ws in wb.worksheets:
        for colcells in ws.columns:
            w = max((len(str(c.value)) for c in colcells if c.value is not None and not str(c.value).startswith("=")), default=8)
            ws.column_dimensions[colcells[0].column_letter].width = min(max(10, w + 2), 70)
        for rowc in ws.iter_rows():
            for c in rowc:
                c.alignment = Alignment(vertical="top", wrap_text=ws.title in ("Attorney Review", "Sources", "Eligibility") and c.column > 1)
    wb.move_sheet("Tables", offset=len(wb.sheetnames))
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return res


ATTORNEY_REVIEW = [
    ("Does an SB 4 project stack with the AB 1287 additional bonus? SB 4 requires 100% affordable units; 65915(v)(1) bars the additional bonus when more than 50% of total units are restricted, and limits it to (b)(1)(A), (B), (D) projects.",
     "Treats SB 4 projects as 65915(b)(1)(G) projects: 80% bonus, 5 concessions, no additional (v) bonus."),
    ("For a 100% affordable project, which count of lower income units does the 80% bonus apply to?",
     "Base units minus moderate units. (b)(1)(G) counts 'total and bonus units', so the statute may support a larger number."),
    ("How is the 50% restricted-unit cap in 65915(v)(1) measured?", "Base-category units plus additional units, against base units (bonus units excluded per (o)(9)(A))."),
    ("A project that provides a fractional percentage (say 10.9% lower income): which table row applies?", "The whole percent actually reached (10%). Affordable unit counts are entered as whole units."),
    ("The (v)(2) additional-bonus table rows were not read from official text.", "Uses 5-10% very low -> 20-38.75% and 5-15% moderate -> 20-50%; end points match HCD's fact sheet."),
    ("Gov. Code 65583.2(c)(3)(B) default densities (30/20/15/10 du/ac) were not read.", "Marked unverified; drives the SB 4 residential-zone density and the AB 130 half-density floor."),
    ("Base density where zoning and general plan differ, or where there is no du/acre standard.", "User enters one number. 65915(o)(6) says greatest allowed density; base density studies are out of scope."),
    ("Parking: AB 2097 (Gov. Code 65863.2) may remove minimums near transit independently of 65915(p).", "Not computed. Only 65915(p) and SB 4 (k) ratios are applied."),
    ("Cross-referenced site exclusions in Gov. Code 65913.4(a)(6) (SB 4 and AB 130).", "Shown as NEEDS REVIEW; not evaluated."),
    ("Replacement-unit obligations under 65915(c)(3) and local inclusionary overlap.", "Out of scope."),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("site"); ap.add_argument("-o", "--out", default="output/Density_Model.xlsx")
    a = ap.parse_args(argv)
    site = json.loads(Path(a.site).read_text())
    res = write_workbook(site, Path(a.out))
    print(json.dumps(res, indent=1)); print("wrote", a.out)
    return res


if __name__ == "__main__":
    main()
