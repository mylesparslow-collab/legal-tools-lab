#!/usr/bin/env python3
"""Build every sample output into output/. Run from this folder: python3 run_demo.py

Python standard library only. If Node with Playwright is present, each statement is
also rendered to a PNG and a one-page-checked PDF; without it that step is skipped.
"""
from __future__ import annotations

import copy
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from statement import drift  # noqa: E402
from statement.build import build_statement  # noqa: E402
from statement.cli import write_outputs  # noqa: E402
from statement.model import load_json  # noqa: E402

SAMPLES, OUT = HERE / "samples", HERE / "output"
AS_OF = date(2026, 11, 25)
LATER = date(2027, 5, 20)


def pdf_page_count(path: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", path.read_bytes()))


def render(folder: Path) -> str:
    if not shutil.which("node"):
        return "PNG/PDF skipped (node not found)"
    r = subprocess.run(["node", str(HERE / "scripts" / "render_page.js"), str(folder / "statement.html"),
                        str(folder / "statement.png"), str(folder / "statement.pdf")], capture_output=True, text=True)
    if r.returncode != 0:
        return "PNG/PDF skipped (Playwright not available)"
    pages = pdf_page_count(folder / "statement.pdf")
    if pages != 1:
        raise SystemExit(f"{folder}: PDF is {pages} pages; the statement must be exactly 1 page")
    return "PNG and 1-page PDF written"


def main() -> int:
    clean = load_json(SAMPLES / "registry.clean.json")
    gaps = load_json(SAMPLES / "registry.gaps.json")
    later = load_json(SAMPLES / "registry.later.json")
    inputs = load_json(SAMPLES / "statement_inputs.json")
    inputs_gaps = load_json(SAMPLES / "statement_inputs.gaps.json")

    draft = build_statement(clean, inputs, AS_OF)
    approved_inputs = copy.deepcopy(inputs)
    approved_inputs["approval"] = {"approved_by": "General Counsel (role; fictional sign-off for the demo)",
                                   "approved_on": AS_OF.isoformat(), "content_hash": draft["content_hash"]}
    jobs = [
        ("", "firm-wide, clean registry", draft),
        ("gaps", "firm-wide, registry with gaps", build_statement(gaps, inputs_gaps, AS_OF)),
        ("client-consent", "client-specific, consent on file",
         build_statement(clean, inputs, AS_OF, load_json(SAMPLES / "client_terms.consent.json"))),
        ("client-restricted", "client-specific, tools and data restricted",
         build_statement(clean, inputs, AS_OF, load_json(SAMPLES / "client_terms.restricted.json"))),
        ("approved-example", "firm-wide, clean registry, with a fictional approval record",
         build_statement(clean, approved_inputs, AS_OF)),
    ]
    for sub, label, stmt in jobs:
        folder = OUT / sub if sub else OUT
        write_outputs(stmt, folder)
        printed = sum(len(s["sentences"]) for s in stmt["sections"])
        print(f"{label}: {stmt['status']}, {stmt['word_count']}/{stmt['word_limit']} words, {printed} sentences, "
              f"{len(stmt['downgraded'])} downgraded, {len(stmt['omitted'])} omitted. {render(folder)}.")

    (OUT / "drift").mkdir(exist_ok=True)
    same = drift.check_statement(draft, clean, AS_OF)
    moved = drift.check_statement(draft, later, LATER)
    (OUT / "drift" / "check_same_registry.md").write_text(drift.report_md(same), encoding="utf-8")
    (OUT / "drift" / "check_later_registry.md").write_text(drift.report_md(moved), encoding="utf-8")
    print(f"drift check, same registry: {same['drift_count']} drifted. "
          f"Later registry ({LATER}): {moved['drift_count']} drifted.")
    print(f"outputs are in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
