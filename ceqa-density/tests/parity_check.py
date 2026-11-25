"""Recalculate the density workbook in LibreOffice for several input variants and confirm the live
formulas equal the Python engine. Run: python3 tests/parity_check.py  (needs `soffice` on PATH)"""
import json, subprocess, sys, tempfile
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import density as de  # noqa: E402

VARIANTS = {
    "mixed_vli15_mod15": ("site_mixed_income.json", {}),
    "sb4_100pct": ("site_sb4.json", {}),
    "sb4_near_transit": ("site_sb4.json", {"near_major_transit": True}),
    "li_10pct": ("site_mixed_income.json", {"base_path": "LI", "base_affordable_units": 10, "add_path": "NONE", "near_major_transit": False}),
    "li_24_plus_vli_10": ("site_mixed_income.json", {"base_path": "LI", "base_affordable_units": 24, "add_path": "VLI", "add_units": 10}),
    "mod44_plus_mod15_over_cap": ("site_mixed_income.json", {"base_path": "MOD_SALE", "base_affordable_units": 43, "add_path": "MOD", "add_units": 15}),
    "mod44_plus_mod5": ("site_mixed_income.json", {"base_path": "MOD_SALE", "base_affordable_units": 43, "add_path": "MOD", "add_units": 5}),
    "vli_below_min": ("site_mixed_income.json", {"base_affordable_units": 4, "add_path": "NONE"}),
    "vli_16_four_concessions": ("site_mixed_income.json", {"base_affordable_units": 16, "add_path": "NONE"}),
    "senior": ("site_mixed_income.json", {"base_path": "SENIOR", "add_path": "NONE"}),
    "special_10pct": ("site_mixed_income.json", {"base_path": "SPECIAL", "base_affordable_units": 11, "add_path": "NONE"}),
    "student_22": ("site_mixed_income.json", {"base_path": "STUDENT", "base_affordable_units": 22, "add_path": "NONE"}),
    "odd_acreage": ("site_mixed_income.json", {"site_acres": 1.37, "zoning_density_du_ac": 27, "base_affordable_units": 6, "add_units": 4}),
}
ok = True
with tempfile.TemporaryDirectory() as td:
    for name, (f, over) in VARIANTS.items():
        site = json.loads((ROOT / "sample_data" / f).read_text()); site["calc"].update(over)
        sp = Path(td) / f"{name}.json"; sp.write_text(json.dumps(site))
        out = Path(td) / f"{name}.xlsx"
        ref = de.write_workbook(site, out)
        rd = Path(td) / "re"; rd.mkdir(exist_ok=True)
        subprocess.run(["soffice", "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(rd), str(out)], check=True, capture_output=True, timeout=300)
        ws = load_workbook(rd / out.name, data_only=True)["Engine Check"]
        verdict = next(r[1] for r in ws.iter_rows(values_only=True) if r[0] == "All checks match?")
        print(f"{name:28s} base={ref['base_units']:>4} total={ref['total_units']:>4} concessions={ref['concessions']} parking={ref['max_required_parking']:>4}  formulas match: {verdict}")
        if verdict != "YES":
            for r in ws.iter_rows(values_only=True):
                print("   ", r)
        ok &= verdict == "YES"
sys.exit(0 if ok else 1)
