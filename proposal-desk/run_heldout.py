"""Run the parser on one held-out batch and save the scores.

    python3 run_heldout.py a first_run
    python3 run_heldout.py a after_fixes
    python3 run_heldout.py b final

A saved result is never overwritten unless --rerun is given, so a recorded first
run or final run stays what it was. Results go to data/heldout_results/.
"""
import json
import os
import sys

from desk.heldout_score import combine, evaluate, report_markdown
from desk.rfp import parse_rfp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "heldout_results")

TITLES = {
    ("a", "first_run"): "Held-out batch A, first run (before any change to the parser)",
    ("a", "after_fixes"): "Held-out batch A, after general fixes made from its misses",
    ("b", "final"): "Held-out batch B, single final run (sealed until this run)",
}


def score_batch(batch):
    base = os.path.join(HERE, "heldout", "batch_%s" % batch)
    results = {}
    for name in sorted(os.listdir(os.path.join(base, "rfps"))):
        if not name.endswith(".txt"):
            continue
        stem = name[:-4]
        with open(os.path.join(base, "rfps", name), encoding="utf-8") as f:
            parsed = parse_rfp(f.read())
        with open(os.path.join(base, "answer_keys", stem + ".json"), encoding="utf-8") as f:
            key = json.load(f)
        results[stem] = evaluate(parsed, key)
    return results


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2 or (args[0], args[1]) not in TITLES:
        print(__doc__)
        return 2
    batch, tag = args
    os.makedirs(OUT, exist_ok=True)
    stem = os.path.join(OUT, "batch_%s_%s" % (batch, tag))
    if os.path.exists(stem + ".json") and "--rerun" not in argv:
        print("Already recorded: %s.json. Not run again." % stem)
        return 1
    results = score_batch(batch)
    intro = ["The RFPs and keys were written by an independent author who had not read the parser.",
             "Scoring rules are in desk/heldout_score.py. Items the parser marked \"check\" count like",
             "any other item. Addendum handling is its own line and is not part of the overall figure."]
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump({"batch": batch, "run": tag, "combined": combine(results), "per_rfp": results}, f, indent=1)
        f.write("\n")
    with open(stem + ".md", "w", encoding="utf-8") as f:
        f.write(report_markdown(TITLES[(batch, tag)], intro, results))
    comb = combine(results)
    for name, res in results.items():
        print("%-45s req P %.3f R %.3f | overall P %.3f R %.3f" % (
            name, res["requirements"]["precision"], res["requirements"]["recall"],
            res["overall"]["precision"], res["overall"]["recall"]))
    print("%-45s req P %.3f R %.3f | overall P %.3f R %.3f" % (
        "batch %s %s" % (batch, tag), comb["requirements"]["precision"], comb["requirements"]["recall"],
        comb["overall"]["precision"], comb["overall"]["recall"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
