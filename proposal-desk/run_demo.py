"""One-command demo: python run_demo.py

Parses the four sample RFPs, scores the parser against the answer keys, builds
drafts and compliance matrices, runs a harvest into a copy of the library, and
writes everything into output/ plus index.html. Fixed "as of" date, so the
outputs are the same on every run. Synthetic data only.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from desk import render                                    # noqa: E402
from desk.__main__ import write_draft_outputs, write_matrix_outputs   # noqa: E402
from desk.demo_page import demo_html                       # noqa: E402
from desk.evaluate import evaluate, report_markdown        # noqa: E402
from desk.harvest import harvest, report_markdown as harvest_report, set_outcome   # noqa: E402
from desk.loader import load_data                          # noqa: E402
from desk.pipeline import build                            # noqa: E402
from desk.rfp import parse_rfp                             # noqa: E402

DATA = os.path.join(ROOT, "data")
LIB = os.path.join(DATA, "library")
OUT = os.path.join(ROOT, "output")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote %s" % os.path.relpath(path, ROOT))


def main():
    cfg = json.loads(read(os.path.join(DATA, "demo_config.json")))
    as_of = cfg["as_of"]
    data = load_data(LIB)
    rfps = sorted(f for f in os.listdir(os.path.join(DATA, "rfps")) if f.endswith(".txt"))
    evals, summary = {}, []
    for name in rfps:
        text = read(os.path.join(DATA, "rfps", name))
        stem = name[:-4]
        parsed = parse_rfp(text)
        key = json.loads(read(os.path.join(DATA, "answer_keys", stem + ".json")))
        evals[name] = evaluate(parsed, key)
        status_file = cfg.get("status_files", {}).get(name)
        status = json.loads(read(os.path.join(DATA, status_file))) if status_file else None
        res = build(text, data, as_of, status=status)
        out = os.path.join(OUT, stem)
        write(os.path.join(out, "parsed.json"), json.dumps(parsed, indent=1, ensure_ascii=False) + "\n")
        write(os.path.join(out, "parse_summary.txt"), render.parse_summary(parsed))
        write_draft_outputs(res, out)
        write_matrix_outputs(res, out)
        write(os.path.join(out, "match.md"), render.match_markdown(res))
        g = res["go_no_go"]
        summary.append((name, g, evals[name]["overall"]))
        if name == cfg["index_rfp"]:
            write(os.path.join(ROOT, "index.html"), demo_html(res, evals[name], "data/rfps/" + name))

    # parser evaluation, with the held-out document reported separately
    report = report_markdown(evals)
    hold_dir = os.path.join(DATA, "holdout")
    hold = evaluate(parse_rfp(read(os.path.join(hold_dir, "bond_counsel_gullwing_harbor.txt"))),
                    json.loads(read(os.path.join(hold_dir, "bond_counsel_gullwing_harbor.key.json"))))
    first = json.loads(read(os.path.join(hold_dir, "first_run_result.json")))
    report += "\n".join([
        "## Held-out document: bond_counsel_gullwing_harbor.txt", "",
        "A fifth RFP in a layout the parser was not written for. It is not one of the four sample RFPs.", "",
        "First run, before any change to the parser: precision %.3f, recall %.3f (%d correct, %d extra, %d missed)." % (
            first["overall"]["precision"], first["overall"]["recall"], first["overall"]["tp"],
            first["overall"]["fp"], first["overall"]["fn"]),
        first["cause"], "",
        "After six general fixes prompted by that run (mixed-case 'Article' headings, 'Tab N' labels, three more",
        "heading keywords, weight-first criteria, 'longer than N pages'): precision %.3f, recall %.3f" % (
            hold["overall"]["precision"], hold["overall"]["recall"]),
        "(%d correct, %d extra, %d missed). This second figure is no longer held out. The remaining" % (
            hold["overall"]["tp"], hold["overall"]["fp"], hold["overall"]["fn"]),
        "misses were left unfixed on purpose and are listed here:", ""])
    from desk.evaluate import CATEGORIES
    for c in CATEGORIES:
        for x in hold[c]["extra"]:
            report += "\n- extra %s: %s" % (c, x)
        for x in hold[c]["missed"]:
            report += "\n- missed %s: %s" % (c, x)
    for x in hold["question_type"]["wrong"]:
        report += "\n- question type: %s" % x
    report += "\n\nThe first-run figure is the better guide to what happens on an RFP layout nobody has tuned for.\n"
    write(os.path.join(OUT, "parser_evaluation.md"), report)
    write(os.path.join(OUT, "parser_evaluation.json"),
          json.dumps({"samples": {k: v["overall"] for k, v in evals.items()}, "holdout_first_run": first["overall"],
                      "holdout_after_fixes": hold["overall"]}, indent=1) + "\n")

    # harvest into a copy of the library, so the demo library itself is not changed
    lib_copy = os.path.join(OUT, "harvest_demo", "library")
    if os.path.exists(lib_copy):
        shutil.rmtree(lib_copy)
    shutil.copytree(LIB, lib_copy)
    hdata = load_data(lib_copy)
    rfp_text = read(os.path.join(DATA, "rfps", "general_counsel_redwood_flats.txt"))
    rep = harvest(read(os.path.join(DATA, "harvest_sample", "final_redwood_flats.md")), rfp_text, hdata, "pending")
    n = set_outcome(lib_copy, rep["proposal_id"], "won")
    text = harvest_report(rep) + "\nLater, when the result was known: outcome set to won on %d answer(s).\n" % n
    write(os.path.join(OUT, "harvest_demo", "harvest_report.md"), text)
    for f in os.listdir(lib_copy):          # keep only what the harvest wrote
        if f != "harvested_answers.json":
            os.remove(os.path.join(lib_copy, f))

    lines = ["# Demo run summary", "", "As of %s. Synthetic data. Not legal advice." % as_of, "",
             "| RFP | Deadline | Coverage | Answered / partial / none / person | Open disqualifiers | Blocking flags | Parser P / R |",
             "|---|---|---|---|---|---|---|"]
    for name, g, ev in summary:
        c = g["coverage"]
        lines.append("| %s | %s | %d%% (%d of %d) | %d / %d / %d / %d | %d | %d | %.3f / %.3f |" % (
            name, g["deadline"]["date"], c["pct"], c["answered_of_answerable"], c["library_answerable"],
            c["answered"], c["partial"], c["no_content"], c["person"], g["open_disqualifiers"],
            len(g["blocking_flags"]), ev["precision"], ev["recall"]))
    lines += ["", "Coverage is the share of requirements the library may answer (everything except cover letter,",
              "conflicts, pricing and disclosures) that were answered in full from approved, current text.", ""]
    write(os.path.join(OUT, "SUMMARY.md"), "\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
