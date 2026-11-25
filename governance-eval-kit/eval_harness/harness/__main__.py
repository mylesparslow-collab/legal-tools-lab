"""Command line: python3 -m harness <command>

  check                         validate every corpus document and answer key
  prompt DOC_ID                 print the standard prompt for one document
  score RUN.json [--out DIR]    score a run; writes <name>.scorecard.md/.csv/.json
  compare RUN.json RUN.json ... print a comparison table

Options for score and compare: --config time_model.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import report
from .config import load_time_model
from .corpus import CORPUS_DIR, list_doc_ids, load_document, validate_document
from .score import score_run

PROMPT = (Path(__file__).resolve().parent.parent / "PROMPT.md")


def _documents():
    return {d: load_document(d) for d in list_doc_ids()}


def _load_run(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="harness", description="Score AI review tools on synthetic California documents.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    pr = sub.add_parser("prompt")
    pr.add_argument("doc_id")
    sc = sub.add_parser("score")
    sc.add_argument("run")
    sc.add_argument("--out")
    sc.add_argument("--config")
    cp = sub.add_parser("compare")
    cp.add_argument("runs", nargs="+")
    cp.add_argument("--config")
    a = p.parse_args(argv)

    if a.cmd == "check":
        bad = 0
        for doc_id in list_doc_ids():
            problems = validate_document(doc_id)
            bad += bool(problems)
            print("\n".join(problems) if problems else f"ok  {doc_id}")
        return 1 if bad else 0
    if a.cmd == "prompt":
        text = (CORPUS_DIR / f"{a.doc_id}.md").read_text(encoding="utf-8")
        print(PROMPT.read_text(encoding="utf-8").split("---PROMPT---")[1].strip())
        print("\n<document id=\"%s\">\n%s\n</document>" % (a.doc_id, text))
        return 0
    model = load_time_model(a.config)
    docs = _documents()
    if a.cmd == "score":
        rs = score_run(_load_run(a.run), docs, model)
        md = report.to_markdown(rs)
        if a.out:
            out = Path(a.out)
            out.mkdir(parents=True, exist_ok=True)
            stem = Path(a.run).stem
            (out / f"{stem}.scorecard.md").write_text(md, encoding="utf-8")
            (out / f"{stem}.scorecard.csv").write_text(report.to_csv(rs), encoding="utf-8")
            (out / f"{stem}.scorecard.json").write_text(report.dumps(rs), encoding="utf-8")
            print(f"wrote {out}/{stem}.scorecard.md, .csv, .json")
        else:
            print(md)
        return 0
    print(report.compare_markdown([score_run(_load_run(r), docs, model) for r in a.runs]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
