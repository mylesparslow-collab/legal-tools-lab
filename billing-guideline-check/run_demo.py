"""Run the whole demo on the sample data and write outputs into output/ and index.html.

    python run_demo.py

Personal portfolio demo. Fictional data. Not legal or billing advice.
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from billcheck import guidelines as G  # noqa: E402
from billcheck import intake, report, scoring  # noqa: E402
from billcheck.cli import write_outputs  # noqa: E402

DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "output")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


HELDOUT_RUNS = [
    ("Batch A, first run, before any change", "batch_a_first_run.json"),
    ("Batch A, after fixes (fitted, not unseen)", "batch_a_after_fixes.json"),
    ("Batch B, single final run", "batch_b_final.json"),
]


def load_heldout_results():
    """Read saved held-out scores, if any. They are written by score_heldout.py."""
    found = []
    for label, name in HELDOUT_RUNS:
        path = os.path.join(HERE, "heldout_results", name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                found.append((label, json.load(handle)))
    return found


def main(out_dir=OUT, index_path=os.path.join(HERE, "index.html"), quiet=False):
    OUT = out_dir
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    guides = G.load_all(os.path.join(DATA, "guidelines"))

    # 1. Intake: propose rules from each plain-text document. Nothing proposed is enforced.
    intake_rows = []
    for guide in guides:
        with open(os.path.join(DATA, "guideline_docs", guide.client_id + ".txt"), "r", encoding="utf-8") as handle:
            text = handle.read()
        proposed = intake.propose_rules(text, guide.client_id, guide.client_name, guide.document)
        _write(os.path.join(OUT, "intake", guide.client_id + ".proposed.json"), G.dumps(proposed))
        intake_rows.append(intake.compare_with_guideline(proposed, guide))
    _write(os.path.join(OUT, "intake", "intake_vs_rules_on_file.json"), json.dumps(intake_rows, indent=2) + "\n")

    # 2. Check every sample invoice against its client's confirmed rules.
    results = scoring.check_all(DATA)
    for result in results:
        write_outputs(result, os.path.join(OUT, "reports"))
    _write(os.path.join(OUT, "all_findings.csv"), report.findings_csv(results))

    # 3. Guidelines comparison across clients.
    _write(os.path.join(OUT, "guidelines_comparison.html"), report.comparison_html(guides))
    _write(os.path.join(OUT, "guidelines_comparison.csv"), report.comparison_csv(guides))

    # 4. Score against the answer key.
    score = scoring.score(results, scoring.load_answer_key(DATA))
    _write(os.path.join(OUT, "answer_key_score.json"), json.dumps(score, indent=2) + "\n")

    # 5. Static demo page.
    _write(index_path, report.index_html(results, guides, score, intake_rows, heldout=load_heldout_results()))
    if quiet:
        return 0

    print("Billing-guideline check demo. Fictional data. Not legal or billing advice.\n")
    for result in results:
        print(report.summary_paragraph(result))
        print()
    print("Intake helper (candidates are proposals only):")
    for row in intake_rows:
        print("  %-34s proposed %2d, match %2d of %2d rules on file, extra %d, missed: %s"
              % (row["client_name"], row["proposed"], row["matched"], row["rules_on_file"], row["extra"], ", ".join(row["missed"]) or "none"))
    print()
    print("Answer key: %d of %d planted violations found; %d findings not in the key; %d of %d clean lines flagged."
          % (score["planted_found"], score["planted_total"], score["false_positive_count"], len(score["clean_lines_flagged"]), score["clean_lines"]))
    print("Outputs are in output/. Open index.html for the static demo page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
