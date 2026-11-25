"""Build the live-formula workbook from the sample (or supplied) data files.

Every total, check and waterfall tier in the workbook is an Excel formula over
the input cells, so a reader can trace any number. The Python engine computes
the same figures independently; tests/test_parity.py recalculates the workbook
and compares the two.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from engine import ipd, seismic
from engine.common import load_params, parse_date
from engine.corrections import CORRECTIONS

ROOT = Path(__file__).resolve().parent
HEAD = PatternFill("solid", fgColor="DDE3EA")
INPUT = PatternFill("solid", fgColor="FFF7D6")
BOLD = Font(bold=True)
MONEY = '#,##0.00;[Red]-#,##0.00'
DATE = "yyyy-mm-dd"
DISCLAIMER = ("Portfolio demonstration. All project, party and facility data is fictional. "
              "Not legal advice; not prepared by an attorney.")


def header(ws, row, labels):
    for i, lab in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=lab)
        c.font, c.fill = BOLD, HEAD
        c.alignment = Alignment(wrap_text=True, vertical="top")


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def build(ledger: dict, facility: dict, out_path: Path, params: dict | None = None) -> dict:
    params = params or load_params()
    states, lfind = ipd.run_ledger(ledger)
    last = states[-1]
    wf = ipd.waterfall(last, ledger["terms"], ledger["forecast_actual_cost"])
    brows = seismic.building_rows(facility, params)
    mrows = seismic.milestone_rows(facility, params)
    fines = seismic.fine_exposure(mrows, params)
    findings = (lfind + ipd.waterfall_findings(last, wf)
                + seismic.facility_deadline(facility, params)[1]
                + seismic.plan_findings(facility, params, brows, mrows))
    cmap: dict = {}
    wb = Workbook()

    # ---- About
    ws = wb.active
    ws.title = "About"
    lines = [
        ("IFOA risk/reward pool checker and hospital seismic deadline tracker", BOLD),
        (DISCLAIMER, None), ("", None),
        ("Project: " + ledger["project"], None), ("Facility: " + facility["facility"], None),
        ("As of: " + ledger["as_of"], None), ("", None),
        ("Sheets", BOLD),
        ("Ledger - one row per amendment. Running totals are formulas over the change columns and are compared with what each amendment's exhibit states.", None),
        ("ICL Changes / ICL Shares - profit-at-risk dollars by member, and the stated percentage shares checked against them.", None),
        ("Members - current ICL, share and forecast payout per risk pool member.", None),
        ("Waterfall - how a forecast overrun or saving is absorbed. Change the yellow cells.", None),
        ("Sensitivity - the same waterfall across a range of final costs.", None),
        ("Seismic - deadline, delay screen and fine exposure for the hospital campus.", None),
        ("Buildings / Milestones - float to the deadline and milestone slippage.", None),
        ("Legal Params - every legal number the formulas use, with citation and verification status.", None),
        ("Findings - the Python engine's findings (values, not formulas).", None),
        ("Corrections - where the source research report was wrong or unconfirmed.", None),
        ("", None),
        ("Yellow cells are inputs. Contract terms (tier order, savings split, cap) are inputs because IFOA terms are negotiated per project.", None),
    ]
    for i, (text, font) in enumerate(lines, 1):
        c = ws.cell(row=i, column=1, value=text)
        if font:
            c.font = font
    widths(ws, {"A": 140})

    # ---- Legal Params
    lp = wb.create_sheet("Legal Params")
    header(lp, 1, ["id", "What it is", "Value", "Citation", "Status", "Note", "Source"])
    P = {}
    for r, (pid, p) in enumerate(params.items(), 2):
        v = p["value"]
        lp.cell(row=r, column=1, value=pid)
        lp.cell(row=r, column=2, value=p["label"])
        cell = lp.cell(row=r, column=3)
        if isinstance(v, list):
            cell.value = ",".join(v)
        elif isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
            cell.value, cell.number_format = parse_date(v), DATE
        else:
            cell.value = v
        lp.cell(row=r, column=4, value=p["citation"])
        lp.cell(row=r, column=5, value=p["status"])
        lp.cell(row=r, column=6, value=p["note"])
        lp.cell(row=r, column=7, value=p["source_url"])
        P[pid] = f"'Legal Params'!$C${r}"
    widths(lp, {"A": 30, "B": 55, "C": 16, "D": 42, "E": 12, "F": 70, "G": 60})

    # ---- ICL Changes
    ic = wb.create_sheet("ICL Changes")
    header(ic, 1, ["Amendment", "Member", "ICL change ($)"])
    r = 2
    for am in ledger["amendments"]:
        for ch in am.get("icl_changes", []):
            ic.cell(row=r, column=1, value=am["no"])
            ic.cell(row=r, column=2, value=ch["member"])
            c = ic.cell(row=r, column=3, value=ch["delta"])
            c.number_format, c.fill = MONEY, INPUT
            r += 1
    widths(ic, {"A": 12, "B": 30, "C": 18})

    # ---- ICL Shares
    sh = wb.create_sheet("ICL Shares")
    header(sh, 1, ["Amendment", "Member", "Stated share (%)", "Member ICL to date ($)",
                   "Total ICL to date ($)", "Computed share (%)", "Stated - computed", "Check"])
    r = 2
    cmap["shares"] = []
    for am in ledger["amendments"]:
        for m, pct in (am.get("stated", {}).get("icl_shares") or {}).items():
            sh.cell(row=r, column=1, value=am["no"])
            sh.cell(row=r, column=2, value=m)
            sh.cell(row=r, column=3, value=pct).fill = INPUT
            sh.cell(row=r, column=4, value=f"=SUMIFS('ICL Changes'!$C:$C,'ICL Changes'!$B:$B,B{r},'ICL Changes'!$A:$A,\"<=\"&A{r})").number_format = MONEY
            sh.cell(row=r, column=5, value=f"=SUMIFS('ICL Changes'!$C:$C,'ICL Changes'!$A:$A,\"<=\"&A{r})").number_format = MONEY
            sh.cell(row=r, column=6, value=f"=IF(E{r}=0,0,D{r}/E{r}*100)").number_format = "0.0000"
            sh.cell(row=r, column=7, value=f"=C{r}-F{r}").number_format = "0.0000"
            sh.cell(row=r, column=8, value=f"=IF(ABS(G{r})<=0.0100001,\"OK\",\"MISMATCH\")")
            cmap["shares"].append({"no": am["no"], "member": m, "row": r})
            r += 1
    widths(sh, {"A": 12, "B": 30, "C": 16, "D": 22, "E": 22, "F": 18, "G": 18, "H": 12})

    # ---- Ledger
    lg = wb.create_sheet("Ledger")
    lg["A1"], lg["A2"] = "Amendment ledger - " + ledger["project"], DISCLAIMER
    lg["A1"].font = BOLD
    cols = ["No.", "Date", "Type", "Title", "Change: target cost", "Change: shared contingency",
            "Change: owner contingency", "Change: EMP", "Change: ICL", "Shared contingency draw",
            "Owner contingency draw", "Running target cost", "Running shared contingency (authorized)",
            "Running owner contingency (authorized)", "Running EMP", "Running ICL",
            "Shared contingency drawn to date", "Owner contingency drawn to date",
            "Shared contingency balance", "Owner contingency balance",
            "Stated target cost", "Stated shared contingency", "Stated owner contingency", "Stated EMP",
            "Stated ICL", "Stated ICL shares sum (%)",
            "Check: target cost", "Check: shared contingency", "Check: owner contingency", "Check: EMP",
            "Check: ICL", "Check: shares sum to 100.00%", "Check: EMP covers target cost + shared contingency + ICL",
            "Check: contingency balances", "Check: each stated share matches ICL dollars", "Row result"]
    header(lg, 4, cols)
    lg.row_dimensions[4].height = 62
    first = 5
    for i, am in enumerate(ledger["amendments"]):
        r = first + i
        d, st, dr = am.get("deltas", {}), am.get("stated", {}), am.get("draws") or {}
        lg.cell(row=r, column=1, value=am["no"])
        lg.cell(row=r, column=2, value=parse_date(am["date"])).number_format = DATE
        lg.cell(row=r, column=3, value=am["type"])
        lg.cell(row=r, column=4, value=am.get("title", ""))
        for col, key in ((5, "target_cost"), (6, "shared_contingency"), (7, "owner_contingency"), (8, "emp")):
            c = lg.cell(row=r, column=col, value=d.get(key, 0))
            c.fill = INPUT
        lg.cell(row=r, column=9, value=f"=SUMIFS('ICL Changes'!$C:$C,'ICL Changes'!$A:$A,A{r})")
        lg.cell(row=r, column=10, value=dr.get("shared", 0)).fill = INPUT
        lg.cell(row=r, column=11, value=dr.get("owner", 0)).fill = INPUT
        for col, src in ((12, "E"), (13, "F"), (14, "G"), (15, "H"), (16, "I"), (17, "J"), (18, "K")):
            lg.cell(row=r, column=col, value=f"=SUM({src}${first}:{src}{r})")
        lg.cell(row=r, column=19, value=f"=M{r}-Q{r}")
        lg.cell(row=r, column=20, value=f"=N{r}-R{r}")
        for col, key in ((21, "target_cost"), (22, "shared_contingency"), (23, "owner_contingency"), (24, "emp"), (25, "icl_total")):
            c = lg.cell(row=r, column=col, value=st.get(key))
            c.fill = INPUT
        lg.cell(row=r, column=26, value=f"=ROUND(SUMIFS('ICL Shares'!$C:$C,'ICL Shares'!$A:$A,A{r}),2)")
        for col, run, stated in ((27, "L", "U"), (28, "M", "V"), (29, "N", "W"), (30, "O", "X"), (31, "P", "Y")):
            lg.cell(row=r, column=col, value=f'=IF({stated}{r}="","n/a",IF(ROUND({run}{r}-{stated}{r},2)=0,"OK","MISMATCH"))')
        lg.cell(row=r, column=32, value=f'=IF(Z{r}=100,"OK","NOT 100%")')
        lg.cell(row=r, column=33, value=f'=IF(O{r}>=L{r}+M{r}+P{r},"OK","EMP TOO LOW")')
        lg.cell(row=r, column=34, value=f'=IF(AND(S{r}>=0,T{r}>=0),"OK","OVERDRAWN")')
        lg.cell(row=r, column=35, value=f"=IF(COUNTIFS('ICL Shares'!$A:$A,A{r},'ICL Shares'!$H:$H,\"MISMATCH\")=0,\"OK\",\"MISMATCH\")")
        lg.cell(row=r, column=36, value=f'=IF(COUNTIF(AA{r}:AI{r},"OK")+COUNTIF(AA{r}:AI{r},"n/a")=9,"OK","REVIEW")')
        for col in list(range(5, 26)):
            lg.cell(row=r, column=col).number_format = MONEY
        lg.cell(row=r, column=26).number_format = "0.00"
    LR = first + len(ledger["amendments"]) - 1
    cmap["ledger"] = {"first": first, "last": LR}
    widths(lg, {"A": 6, "B": 12, "C": 24, "D": 48})
    for col in range(5, 37):
        lg.column_dimensions[get_column_letter(col)].width = 19
    lg.freeze_panes = "E5"

    # ---- Waterfall
    wf_ws = wb.create_sheet("Waterfall")
    rows = [
        (1, "Closeout waterfall - " + ledger["project"], None, None),
        (2, DISCLAIMER, None, None),
        (3, "Position after the latest amendment", None, None),
        (4, "Target cost", f"=Ledger!L{LR}", MONEY),
        (5, "Shared contingency (authorized)", f"=Ledger!M{LR}", MONEY),
        (6, "ICL (profit at risk)", f"=Ledger!P{LR}", MONEY),
        (7, "Owner contingency (authorized)", f"=Ledger!N{LR}", MONEY),
        (8, "Estimated maximum price (EMP)", f"=Ledger!O{LR}", MONEY),
        (9, "Inputs", None, None),
        (10, "Forecast actual reimbursable cost", ledger["forecast_actual_cost"], MONEY),
        (11, "Owner share of savings (%)", ledger["terms"]["owner_savings_pct"], "0.00"),
        (12, "Team share of savings (%)", ledger["terms"]["team_savings_pct"], "0.00"),
        (13, "Cap on ICL pool, as a multiple of base ICL (blank = no cap)", ledger["terms"].get("icl_cap_multiple"), "0.00"),
        (14, "Overrun: absorbed in this order", None, None),
        (15, "Overrun above target cost", "=MAX(0,B10-B4)", MONEY),
        (16, "1. Shared contingency", "=MIN(B15,B5)", MONEY),
        (17, "2. Team ICL (up to 100%)", "=MIN(B15-B16,B6)", MONEY),
        (18, "3. Owner contingency", "=MIN(B15-B16-B17,B7)", MONEY),
        (19, "4. Owner, at cost with no profit", "=B15-B16-B17-B18", MONEY),
        (20, "Check: tiers add up to the overrun", '=IF(ROUND(B16+B17+B18+B19-B15,2)=0,"OK","ERROR")', None),
        (21, "Savings", None, None),
        (22, "Savings below target cost", "=MAX(0,B4-B10)", MONEY),
        (23, "Team share before cap", "=ROUND(B22*B12/100,2)", MONEY),
        (24, "ICL pool before cap", "=B6-B17+B23", MONEY),
        (25, "ICL pool, final", '=IF(B13="",B24,MIN(B24,B6*B13))', MONEY),
        (26, "Amount removed by the cap", "=B24-B25", MONEY),
        (27, "Team savings kept", "=B23-B26", MONEY),
        (28, "Owner savings", "=B22-B23+B26", MONEY),
        (29, "ICL pool as % of base ICL", "=IF(B6=0,0,B25/B6*100)", "0.00"),
        (30, "Owner position", None, None),
        (31, "Owner total payment (cost + ICL pool)", "=B10+B25", MONEY),
        (32, "Headroom under EMP", "=B8-B31", MONEY),
        (33, "EMP check", '=IF(B31>B8,"OVER EMP","Within EMP")', None),
        (34, "Check: ICL is exhausted before owner funds are used", '=IF(OR(B18+B19=0,AND(B16=B5,B17=B6)),"OK","ERROR")', None),
        (35, "Check: savings split adds to 100%", '=IF(B11+B12=100,"OK","NOT 100%")', None),
        (36, "Contingency draws logged so far", None, None),
        (37, "Draws logged (shared + owner)", f"=Ledger!Q{LR}+Ledger!R{LR}", MONEY),
        (38, "Forecast overrun not yet covered by a logged draw", "=MAX(0,B15-B37)", MONEY),
        (40, "Tax-exempt bond financing recorded", "Y" if ledger["terms"].get("tax_exempt_bond_financed") else "N", None),
        (41, "Contract includes services after the building is placed in service", "Y" if ledger["terms"].get("post_occupancy_services_in_scope") else "N", None),
        (42, "Bond counsel question", '=IF(AND(B40="Y",B41="Y"),"Ask bond counsel whether the post-occupancy services are a management contract (Rev. Proc. 2017-13)","None raised: Rev. Proc. 2017-13 s. 4.03 excludes services before the property is placed in service")', None),
    ]
    for r, label, val, fmt in rows:
        a = wf_ws.cell(row=r, column=1, value=label)
        if val is None and fmt is None and r not in (2,):
            a.font = BOLD
        if not (val is None and fmt is None):
            b = wf_ws.cell(row=r, column=2, value=val)
            if fmt:
                b.number_format = fmt
            if r in (10, 11, 12, 13, 40, 41):
                b.fill = INPUT
    widths(wf_ws, {"A": 62, "B": 24})

    # ---- Members
    mb = wb.create_sheet("Members")
    header(mb, 1, ["Member", "Role", "Joined in amendment", "ICL ($)", "Share of ICL", "Forecast ICL payout ($)"])
    roles, joined = {}, {}
    for am in ledger["amendments"]:
        for m in am.get("base_members", []):
            joined[m], roles[m] = am["no"], "Signatory to base agreement"
        if am.get("joining"):
            joined[am["joining"]["member"]] = am["no"]
            roles[am["joining"]["member"]] = am["joining"].get("role", "")
    members = list(last["icl"].keys())
    end = 1 + len(members)
    cmap["members"] = {}
    for r, m in enumerate(members, 2):
        mb.cell(row=r, column=1, value=m)
        mb.cell(row=r, column=2, value=roles.get(m, ""))
        mb.cell(row=r, column=3, value=joined.get(m))
        mb.cell(row=r, column=4, value=f"=SUMIFS('ICL Changes'!$C:$C,'ICL Changes'!$B:$B,A{r})").number_format = MONEY
        mb.cell(row=r, column=5, value=f"=IF(SUM($D$2:$D${end})=0,0,D{r}/SUM($D$2:$D${end}))").number_format = "0.0000%"
        mb.cell(row=r, column=6, value=f"=ROUND(Waterfall!$B$25*E{r},2)").number_format = MONEY
        cmap["members"][m] = r
    t = end + 1
    mb.cell(row=t, column=1, value="Total").font = BOLD
    mb.cell(row=t, column=4, value=f"=SUM(D2:D{end})").number_format = MONEY
    mb.cell(row=t, column=5, value=f"=SUM(E2:E{end})").number_format = "0.0000%"
    mb.cell(row=t, column=6, value=f"=SUM(F2:F{end})").number_format = MONEY
    mb.cell(row=t + 1, column=1, value="Check: shares sum to 100.00%")
    mb.cell(row=t + 1, column=5, value=f'=IF(ROUND(E{t},6)=1,"OK","NOT 100%")')
    mb.cell(row=t + 2, column=1, value="Check: payouts equal the ICL pool (within rounding)")
    mb.cell(row=t + 2, column=6, value=f'=IF(ABS(F{t}-Waterfall!$B$25)<=0.01*{len(members)},"OK","ERROR")')
    cmap["members_total_row"] = t
    widths(mb, {"A": 30, "B": 36, "C": 14, "D": 20, "E": 14, "F": 24})

    # ---- Sensitivity
    se = wb.create_sheet("Sensitivity")
    se["A1"] = "Waterfall across a range of final costs (uses the terms on the Waterfall sheet)"
    se["A1"].font = BOLD
    header(se, 3, ["Final cost as multiple of target cost", "Final cost", "Overrun", "1. Shared contingency",
                   "2. Team ICL", "3. Owner contingency", "4. Owner at cost", "Savings", "Team savings kept",
                   "ICL pool, final", "ICL pool % of base", "Owner total payment", "Headroom under EMP"])
    se.row_dimensions[3].height = 48
    W = "Waterfall!"
    factors = [0.90 + 0.025 * i for i in range(11)]
    cmap["sensitivity"] = {"first": 4, "factors": factors}
    for i, fct in enumerate(factors):
        r = 4 + i
        se.cell(row=r, column=1, value=round(fct, 3)).fill = INPUT
        se.cell(row=r, column=2, value=f"=ROUND({W}$B$4*A{r},0)")
        se.cell(row=r, column=3, value=f"=MAX(0,B{r}-{W}$B$4)")
        se.cell(row=r, column=4, value=f"=MIN(C{r},{W}$B$5)")
        se.cell(row=r, column=5, value=f"=MIN(C{r}-D{r},{W}$B$6)")
        se.cell(row=r, column=6, value=f"=MIN(C{r}-D{r}-E{r},{W}$B$7)")
        se.cell(row=r, column=7, value=f"=C{r}-D{r}-E{r}-F{r}")
        se.cell(row=r, column=8, value=f"=MAX(0,{W}$B$4-B{r})")
        se.cell(row=r, column=10, value=f'=IF({W}$B$13="",{W}$B$6-E{r}+ROUND(H{r}*{W}$B$12/100,2),MIN({W}$B$6-E{r}+ROUND(H{r}*{W}$B$12/100,2),{W}$B$6*{W}$B$13))')
        se.cell(row=r, column=9, value=f"=J{r}-({W}$B$6-E{r})")
        se.cell(row=r, column=11, value=f"=IF({W}$B$6=0,0,J{r}/{W}$B$6*100)")
        se.cell(row=r, column=12, value=f"=B{r}+J{r}")
        se.cell(row=r, column=13, value=f"={W}$B$8-L{r}")
        for col in range(2, 14):
            se.cell(row=r, column=col).number_format = MONEY if col != 11 else "0.00"
        se.cell(row=r, column=1).number_format = "0.000"
    for col in range(1, 14):
        se.column_dimensions[get_column_letter(col)].width = 20

    # ---- Seismic
    sz = wb.create_sheet("Seismic")
    e, lpj = facility["eligibility"], facility["linked_project"]
    S = "Seismic!"
    srows = [
        (1, "Hospital seismic deadline tracker", None, None, False),
        (2, DISCLAIMER, None, None, False),
        (3, "Facility", facility["facility"], None, True),
        (4, "HCAI Perm ID (fictional)", facility["perm_id"], None, True),
        (5, "As-of date", parse_date(facility["as_of"]), DATE, True),
        (7, "Delay screen under Health & Saf. Code s. 130065.1 (a screen of recorded facts; HCAI decides)", None, None, False),
        (8, "Licensed beds", e["licensed_beds"], None, True),
        (9, "General acute care beds", e["gac_beds"], None, True),
        (10, "Rural hospital (Y/N)", e["rural"], None, True),
        (11, "Critical access hospital (Y/N)", e["critical_access"], None, True),
        (12, "Health care district hospital (Y/N)", e["district"], None, True),
        (13, "Distressed Hospital Loan Program recipient (Y/N)", e["dhlp_recipient"], None, True),
        (14, "Part of an integrated system with 2+ separately licensed hospitals (Y/N)", e["integrated_system"], None, True),
        (15, "A health system bears financial responsibility for seismic infrastructure cost (Y/N)", e["system_bears_seismic_cost"], None, True),
        (16, "System is operated by a district or its sole-member nonprofit (Y/N)", e["system_operated_by_district"], None, True),
        (17, "Entire system determined to be in financial distress (Y/N)", e["system_in_financial_distress"], None, True),
        (18, "General acute care hospital revenue reported for 2020 ($)", e["gac_revenue_2020"], MONEY, True),
        (19, "NPC-5 evaluation report filed by 1/1/2025 (Y / N / Not needed)", e["npc5_report_by_2025_01_01"], None, True),
        (20, "Seismic compliance plan submitted on", parse_date(e["compliance_plan_submitted"]), DATE, True),
        (22, "In an eligible category", f'=IF(OR(B8<={P["small_hospital_beds"]},B10="Y",B11="Y",B12="Y",B13="Y"),"Y","N")', None, False),
        (23, "Integrated-system exclusion applies", '=IF(OR(B14="Y",AND(B12="Y",B15="Y")),"Y","N")', None, False),
        (24, "Exception (c)(2)(A): small rural system hospital", f'=IF(AND(B10="Y",B9<{P["rural_exception_gac_beds"]},B18<={P["rural_exception_revenue_2020"]}),"Y","N")', None, False),
        (25, "Exception (c)(2)(B): district-operated system", '=IF(B16="Y","Y","N")', None, False),
        (26, "Exception (c)(2)(C): district hospital, no system cost responsibility", '=IF(AND(B12="Y",B15<>"Y"),"Y","N")', None, False),
        (27, "Exclusion lifted (system distress or an exception)", '=IF(OR(B17="Y",B24="Y",B25="Y",B26="Y"),"Y","N")', None, False),
        (28, "Filings made on time", f'=IF(AND(OR(B19="Y",B19="Not needed"),B20<>"",B20<={P["compliance_plan_due"]}),"Y","N")', None, False),
        (29, "Screen result", '=IF(AND(B22="Y",OR(B23="N",B27="Y"),B28="Y"),"Passes screen","Does not pass screen")', None, False),
        (31, "Deadline", None, None, False),
        (32, "Base deadline (s. 130065(a))", f'={P["seismic_base_deadline"]}', DATE, False),
        (33, "HCAI-approved delay date (blank if none)", parse_date(facility.get("approved_delay_date")), DATE, True),
        (34, "Additional two-year delay granted (Y/N)", facility.get("additional_delay_granted", "N"), None, True),
        (35, "Latest date a delay can run to", f'=IF(B34="Y",{P["ab869_outer_limit"]},{P["ab869_max_delay"]})', DATE, False),
        (36, "Applicable deadline", '=IF(B33="",B32,B33)', DATE, False),
        (37, "Check: delay date within limit", '=IF(B33="","n/a",IF(B33>B35,"AFTER LIMIT","OK"))', None, False),
        (38, "Days from as-of date to deadline", "=B36-B5", "0", False),
        (40, "Linked construction project", None, None, False),
        (41, "Project", lpj["name"], None, True),
        (42, "Baseline completion", parse_date(lpj["baseline_completion"]), DATE, True),
        (43, "Current forecast completion", parse_date(lpj["forecast_completion"]), DATE, True),
        (44, "Scenario: extra drift days to test", lpj.get("scenario_extra_drift_days", 0), "0", True),
        (45, "Total schedule drift (days) applied to linked buildings", "=B43-B42+B44", "0", False),
        (47, "Fine exposure for critical milestones (s. 130065.1(g); PIN 80 p. 10)", None, None, False),
        (48, "Fine per calendar day", f'={P["milestone_fine_per_day"]}', MONEY, False),
        (49, "Accrued to as-of date: longest single late period (days)", "=MAX(Milestones!L5:L200)", "0", False),
        (50, "Accrued: all late periods stacked (days)", "=SUM(Milestones!L5:L200)", "0", False),
        (51, "Accrued: calendar days with any critical milestone late (engine value)", fines["accrued"]["union_days"], "0", False),
        (52, "Accrued fine, low bound", "=B49*B48", MONEY, False),
        (53, "Accrued fine, per-facility reading", "=B51*B48", MONEY, False),
        (54, "Accrued fine, high bound", "=B50*B48", MONEY, False),
        (55, "Check: engine value sits between the bounds", '=IF(AND(B51>=B49,B51<=B50),"OK","RE-RUN ENGINE")', None, False),
        (56, "Projected to forecast dates: longest single late period (days)", "=MAX(Milestones!M5:M200)", "0", False),
        (57, "Projected: all late periods stacked (days)", "=SUM(Milestones!M5:M200)", "0", False),
        (58, "Projected: calendar days with any critical milestone late (engine value)", fines["projected"]["union_days"], "0", False),
        (59, "Projected fine, low bound", "=B56*B48", MONEY, False),
        (60, "Projected fine, per-facility reading", "=B58*B48", MONEY, False),
        (61, "Projected fine, high bound", "=B57*B48", MONEY, False),
        (62, "Check: engine value sits between the bounds", '=IF(AND(B58>=B56,B58<=B57),"OK","RE-RUN ENGINE")', None, False),
        (64, "Approved milestones unmet and overdue", '=COUNTIF(Milestones!O5:O200,"OVERDUE")', "0", False),
        (65, "Building permit hold (s. 130065.1(i))", '=IF(B64>0,"Hold applies: only seismic, maintenance and emergency repair permits","No hold")', None, False),
        (66, "Critical milestones in plan", '=COUNTIF(Milestones!E5:E200,"Y")', "0", False),
        (67, "Check: critical milestone count (PIN 80)", f'=IF(B66={P["critical_milestones_per_facility"]},"OK","PIN 80 calls for "&{P["critical_milestones_per_facility"]})', None, False),
        (69, "The two 'engine value' cells are written by the Python engine because counting overlapping late periods once is not practical as a cell formula. Re-run the engine after changing milestone dates.", None, None, False),
    ]
    for r, label, val, fmt, is_input in srows:
        a = sz.cell(row=r, column=1, value=label)
        if val is None and r not in (2, 69):
            a.font = BOLD
        if val is not None or is_input:
            b = sz.cell(row=r, column=2, value=val)
            if fmt:
                b.number_format = fmt
            if is_input:
                b.fill = INPUT
            b.alignment = Alignment(horizontal="left")
    widths(sz, {"A": 78, "B": 44})

    # ---- Buildings
    bd = wb.create_sheet("Buildings")
    bd["A1"], bd["A2"] = "Buildings - float to the applicable deadline", DISCLAIMER
    bd["A1"].font = BOLD
    header(bd, 4, ["Building Nbr", "Building name", "SPC rating", "NPC rating (hospital records)", "HCAI building status",
                   "Method of compliance", "Depends on linked project (Y/N)", "Forecast compliance date (plan)",
                   "Drift applied (days)", "Forecast compliance date (adjusted)", "Compliant now",
                   "Applicable deadline", "Float (days)", "Status", "Posted notice text required (s. 130066.5(c))"])
    bd.row_dimensions[4].height = 48
    cmap["buildings"] = {}
    for i, b in enumerate(facility["buildings"]):
        r = 5 + i
        vals = [b["building_nbr"], b["name"], str(b["spc"]), str(b["npc"]), b.get("hcai_status", ""), b["method"],
                b.get("linked_to_project", "N"), parse_date(b.get("forecast_compliance_date"))]
        for col, v in enumerate(vals, 1):
            c = bd.cell(row=r, column=col, value=v)
            c.fill = INPUT
        bd.cell(row=r, column=8).number_format = DATE
        bd.cell(row=r, column=9, value=f'=IF(G{r}="Y",{S}$B$45,0)')
        bd.cell(row=r, column=10, value=f'=IF(H{r}="","",H{r}+I{r})').number_format = DATE
        bd.cell(row=r, column=11, value=f'=IF(AND(ISNUMBER(SEARCH(","&C{r}&",",","&{P["compliant_spc"]}&",")),ISNUMBER(SEARCH(","&D{r}&",",","&{P["compliant_npc"]}&","))),"Y","N")')
        bd.cell(row=r, column=12, value=f"={S}$B$36").number_format = DATE
        bd.cell(row=r, column=13, value=f'=IF(OR(K{r}="Y",J{r}=""),"",L{r}-J{r})')
        bd.cell(row=r, column=14, value=f'=IF(K{r}="Y","Compliant",IF(J{r}="","No forecast date",IF(M{r}<0,"Past deadline",IF(M{r}<{P["tight_float_days"]},"Tight","On track"))))')
        bd.cell(row=r, column=15, value=f'=IF(K{r}="Y","",IF(C{r}="2",{P["ab1882_notice_spc2"]},{P["ab1882_notice_other"]}))')
        cmap["buildings"][b["building_nbr"]] = r
    widths(bd, {"A": 13, "B": 26, "C": 8, "D": 14, "E": 22, "F": 36, "G": 14, "H": 16, "I": 10, "J": 16,
                "K": 10, "L": 14, "M": 10, "N": 16, "O": 90})

    # ---- Milestones
    ms = wb.create_sheet("Milestones")
    ms["A1"], ms["A2"] = "Compliance plan milestones", DISCLAIMER
    ms["A1"].font = BOLD
    header(ms, 4, ["ID", "Building", "Milestone type (PIN 80 list)", "Description", "Critical (Y/N)", "Approved date",
                   "Forecast or actual date", "Status", "Slip (days)", "Late as of as-of date (days)",
                   "Late to forecast (days)", "Critical: late as of as-of date", "Critical: late to forecast",
                   "Adjustment request due by", "Flag"])
    ms.row_dimensions[4].height = 48
    cmap["milestones"] = {}
    for i, m in enumerate(facility["milestones"]):
        r = 5 + i
        vals = [m["id"], m["building"], m["type"], m["description"], m["critical"],
                parse_date(m["approved_date"]), parse_date(m["forecast_or_actual_date"]), m["status"]]
        for col, v in enumerate(vals, 1):
            ms.cell(row=r, column=col, value=v).fill = INPUT
        ms.cell(row=r, column=6).number_format = DATE
        ms.cell(row=r, column=7).number_format = DATE
        ms.cell(row=r, column=9, value=f"=MAX(0,G{r}-F{r})")
        ms.cell(row=r, column=10, value=f'=IF(H{r}="Completed",MAX(0,G{r}-F{r}),MAX(0,{S}$B$5-F{r}))')
        ms.cell(row=r, column=11, value=f'=MAX(0,IF(H{r}="Completed",G{r},MAX(G{r},{S}$B$5))-F{r})')
        ms.cell(row=r, column=12, value=f'=IF(E{r}="Y",J{r},0)')
        ms.cell(row=r, column=13, value=f'=IF(E{r}="Y",K{r},0)')
        ms.cell(row=r, column=14, value=f'=F{r}-{P["adjustment_request_lead_days"]}').number_format = DATE
        ms.cell(row=r, column=15, value=f'=IF(AND(H{r}<>"Completed",J{r}>0),"OVERDUE",IF(I{r}>0,"Slipping","On schedule"))')
        cmap["milestones"][m["id"]] = r
    widths(ms, {"A": 7, "B": 12, "C": 32, "D": 42, "E": 9, "F": 13, "G": 13, "H": 13, "I": 9, "J": 12,
                "K": 12, "L": 12, "M": 12, "N": 14, "O": 13})

    # ---- Findings
    fd = wb.create_sheet("Findings")
    fd["A1"] = "Findings from the Python engine (values written at build time, not formulas)"
    fd["A1"].font = BOLD
    header(fd, 3, ["Code", "Severity", "Where", "Finding"])
    for r, f in enumerate(findings, 4):
        for col, v in enumerate([f.code, f.severity, f.where, f.message], 1):
            fd.cell(row=r, column=col, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    widths(fd, {"A": 8, "B": 10, "C": 16, "D": 130})

    # ---- Corrections
    co = wb.create_sheet("Corrections")
    co["A1"] = "Research report (Tool 4 section) compared with primary sources, checked 2026-11-25"
    co["A1"].font = BOLD
    header(co, 3, ["Report says", "What the source says", "Checked against", "Result"])
    for r, row in enumerate(CORRECTIONS, 4):
        for col, v in enumerate(row, 1):
            co.cell(row=r, column=col, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    widths(co, {"A": 50, "B": 110, "C": 44, "D": 18})

    wb.move_sheet("Legal Params", offset=len(wb.sheetnames))
    order = ["About", "Ledger", "ICL Changes", "ICL Shares", "Members", "Waterfall", "Sensitivity",
             "Seismic", "Buildings", "Milestones", "Findings", "Legal Params", "Corrections"]
    wb._sheets = [wb[n] for n in order]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return {"cmap": cmap, "findings": findings, "states": states, "waterfall": wf,
            "buildings": brows, "milestones": mrows, "fines": fines}


def recalc_in_place(path: Path) -> bool:
    """Store calculated values next to the formulas (for viewers that do not recalculate)."""
    import shutil
    import subprocess
    import tempfile
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice, "--headless", "--convert-to", "xlsx", "--outdir", tmp, str(path)],
                       check=True, capture_output=True, timeout=180)
        shutil.copy(Path(tmp) / path.name, path)
    return True


def main(argv=None):
    argv = argv or sys.argv[1:]
    ledger_path = Path(argv[0]) if len(argv) > 0 else ROOT / "sample_data" / "ifoa_ledger.json"
    campus_path = Path(argv[1]) if len(argv) > 1 else ROOT / "sample_data" / "seismic_campus.json"
    out = Path(argv[2]) if len(argv) > 2 else ROOT / "output" / "IFOA_Seismic_Model.xlsx"
    ledger, facility = json.loads(ledger_path.read_text()), json.loads(campus_path.read_text())
    res = build(ledger, facility, out)
    recalc_in_place(out)
    hcai = ROOT / "sample_data" / "hcai_buildings_sample.csv"
    extra = seismic.hcai_crosscheck(facility, hcai) if hcai.exists() else []
    allf = res["findings"] + extra
    (out.parent / "findings.json").write_text(json.dumps([f.as_dict() for f in allf], indent=2))
    n = {s: sum(1 for f in allf if f.severity == s) for s in ("error", "warn", "info")}
    print(f"wrote {out}  findings: {n['error']} error, {n['warn']} warn, {n['info']} info")


if __name__ == "__main__":
    main()
