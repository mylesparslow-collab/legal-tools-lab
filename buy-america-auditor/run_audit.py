"""Run the audit on a case file and bill of materials.

    python run_audit.py                      # uses sample_data/, writes to output/
    python run_audit.py --case c.json --bom b.csv --out out_dir
"""
import argparse
import json
from pathlib import Path

from buy_america.engine import Rules, run
from buy_america.report import findings_markdown
from buy_america.workbook import build_workbook

HERE = Path(__file__).parent


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default=HERE / "sample_data" / "case.json")
    ap.add_argument("--bom", default=HERE / "sample_data" / "bom.csv")
    ap.add_argument("--out", default=HERE / "output")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rules = Rules()
    audit = run(args.case, args.bom, rules)
    (out / "findings.json").write_text(json.dumps(audit, indent=2) + "\n")
    (out / "findings.md").write_text(findings_markdown(audit, rules))
    build_workbook(audit, args.case, args.bom, out / "Buy_America_BOM_Audit.xlsx", rules)
    for p in audit["projects"]:
        print(f"{p['project_id']:12} {p['overall']}")
    print(f"Wrote findings.json, findings.md and Buy_America_BOM_Audit.xlsx to {out}")


if __name__ == "__main__":
    main()
