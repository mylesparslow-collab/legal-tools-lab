"""Two measurements on regenerated synthetic firms. Nothing here tunes anything.

1. Drift study: how big a planted shift does the change check catch, beside the first drift
   rule it replaced, and how often is a type with no planted shift flagged.

       python -m feemodel drift-sensitivity --out output                 # evaluation seeds 1 to 20
       python -m feemodel drift-sensitivity --seeds 101-120 --alpha 1/50  # how the threshold was chosen

2. Calibration study: overrun rates of the planning bands beside the descriptive comp
   quantiles, firm by firm.

       python -m feemodel calibration-study --out output                 # evaluation seeds 1 to 20
       python -m feemodel calibration-study --seeds 101-110              # the seeds the method was chosen on
"""

from decimal import Decimal

from . import backtest, bands, drift, synth
from .cost import CostBook
from .comps import DEFAULT_MIN_COMPS
from .money import ratio

STEPS = ("1.0", "1.3", "1.5", "1.7", "2.0")
GRADUAL = ("0.12",)
SEEDS = tuple(range(1, 21))
TUNING_SEEDS_DRIFT = tuple(range(101, 121))
TUNING_SEEDS_BANDS = tuple(range(101, 111))


def parse_seeds(text):
    """'1-20' or '3,5,8' or a mix."""
    out = []
    for part in str(text).split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return tuple(out)


def build(seed, code_map, step=None, per_year=None):
    """One generated firm. The generator draws in floats by design; costs are Decimal from the loader on."""
    kwargs = {}
    if per_year is not None:
        kwargs["drift_per_year"] = float(per_year)
    elif step is not None:
        kwargs["drift_factor"] = float(step)
    ds = synth.to_dataset(synth.generate(seed, **kwargs))
    return ds, CostBook(ds, code_map)


def _over(recs, key):
    return sum(1 for r in recs if not r[key])


def one_run(seed, code_map, rate_card, step=None, per_year=None, alpha=drift.DRIFT_ALPHA):
    ds, book = build(seed, code_map, step, per_year)
    records = backtest.walk_forward(ds, book, rate_card, DEFAULT_MIN_COMPS)
    new, old = {}, {}
    for mtype in sorted({m.matter_type for m in ds.matters.values()}):
        clean = backtest.clean_closed(ds, mtype)
        tested = [r for r in records if r["matter_type"] == mtype and r["tested"]]
        scan = drift.change_point_scan(backtest._drift_items(clean, book, rate_card), alpha=alpha)
        if scan["judged"]:
            new[mtype] = scan
        if len(tested) >= backtest.MIN_TESTED_TO_JUDGE:
            old[mtype] = backtest.old_drift_rule(clean, tested, book, rate_card)[1]
    t = synth.DRIFT_TYPE
    mine_d = [r for r in records if r["matter_type"] == t and r["tested"]]
    mine_p = [r for r in records if r["matter_type"] == t and r["plan_tested"]]
    scan = new.get(t)
    return {
        "seed": seed,
        "new_flagged": bool(scan and scan["flagged"]), "old_flagged": bool(old.get(t)),
        "change_date": scan["change_date"] if scan and scan["flagged"] else None,
        "after_over_before": scan["after_over_before"] if scan else None,
        "new_other_flagged": sorted(k for k, v in new.items() if k != t and v["flagged"]),
        "new_other_judged": sum(1 for k in new if k != t),
        "old_other_flagged": sorted(k for k, v in old.items() if k != t and v),
        "old_other_judged": sum(1 for k in old if k != t),
        "drift_type_descriptive": {"n": len(mine_d), "over_p75": _over(mine_d, "at_or_under_p75"),
                                   "over_p90": _over(mine_d, "at_or_under_p90")},
        "drift_type_planning": {"n": len(mine_p), "over_p75": _over(mine_p, "plan_at_or_under_p75"),
                                "over_p90": _over(mine_p, "plan_at_or_under_p90")},
    }


def _pool(runs, key):
    return {k: sum(r[key][k] for r in runs) for k in ("n", "over_p75", "over_p90")}


def _row(label, kind, runs):
    days = sorted((r["change_date"] - synth.DRIFT_FROM).days for r in runs if r["change_date"] is not None)
    ratios = sorted(r["after_over_before"] for r in runs if r["after_over_before"] is not None)
    return {
        "condition": label, "kind": kind, "seeds": len(runs),
        "new_flagged": sum(1 for r in runs if r["new_flagged"]),
        "old_flagged": sum(1 for r in runs if r["old_flagged"]),
        "median_days_estimate_minus_true": days[len(days) // 2] if days and kind == "step" else None,
        "median_after_over_before": ratios[len(ratios) // 2] if ratios else None,
        "new_other_flagged": sum(len(r["new_other_flagged"]) for r in runs),
        "new_other_judged": sum(r["new_other_judged"] for r in runs),
        "old_other_flagged": sum(len(r["old_other_flagged"]) for r in runs),
        "old_other_judged": sum(r["old_other_judged"] for r in runs),
        "drift_type_descriptive": _pool(runs, "drift_type_descriptive"),
        "drift_type_planning": _pool(runs, "drift_type_planning"),
        "runs": runs,
    }


def run_study(code_map, rate_card, steps=STEPS, seeds=SEEDS, gradual=GRADUAL, alpha=drift.DRIFT_ALPHA):
    rows = []
    for step in steps:
        kind = "none" if Decimal(step) == 1 else "step"
        rows.append(_row(step + "x" + (" (none)" if kind == "none" else ""), kind,
                         [one_run(seed, code_map, rate_card, step=step, alpha=alpha) for seed in seeds]))
        rows[-1]["planted_step"] = step
    for rate in gradual:
        rows.append(_row("gradual %s%% a year" % (Decimal(rate) * 100).quantize(Decimal("1")), "gradual",
                         [one_run(seed, code_map, rate_card, per_year=rate, alpha=alpha) for seed in seeds]))
        rows[-1]["per_year"] = rate
    none = [r for r in rows if r["kind"] == "none"]
    unplanted = None
    if none:
        r = none[0]
        unplanted = {
            "new_flagged": r["new_other_flagged"] + r["new_flagged"], "new_judged": r["new_other_judged"] + r["seeds"],
            "old_flagged": r["old_other_flagged"] + r["old_flagged"], "old_judged": r["old_other_judged"] + r["seeds"],
        }
    return {
        "what": "Drift study on regenerated synthetic firms, seeds %s. The planted type is %s; a step applies to "
                "matters opened from %s, a gradual drift compounds from the first opening date. Everything else is "
                "as shipped." % (_seed_text(seeds), synth.DRIFT_TYPE, synth.DRIFT_FROM),
        "seeds": list(seeds), "alpha": list(alpha), "shipped_alpha": list(drift.DRIFT_ALPHA),
        "threshold_seeds": "Thresholds were chosen on seeds %d to %d (rerun with --seeds %d-%d and --alpha to see the "
                           "alternatives). Seeds 1 to 20 were not looked at until the thresholds were fixed."
                           % (TUNING_SEEDS_DRIFT[0], TUNING_SEEDS_DRIFT[-1], TUNING_SEEDS_DRIFT[0], TUNING_SEEDS_DRIFT[-1]),
        "drift_type": synth.DRIFT_TYPE, "shipped_step": str(Decimal(str(synth.DRIFT_FACTOR))),
        "new_rule": "New change check: scan of every split by opening date (at least %d matters each side), flagged "
                    "when at most %d in %d of %d seeded reshuffles are as lopsided and the medians differ by %sx or more."
                    % (drift.DRIFT_MIN_SEG, alpha[0], alpha[1], drift.DRIFT_SHUFFLES, drift.DRIFT_MATERIAL),
        "old_rule": "Old rule: later half of closes vs earlier half differs by %sx, at most %s of %d rank shuffles as "
                    "lopsided, and descriptive P75 coverage more than %d points off nominal with at least %d tested."
                    % (backtest.DRIFT_RATIO, backtest.DRIFT_MAX_SHUFFLE_SHARE, backtest.DRIFT_SHUFFLES,
                       backtest.COVERAGE_TOLERANCE_PTS, backtest.MIN_TESTED_TO_JUDGE),
        "rows": rows, "no_planted_shift": unplanted,
    }


def _seed_text(seeds):
    seeds = list(seeds)
    if seeds == list(range(seeds[0], seeds[-1] + 1)):
        return "%d to %d" % (seeds[0], seeds[-1])
    return ", ".join(str(s) for s in seeds)


def _pct(count, n):
    return "%s%%" % ratio(Decimal(count) * 100, Decimal(n), "0.1") if n else "n/a"


def format_study(study):
    lines = [study["what"], study["new_rule"], study["old_rule"], study["threshold_seeds"], "",
             "%-22s %-14s %-14s %-26s %-26s %s" % ("planted", "new: flagged", "old: flagged", "new: other types flagged",
                                                   "old: other types flagged", "new: median date error")]
    for r in study["rows"]:
        err = r["median_days_estimate_minus_true"]
        lines.append("%-22s %-14s %-14s %-26s %-26s %s"
                     % (r["condition"], "%d of %d" % (r["new_flagged"], r["seeds"]), "%d of %d" % (r["old_flagged"], r["seeds"]),
                        "%d of %d (%s)" % (r["new_other_flagged"], r["new_other_judged"],
                                           _pct(r["new_other_flagged"], r["new_other_judged"])),
                        "%d of %d (%s)" % (r["old_other_flagged"], r["old_other_judged"],
                                           _pct(r["old_other_flagged"], r["old_other_judged"])),
                        ("%+d days" % err) if err is not None else "n/a"))
    u = study["no_planted_shift"]
    if u:
        lines += ["", "With nothing planted (the 1.0x row, counting %s too): new check flags %d of %d type-runs (%s); "
                      "old rule %d of %d (%s)."
                  % (study["drift_type"], u["new_flagged"], u["new_judged"], _pct(u["new_flagged"], u["new_judged"]),
                     u["old_flagged"], u["old_judged"], _pct(u["old_flagged"], u["old_judged"]))]
    lines += ["", "Does acting on it help? Back-tested matters of the planted type above their band, pooled over the seeds:",
              "%-22s %-34s %s" % ("planted", "comp quantiles (descriptive)", "planning bands (higher of two on a flag)"),
              "%-22s %-34s %s" % ("", "over P75, over P90, of n", "over P75, over P90, of n")]
    for r in study["rows"]:
        d, p = r["drift_type_descriptive"], r["drift_type_planning"]
        lines.append("%-22s %-34s %s"
                     % (r["condition"],
                        "%d (%s), %d (%s), %d" % (d["over_p75"], _pct(d["over_p75"], d["n"]), d["over_p90"],
                                                  _pct(d["over_p90"], d["n"]), d["n"]),
                        "%d (%s), %d (%s), %d" % (p["over_p75"], _pct(p["over_p75"], p["n"]), p["over_p90"],
                                                  _pct(p["over_p90"], p["n"]), p["n"])))
    lines += ["", "Other types are the matter types with nothing planted that have enough matters to be checked. The "
                  "same seeds are used in every row and those types barely change between rows, so their columns "
                  "are close to the same type-runs repeated, not independent ones. Date error is the estimated "
                  "change date minus the planted one, median over the seeds where the type was flagged."]
    return "\n".join(lines)


# ---- calibration study -------------------------------------------------------------------------

def calibration_run(seed, code_map, rate_card, min_history=bands.MIN_CAL_HISTORY):
    ds, book = build(seed, code_map)
    records = backtest.walk_forward(ds, book, rate_card, DEFAULT_MIN_COMPS, min_cal_history=min_history)
    desc = [r for r in records if r["tested"]]
    plan = [r for r in records if r["plan_tested"]]
    both = [r for r in records if r["tested"] and r["plan_tested"] and r["p90"] > 0]
    widths = sorted(r["plan"]["p90"] / r["p90"] for r in both)

    def more(recs, key, over_pct):
        found = []
        for mtype in sorted({r["matter_type"] for r in recs}):
            mine = [r for r in recs if r["matter_type"] == mtype]
            if len(mine) >= backtest.MIN_TESTED_TO_JUDGE and backtest.overrun_check(
                    _over(mine, key), len(mine), "p", over_pct)["judgement"] == "more":
                found.append("%s (%d of %d)" % (mtype, _over(mine, key), len(mine)))
        return found

    flagged = [r for r in plan if r["matter_type"] != synth.DRIFT_TYPE and r["drift"] and r["drift"]["flagged"]]
    unplanted = {
        "flagged_predictions": len(flagged),
        "types": sorted({r["matter_type"] for r in flagged}),
        "p90_below_whole_history": sum(1 for r in flagged if r["plan"]["p90"] < r["plan_whole"]["p90"]),
        "any_band_below_whole_history": sum(1 for r in flagged if any(r["plan"][b] < r["plan_whole"][b] for b in r["plan"])),
        "p90_raised": sum(1 for r in flagged if r["plan"]["p90"] > r["plan_whole"]["p90"]),
        "said_costs_fell": sum(1 for r in flagged if r["drift"]["after_over_before"] < 1),
    }
    out = {"seed": seed, "unplanted_flags": unplanted, "types_judged": sum(1 for t in {r["matter_type"] for r in plan}
                                             if sum(1 for r in plan if r["matter_type"] == t) >= backtest.MIN_TESTED_TO_JUDGE),
           "median_planning_p90_over_descriptive_p90": widths[len(widths) // 2].quantize(Decimal("0.01")) if widths else None}
    for name, recs, k75, k90 in (("descriptive", desc, "at_or_under_p75", "at_or_under_p90"),
                                 ("finite_sample_only", plan, "base_at_or_under_p75", "base_at_or_under_p90"),
                                 ("planning", plan, "plan_at_or_under_p75", "plan_at_or_under_p90")):
        out[name] = {"n": len(recs), "over_p75": _over(recs, k75), "over_p90": _over(recs, k90),
                     "types_more_p75": len(more(recs, k75, 25)), "types_more_p90": len(more(recs, k90, 10)),
                     "which_p75": more(recs, k75, 25), "which_p90": more(recs, k90, 10)}
    return out


def run_calibration_study(code_map, rate_card, seeds=SEEDS, min_history=bands.MIN_CAL_HISTORY):
    runs = [calibration_run(seed, code_map, rate_card, min_history) for seed in seeds]
    total = {}
    for name in ("descriptive", "finite_sample_only", "planning"):
        total[name] = {k: sum(r[name][k] for r in runs) for k in ("n", "over_p75", "over_p90", "types_more_p75", "types_more_p90")}
    widths = sorted(r["median_planning_p90_over_descriptive_p90"] for r in runs)
    return {
        "what": "Calibration study on regenerated synthetic firms, seeds %s, generator as shipped (planted step %sx). "
                "Each firm is back-tested walk-forward; overruns are counted against the descriptive comp quantiles, "
                "the finite-sample bands alone, and the planning bands (finite-sample plus the upward adjustment; "
                "where the change check fires, the higher of the recent-only and whole-history versions)." % (_seed_text(seeds), Decimal(str(synth.DRIFT_FACTOR))),
        "method_seeds": "The method (same type only, upward only, at least %d earlier outcomes) was chosen on seeds "
                        "%d to %d. Seeds 1 to 20 were not looked at until it was fixed."
                        % (bands.MIN_CAL_HISTORY, TUNING_SEEDS_BANDS[0], TUNING_SEEDS_BANDS[-1]),
        "seeds": list(seeds), "min_history": min_history, "runs": runs, "total": total,
        "unplanted_flags": {k: sum(r["unplanted_flags"][k] for r in runs)
                            for k in ("flagged_predictions", "p90_below_whole_history", "any_band_below_whole_history",
                                      "p90_raised", "said_costs_fell")},
        "type_runs_judged": sum(r["types_judged"] for r in runs),
        "median_planning_p90_over_descriptive_p90": widths[len(widths) // 2] if widths else None,
    }


def format_calibration_study(study):
    def cell(d, k):
        return "%4d/%-4d %5s" % (d[k], d["n"], _pct(d[k], d["n"]))

    lines = [study["what"], study["method_seeds"], "",
             "Share of back-tested matters that cost more than the band. Implied: 25% over P75, 10% over P90.",
             "%-6s %-33s %-33s %-33s" % ("", "comp quantiles (descriptive)", "finite-sample bands alone", "planning bands"),
             "%-6s %-16s %-16s %-16s %-16s %-16s %-16s" % ("seed", "over P75", "over P90", "over P75", "over P90",
                                                          "over P75", "over P90")]
    for r in study["runs"] + [dict(study["total"], seed="all")]:
        lines.append("%-6s %-16s %-16s %-16s %-16s %-16s %-16s"
                     % (r["seed"], cell(r["descriptive"], "over_p75"), cell(r["descriptive"], "over_p90"),
                        cell(r["finite_sample_only"], "over_p75"), cell(r["finite_sample_only"], "over_p90"),
                        cell(r["planning"], "over_p75"), cell(r["planning"], "over_p90")))
    t = study["total"]
    lines += ["", "Matter types judged to understate overruns (one-sided binomial, 1 in 20), of %d type-runs with at "
                  "least %d back-tested matters:" % (study["type_runs_judged"], backtest.MIN_TESTED_TO_JUDGE)]
    for name, label in (("descriptive", "comp quantiles (descriptive)"), ("finite_sample_only", "finite-sample bands alone"),
                        ("planning", "planning bands")):
        lines.append("  %-30s at P75: %d   at P90: %d" % (label, t[name]["types_more_p75"], t[name]["types_more_p90"]))
    still = ["seed %s, P%s: %s" % (r["seed"], b, t_) for r in study["runs"] for b in ("75", "90")
             for t_ in r["planning"]["which_p" + b]]
    lines += ["", "Where the planning bands still understate: " + ("; ".join(still) if still else "nowhere") + "."]
    u = study["unplanted_flags"]
    lines += ["", "A flag never lowers a figure. Across these seeds the change check was flagging an unplanted matter "
                  "type at the moment of %d back-test predictions (%d of them saying costs had fallen). The planning P90 "
                  "was below the whole-history planning P90 in %d of them, and any band was below in %d. It was raised "
                  "above the whole-history P90 in %d."
              % (u["flagged_predictions"], u["said_costs_fell"], u["p90_below_whole_history"],
                 u["any_band_below_whole_history"], u["p90_raised"])]
    lines += ["", "Cost of the fix: the planning P90 is %sx the descriptive P90 for the median back-tested matter "
                  "(median of the per-seed medians)." % study["median_planning_p90_over_descriptive_p90"]]
    return "\n".join(lines)
