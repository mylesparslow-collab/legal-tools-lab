"""Command line: python -m filingkit {check,sign,record,verify-ledger,judge} ...

Exit codes: 0 ok / clear / valid; 1 usage or input error; 2 blocked (check, sign);
3 invalid (record, verify-ledger); 4 record check incomplete.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import judges
from .authorities import Authorities
from .checklist import DescriptorError, format_text, load_descriptor, run_checklist
from .ledger import Ledger, verify_ledger
from .policy import load_policy
from .record import SignError, load_record, log_checklist, sign_filing, verify_record
from .render import record_html
from .util import now_iso, parse_ts, write_json


def _common(p):
    p.add_argument("--judge-orders", default=judges.DEFAULT_PATH, help="judge orders JSON file")
    p.add_argument("--policy", default=None, help="firm policy JSON file (overrides data/policy.json)")
    p.add_argument("--as-of", default=None, help="ISO timestamp to use as 'now' (default: current time)")


def _context(a):
    return {"judge_orders": judges.load_orders(a.judge_orders), "policy": load_policy(a.policy),
            "authorities": Authorities(), "now": a.as_of}


def cmd_check(a) -> int:
    desc, base = load_descriptor(a.filing)
    result = run_checklist(desc, base, **_context(a))
    if a.ledger:
        log_checklist(Ledger(a.ledger), result, now=result["generated_at"])
    if a.out:
        write_json(a.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False) if a.json else format_text(result))
    return 0 if result["clear_to_file"] else 2


def cmd_sign(a) -> int:
    desc, base = load_descriptor(a.filing)
    try:
        out = sign_filing(desc, base, signer=a.signer, attest=a.attest, out_dir=a.out_dir, ledger_path=a.ledger,
                          **_context(a))
    except SignError as e:
        print(f"Sign-off refused: {e}", file=sys.stderr)
        if e.result is not None:
            print(format_text(e.result))
        return 2
    print(f"Signed. Record: {out['json_path']}")
    print(f"Printable page: {out['html_path']}")
    print(f"Ledger entry {out['ledger_entry']['seq']}: {out['ledger_entry']['hash']}")
    return 0


def cmd_record(a) -> int:
    rec = load_record(a.record)
    res = verify_record(rec, document_path=a.document, ledger_path=a.ledger)
    if a.log and a.ledger and res["checks"].get("ledger_intact"):
        Ledger(a.ledger).append({"event": "record_verification", "filing_id": res["filing_id"],
                                 "record_sha256": res["record_sha256"], "status": res["status"],
                                 "problems": res["problems"]}, now=now_iso(a.as_of))
    if a.html:
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(record_html(rec))
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"Record {res['filing_id']}: {res['status']}")
        for name, ok in res["checks"].items():
            print(f"  {name}: {'not checked' if ok is None else 'ok' if ok else 'FAILED'}")
        for p in res["problems"]:
            print(f"  - {p}")
        if res["status"] == "INCOMPLETE":
            print("  Give --document and --ledger for a full check.")
    return {"VALID": 0, "INVALID": 3, "INCOMPLETE": 4}[res["status"]]


def cmd_verify_ledger(a) -> int:
    res = verify_ledger(a.ledger, expect_head=a.expect_head)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Ledger {a.ledger}: {'chain intact' if res['ok'] else 'TAMPERING OR DAMAGE DETECTED'}")
        print(f"  entries: {res['entries']}  head: {res['head']}")
        for p in res["problems"]:
            print(f"  - line {p['line']}" + (f" (seq {p['seq']})" if p["seq"] is not None else "") + f": {p['problem']}")
    return 0 if res["ok"] else 3


def cmd_judge(a) -> int:
    data = judges.load_orders(a.judge_orders)
    if a.list:
        for e in data["entries"]:
            print(f"{e['entry_id']}  {e['court_id']}  {e['judge_id'] or '(court-wide)'}  {e['requirement_type']}  "
                  f"last checked {e['last_checked']}")
        return 0
    if not a.court_id:
        print("judge: --court-id is required (or use --list)", file=sys.stderr)
        return 1
    as_of = parse_ts(now_iso(a.as_of)).date()
    days = a.staleness_days if a.staleness_days is not None else load_policy(a.policy)["judge_entry_staleness_days"]
    res = judges.lookup(data, a.court_id, a.judge_id, as_of, days)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    label = {"not_checked": "NOT CHECKED", "stale": "RECHECK BEFORE RELYING", "current": "CURRENT"}[res["status"]]
    print(f"Status: {label}")
    print(res["message"])
    if res["fictional_sample_data"]:
        print("(Fictional sample data. No real court or judge.)")
    for e in res["entries"]:
        print(f"  {e['entry_id']}  {e['judge'] or 'court-wide'}")
        print(f"    order: {e['order_title']}")
        print(f"    requirement: {e['requirement_type']} (applies: {e['applies_when']})")
        if e["required_text"]:
            print(f"    required text: {e['required_text']}")
        print(f"    effective: {e['effective_date'] or 'n/a'}   last checked: {e['last_checked']} by {e['checked_by']}"
              + ("   STALE" if e["stale"] else ""))
        print(f"    source: {e['source_url']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m filingkit",
                                 description="Filing verification kit (demo, fictional data, not legal advice).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="run the pre-filing checklist for a filing descriptor")
    p.add_argument("filing")
    p.add_argument("--out", help="write the checklist result as JSON")
    p.add_argument("--ledger", help="append a checklist_run entry to this ledger")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    _common(p)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("sign", help="sign off a filing that is clear to file and write its record")
    p.add_argument("filing")
    p.add_argument("--signer", required=True, help="name of the signing attorney")
    p.add_argument("--attest", action="store_true", help="the signer makes the sign-off statement")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--ledger", required=True)
    _common(p)
    p.set_defaults(fn=cmd_sign)

    p = sub.add_parser("record", help="check a saved record against the document and the ledger")
    p.add_argument("record")
    p.add_argument("--document", help="the document file as it is now")
    p.add_argument("--ledger")
    p.add_argument("--html", help="write the printable page again to this path")
    p.add_argument("--log", action="store_true", help="append the outcome to the ledger")
    p.add_argument("--json", action="store_true")
    p.add_argument("--as-of", default=None)
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("verify-ledger", help="check the ledger hash chain")
    p.add_argument("ledger")
    p.add_argument("--expect-head", help="head hash saved elsewhere, to detect removed trailing entries")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_verify_ledger)

    p = sub.add_parser("judge", help="look up judge or court AI orders")
    p.add_argument("--court-id")
    p.add_argument("--judge-id")
    p.add_argument("--staleness-days", type=int)
    p.add_argument("--list", action="store_true")
    p.add_argument("--json", action="store_true")
    _common(p)
    p.set_defaults(fn=cmd_judge)
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except (DescriptorError, judges.JudgeDataError, OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
