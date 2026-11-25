"""Write the audit to an .xlsx whose arithmetic is live.

The engine's numbers are not pasted in. Subcomponent sums, the component
credit under 49 CFR 661.11(g)/(l), the vehicle percentage and both
manufactured-product tests are spreadsheet formulas that point at the Rules
sheet, so a reviewer can change an origin or a cost and watch the result move.
tests/test_workbook_parity.py recalculates the file and checks it against the
engine.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .engine import Line, Rules, load_bom

HEAD = PatternFill("solid", fgColor="1F3A4D")
INPUT = PatternFill("solid", fgColor="FFF6D6")
STATUS_FILL = {"PASS": "DDEFD9", "FAIL": "F6D5D2", "REVIEW": "FCEBC2", "N/A": "ECECEC"}
DISCLAIMER = ("Synthetic data. Personal portfolio demo, not legal advice and not a compliance "
              "determination. Prepared by a non-attorney; every result needs review by qualified counsel.")

# Cells on the Rules sheet that formulas point at.
R_PCT_2016, R_PCT_2018, R_PCT_2020, R_BABA, R_FRAME = "Rules!$B$4", "Rules!$B$5", "Rules!$B$6", "Rules!$B$7", "Rules!$B$8"


def _header(ws, row, labels, widths=None):
    for i, label in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=label)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="top")
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _status(cell):
    fill = STATUS_FILL.get(str(cell.value))
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    cell.font = Font(bold=True)


def _title(ws, text):
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = DISCLAIMER
    ws["A2"].font = Font(italic=True, color="8A1F11")


def _rules_sheet(wb, rules: Rules):
    ws = wb.create_sheet("Rules")
    _title(ws, "Thresholds the formulas use, and where each rule comes from")
    bands = {b["fy_from"]: b["pct"] for b in rules.value("rs_domestic_content_by_fy")}
    live = [
        ("Rolling stock %, FY2016-17 delivery", bands[2016], "rs_domestic_content_by_fy"),
        ("Rolling stock %, FY2018-19 delivery", bands[2018], "rs_domestic_content_by_fy"),
        ("Rolling stock %, FY2020 and later", bands[2020], "rs_domestic_content_by_fy"),
        ("BABA manufactured product %", rules.value("baba_manufactured_product_pct"), "baba_manufactured_product_pct"),
        ("Frame or shell steel credit: average vehicle cost above ($)",
         rules.value("rs_frame_shell_steel_credit_min_avg_cost"), "rs_frame_shell_steel_credit_min_avg_cost"),
    ]
    _header(ws, 3, ["Live threshold", "Value", "Source", "Status"], [58, 16, 70, 20, 14, 60, 70])
    for i, (label, value, rid) in enumerate(live, 4):
        ws.cell(row=i, column=1, value=label)
        c = ws.cell(row=i, column=2, value=value)
        c.fill = INPUT
        ws.cell(row=i, column=3, value=rules.cite(rid))
        ws.cell(row=i, column=4, value=rules.entries[rid]["status"])
    start = 11
    _header(ws, start, ["Rule", "Value", "Source", "Status", "Checked on", "How it was checked", "Note"])
    for i, r in enumerate(rules.entries.values(), start + 1):
        v = r["value"]
        vals = [r["label"], v if isinstance(v, (int, float, str)) and not isinstance(v, bool) else json.dumps(v),
                r["source"], r["status"], r.get("verified_on") or "", r.get("verified_how", ""), r.get("note", "")]
        for j, val in enumerate(vals, 1):
            ws.cell(row=i, column=j, value=val).alignment = Alignment(wrap_text=True, vertical="top")


def _rolling_stock_sheets(wb, project: dict, end: Line, result: dict):
    pid = project["project_id"]
    ws = wb.create_sheet(pid[:31])
    subs = wb.create_sheet(f"{pid[:26]} subs")
    sref = f"'{subs.title}'"
    n_subs = sum(len(c.children) for c in end.children)
    last = max(n_subs + 1, 2)

    _header(subs, 1, ["Line", "Parent component", "Subcomponent", "Country of manufacture", "Cost ($)",
                      "Waived", "Tariff-exempt re-export", "Raw material", "Counts as domestic",
                      "Counts inside a foreign component"], [12, 12, 34, 14, 14, 9, 12, 10, 12, 16])
    r = 2
    for comp in end.children:
        for s in comp.children:
            row = [s.line_id, comp.line_id, s.description, s.mfg_country, s.cost,
                   "Y" if s.waived else "N", "Y" if s.tariff_exempt_reexport else "N", "Y" if s.raw_material else "N",
                   f'=IF(OR(D{r}="US",F{r}="Y"),"Y","N")', f'=IF(AND(D{r}="US",G{r}="Y",H{r}<>"Y"),"Y","N")']
            for j, v in enumerate(row, 1):
                c = subs.cell(row=r, column=j, value=v)
                if j in (4, 5, 6, 7, 8):
                    c.fill = INPUT
            r += 1

    _title(ws, f"{project.get('name', pid)}: rolling stock domestic content (49 U.S.C. 5323(j)(2)(C), 49 CFR 661.11)")
    inputs = [
        ("Scheduled delivery date", dt.date.fromisoformat(project["scheduled_delivery_date"]), True),
        ("Federal fiscal year of delivery", "=YEAR(B4)+IF(MONTH(B4)>=10,1,0)", False),
        ("Required domestic content (more than, %)", f"=IF(B5>=2020,{R_PCT_2020},IF(B5>=2018,{R_PCT_2018},{R_PCT_2016}))", False),
        ("Final assembly country", str(project.get("final_assembly_country", "")).upper(), True),
        ("Average vehicle cost ($)", float(project.get("average_vehicle_cost", 0) or 0), True),
        ("US steel in a foreign frame or shell counts", f'=IF(B8>{R_FRAME},"Y","N")', False),
    ]
    for i, (label, value, is_input) in enumerate(inputs, 4):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        c = ws.cell(row=i, column=2, value=value)
        if is_input:
            c.fill = INPUT
    ws["B4"].number_format = "yyyy-mm-dd"

    top = 12
    _header(ws, top, ["Component", "Description", "Supplier", "Country of manufacture", "Cost ($)",
                      "Subcomponents total ($)", "Domestic subcomponents ($)", "Tariff-exempt US subcomponents ($)",
                      "Waived", "US steel or iron in frame or shell ($)", "Domestic subcomponent share (%)",
                      "Counts toward domestic content ($)", "Basis (from the engine)", "Flags"],
            [44, 30, 24, 14, 13, 14, 14, 16, 8, 16, 14, 16, 70, 70])
    first = top + 1
    for k, (comp, cres) in enumerate(zip(end.children, result["components"])):
        r = first + k
        rng = lambda col: f"{sref}!${col}$2:${col}${last}"
        row = [
            comp.line_id, comp.description, comp.supplier, comp.mfg_country, comp.cost,
            f"=SUMIFS({rng('E')},{rng('B')},A{r})",
            f'=SUMIFS({rng("E")},{rng("B")},A{r},{rng("I")},"Y")',
            f'=SUMIFS({rng("E")},{rng("B")},A{r},{rng("J")},"Y")',
            "Y" if comp.waived else "N",
            comp.us_steel_iron_cost if comp.frame_or_shell else 0,
            f'=IF(F{r}>0,G{r}/F{r}*100,"")',
            (f'=IF(I{r}="Y",E{r},IF(D{r}="US",IF(F{r}=0,E{r},IF(G{r}*100>$B$6*F{r},E{r},G{r}+MAX(E{r}-F{r},0))),'
             f'H{r}+IF(AND($B$9="Y",J{r}>0),MIN(J{r},E{r}),0)))'),
            cres["basis"], " | ".join(cres["flags"]),
        ]
        for j, v in enumerate(row, 1):
            c = ws.cell(row=r, column=j, value=v)
            if j in (4, 5, 9, 10):
                c.fill = INPUT
            if j >= 13:
                c.alignment = Alignment(wrap_text=True, vertical="top")
            if j == 11:
                c.number_format = "0.0"
    end_row = first + len(end.children) - 1
    t = end_row + 2
    ws.cell(row=t, column=1, value="Total").font = Font(bold=True)
    ws.cell(row=t, column=5, value=f"=SUM(E{first}:E{end_row})")
    ws.cell(row=t, column=12, value=f"=SUM(L{first}:L{end_row})")
    labels = [
        ("Domestic content (%)", f"=IF(E{t}>0,L{t}/E{t}*100,0)"),
        ("Result", f'=IF(AND(L{t}*100>$B$6*E{t},$B$7="US"),"PASS","FAIL")'),
        ("Domestic cost still needed to clear the threshold ($)", f"=MAX(0,$B$6/100*E{t}-L{t})"),
    ]
    for i, (label, formula) in enumerate(labels, t + 1):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        ws.cell(row=i, column=2, value=formula)
    ws.cell(row=t + 1, column=2).number_format = "0.00"
    ws.cell(row=t + 2, column=2).font = Font(bold=True)
    ws.freeze_panes = ws.cell(row=first, column=2)
    return {"sheet": ws.title, "total_row": t, "first": first, "end": end_row}


def _infrastructure_sheets(wb, project: dict, ends: list[Line], results: list[dict]):
    pid = project["project_id"]
    ws = wb.create_sheet(pid[:31])
    comps = wb.create_sheet(f"{pid[:25]} comps")
    cref = f"'{comps.title}'"
    n = sum(len(e.children) for e in ends)
    last = max(n + 1, 2)
    _header(comps, 1, ["Line", "Parent item", "Component", "Country of manufacture", "Cost ($)", "Waived",
                       "Counts as US component"], [12, 12, 34, 14, 14, 9, 14])
    r = 2
    for e in ends:
        for c in e.children:
            row = [c.line_id, e.line_id, c.description, c.mfg_country, c.cost, "Y" if c.waived else "N",
                   f'=IF(OR(D{r}="US",F{r}="Y"),"Y","N")']
            for j, v in enumerate(row, 1):
                cell = comps.cell(row=r, column=j, value=v)
                if j in (4, 5, 6):
                    cell.fill = INPUT
            r += 1

    _title(ws, f"{project.get('name', pid)}: steel, manufactured products and construction materials")
    ws["A4"] = "Funding source"
    ws["A4"].font = Font(bold=True)
    ws["B4"] = project.get("funding", "FTA")
    ws["A5"] = ("Both manufactured-product tests are shown for every manufactured product. "
                "The 'Governing result' column applies the one that matches the funding source.")
    top = 7
    _header(ws, top, ["Item", "Category", "Description", "Supplier", "Country of manufacture", "Cost ($)",
                      "All processes in US", "Components total ($)", "US components ($)", "US component share (%)",
                      "Foreign components (count)", "FTA test: 49 CFR 661.5(d), all components US",
                      "BABA test: 2 CFR 184, more than 55%", "Governing result (from the engine)",
                      "Governing test", "Source", "Flags"],
            [10, 22, 40, 24, 12, 13, 10, 13, 13, 11, 11, 16, 16, 14, 50, 36, 80])
    first = top + 1
    for k, (e, res) in enumerate(zip(ends, results)):
        r = first + k
        rng = lambda col: f"{cref}!${col}$2:${col}${last}"
        mp = f'B{r}="manufactured_product"'
        row = [
            e.line_id, e.category, e.description, e.supplier, e.mfg_country, e.cost, e.all_processes_us,
            f"=SUMIFS({rng('E')},{rng('B')},A{r})",
            f'=SUMIFS({rng("E")},{rng("B")},A{r},{rng("G")},"Y")',
            f'=IF(H{r}>0,I{r}/H{r}*100,"")',
            f'=COUNTIFS({rng("B")},A{r},{rng("G")},"N")',
            f'=IF({mp},IF(H{r}=0,"REVIEW",IF(AND(E{r}="US",K{r}=0),"PASS","FAIL")),"N/A")',
            f'=IF({mp},IF(H{r}=0,"REVIEW",IF(AND(E{r}="US",I{r}*100>{R_BABA}*H{r}),"PASS","FAIL")),"N/A")',
            res["status"], res.get("governing_test", ""), res.get("cite", ""), " | ".join(res["flags"]),
        ]
        for j, v in enumerate(row, 1):
            c = ws.cell(row=r, column=j, value=v)
            if j in (5, 6, 7):
                c.fill = INPUT
            if j >= 15:
                c.alignment = Alignment(wrap_text=True, vertical="top")
            if j == 10:
                c.number_format = "0.0"
            if j == 14:
                _status(c)
    ws.freeze_panes = ws.cell(row=first, column=2)
    return {"sheet": ws.title, "first": first}


def build_workbook(audit: dict, case_path, bom_path, out_path, rules: Rules | None = None) -> dict:
    rules = rules or Rules()
    case = json.loads(Path(case_path).read_text())
    bom = load_bom(bom_path)
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    _rules_sheet(wb, rules)
    layout: dict = {}

    _title(summary, f"Buy America bill-of-materials audit: {audit['agency']}")
    summary["A3"] = f"Generated {audit['generated_on']}. Yellow cells on the project sheets are inputs; results recalculate."
    _header(summary, 5, ["Project", "Item", "Description", "Result", "Domestic content (%)", "Required (more than, %)",
                         "Test applied", "Source"], [14, 10, 44, 10, 14, 14, 62, 48])
    row = 6
    docs_ws = wb.create_sheet("Documents")
    _title(docs_ws, "Certificates and Part 663 audit documents")
    _header(docs_ws, 4, ["Project", "Stage", "Document", "Source", "Status", "Note"], [14, 16, 56, 30, 10, 70])
    drow = 5

    for project, pres in zip(case["projects"], audit["projects"]):
        pid = project["project_id"]
        ends = bom.get(pid, [])
        rs_ends = [e for e in ends if e.category == "rolling_stock"]
        infra_ends = [e for e in ends if e.category != "rolling_stock"]
        if len(rs_ends) > 1 or (rs_ends and infra_ends):
            raise ValueError(f"{pid}: the workbook writer expects one vehicle bill of materials, or infrastructure items, per project")
        if rs_ends:
            res = pres["rolling_stock"][0]
            lay = _rolling_stock_sheets(wb, project, rs_ends[0], res)
            layout[pid] = {"kind": "rolling_stock", **lay}
            sref = f"'{lay['sheet']}'"
            vals = [pid, res["line_id"], res["description"], f"={sref}!B{lay['total_row'] + 2}",
                    f"={sref}!B{lay['total_row'] + 1}", f"={sref}!B6", res["governing_test"], res["cite"]]
            for j, v in enumerate(vals, 1):
                summary.cell(row=row, column=j, value=v)
            summary.cell(row=row, column=5).number_format = "0.00"
            row += 1
        if infra_ends:
            lay = _infrastructure_sheets(wb, project, infra_ends, pres["infrastructure"])
            layout[pid] = {"kind": "infrastructure", **lay}
            for res in pres["infrastructure"]:
                vals = [pid, res["line_id"], res["description"], res["status"], "", "",
                        res.get("governing_test", ""), res.get("cite", "")]
                for j, v in enumerate(vals, 1):
                    c = summary.cell(row=row, column=j, value=v)
                    if j == 4:
                        _status(c)
                row += 1
        for d in pres["documents"]:
            vals = [pid, pres["stage"].replace("_", " "), d["document"], d["cite"], d["status"], d["note"]]
            for j, v in enumerate(vals, 1):
                c = docs_ws.cell(row=drow, column=j, value=v)
                if j == 5:
                    _status(c)
            drow += 1

    wb.move_sheet("Rules", offset=len(wb.sheetnames))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return layout
