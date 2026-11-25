"""Compare findings with the answer key of planted violations."""

import json
import os

from . import guidelines as G
from .engine import check_invoice
from .readers import read_invoice_file
from .waivers import load_waivers


def invoice_files(data_dir):
    folder = os.path.join(data_dir, "invoices")
    return sorted(os.path.join(folder, name) for name in os.listdir(folder) if name.endswith((".csv", ".txt")))


def check_all(data_dir):
    """Run every sample invoice against its client's guideline. Returns a list of CheckResult."""
    guides = {g.client_id: g for g in G.load_all(os.path.join(data_dir, "guidelines"))}
    matters = G.load_matters(os.path.join(data_dir, "matters.json"))
    waivers = load_waivers(os.path.join(data_dir, "waivers.json"))
    codes = G.load_code_table(os.path.join(data_dir, "utbms_sample_codes.json"))
    results = []
    for path in invoice_files(data_dir):
        for invoice in read_invoice_file(path):
            results.append(
                check_invoice(invoice, guides[invoice.client_id], matters.get(invoice.matter_id), waivers, codes)
            )
    return results


def _key(invoice_id, line_no, timekeeper_id, rule_id):
    # Timekeeper only distinguishes findings that are not tied to a line.
    return (invoice_id, line_no, timekeeper_id if line_no is None else "", rule_id)


def score(results, answer_key):
    """Return counts and lists: planted found/missed, false positives, clean lines."""
    findings = {}
    for result in results:
        for f in result.findings:
            findings[_key(f.invoice_id, f.line_no, f.timekeeper_id, f.rule_id)] = f
    planted = {}
    for item in answer_key["planted"]:
        planted[_key(item["invoice_id"], item["line_no"], item["timekeeper_id"], item["rule_id"])] = item
    found, missed, wrong_status = [], [], []
    for key, item in planted.items():
        f = findings.get(key)
        if f is None:
            missed.append(item)
        elif f.status != item["expected_status"]:
            wrong_status.append(item)
        else:
            found.append(item)
    false_positives = [f.to_dict() for key, f in sorted(findings.items(), key=lambda kv: str(kv[0])) if key not in planted]
    planted_lines = {(i["invoice_id"], i["line_no"]) for i in answer_key["planted"] if i["line_no"] is not None}
    total_lines = sum(answer_key["invoice_line_counts"].values())
    clean_lines = total_lines - len(planted_lines)
    clean_lines_flagged = sorted(
        {(f["invoice_id"], f["line_no"]) for f in false_positives if f["line_no"] is not None and (f["invoice_id"], f["line_no"]) not in planted_lines}
    )
    return {
        "planted_total": len(planted),
        "planted_found": len(found),
        "planted_missed": missed,
        "planted_wrong_status": wrong_status,
        "false_positive_count": len(false_positives),
        "false_positives": false_positives,
        "total_lines": total_lines,
        "clean_lines": clean_lines,
        "clean_lines_flagged": [list(x) for x in clean_lines_flagged],
    }


def load_answer_key(data_dir):
    with open(os.path.join(data_dir, "ANSWER_KEY.json"), "r", encoding="utf-8") as handle:
        return json.load(handle)
