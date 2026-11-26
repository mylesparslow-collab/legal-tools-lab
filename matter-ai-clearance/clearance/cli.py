"""Command line: python -m clearance scan-terms | clear | tracker | diff."""
import argparse
import json
import sys
from pathlib import Path

from . import DATA
from . import clauses, engine, lanes, reports
from .store import Store, load_json, load_policy


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _dump(obj):
    return json.dumps(obj, indent=1) + "\n"


def evaluate_all(store, patterns, answer_key_path=None):
    entries = store.all_document_entries()
    results = {d["id"]: store.scan(d["id"], patterns) for d in entries}
    splits = {d["id"]: d.get("eval_split", "dev") for d in entries}
    key = load_json(answer_key_path or store.dir / "answer_key.json")
    return clauses.evaluate(key, results, splits)


def cmd_scan(args):
    store = Store(args.data)
    patterns = clauses.load_patterns(args.patterns)
    results = []
    if args.files:
        for f in args.files:
            results.append(clauses.classify_file(f, patterns))
    else:
        entries = store.all_document_entries()
        if args.client:
            entries = [d for d in entries if d["owner_id"] == args.client]
            if not entries:
                print("no documents on file for %s" % args.client, file=sys.stderr)
                return 2
        results = [store.scan(d["id"], patterns) for d in entries]
    if args.json:
        print(_dump(results), end="")
    else:
        for r in results:
            print("%s: %s" % (r["document_id"], "silent (no AI clause found)" if r["silent"] else "%d hit(s)" % len(r["hits"])))
            for h in r["hits"]:
                print("  [%s] %d-%d  %s" % (h["class"], h["start"], h["end"], h["quote"]))
            for g in r["guarded"]:
                print("  (not classified: %s guard %s stopped %s)  %s" % (g["guard_kind"], g["guard_id"], g["class"], g["quote"]))
    if args.evaluate:
        print(clauses.format_evaluation(evaluate_all(store, patterns)))
    return 0


def cmd_clear(args):
    store = Store(args.data)
    patterns = clauses.load_patterns(args.patterns)
    policy = load_policy(args.policy)
    features, report = lanes.load_lanes(args.lanes)
    rec = engine.clear_matter(store.matter(args.matter), store, features, policy, patterns, args.as_of)
    if report:
        rec["lanes_import_report"] = report
    if args.out:
        base = Path(args.out) / rec["matter"]["id"]
        print("wrote", _write(str(base) + ".json", _dump(rec)))
        print("wrote", _write(str(base) + ".html", reports.memo_html(rec)))
    if args.json:
        print(_dump(rec), end="")
    else:
        print(reports.memo_text(rec))
        if report:
            print("  lanes read from a registry file; fields not mapped: %s" % ", ".join(
                report["unmapped_top_level_fields"] + report["unmapped_tool_fields"]))
    return 0


def cmd_tracker(args):
    store = Store(args.data)
    patterns = clauses.load_patterns(args.patterns)
    rows = reports.tracker_rows(store, patterns)
    csv_text = reports.tracker_csv(rows, patterns)
    if args.out:
        print("wrote", _write(Path(args.out) / "client_terms_tracker.csv", csv_text))
        print("wrote", _write(Path(args.out) / "client_terms_tracker.html", reports.tracker_html(rows, patterns)))
    else:
        print(csv_text, end="")
    return 0


def cmd_diff(args):
    store = Store(args.data)
    patterns = clauses.load_patterns(args.patterns)
    policy = load_policy(args.policy)
    features, _ = lanes.load_lanes(args.lanes)
    rep = reports.diff_terms(args.client, args.replace, args.with_doc, store, features, policy, patterns,
                             args.as_of or engine.date.today().isoformat())
    if args.out:
        base = Path(args.out) / ("change_report_" + args.client)
        print("wrote", _write(str(base) + ".json", _dump(rep)))
        print("wrote", _write(str(base) + ".html", reports.diff_html(rep)))
    if args.json:
        print(_dump(rep), end="")
    else:
        print(reports.diff_text(rep))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="python -m clearance",
                                description="Matter clearance for AI. Demo with fictional data. Not legal advice.")
    p.add_argument("--data", default=str(DATA), help="data directory")
    p.add_argument("--patterns", default=None, help="clause pattern file")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan-terms", help="find and classify AI clauses in terms documents")
    s.add_argument("files", nargs="*", help="plain-text files; default is every document on file")
    s.add_argument("--client", help="scan only this party's documents")
    s.add_argument("--evaluate", action="store_true", help="print precision and recall against the answer key")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("clear", help="clearance decision for one matter")
    c.add_argument("--matter", required=True, help="matter id or path to an intake JSON file")
    c.add_argument("--lanes", help="tool lanes file, or a registry file in the governance-eval-kit format")
    c.add_argument("--policy", help="policy file")
    c.add_argument("--as-of", dest="as_of", help="date for review-date checks, YYYY-MM-DD; default today")
    c.add_argument("--out", help="directory for the memo (HTML and JSON)")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_clear)

    t = sub.add_parser("tracker", help="client-terms tracker across all clients")
    t.add_argument("--out", help="directory for CSV and HTML; default prints CSV")
    t.set_defaults(func=cmd_tracker)

    d = sub.add_parser("diff", help="change report when a client's terms are updated")
    d.add_argument("--client", required=True)
    d.add_argument("--replace", required=True, help="document id being replaced")
    d.add_argument("--with", dest="with_doc", required=True, help="new document id")
    d.add_argument("--lanes")
    d.add_argument("--policy")
    d.add_argument("--as-of", dest="as_of")
    d.add_argument("--out")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_diff)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
