#!/usr/bin/env python3
"""Runs the whole kit over the fictional sample filings and writes output/ and index.html.

    python run_demo.py

Uses a fixed clock so the outputs are the same on every run.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from filingkit import judges  # noqa: E402
from filingkit.authorities import Authorities  # noqa: E402
from filingkit.checklist import format_text, load_descriptor, run_checklist  # noqa: E402
from filingkit.demo_page import build_page  # noqa: E402
from filingkit.ledger import Ledger, verify_ledger  # noqa: E402
from filingkit.policy import load_policy  # noqa: E402
from filingkit.record import SignError, log_checklist, sign_filing, verify_record  # noqa: E402
from filingkit.util import parse_ts, write_json  # noqa: E402

OUT = os.path.join(ROOT, "output")
SAMPLES = os.path.join(ROOT, "sample_filings")
CHECK_AT = "2027-01-12T17:00:00+00:00"
SIGN_AT = "2027-01-12T17:30:00+00:00"
LATER = "2027-01-13T09:15:00+00:00"
NOTES = {
    "F-2027-001": "Every citation attested, AI use disclosed, judge entry current.",
    "F-2027-002": "All three citations pass the machine check, but the attorney attested only two.",
    "F-2027-003": "Clear and signed here. Step 6 shows what happens when the document is edited afterwards.",
    "F-2027-004": "Discovery paper. Citation items are advisory under the default policy; AI-use items still apply.",
    "F-2027-005": "Generative AI was used and nothing records whether or how it will be disclosed.",
    "F-2027-006": "This fictional judge requires a certification; the filing records that it was added.",
    "F-2027-007": "The entry for this fictional judge was last checked more than 30 days ago.",
    "F-2027-008": "One citation was not found and one quotation does not match. An attorney note does not clear either.",
}


def w(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for sub in ("checklists", "records", "ledger", "edited_after_signoff", "tamper_demo"):
        os.makedirs(os.path.join(OUT, sub))
    ctx = {"judge_orders": judges.load_orders(), "policy": load_policy(), "authorities": Authorities()}
    ledger_path = os.path.join(OUT, "ledger", "verification_ledger.jsonl")
    ledger = Ledger(ledger_path)

    scenarios, summary, signed = [], [], {}
    for fid in sorted(os.listdir(SAMPLES)):
        desc, base = load_descriptor(os.path.join(SAMPLES, fid, "filing.json"))
        result = run_checklist(desc, base, now=CHECK_AT, **ctx)
        log_checklist(ledger, result, now=CHECK_AT)
        write_json(os.path.join(OUT, "checklists", f"{fid}.checklist.json"), result)
        w(os.path.join(OUT, "checklists", f"{fid}.checklist.txt"), format_text(result))
        scenarios.append({"scenario": desc["scenario"], "title": desc["document"]["title"], "note": NOTES[fid],
                          "checklist": result})
        signer = desc["responsible_attorney"]["name"]
        try:
            out = sign_filing(desc, base, signer=signer, attest=True, out_dir=os.path.join(OUT, "records"),
                              ledger_path=ledger_path, now=SIGN_AT, **ctx)
            signed[fid] = (desc, base, out)
            outcome = "signed"
        except SignError as e:
            outcome = "sign-off refused"
            w(os.path.join(OUT, "checklists", f"{fid}.sign_refused.txt"), f"Sign-off refused: {e}")
        summary.append(f"{fid}  {result['result']:<14} {outcome:<17} {desc['scenario']}")
        print(summary[-1])

    # document edited after sign-off
    fid = "F-2027-003"
    desc, base, out = signed[fid]
    ed_dir = os.path.join(OUT, "edited_after_signoff")
    filing_copy = os.path.join(ed_dir, "filing")
    shutil.copytree(base, filing_copy)
    original = os.path.join(base, desc["document"]["path"])
    edited = os.path.join(filing_copy, desc["document"]["path"])
    with open(edited, "a", encoding="utf-8") as f:
        f.write("Added after sign-off: see also Renwick v. Tallmadge Freight Systems (2022) 940 Cal.App.5th 1312.\n")
    before = verify_record(out["record"], document_path=original, ledger_path=ledger_path)
    after = verify_record(out["record"], document_path=edited, ledger_path=ledger_path)
    ledger.append({"event": "record_verification", "filing_id": fid, "record_sha256": after["record_sha256"],
                   "status": after["status"], "problems": after["problems"]}, now=LATER)
    desc2, base2 = load_descriptor(os.path.join(filing_copy, "filing.json"))
    recheck = run_checklist(desc2, base2, now=LATER, **ctx)
    log_checklist(ledger, recheck, now=LATER)
    write_json(os.path.join(ed_dir, "record_check_before_edit.json"), before)
    write_json(os.path.join(ed_dir, "record_check_after_edit.json"), after)
    write_json(os.path.join(ed_dir, "checklist_after_edit.json"), recheck)
    w(os.path.join(ed_dir, "checklist_after_edit.txt"), format_text(recheck))
    print(f"{fid}  record before edit: {before['status']}; after edit: {after['status']}; recheck: {recheck['result']}")

    # ledger check, then a tampered copy
    check = verify_ledger(ledger_path)
    write_json(os.path.join(OUT, "ledger", "ledger_check.json"), check)
    tampered = os.path.join(OUT, "tamper_demo", "ledger_tampered.jsonl")
    lines = open(ledger_path, encoding="utf-8").read().splitlines()
    target = next(i for i, line in enumerate(lines) if '"sign_refused"' not in line and '"record_signed"' in line)
    entry = json.loads(lines[target])
    entry["signer"] = "Someone Else (fictional)"
    lines[target] = json.dumps(entry, ensure_ascii=False)
    w(tampered, "\n".join(lines))
    tcheck = verify_ledger(tampered)
    write_json(os.path.join(OUT, "tamper_demo", "ledger_tampered_check.json"), tcheck)
    what = (f"In a copy of the ledger, the signer name in entry {entry['seq']} was changed by hand. "
            "The chain check reports it.")
    print(f"ledger: {'intact' if check['ok'] else 'BROKEN'} ({check['entries']} entries); tampered copy: "
          f"{'intact' if tcheck['ok'] else 'detected'}")

    # judge lookups
    as_of = parse_ts(CHECK_AT).date()
    examples = []
    for title, court, judge in (("Judge with a current entry and a certification order", "fict-alder-ridge", "fict-ostergaard"),
                                ("Judge with a stale entry", "fict-port-selwyn", "fict-marrowby"),
                                ("Judge with no entry", "fict-alder-ridge", "fict-unlisted")):
        res = judges.lookup(ctx["judge_orders"], court, judge, as_of, ctx["policy"]["judge_entry_staleness_days"])
        examples.append({"title": title, **res})
    write_json(os.path.join(OUT, "judge_lookups.json"), examples)

    w(os.path.join(OUT, "SUMMARY.txt"), "\n".join(
        ["Filing verification kit demo run (fixed clock, fictional data, not legal advice)", ""] + summary + [
            "", f"{fid} record against signed document: {before['status']}",
            f"{fid} record against edited document: {after['status']}",
            f"{fid} checklist on edited document: {recheck['result']}",
            f"Ledger: {'chain intact' if check['ok'] else 'BROKEN'}, {check['entries']} entries",
            f"Tampered ledger copy: {'not detected' if tcheck['ok'] else 'detected'}"]))

    # demo page
    walk_id = "F-2027-001"
    wdesc, wbase, wout = signed[walk_id]
    auth = Authorities()
    page = build_page({
        "walk": {"descriptor": wdesc, "checklist": wout["checklist"], "record": wout["record"],
                 "document_text": open(os.path.join(wbase, wdesc["document"]["path"]), encoding="utf-8").read(),
                 "record_html": f"output/records/{walk_id}.record.html",
                 "record_json": f"output/records/{walk_id}.record.json"},
        "ledger_entries": ledger.entries(), "ledger_check": check, "scenarios": scenarios,
        "edited": {"filing_id": fid, "before": before, "after": after, "recheck": recheck},
        "tamper": {"what": what, "check": tcheck}, "judge_examples": examples,
        "authorities": auth.snapshot(auth.items.keys()),
        "auth_sections": {k: v["section"] for k, v in auth.items.items()},
    })
    w(os.path.join(ROOT, "index.html"), page)
    print("Wrote output/ and index.html")


if __name__ == "__main__":
    main()
