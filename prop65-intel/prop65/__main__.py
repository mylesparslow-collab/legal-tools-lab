"""Command line: python -m prop65 <command>. Run with no arguments for help."""
from __future__ import annotations
import argparse, json, sys
from datetime import date
from pathlib import Path

from . import analytics, ingest
from .rules import ROOT
from .triage import triage_case
from .verifier import Record, verify_claims, verify_draft

DATA = sorted((ROOT / "data").glob("oag_60day_notices_*.csv.gz"))
SAMPLE = ROOT / "sample"
DATA_NOTE = "Public data downloaded from the California Attorney General's 60-Day Notice Search on November 24, 2026."


def _load():
    if not DATA:
        sys.exit("No OAG data in data/. Run scripts/fetch_oag.py first.")
    return ingest.load(DATA)


def _usd(v):
    return "n/a" if v is None else f"${v:,.0f}"


def cmd_stats(a):
    notices, res = _load()
    s = analytics.summarize(res)
    print(f"{len(notices):,} notices, {s['n_paid']:,} paid settlements and judgments")
    print(f"total payment p25 {_usd(s['total_p25'])}  median {_usd(s['total_p50'])}  p75 {_usd(s['total_p75'])}")
    for r in analytics.firm_table(notices, res, a.top):
        print(f"{r['firm'][:40]:40} notices {r['n_notices']:5}  paid {r['n_paid']:5}  median {_usd(r['total_p50']):>9}")


def cmd_benchmark(a):
    notices, res = _load()
    for b in analytics.benchmark(res, firm=a.firm, chemical=a.chemical, product_class=a.product_class):
        thin = "  (thin sample)" if b["thin_sample"] else ""
        print(f"{b['slice']:45} n={b['n_paid']:5}  p25 {_usd(b['total_p25']):>9}  median {_usd(b['total_p50']):>9}  p75 {_usd(b['total_p75']):>9}{thin}")
    if a.defendant:
        hist = analytics.defendant_history(notices, a.defendant)
        print(f"\n{len(hist)} earlier notices name '{a.defendant}'")
        for n in hist[-10:]:
            print(f"  {n.ag_number} {n.date} {n.plaintiff_attorney[:30]:30} {', '.join(n.chemicals)[:30]:30} {n.source[:50]}")


def _triage(path, record, today):
    case = json.loads(Path(path).read_text(encoding="utf-8"))
    if record is not None:
        pending = any("anchor_status" not in c for c in case.get("claims", {}).values())
        if pending:
            verify_claims(case, record)
    out = triage_case(case, today)
    out["title"] = f"{case['case_id']}: {case.get('defendant', '')}".strip(": ")
    out["note"] = case.get("_note", "")
    out["claims"] = {k: {"value": c["value"], "anchor_status": c.get("anchor_status"), "anchor_message": c.get("anchor_message")} for k, c in case.get("claims", {}).items()}
    return out


def cmd_triage(a):
    record = Record(a.record) if a.record else None
    out = _triage(a.case, record, date.fromisoformat(a.today) if a.today else date.today())
    if a.json:
        print(json.dumps(out, indent=1, default=str)); return
    for k, c in out["claims"].items():
        print(f"claim {k:18} {c['anchor_status']:9} {c['anchor_message'] or ''}")
    for c in out["checks"]:
        print(f"[{c['status']}] {c['check']}: {c['summary']}")
        for r in c["rules"]:
            print(f"      rule: {r['citation']} ({r['status']})")


def cmd_verify(a):
    record = Record(a.record)
    rep = verify_draft(Path(a.draft).read_text(encoding="utf-8"), record, Path(a.draft).stem)
    if a.json:
        print(json.dumps(rep, indent=1)); return
    print(rep["counts"])
    for r in rep["results"]:
        print(f"[{r['status']}] {r['cite'] or '(no cite)'}: {r['assertion'][:90]}")
        for i in r["items"]:
            if i["status"] != "PASS":
                print(f"      {i['type']}: {i['message']}")
    sys.exit(1 if rep["counts"]["FAIL"] else 0)


def cmd_build(a):
    from .report import build_html, build_workbook
    notices, res = _load()
    record = Record(SAMPLE / "record" / "record_index.json")
    today = date.fromisoformat(a.today)
    tri = [_triage(SAMPLE / "cases" / f, record, today) for f in
           ["kelp_crisps_case.json", "kelp_crisps_case_bad_anchor.json", "receipt_paper_case.json", "parking_garage_case.json"]]
    drafts = {p.stem: p.read_text(encoding="utf-8") for p in sorted((SAMPLE / "drafts").glob("*.md"))}
    reps = [verify_draft(t, record, n) for n, t in drafts.items()]
    out = ROOT / "output"; out.mkdir(exist_ok=True)
    build_workbook(notices, res, tri, reps, out / "Prop65_Notice_Desk.xlsx", DATA_NOTE)
    build_html(notices, res, tri, reps, drafts, record, out / "prop65_notice_desk.html", DATA_NOTE, (ROOT / "docs" / "REPORT_CORRECTIONS.md").read_text(encoding="utf-8"))
    (out / "triage_results.json").write_text(json.dumps(tri, indent=1, default=str), encoding="utf-8")
    (out / "record_check_results.json").write_text(json.dumps(reps, indent=1), encoding="utf-8")
    print("wrote", ", ".join(sorted(p.name for p in out.iterdir())))


def main(argv=None):
    p = argparse.ArgumentParser(prog="prop65", description="Proposition 65 notice intelligence and record check (portfolio demo, not legal advice).")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats", help="headline numbers and the most active plaintiff firms"); s.add_argument("--top", type=int, default=15); s.set_defaults(fn=cmd_stats)
    s = sub.add_parser("benchmark", help="settlement percentiles for a firm, chemical and product class")
    s.add_argument("--firm"); s.add_argument("--chemical"); s.add_argument("--product-class"); s.add_argument("--defendant"); s.set_defaults(fn=cmd_benchmark)
    s = sub.add_parser("triage", help="run the deterministic checks on a case file")
    s.add_argument("case"); s.add_argument("--record"); s.add_argument("--today"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_triage)
    s = sub.add_parser("verify", help="check every record cite in a draft")
    s.add_argument("draft"); s.add_argument("--record", required=True); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("build", help="write the workbook, the HTML report and the JSON results to output/")
    s.add_argument("--today", default="2026-11-25"); s.set_defaults(fn=cmd_build)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
