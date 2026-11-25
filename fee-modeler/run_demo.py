"""One command: regenerate the synthetic data, run every step, write output/ and index.html.

    python run_demo.py
"""

import glob
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from feemodel import memo, profile, site, synth  # noqa: E402
from feemodel.cli import format_backtest, format_price, run_backtest, write_backtest  # noqa: E402
from feemodel.engine import Workspace, default_paths, dump_json, price_proposal  # noqa: E402
from feemodel.loader import load_json  # noqa: E402


def main():
    data = os.path.join(ROOT, "data")
    out = os.path.join(ROOT, "output")
    os.makedirs(out, exist_ok=True)

    world = synth.write_all(data)
    print("1. Generated synthetic data (seed %d): %d matters, %d time entries, %d invoices, two export shapes."
          % (synth.SEED, len(world["matters"]), len(world["entries"]), len(world["invoices"])))

    ws = Workspace(**default_paths(ROOT))
    for name in ("export_a", "export_b"):
        report = profile.profile_export(os.path.join(data, name), os.path.join(data, "mappings", name + ".json"),
                                        ws.code_map, ws.rate_card, ws.cost_rates)
        # Record the folder relative to this tool so committed outputs do not depend on where it is checked out.
        report["export_dir"] = "data/" + name
        with open(os.path.join(out, "profile_%s.txt" % name), "w", encoding="utf-8") as fh:
            fh.write(profile.format_report(report) + "\n")
        dump_json(report, os.path.join(out, "profile_%s.json" % name))
        print("2. Profiled %s: %s." % (name, "ready" if report["ready"] else "NOT READY"))

    records, summary, table = run_backtest(ws, 8)
    write_backtest(out, records, summary, table)
    print("3. Back-test:")
    print(format_backtest(summary))

    results = []
    print("4. Pricing memos:")
    for path in sorted(glob.glob(os.path.join(data, "proposals", "*.json"))):
        proposal = load_json(path)
        result = price_proposal(ws, proposal)
        results.append(result)
        stem = "memo_%s" % proposal["proposal_id"]
        dump_json(result, os.path.join(out, stem + ".json"))
        with open(os.path.join(out, stem + ".html"), "w", encoding="utf-8") as fh:
            fh.write(memo.render_memo(result))
        print("   " + format_price(result).replace("\n", "\n   "))

    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(site.render_index(results, summary, table))
    print("5. Wrote output/ and index.html. Open index.html in a browser.")


if __name__ == "__main__":
    main()
