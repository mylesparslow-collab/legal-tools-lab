"""Command line: python -m desk parse|match|draft|matrix|harvest|check-data"""
import argparse
import datetime as dt
import json
import os
import sys

from . import render
from .evaluate import evaluate, report_markdown as eval_report
from .harvest import harvest, report_markdown as harvest_report, set_outcome
from .loader import load_data
from .pipeline import build
from .rfp import parse_rfp
from .util import load_holidays

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA = os.path.join(ROOT, "data", "library")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote %s" % path)


def _common(p):
    p.add_argument("--data", default=DEFAULT_DATA, help="library folder (default: data/library)")
    p.add_argument("--mapping", help="mapping file (default: mapping.json in the library folder)")
    p.add_argument("--as-of", default=dt.date.today().isoformat(), help="date to work from, YYYY-MM-DD (default: today)")
    p.add_argument("--holidays", help="holiday file: JSON list or one ISO date per line")
    p.add_argument("--status", help="JSON file marking matrix items done: {\"F1\": {\"done\": true, \"by\": \"name\"}}")


def _build(args):
    data = load_data(args.data, args.mapping)
    status = json.loads(_read(args.status)) if args.status else None
    res = build(_read(args.rfp), data, args.as_of, load_holidays(args.holidays), status)
    if data.errors:
        print("warning: %d library record(s) rejected on load; run check-data" % len(data.errors), file=sys.stderr)
    for w in data.warnings:
        print("warning: %s" % w, file=sys.stderr)
    return res


def write_draft_outputs(res, out):
    _write(os.path.join(out, "draft.md"), render.draft_markdown(res))
    _write(os.path.join(out, "draft.html"), render.draft_html(res))
    _write(os.path.join(out, "go_no_go.md"), render.go_no_go_markdown(res))
    _write(os.path.join(out, "conflicts_parties.csv"), render.conflicts_csv(res))
    _write(os.path.join(out, "conflicts_parties.md"), render.conflicts_markdown(res))


def write_matrix_outputs(res, out):
    _write(os.path.join(out, "matrix.html"), render.matrix_html(res))
    _write(os.path.join(out, "matrix.csv"), render.matrix_csv(res))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m desk",
                                 description="Proposal desk demo. Synthetic data only. Not legal advice.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="parse an RFP and print what was found")
    p.add_argument("rfp")
    p.add_argument("--json", help="write the parsed RFP as JSON to this file")
    p.add_argument("--key", help="answer key JSON: print precision and recall against it")

    p = sub.add_parser("match", help="choose experience records and team for an RFP, with reasons")
    p.add_argument("rfp")
    _common(p)

    p = sub.add_parser("draft", help="write draft.md, draft.html, go_no_go.md and the conflicts party list")
    p.add_argument("rfp")
    p.add_argument("--out", required=True)
    _common(p)

    p = sub.add_parser("matrix", help="write the compliance matrix as HTML and CSV")
    p.add_argument("rfp")
    p.add_argument("--out", required=True)
    _common(p)

    p = sub.add_parser("harvest", help="file final answers back into the library, or record an outcome")
    p.add_argument("final", nargs="?", help="final response as Markdown")
    p.add_argument("--rfp", help="the RFP the response answered")
    p.add_argument("--outcome", default="pending", choices=["won", "lost", "pending"])
    p.add_argument("--submitted", help="submission date, YYYY-MM-DD (default: the RFP deadline)")
    p.add_argument("--proposal-id")
    p.add_argument("--set-outcome", nargs=2, metavar=("PROPOSAL_ID", "OUTCOME"),
                   help="record won, lost or pending for a harvested proposal")
    p.add_argument("--data", default=DEFAULT_DATA)
    p.add_argument("--mapping")

    p = sub.add_parser("check-data", help="load the library through the mapping and report rejected records")
    p.add_argument("--data", default=DEFAULT_DATA)
    p.add_argument("--mapping")

    args = ap.parse_args(argv)

    if args.cmd == "parse":
        rfp = parse_rfp(_read(args.rfp))
        sys.stdout.write(render.parse_summary(rfp))
        if args.json:
            _write(args.json, json.dumps(rfp, indent=1, ensure_ascii=False) + "\n")
        if args.key:
            res = evaluate(rfp, json.loads(_read(args.key)))
            sys.stdout.write("\n" + eval_report({os.path.basename(args.rfp): res}))
        return 0
    if args.cmd == "match":
        sys.stdout.write(render.match_markdown(_build(args)))
        return 0
    if args.cmd == "draft":
        res = _build(args)
        write_draft_outputs(res, args.out)
        g = res["go_no_go"]
        print("coverage %d%%, open disqualifiers %d, blocking flags %d" % (
            g["coverage"]["pct"], g["open_disqualifiers"], len(g["blocking_flags"])))
        return 0
    if args.cmd == "matrix":
        res = _build(args)
        write_matrix_outputs(res, args.out)
        print("open disqualifiers %d" % res["go_no_go"]["open_disqualifiers"])
        return 0
    if args.cmd == "harvest":
        if args.set_outcome:
            pid, outcome = args.set_outcome
            if outcome not in ("won", "lost", "pending"):
                ap.error("outcome must be won, lost or pending")
            n = set_outcome(args.data, pid, outcome)
            if not n:
                print("no harvested answers found for %s; proposals in the firm's own files are updated at source" % pid)
                return 1
            print("recorded %s on %d answer(s) of %s" % (outcome, n, pid))
            return 0
        if not args.final or not args.rfp:
            ap.error("harvest needs FINAL and --rfp, or --set-outcome")
        data = load_data(args.data, args.mapping)
        rep = harvest(_read(args.final), _read(args.rfp), data, args.outcome, args.submitted, args.proposal_id)
        sys.stdout.write(harvest_report(rep))
        return 0
    if args.cmd == "check-data":
        data = load_data(args.data, args.mapping)
        print("answers %d, experience %d, bios %d, rate schedules %d, references %d, forms %d" % (
            len(data.answers), len(data.experience), len(data.bios), len(data.rate_schedules),
            len(data.references), len(data.forms)))
        print("firm facts as of %s" % data.facts["as_of"])
        print("experience records without consent to name the client: %d of %d" % (
            sum(1 for e in data.experience if e["consent_to_name_client"] is not True), len(data.experience)))
        print("reference records without consent to list the contact: %d of %d" % (
            sum(1 for r in data.references if r["consent_to_list_contact"] is not True), len(data.references)))
        for w in data.warnings:
            print("WARNING %s" % w)
        for e in data.errors:
            print("REJECTED %s row %s (%s): %s" % (e["schema"], e["row"], e["id"], "; ".join(e["problems"])))
        print("rejected records: %d" % len(data.errors))
        return 1 if data.errors else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
