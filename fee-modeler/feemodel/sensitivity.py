"""How big a shift does the back-test's drift flag catch?

Regenerates the synthetic firm with a different planted step and seed each time, everything
else as shipped, runs the walk-forward back-test, and counts how often the drifting type is
flagged and how often a type with no planted shift is flagged. Thresholds are not touched.

    python -m feemodel drift-sensitivity --out output
"""

from decimal import Decimal

from . import backtest, synth
from .cost import CostBook, TaskCodeMap
from .comps import DEFAULT_MIN_COMPS

STEPS = ("1.0", "1.3", "1.5", "1.7", "2.0")
SEEDS = tuple(range(1, 21))


def one_run(seed, step, code_map, rate_card):
    """Back-test one generated firm. Returns (drift type flagged, [other types flagged], n other types judged)."""
    ds = synth.to_dataset(synth.generate(seed, drift_factor=float(step)))   # generator draws are floats by design
    book = CostBook(ds, code_map)
    records = backtest.walk_forward(ds, book, rate_card, DEFAULT_MIN_COMPS)
    summary = backtest.summarize_backtest(records, ds, book, rate_card, DEFAULT_MIN_COMPS)
    target = [r for r in summary["by_type"] if r["matter_type"] == synth.DRIFT_TYPE][0]
    others = [r for r in summary["by_type"] if r["matter_type"] != synth.DRIFT_TYPE
              and r["n_tested"] >= backtest.MIN_TESTED_TO_JUDGE]
    return {
        "seed": seed, "flagged": target["drift_flag"], "shifted_by_shuffle_test": target["drift"]["shifted"],
        "late_over_early": target["drift"]["late_over_early"], "n_tested": target["n_tested"],
        "other_types_flagged": sorted(r["matter_type"] for r in others if r["drift_flag"]),
        "other_types_judged": len(others),
    }


def run_study(code_map, rate_card, steps=STEPS, seeds=SEEDS):
    rows = []
    for step in steps:
        runs = [one_run(seed, step, code_map, rate_card) for seed in seeds]
        ratios = sorted(r["late_over_early"] for r in runs if r["late_over_early"] is not None)
        rows.append({
            "planted_step": step, "seeds": len(runs),
            "drift_type_flagged": sum(1 for r in runs if r["flagged"]),
            "drift_type_passed_shuffle_test": sum(1 for r in runs if r["shifted_by_shuffle_test"]),
            "median_observed_late_over_early": ratios[len(ratios) // 2] if ratios else None,
            "other_types_flagged": sum(len(r["other_types_flagged"]) for r in runs),
            "other_type_runs": sum(r["other_types_judged"] for r in runs),
            "runs": runs,
        })
    false_flags = sum(r["other_types_flagged"] for r in rows)
    false_runs = sum(r["other_type_runs"] for r in rows)
    unplanted = [r for r in rows if Decimal(r["planted_step"]) == 1]
    return {
        "what": "Drift-flag sensitivity on regenerated synthetic firms. Seeds %d to %d, each planted step, "
                "everything else as shipped. Thresholds unchanged." % (seeds[0], seeds[-1]),
        "drift_type": synth.DRIFT_TYPE, "shipped_step": str(Decimal(str(synth.DRIFT_FACTOR))),
        "rule": "Flag = later/earlier median ratio at least %s either way, at most %s of %d rank shuffles as "
                "lopsided, and P75 coverage more than %d points off nominal with at least %d tested matters."
                % (backtest.DRIFT_RATIO, backtest.DRIFT_MAX_SHUFFLE_SHARE, backtest.DRIFT_SHUFFLES,
                   backtest.COVERAGE_TOLERANCE_PTS, backtest.MIN_TESTED_TO_JUDGE),
        "rows": rows,
        "no_planted_shift": {
            "other_types_flagged": false_flags, "other_type_runs": false_runs,
            "drift_type_at_step_1_flagged": unplanted[0]["drift_type_flagged"] if unplanted else None,
            "drift_type_at_step_1_seeds": unplanted[0]["seeds"] if unplanted else None,
        },
    }


def format_study(study):
    lines = [study["what"], study["rule"], "",
             "%-13s %-20s %-32s %-23s %s" % ("planted step", "flagged (of seeds)", "ratio and shuffle conditions met",
                                             "median observed ratio", "unplanted types flagged")]
    for r in study["rows"]:
        lines.append("%-13s %-20s %-32s %-23s %s"
                     % (r["planted_step"] + "x" + (" (none)" if Decimal(r["planted_step"]) == 1 else ""),
                        "%d of %d" % (r["drift_type_flagged"], r["seeds"]),
                        "%d of %d" % (r["drift_type_passed_shuffle_test"], r["seeds"]),
                        "%sx" % r["median_observed_late_over_early"],
                        "%d of %d type-runs" % (r["other_types_flagged"], r["other_type_runs"])))
    nps = study["no_planted_shift"]
    lines.append("")
    lines.append("Unplanted types are the other matter types with at least %d tested matters. The same seeds are "
                 "used at every step and the other types' costs barely change with the step, so the last column "
                 "is close to the same 200 type-runs repeated, not %d independent ones."
                 % (backtest.MIN_TESTED_TO_JUDGE, nps["other_type_runs"]))
    return "\n".join(lines)
