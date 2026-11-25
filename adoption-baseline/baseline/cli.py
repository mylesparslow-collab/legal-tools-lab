"""Command line: python -m baseline ingest | report | compare | survey"""
import argparse
import json
import os
import sys

from . import compare as compare_mod
from . import ingest as ingest_mod
from . import outputs, pipeline, survey_render
from .ingest import MappingError
from .roster import RosterError, parse_iso

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_config(args):
    base = os.path.abspath(args.base_dir)
    config = pipeline.load_json(os.path.join(base, args.config))
    if getattr(args, "roster", None):
        config["roster"] = args.roster
    if getattr(args, "source", None):
        config["sources"] = []
        for item in args.source:
            file, sep, mapping = item.partition("=")
            if not sep:
                raise SystemExit("--source must look like export.csv=mapping.json")
            config["sources"].append({"file": file, "mapping": mapping})
    if getattr(args, "survey", None):
        config["survey_responses"] = args.survey
    if getattr(args, "targets", None):
        config["targets"] = args.targets
    if getattr(args, "min_group", None) is not None:
        config["suppression_threshold"] = args.min_group
    return base, config


def cmd_ingest(args):
    base, config = _load_config(args)
    start = parse_iso(args.period_start or config["period_start"])
    end = parse_iso(args.period_end or config["period_end"])
    roster, table, quality, unknown = pipeline.run_ingest(config, base, start, end)
    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, "data_quality.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(quality, f, indent=2)
        f.write("\n")
    t = quality["totals"]
    print("Read %d rows, kept %d, dropped %d, repaired %d." % (t["rows_read"], t["rows_kept"], t["rows_dropped"], t["rows_repaired"]))
    for q in quality["sources"]:
        drops = ", ".join("%s %d" % (k, v) for k, v in q["dropped"].items() if v) or "none"
        print("  %s: read %d, kept %d, dropped: %s" % (q["source"], q["rows_read"], q["rows_kept"], drops))
    print("Canonical table: %d rows (person, date, tool, feature). Data quality written to %s" % (len(table), out))
    if args.list_unknown:
        for source, names in unknown.items():
            for name, n in sorted(names.items()):
                print("  not on roster [%s]: %s (%d rows)" % (source, name, n))
    if args.write_events:
        ingest_mod.write_day_table(table, args.write_events)
        print("Wrote the person-level table to %s. This file identifies individuals; handle it accordingly." % args.write_events)
    else:
        print("The person-level table was not written. Use --write-events PATH if you need it.")
    return 0


def cmd_report(args):
    base, config = _load_config(args)
    baseline, analysis = pipeline.build_baseline(config, base, period_end=args.period_end,
                                                 period_start=args.period_start, with_analysis=True)
    written = outputs.write_outputs(baseline, args.out_dir, args.prefix)
    if args.include_individuals or config.get("individual_output"):
        p = outputs.write_individuals(analysis, args.out_dir, args.prefix)
        print("Wrote %s. This file identifies individuals; it is off by default." % p)
    print("Wrote %d files to %s" % (len(written), args.out_dir))
    for t in baseline["targets"]["targets"] + baseline["targets"]["gates"]:
        print("  %-12s %s" % (t["status"], t["label"]))
    return 0


def cmd_compare(args):
    earlier, later = compare_mod.load(args.earlier), compare_mod.load(args.later)
    rules = {}
    if args.min_people is not None:
        rules["min_people"] = args.min_people
    if args.min_change_points is not None:
        rules["min_change_points"] = args.min_change_points
    base_rules = dict(later["meta"].get("compare_rules") or {})
    base_rules.update(rules)
    result = compare_mod.compare(earlier, later, base_rules)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "compare.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    md = compare_mod.to_markdown(result)
    with open(os.path.join(args.out_dir, "compare.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    return 0


def cmd_survey(args):
    base = os.path.abspath(args.base_dir)
    defn = pipeline.load_json(os.path.join(base, "survey", "survey.json"))
    with open(os.path.join(base, "survey", "survey.html"), "w", encoding="utf-8") as f:
        f.write(survey_render.render_html(defn))
    with open(os.path.join(base, "survey", "SURVEY.md"), "w", encoding="utf-8") as f:
        f.write(survey_render.render_markdown(defn))
    print("Wrote survey/survey.html and survey/SURVEY.md from survey/survey.json")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="python -m baseline", description="Adoption baseline for approved AI tools. Synthetic demo.")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--base-dir", default=BASE_DIR, help="folder that relative paths are read from")
        sp.add_argument("--config", default="data/config.json")
        sp.add_argument("--roster", help="roster CSV (overrides config)")
        sp.add_argument("--source", action="append", metavar="CSV=MAPPING", help="usage export and its mapping; repeatable")
        sp.add_argument("--period-start", help="YYYY-MM-DD (overrides config)")
        sp.add_argument("--period-end", help="YYYY-MM-DD (overrides config)")
        sp.add_argument("--out-dir", default=os.path.join(BASE_DIR, "output"))

    sp = sub.add_parser("ingest", help="load exports into the canonical table and report data quality")
    common(sp)
    sp.add_argument("--write-events", metavar="PATH", help="also write the person-level canonical table (off by default)")
    sp.add_argument("--list-unknown", action="store_true", help="print export users that are not on the roster")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("report", help="compute metrics and write baseline.json, CSVs and the HTML report")
    common(sp)
    sp.add_argument("--survey", help="survey responses CSV or folder of JSON responses")
    sp.add_argument("--targets", help="targets JSON")
    sp.add_argument("--min-group", type=int, help="small-group suppression threshold")
    sp.add_argument("--prefix", default="baseline", help="output file name prefix")
    sp.add_argument("--include-individuals", action="store_true", help="also write a per-person CSV (off by default)")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("compare", help="compare two baseline.json files")
    sp.add_argument("earlier")
    sp.add_argument("later")
    sp.add_argument("--min-people", type=int)
    sp.add_argument("--min-change-points", type=float)
    sp.add_argument("--out-dir", default=os.path.join(BASE_DIR, "output"))
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("survey", help="re-render survey.html and SURVEY.md from survey.json")
    sp.add_argument("--base-dir", default=BASE_DIR)
    sp.set_defaults(func=cmd_survey)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (MappingError, RosterError, compare_mod.CompareError, FileNotFoundError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
