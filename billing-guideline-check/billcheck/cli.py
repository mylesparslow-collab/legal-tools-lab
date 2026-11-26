"""Command line: python -m billcheck intake|check|compare"""

import argparse
import os
import sys

from . import guidelines as G
from . import intake as intake_mod
from . import report
from .engine import check_invoice
from .model import DataError
from .readers import detect_format, ledes_format_warnings, read_invoice_file
from .waivers import load_waivers


def _write(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def write_outputs(result, out_dir):
    """Write every per-invoice output. Returns the list of paths."""
    base = os.path.join(out_dir, result.invoice.invoice_id)
    paths = []
    for suffix, text in (
        (".html", report.html_report(result)),
        (".json", report.result_json(result)),
        (".csv", report.findings_csv(result)),
        (".summary.txt", report.summary_paragraph(result) + "\n"),
    ):
        _write(base + suffix, text)
        paths.append(base + suffix)
    notes = report.timekeeper_notes(result)
    if notes:
        text = ("\n" + "-" * 72 + "\n\n").join(notes[tk] for tk in sorted(notes))
        _write(base + ".timekeeper_notes.txt", text)
        paths.append(base + ".timekeeper_notes.txt")
    return paths


def cmd_intake(args):
    with open(args.document, "r", encoding="utf-8") as handle:
        text = handle.read()
    client_id = args.client_id or os.path.splitext(os.path.basename(args.document))[0]
    proposed = intake_mod.propose_rules(text, client_id, args.client_name or client_id, args.document)
    output = G.dumps(proposed)
    if args.output:
        _write(args.output, output)
        print("wrote %d proposed rules to %s" % (len(proposed["rules"]), args.output))
    else:
        sys.stdout.write(output)
    print("Every rule is proposed and needs confirmation. None is enforced until a person sets status to confirmed.", file=sys.stderr)
    return 0


def cmd_check(args):
    guideline = G.load_guideline(args.guidelines)
    matters = G.load_matters(args.matters) if args.matters else {}
    waivers = load_waivers(args.waivers) if args.waivers else []
    codes = G.load_code_table(args.codes) if args.codes else None
    invoices = read_invoice_file(args.invoice, args.format)
    with open(args.invoice, "r", encoding="utf-8", newline="") as handle:
        raw = handle.read()
    if detect_format(raw) == "ledes" and args.format != "csv":
        for warning in ledes_format_warnings(raw):
            print("format note: %s" % warning, file=sys.stderr)
    for invoice in invoices:
        result = check_invoice(invoice, guideline, matters.get(invoice.matter_id), waivers, codes)
        print(report.summary_paragraph(result))
        if args.out_dir:
            for path in write_outputs(result, args.out_dir):
                print("  wrote %s" % path)
        else:
            for f in result.findings:
                where = "line %d" % f.line_no if f.line_no is not None else "invoice"
                state = "waived" if f.status == "waived" else f.severity_label
                print("  [%s] %s, %s: %s (at risk %s)" % (state, where, f.rule_id, f.explanation, report.fmt_money(f.amount_at_risk)))
    return 0


def cmd_compare(args):
    guides = []
    for path in args.guidelines:
        if os.path.isdir(path):
            guides += G.load_all(path)
        else:
            guides.append(G.load_guideline(path))
    if not guides:
        raise DataError("no guideline files found")
    text = {"text": report.comparison_text, "csv": report.comparison_csv, "html": report.comparison_html}[args.format](guides)
    if args.output:
        _write(args.output, text)
        print("wrote %s" % args.output)
    else:
        sys.stdout.write(text)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m billcheck",
        description="Compare a draft bill to a client's billing rules. Personal portfolio demo, fictional data, not legal or billing advice.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("intake", help="propose candidate rules from a plain-text guideline document")
    p.add_argument("document")
    p.add_argument("--client-id")
    p.add_argument("--client-name")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("check", help="check a draft invoice against a client's confirmed rules")
    p.add_argument("invoice")
    p.add_argument("--guidelines", required=True, help="the client's guideline JSON")
    p.add_argument("--matters", help="matter records JSON (approved timekeepers, rate card, budget)")
    p.add_argument("--waivers", help="waivers JSON")
    p.add_argument("--codes", help="code table JSON")
    p.add_argument("--format", choices=["auto", "ledes", "csv"], default="auto")
    p.add_argument("--out-dir", help="write HTML, JSON, CSV, summary and timekeeper notes here")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("compare", help="table of which clients have which rule types")
    p.add_argument("guidelines", nargs="+", help="guideline JSON files or a folder of them")
    p.add_argument("--format", choices=["text", "csv", "html"], default="text")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_compare)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (DataError, ValueError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
