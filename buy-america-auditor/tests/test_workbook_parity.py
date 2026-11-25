"""Recalculate the workbook in LibreOffice and check its formulas agree with the engine."""
import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

from buy_america.engine import Rules, run
from buy_america.workbook import build_workbook

ROOT = Path(__file__).resolve().parents[1]
CASE, BOM = ROOT / "sample_data" / "case.json", ROOT / "sample_data" / "bom.csv"
SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("wb")
    audit = run(CASE, BOM)
    layout = build_workbook(audit, CASE, BOM, tmp / "audit.xlsx", Rules())
    return audit, layout, tmp


def test_workbook_arithmetic_is_formulas_not_pasted_values(built):
    _, layout, tmp = built
    wb = load_workbook(tmp / "audit.xlsx")
    lay = layout["TB-BEB-40"]
    ws = wb[lay["sheet"]]
    assert str(ws.cell(row=lay["first"], column=12).value).startswith("=IF(")
    assert "Rules!" in str(ws["B6"].value)
    assert str(wb["Summary"]["D6"].value).startswith("=")


@pytest.mark.skipif(not SOFFICE, reason="LibreOffice not installed")
def test_recalculated_workbook_matches_engine(built):
    audit, layout, tmp = built
    out = tmp / "recalc"
    subprocess.run([SOFFICE, f"-env:UserInstallation=file://{tmp}/lo", "--headless", "--convert-to",
                    "xlsx:Calc MS Excel 2007 XML", "--outdir", str(out), str(tmp / "audit.xlsx")],
                   check=True, capture_output=True, timeout=180)
    wb = load_workbook(out / "audit.xlsx", data_only=True)
    for p in audit["projects"]:
        lay = layout[p["project_id"]]
        ws = wb[lay["sheet"]]
        if lay["kind"] == "rolling_stock":
            res = p["rolling_stock"][0]
            for i, c in enumerate(res["components"]):
                assert ws.cell(row=lay["first"] + i, column=12).value == pytest.approx(c["counted"]), c["line_id"]
            t = lay["total_row"]
            assert ws.cell(row=t, column=12).value == pytest.approx(res["domestic_cost"])
            assert ws.cell(row=t + 1, column=2).value == pytest.approx(res["domestic_pct"])
            assert ws.cell(row=t + 2, column=2).value == res["status"]
            assert ws.cell(row=t + 3, column=2).value == pytest.approx(res["shortfall_usd"])
            assert ws["B6"].value == res["threshold_pct"]
        else:
            for i, r in enumerate(p["infrastructure"]):
                row = lay["first"] + i
                assert ws.cell(row=row, column=12).value == r["fta_661_5d"], r["line_id"]
                assert ws.cell(row=row, column=13).value == r["baba_184"], r["line_id"]
