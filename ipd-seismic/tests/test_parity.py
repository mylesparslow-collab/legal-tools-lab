"""Recalculate the workbook with LibreOffice and compare its formulas' results
with the Python engine. Skipped when LibreOffice is not installed."""
import shutil
import subprocess
from datetime import datetime

import openpyxl
import pytest

import build_workbook
from engine.common import D

SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")
pytestmark = pytest.mark.skipif(SOFFICE is None, reason="LibreOffice not installed")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    import json
    from pathlib import Path
    root = Path(build_workbook.__file__).parent
    ledger = json.loads((root / "sample_data" / "ifoa_ledger.json").read_text())
    campus = json.loads((root / "sample_data" / "seismic_campus.json").read_text())
    tmp = tmp_path_factory.mktemp("wb")
    src = tmp / "model.xlsx"
    res = build_workbook.build(ledger, campus, src)
    subprocess.run([SOFFICE, "--headless", "--convert-to", "xlsx", "--outdir", str(tmp / "out"), str(src)],
                   check=True, capture_output=True, timeout=180,
                   env={"HOME": str(tmp), "PATH": "/usr/bin:/bin"})
    wb = openpyxl.load_workbook(tmp / "out" / "model.xlsx", data_only=True)
    return res, wb


def near(a, b):
    return abs(D(a) - D(b)) <= D("0.005")


def test_no_formula_errors(built):
    _, wb = built
    bad = [(ws.title, c.coordinate, c.value) for ws in wb for row in ws.iter_rows() for c in row
           if isinstance(c.value, str) and c.value.startswith(("#", "Err:"))]
    assert bad == []


def test_ledger_running_totals(built):
    res, wb = built
    ws, first = wb["Ledger"], res["cmap"]["ledger"]["first"]
    for i, s in enumerate(res["states"]):
        r = first + i
        for col, key in (("L", "target_cost"), ("M", "shared_contingency"), ("N", "owner_contingency"),
                         ("O", "emp"), ("P", "icl_total"), ("S", "shared_balance"), ("T", "owner_balance")):
            assert near(ws[f"{col}{r}"].value, s[key]), (col, r)


def test_ledger_checks_match_engine_findings(built):
    res, wb = built
    ws, first = wb["Ledger"], res["cmap"]["ledger"]["first"]
    flagged = {int(f.where.split()[1]) for f in res["findings"]
               if f.severity == "error" and f.code.startswith("L") and f.where.startswith("Amendment")}
    review = {ws[f"A{r}"].value for r in range(first, res["cmap"]["ledger"]["last"] + 1) if ws[f"AJ{r}"].value == "REVIEW"}
    assert review == flagged == {6, 8}
    assert ws[f"AF{first + 6}"].value == "NOT 100%" and ws[f"AA{first + 8}"].value == "MISMATCH"


def test_waterfall(built):
    res, wb = built
    ws, w = wb["Waterfall"], res["waterfall"]
    for cell, key in (("B15", "overrun"), ("B16", "tier1_shared_contingency"), ("B17", "tier2_icl"),
                      ("B18", "tier3_owner_contingency"), ("B19", "tier4_owner_at_cost"), ("B22", "savings"),
                      ("B25", "icl_pool_final"), ("B27", "team_savings"), ("B28", "owner_savings"),
                      ("B31", "owner_total"), ("B32", "emp_headroom")):
        assert near(ws[cell].value, w[key]), cell
    assert ws["B20"].value == ws["B34"].value == ws["B35"].value == "OK"


def test_member_payouts(built):
    res, wb = built
    ws = wb["Members"]
    for m, r in res["cmap"]["members"].items():
        assert near(ws[f"F{r}"].value, res["waterfall"]["payouts"][m]), m
    t = res["cmap"]["members_total_row"]
    assert ws[f"E{t + 1}"].value == "OK" and ws[f"F{t + 2}"].value == "OK"


def test_sensitivity_rows(built):
    from engine import ipd
    res, wb = built
    ws, last = wb["Sensitivity"], res["states"][-1]
    terms = {"team_savings_pct": 50, "owner_savings_pct": 50, "icl_cap_multiple": 2.0}
    for i in range(len(res["cmap"]["sensitivity"]["factors"])):
        r = res["cmap"]["sensitivity"]["first"] + i
        w = ipd.waterfall(last, terms, ws[f"B{r}"].value)
        for col, key in (("C", "overrun"), ("D", "tier1_shared_contingency"), ("E", "tier2_icl"),
                         ("F", "tier3_owner_contingency"), ("G", "tier4_owner_at_cost"), ("I", "team_savings"),
                         ("J", "icl_pool_final"), ("L", "owner_total"), ("M", "emp_headroom")):
            assert near(ws[f"{col}{r}"].value, w[key]), (col, r)


def test_seismic_sheets(built):
    res, wb = built
    sz, bd, ms = wb["Seismic"], wb["Buildings"], wb["Milestones"]
    assert sz["B29"].value == "Passes screen" and sz["B36"].value == datetime(2032, 7, 1)
    assert sz["B45"].value == 165 and sz["B55"].value == sz["B62"].value == "OK"
    fx = res["fines"]
    assert (sz["B49"].value, sz["B50"].value) == (fx["accrued"]["max_days"], fx["accrued"]["sum_days"])
    assert (sz["B56"].value, sz["B57"].value) == (fx["projected"]["max_days"], fx["projected"]["sum_days"])
    assert sz["B53"].value == fx["accrued"]["per_facility"] and sz["B64"].value == 2
    for b in res["buildings"]:
        r = res["cmap"]["buildings"][b["building_nbr"]]
        assert bd[f"N{r}"].value == b["status"]
        assert (bd[f"M{r}"].value in (None, "")) if b["float_days"] is None else bd[f"M{r}"].value == b["float_days"]
        assert (bd[f"O{r}"].value or "") == b["notice"]
    for m in res["milestones"]:
        r = res["cmap"]["milestones"][m["id"]]
        assert (ms[f"I{r}"].value, ms[f"J{r}"].value, ms[f"K{r}"].value) == \
               (m["slip_days"], m["accrued_late_days"], m["projected_late_days"]), m["id"]
