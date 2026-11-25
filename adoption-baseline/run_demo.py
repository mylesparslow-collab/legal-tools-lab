#!/usr/bin/env python3
"""One-command demo. Rebuilds every sample output in output/ from sample_data/.

    python run_demo.py

Uses the committed synthetic data. Run generate_synthetic.py first only if you
want to regenerate that data.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from baseline.cli import main  # noqa: E402

OUT = os.path.join(HERE, "output")


def run():
    steps = [
        ["survey"],
        ["ingest", "--out-dir", OUT],
        ["report", "--out-dir", OUT],
        # An earlier cut-off of the same data stands in for a previous quarter.
        ["report", "--out-dir", OUT, "--period-end", "2026-10-18", "--prefix", "checkpoint"],
        ["compare", os.path.join(OUT, "checkpoint.json"), os.path.join(OUT, "baseline.json"), "--out-dir", OUT],
    ]
    for step in steps:
        print("\n$ python -m baseline %s" % " ".join(os.path.relpath(a, HERE) if os.path.isabs(a) else a for a in step))
        code = main(step)
        if code:
            return code
    print("\nOpen output/baseline_report.html")
    return 0


if __name__ == "__main__":
    sys.exit(run())
