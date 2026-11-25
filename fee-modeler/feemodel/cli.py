"""Command line: python -m feemodel profile|comps|price|backtest|generate"""

import argparse
import json
import os
import sys

from . import backtest as bt
from . import memo, profile as prof, synth
from .comps import DEFAULT_MIN_COMPS
from .engine import Workspace, default_paths, dump_json, price_proposal, to_jsonable
from .loader import MappingError, load_cost_rates, load_json, load_mapping, load_rate_card
from .cost import TaskCodeMap
from .money import display_hours, display_money, display_pct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXIT_OK, EXIT_ERROR, EXIT_NOT_READY, EXIT_REFUSED = 0, 1, 2, 3


def _add_data_args(p):
    d = default_paths(ROOT)
    p.add_argument("--data", default=d["export_dir"], help="export folder (default: synthetic shape A)")
    p.add_argument("--mapping", default=d["mapping_path"], help="column mapping JSON")
    p.add_argument("--rate-card", default=d["rate_card_path"], help="current standard rates by level")
    p.add_argument("--cost-rates", default=d["cost_rates_path"], help="internal cost per hour by level (your input)")
    p.add_argument("--task-codes", default=d["task_codes_path"], help="task code to phase map")


def _workspace(args):
    return Workspace(args.data, args.mapping, args.rate_card, args.cost_rates, args.task_codes)


def _blocked(ws):
    blocking = ws.dataset.blocking_issues()
    if blocking:
        print("Warning: %d rows or tables failed to load. Run 'python -m feemodel profile' first; "
              "results below ignore the dropped rows." % len(blocking), file=sys.stderr)


def cmd_profile(args):
    if not args.mapping:
        print(prof.format_unmapped(args.export))
        return EXIT_NOT_READY
    d = default_paths(ROOT)

    def opt(path, loader):
        return loader(path) if path and os.path.isfile(path) else None

    for flag, key in (("--task-codes", "task_codes"), ("--rate-card", "rate_card"), ("--cost-rates", "cost_rates")):
        if getattr(args, key) is None:
            print("Note: %s not given; checking against the demo file %s"
                  % (flag, os.path.relpath(d[key + "_path"], ROOT)), file=sys.stderr)
    code_map = opt(args.task_codes or d["task_codes_path"], lambda p: TaskCodeMap.from_dict(load_json(p)))
    report = prof.profile_export(args.export, load_mapping(args.mapping), code_map,
                                 opt(args.rate_card or d["rate_card_path"], load_rate_card),
                                 opt(args.cost_rates or d["cost_rates_path"], load_cost_rates), args.min_comps)
    if args.json:
        print(json.dumps(to_jsonable(report), indent=2))
    else:
        print(prof.format_report(report))
    return EXIT_OK if report["ready"] else EXIT_NOT_READY


def format_comps(result):
    sel = result["selection"]
    lines = ["Comps for %s (as of %s)" % (result["proposal"]["matter_type"], result["proposal"]["as_of"]), "",
             "Selection rules:"]
    lines += ["  - %s" % r for r in sel["rules"]]
    lines.append("")
    lines.append("%d matters of this type on file, %d selected." % (sel["type_total"], sel["n"]))
    for reason, count in sorted(sel["exclusion_counts"].items(), key=lambda kv: -kv[1]):
        lines.append("  left out, %s: %d" % (reason, count))
    lines.append("")
    lines.append("%-8s %-10s %-15s %3s %4s %5s %4s %7s %12s %12s  %s"
                 % ("matter", "closed", "forum", "pty", "band", "units", "hrg", "hours", "raw worked", "normalized", "flags"))
    for c in sel["comps"]:
        lines.append("%-8s %-10s %-15s %3s %4s %5s %4s %7s %12s %12s  %s"
                     % (c["matter_id"], c["close_date"], c["forum"], c["num_parties"], c["amount_band"], c["num_units"],
                        "yes" if c["hearing_occurred"] else "no", display_hours(c["hours"]),
                        display_money(c["raw_worked"]), display_money(c["normalized_value"]),
                        "; ".join(c["flags"] + (["phases from date windows"] if c["phase_confidence"] == "date_window" else []))))
    if result["status"] == "refused":
        lines += ["", result["refusal"]]
    return "\n".join(lines)


def cmd_comps(args):
    ws = _workspace(args)
    _blocked(ws)
    proposal = load_json(args.proposal)
    proposal = dict(proposal, scenarios=[], target_probability=None)
    result = price_proposal(ws, proposal)
    if args.json:
        print(json.dumps(to_jsonable({"proposal": result["proposal"], "status": result["status"],
                                      "refusal": result.get("refusal"), "selection": result["selection"]}), indent=2))
    else:
        print(format_comps(result))
    return EXIT_OK if result["status"] == "modeled" else EXIT_REFUSED


def format_price(result):
    if result["status"] == "refused":
        return result["refusal"]
    d = result["distribution"]
    q, iv = d["normalized"]["quantiles"], d["normalized"]["intervals"]
    lines = ["%s (n=%d comps)" % (result["proposal"].get("title") or result["proposal"]["matter_type"], d["n"]),
             d["basis"]]
    for k in ("p25", "p50", "p75", "p90"):
        lines.append("  %s %10s   90%% interval %s to %s" % (k.upper(), display_money(q[k]), display_money(iv[k][0]),
                                                           display_money(iv[k][1])))
    for w in result["warnings"]:
        lines.append("  ! %s" % w)
    b = result["backtest"]
    lines.append("  Out of sample (walk-forward, this matter type): %s %s" % (b["headline"], " ".join(b["statements"])))
    for s in result["scenarios"]:
        lines.append("  %s: in sample, under fee %d of %d (%s); no loss %d of %d; mean margin %s; P90-case margin %s"
                     % (s["label"], s["under_fee"]["count"], s["n"], display_pct(s["under_fee"]["count"], s["n"]),
                        s["no_loss"]["count"], s["n"], display_money(s["expected_margin"]),
                        display_money(s["downside_p90_margin"])))
        lines.append("      out of sample: %s" % s["out_of_sample"]["text"])
    return "\n".join(lines)


def cmd_price(args):
    ws = _workspace(args)
    _blocked(ws)
    proposal = load_json(args.proposal)
    result = price_proposal(ws, proposal)
    os.makedirs(args.out, exist_ok=True)
    stem = "memo_%s" % (proposal.get("proposal_id") or "proposal")
    dump_json(result, os.path.join(args.out, stem + ".json"))
    with open(os.path.join(args.out, stem + ".html"), "w", encoding="utf-8") as fh:
        fh.write(memo.render_memo(result))
    print(format_price(result))
    print("Wrote %s and %s" % (os.path.join(args.out, stem + ".html"), os.path.join(args.out, stem + ".json")))
    return EXIT_OK if result["status"] == "modeled" else EXIT_REFUSED


def format_backtest(summary):
    def cell(c):
        return "%3d/%-3d %4s" % (c["count"], c["n"], display_pct(c["count"], c["n"])) if c["n"] else "     n/a    "

    lines = ["Walk-forward back-test (minimum %d comps)" % summary["min_comps"], summary["method"],
             summary["overrun_rule"], "",
             "%-38s %6s  %-13s %-13s %-13s" % ("matter type", "tested", "in P25-P75", "<= P75", "<= P90"),
             "%-38s %6s  %-13s %-13s %-13s" % ("", "", "(nominal 50%)", "(nominal 75%)", "(nominal 90%)")]
    for r in summary["by_type"]:
        c = r["coverage"]
        lines.append("%-38s %6d  %-13s %-13s %-13s" % (r["matter_type"], r["n_tested"], cell(c["inside_p25_p75"]),
                                                      cell(c["at_or_under_p75"]), cell(c["at_or_under_p90"])))
        lines.append("    %s" % r["verdict"])
    o = summary["overall"]
    lines.append("%-38s %6d  %-13s %-13s %-13s" % ("ALL TYPES", summary["n_tested"], cell(o["inside_p25_p75"]),
                                                  cell(o["at_or_under_p75"]), cell(o["at_or_under_p90"])))
    lines.append("    %s" % summary["overall_verdict"])
    return "\n".join(lines)


def run_backtest(ws, min_comps):
    records, summary = ws.backtest(min_comps)
    table = bt.modelability(ws.dataset, ws.book, summary, min_comps)
    return records, summary, table


def write_backtest(out, records, summary, table):
    os.makedirs(out, exist_ok=True)
    slim = [{k: v for k, v in r.items() if k != "comp_ids"} for r in records]
    dump_json({"summary": summary, "records": slim}, os.path.join(out, "backtest.json"))
    with open(os.path.join(out, "backtest.txt"), "w", encoding="utf-8") as fh:
        fh.write(format_backtest(summary) + "\n")
    dump_json(table, os.path.join(out, "modelability.json"))
    with open(os.path.join(out, "modelability.html"), "w", encoding="utf-8") as fh:
        fh.write(memo.render_modelability(table, summary))


def cmd_backtest(args):
    ws = _workspace(args)
    _blocked(ws)
    records, summary, table = run_backtest(ws, args.min_comps)
    print(format_backtest(summary))
    if args.out:
        write_backtest(args.out, records, summary, table)
        print("Wrote backtest.json, backtest.txt, modelability.json and modelability.html to %s" % args.out)
    return EXIT_OK


def cmd_drift_sensitivity(args):
    from . import sensitivity
    d = default_paths(ROOT)
    study = sensitivity.run_study(TaskCodeMap.from_dict(load_json(d["task_codes_path"])), load_rate_card(d["rate_card_path"]))
    print(sensitivity.format_study(study))
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        dump_json(study, os.path.join(args.out, "drift_sensitivity.json"))
        with open(os.path.join(args.out, "drift_sensitivity.txt"), "w", encoding="utf-8") as fh:
            fh.write(sensitivity.format_study(study) + "\n")
        print("Wrote drift_sensitivity.json and drift_sensitivity.txt to %s" % args.out)
    return EXIT_OK


def cmd_generate(args):
    world = synth.write_all(args.data_dir)
    print("Wrote synthetic exports to %s: %d matters, %d time entries, %d invoices."
          % (args.data_dir, len(world["matters"]), len(world["entries"]), len(world["invoices"])))
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(prog="feemodel", description="Fee modeler demo. Synthetic data only.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("profile", help="check an export against the canonical schema before modeling")
    p.add_argument("export", help="folder holding the export files")
    p.add_argument("--mapping", help="column mapping JSON; without it the files and headers are listed")
    p.add_argument("--task-codes")
    p.add_argument("--rate-card")
    p.add_argument("--cost-rates")
    p.add_argument("--min-comps", type=int, default=DEFAULT_MIN_COMPS)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("comps", help="show the comparable matters and the rules that chose them")
    p.add_argument("--proposal", required=True)
    p.add_argument("--json", action="store_true")
    _add_data_args(p)
    p.set_defaults(func=cmd_comps)

    p = sub.add_parser("price", help="write the pricing memo (HTML and JSON) for a proposal")
    p.add_argument("--proposal", required=True)
    p.add_argument("--out", default=os.path.join(ROOT, "output"))
    _add_data_args(p)
    p.set_defaults(func=cmd_price)

    p = sub.add_parser("backtest", help="walk-forward back-test and modelability table")
    p.add_argument("--out", default=None, help="folder for backtest and modelability files")
    p.add_argument("--min-comps", type=int, default=DEFAULT_MIN_COMPS)
    _add_data_args(p)
    p.set_defaults(func=cmd_backtest)

    p = sub.add_parser("drift-sensitivity", help="measure how big a planted shift the drift flag catches (about a minute)")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_drift_sensitivity)

    p = sub.add_parser("generate", help="regenerate the synthetic exports (seeded)")
    p.add_argument("--data-dir", default=os.path.join(ROOT, "data"))
    p.set_defaults(func=cmd_generate)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (MappingError, FileNotFoundError, KeyError, ValueError) as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return EXIT_ERROR
