"""Command line: python -m desk <command>. Run 'python -m desk demo' for the full sample run."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import agenda, cpra, report

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "sample_data"


def _print_findings(fs):
    for f in fs:
        print(f"  [{f['level'].upper():6}] {f['message']}" + (f"  ({f['cite']})" if f.get("cite") else ""))


def cmd_agenda(args):
    res = agenda.validate(json.loads(Path(args.file).read_text(encoding="utf-8")))
    if args.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        print(f"{res['agency']} / {res['body']} / {res['meeting']['type']} {res['meeting']['start']}")
        for k, fs in res["sections"].items():
            print(k.upper())
            _print_findings(fs)
        print("Totals:", res["counts"])
    return 1 if res["counts"]["fail"] else 0


def cmd_cpra(args):
    today = date.fromisoformat(args.today) if args.today else date.today()
    rows = [cpra.deadlines(r, today) for r in cpra.read_requests(args.file)]
    for r in rows:
        print(f"{r['id']}: received {r['received']}, day 10 {r['determination_due']}, latest with extension {r['extension_latest']} -> {r['status']}")
        _print_findings([f for f in r["findings"] if f["code"] != "determination"])
    if args.ics:
        Path(args.ics).write_text(cpra.to_ics(rows), encoding="utf-8", newline="")
    return 0


def cmd_legacy(args):
    for m in cpra.map_legacy(Path(args.file).read_text(encoding="utf-8")):
        print(f"{m['found']!r}: {m['message']} [{m['status']}]")
    return 0


def _load_records(folder):
    folder = Path(folder)
    cfg = json.loads((folder.parent / "decisions.json").read_text(encoding="utf-8")) if (folder.parent / "decisions.json").exists() else {}
    texts = {p.stem: p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.txt"))}
    props = [x for d, t in texts.items() for x in cpra.propose(d, t, tuple(cfg.get("counsel", ())))]
    return folder, cfg, texts, props


def cmd_propose(args):
    _, _, _, props = _load_records(args.folder)
    for p in props:
        print(f"{p['id']:12} {p['scope']:8} {p['cite']:24} {p['basis']}: {p['text'][:60]!r}")
    return 0


def produce(folder, out_dir):
    from . import redact
    folder, cfg, texts, props = _load_records(folder)
    props = cpra.propagate_decisions(cpra.apply_decisions(props, cfg.get("decisions", {})))
    meta = {}
    for d, t in texts.items():
        head = dict(line.split(":", 1) for line in t.splitlines()[:6] if ":" in line and not line.startswith(">"))
        meta[d] = {k.lower(): v.strip() for k, v in head.items()}
    log = cpra.privilege_log(props, meta)
    withheld = {p["doc"] for p in props if p["status"] == "approved" and p["scope"] == "document"}
    terms = sorted({p["text"] for p in props if p["status"] == "approved" and p["scope"] == "span"}, key=len, reverse=True)
    sources = {d: folder / f"{d}.pdf" for d in texts if d not in withheld and (folder / f"{d}.pdf").exists()}
    out_dir = Path(out_dir)
    production = redact.propagate(terms, sources, out_dir / "production")
    for d in withheld:
        production[d] = {"withheld": True}
    cpra.write_csv(log, out_dir / "withholding_log.csv")
    return props, log, production, redact.near_duplicates(texts)


def cmd_produce(args):
    props, log, production, groups = produce(args.folder, args.out)
    print("Near-duplicate groups:", groups)
    for d, r in sorted(production.items()):
        print(d, "withheld in full" if r.get("withheld") else f"{sum(r['hits'].values())} redaction(s), leak check: {'LEAK' if r['leaks'] else 'clean'}")
    print(f"{len(log)} log entries; {sum(1 for p in props if p['status'] == 'proposed')} proposal(s) still awaiting review.")
    return 0


def cmd_demo(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    asof = date(2027, 1, 22)
    agendas = [agenda.validate(json.loads((SAMPLE / f"agenda_{n}.json").read_text(encoding="utf-8"))) for n in ("regular", "special", "clean")]
    rows = [cpra.deadlines(r, asof) for r in cpra.read_requests(SAMPLE / "requests.csv")]
    legacy = cpra.map_legacy((SAMPLE / "denial_letter_draft.txt").read_text(encoding="utf-8"))
    props, log, production, groups = produce(SAMPLE / "records", out)
    (out / "requests.ics").write_text(cpra.to_ics(rows), encoding="utf-8", newline="")
    (out / "agenda_findings.json").write_text(json.dumps(agendas, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "report.html").write_text(report.render(agendas, rows, legacy, log, production, asof.isoformat()), encoding="utf-8")
    print(f"Wrote {out}/report.html, agenda_findings.json, requests.ics, withholding_log.csv and {len(production) - sum(1 for r in production.values() if r.get('withheld'))} redacted PDFs.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="desk", description="Brown Act agenda checks and CPRA desk. Demo with fictional data; not legal advice.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("agenda", help="check one agenda JSON file"); p.add_argument("file"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_agenda)
    p = sub.add_parser("cpra", help="compute request clocks from a CSV"); p.add_argument("file"); p.add_argument("--today"); p.add_argument("--ics"); p.set_defaults(fn=cmd_cpra)
    p = sub.add_parser("legacy", help="find former § 6250-series cites in a text file"); p.add_argument("file"); p.set_defaults(fn=cmd_legacy)
    p = sub.add_parser("propose", help="list proposed exemptions for a records folder"); p.add_argument("folder"); p.set_defaults(fn=cmd_propose)
    p = sub.add_parser("produce", help="apply approved decisions, redact PDFs, verify, write the log"); p.add_argument("folder"); p.add_argument("--out", default="output"); p.set_defaults(fn=cmd_produce)
    p = sub.add_parser("demo", help="run everything on the sample data"); p.add_argument("--out", default=str(ROOT / "output")); p.set_defaults(fn=cmd_demo)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
