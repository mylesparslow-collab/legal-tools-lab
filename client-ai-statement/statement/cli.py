"""Command line: python -m statement build | check | appendix

  build     build the statement, proposal paragraph and evidence appendix from a registry
  check     re-check an issued statement.json against the current registry (exit 1 on drift)
  appendix  re-render the internal evidence appendix from a statement.json

Exit codes: 0 ok, 1 drift found (check only), 2 bad input or the build was refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import drift, render
from .build import BuildError, build_statement
from .evidence import RuleError
from .model import InputError, load_json, parse_date


def write_outputs(stmt: dict, out_dir) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "statement.html": render.statement_html(stmt),
        "statement.md": render.statement_md(stmt),
        "statement.json": json.dumps(stmt, indent=2, ensure_ascii=False) + "\n",
        "proposal.md": render.proposal_md(stmt),
        "appendix.html": render.appendix_html(stmt),
        "appendix.md": render.appendix_md(stmt),
    }
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    return [out / n for n in files]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m statement", description="Client AI-use statement generator.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build statement, proposal paragraph and evidence appendix")
    b.add_argument("--registry", required=True, help="registry JSON in the governance-eval-kit schema")
    b.add_argument("--inputs", required=True, help="statement inputs JSON")
    b.add_argument("--as-of", required=True, help="date the statement speaks as of (YYYY-MM-DD)")
    b.add_argument("--client", help="client-terms record JSON; builds the client-specific version")
    b.add_argument("--out", default="output", help="output directory (default: output)")

    c = sub.add_parser("check", help="re-check an issued statement against the current registry")
    c.add_argument("--statement", required=True, help="statement.json written by build")
    c.add_argument("--registry", required=True)
    c.add_argument("--as-of", required=True)
    c.add_argument("--out", help="also write the report to this Markdown file")

    a = sub.add_parser("appendix", help="re-render the evidence appendix from statement.json")
    a.add_argument("--statement", required=True)
    a.add_argument("--out", default="output")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "build":
            stmt = build_statement(load_json(args.registry), load_json(args.inputs), parse_date(args.as_of, "--as-of"),
                                   load_json(args.client) if args.client else None)
            paths = write_outputs(stmt, args.out)
            print(f"{stmt['status']} {stmt['variant']} statement: {stmt['word_count']} of {stmt['word_limit']} words, "
                  f"{sum(len(s['sentences']) for s in stmt['sections'])} sentences printed, "
                  f"{len(stmt['downgraded'])} downgraded, {len(stmt['omitted'])} omitted.")
            for w in stmt["warnings"]:
                print(f"warning: {w}")
            print("wrote " + ", ".join(str(p) for p in paths))
            return 0
        if args.cmd == "check":
            report = drift.check_statement(load_json(args.statement), load_json(args.registry),
                                           parse_date(args.as_of, "--as-of"))
            text = drift.report_md(report)
            print(text)
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(text, encoding="utf-8")
            return 1 if report["drift"] else 0
        stmt = load_json(args.statement)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "appendix.html").write_text(render.appendix_html(stmt), encoding="utf-8")
        (out / "appendix.md").write_text(render.appendix_md(stmt), encoding="utf-8")
        print(f"wrote {out / 'appendix.html'}, {out / 'appendix.md'}")
        return 0
    except (InputError, BuildError, RuleError, KeyError) as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
