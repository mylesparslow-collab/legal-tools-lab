"""Walk-forward back-test and the matter-type modelability table.

For each past matter, the bands are built only from matters of the same type that had
already closed before it opened, using only time dated before it opened. Then the matter's
actual cost is compared with those bands. Coverage near the nominal share means the bands
can be trusted on this data; coverage far from it means they cannot.

All amounts are in today's standard rates on both sides (comps and the matter tested), so
rate normalization is a change of units and carries no information about outcomes.
"""

import random
from datetime import timedelta
from decimal import Decimal

from . import bands, drift, stats
from .comps import DEFAULT_MIN_COMPS
from .money import ZERO, ratio

P25, P50, P75, P90 = Decimal("0.25"), Decimal("0.50"), Decimal("0.75"), Decimal("0.90")
NOMINAL = {"inside_p25_p75": 50, "at_or_under_p75": 75, "at_or_under_p90": 90}
COVERAGE_TOLERANCE_PTS = 15       # coverage this many points off nominal counts as a miss
MIN_TESTED_TO_JUDGE = 10
DRIFT_MIN_N = 16
DRIFT_RATIO = Decimal("1.3")      # later-half median vs earlier-half median
DRIFT_SHUFFLES = 1000
DRIFT_SEED = 7
DRIFT_MAX_SHUFFLE_SHARE = Decimal("0.02")
THIN_N = 20
UNDER_BANDS = (("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))
OVERRUN_ALPHA = (1, 20)           # one-sided exact binomial check: 1 in 20


class LookAheadError(AssertionError):
    pass


def clean_closed(dataset, matter_type=None):
    """Closed, normally completed matters, oldest close first."""
    out = [m for m in dataset.matters.values()
           if m.is_closed and not m.is_abnormal_close and (matter_type is None or m.matter_type == matter_type)]
    out.sort(key=lambda m: (m.close_date, m.matter_id))
    return out


def _drift_items(matters, book, rate_card, cutoff=None):
    return [(m.open_date, m.matter_id,
             (book.cost_as_of(m.matter_id, cutoff) if cutoff else book.cost(m.matter_id)).value_total(rate_card))
            for m in matters]


def walk_forward(dataset, book, rate_card, min_comps=DEFAULT_MIN_COMPS, act_on_drift=True, calibrate=True,
                 min_cal_history=bands.MIN_CAL_HISTORY):
    """One record per clean closed matter, in order of opening across all matter types.

    Each record carries two predictions made as of the day the matter opened:
    - descriptive: interpolated quantiles of every earlier closed matter of the type (keys p25..p90);
    - planning: the bands the tool would now quote from (key "plan"): finite-sample quantiles and a
      walk-forward adjustment learned from earlier matters whose cost was already known that day.
      If the change check fires, a recent-only version is also built and each band is the higher
      of the two (key "plan_whole" keeps the whole-history version).
    """
    by_type = {}
    for m in clean_closed(dataset):
        by_type.setdefault(m.matter_type, []).append(m)
    records = []
    scored = []          # earlier planning-tested records, the source of adjustment ratios
    for target in sorted(clean_closed(dataset), key=lambda m: (m.open_date, m.matter_id)):
        mtype = target.matter_type
        cutoff = target.open_date - timedelta(days=1)   # last day whose data may be used
        prior = [m for m in by_type[mtype] if m.close_date < target.open_date and m.matter_id != target.matter_id]
        rec = {"matter_id": target.matter_id, "matter_type": mtype, "open_date": target.open_date,
               "close_date": target.close_date, "n_comps": len(prior),
               "comp_ids": [m.matter_id for m in prior],
               "latest_comp_close": max((m.close_date for m in prior), default=None),
               "data_cutoff": cutoff, "tested": False, "plan_tested": False, "plan_reason": None,
               "plan_comp_ids": [], "drift": None, "cal_ids": []}
        actual = book.cost(target.matter_id).value_total(rate_card)
        value_of = {m.matter_id: book.cost_as_of(m.matter_id, cutoff).value_total(rate_card) for m in prior}
        if len(prior) >= min_comps:
            values = sorted(value_of.values())
            emp = {k: stats.quantile(values, p, presorted=True)
                   for k, p in (("p25", P25), ("p50", P50), ("p75", P75), ("p90", P90))}
            rec.update(emp)
            rec.update({
                "tested": True, "actual": actual,
                "inside_p25_p75": emp["p25"] <= actual <= emp["p75"],
                "at_or_under_p25": actual <= emp["p25"], "at_or_under_p50": actual <= emp["p50"],
                "at_or_under_p75": actual <= emp["p75"], "at_or_under_p90": actual <= emp["p90"],
                "actual_over_p50": ratio(actual, emp["p50"], "0.01") if emp["p50"] > 0 else None,
            })
        # Planning bands. Whole history first; if the change check fires, a recent-only version too,
        # and each band is the higher of the two. A flag can raise a planning figure, never lower it.
        if len(prior) < min_comps:
            rec["plan_reason"] = "too few earlier closed matters"
        else:
            mine = [s for s in scored if calibrate and s["matter_type"] == mtype and s["close_date"] < target.open_date]
            whole = bands.planning_bands([value_of[m.matter_id] for m in prior],
                                         {b: [s["scores"][b] for s in mine] for b, _q in bands.BANDS},
                                         min_history=min_cal_history)
            used = list(mine) if whole["calibrated"] else []
            plan = dict(whole["plan"])
            recent = None
            if act_on_drift and len(prior) >= 2 * drift.DRIFT_MIN_SEG:
                scan = drift.change_point_scan([(m.open_date, m.matter_id, value_of[m.matter_id]) for m in prior])
                rec["drift"] = {"flagged": scan["flagged"], "change_date": None, "n_after": None,
                                "after_over_before": scan["after_over_before"] if scan["flagged"] else None,
                                "recent_version": False, "raised": []}
                if scan["flagged"]:
                    change_date = scan["change_date"]
                    comps = [m for m in prior if m.open_date >= change_date]
                    rec["drift"].update(change_date=change_date, n_after=len(comps))
                    if len(comps) >= min_comps:
                        since = [s for s in mine if s["open_date"] >= change_date]
                        recent = bands.planning_bands(
                            [value_of[m.matter_id] for m in comps],
                            {b: [s.get("scores_recent", s["scores"])[b] for s in since] for b, _q in bands.BANDS},
                            min_history=min_cal_history)
                        rec["drift"]["recent_version"] = True
                        rec["plan_recent"] = recent["plan"]
                        rec["recent_values"] = sorted(value_of[m.matter_id] for m in comps)
                        rec["drift"]["raised"] = [b for b, _q in bands.BANDS if recent["plan"][b] > plan[b]]
                        plan = bands.higher_of(plan, recent["plan"])
            rec.update({
                "plan_tested": True, "actual": actual, "plan_comp_ids": [m.matter_id for m in prior],
                "plan_values": sorted(value_of[m.matter_id] for m in prior),
                "plan": plan, "plan_whole": whole["plan"], "base": whole["base"], "factor": whole["factor"],
                "cal_source": whole["source_summary"], "cal_ids": [s["matter_id"] for s in used],
                "plan_inside_p25_p75": plan["p25"] <= actual <= plan["p75"],
                "scores": {b: (actual / whole["base"][b]) for b, _q in bands.BANDS if whole["base"][b] > 0},
            })
            if recent is not None and all(recent["base"][b] > 0 for b, _q in bands.BANDS):
                rec["scores_recent"] = {b: actual / recent["base"][b] for b, _q in bands.BANDS}
            for b, _q in bands.BANDS:
                rec["plan_at_or_under_" + b] = actual <= plan[b]
                rec["base_at_or_under_" + b] = actual <= whole["base"][b]
            if len(rec["scores"]) == len(bands.BANDS):
                scored.append(rec)
        records.append(rec)
    records.sort(key=lambda r: (r["matter_type"], r["open_date"], r["matter_id"]))
    verify_no_lookahead(records, dataset)
    return records


def verify_no_lookahead(records, dataset):
    """Fail loudly if any prediction used something not yet known when the target opened.

    Checks the comps of both predictions and the matters whose outcomes fed the adjustment.
    """
    for rec in records:
        if not (rec["data_cutoff"] < rec["open_date"]):
            raise LookAheadError("data cutoff for %s is not before it opened" % rec["matter_id"])
        for what, ids in (("comp", rec["comp_ids"]), ("planning comp", rec.get("plan_comp_ids", [])),
                          ("adjustment matter", rec.get("cal_ids", []))):
            for cid in ids:
                other = dataset.matters[cid]
                if cid == rec["matter_id"] or other.close_date is None or not (other.close_date < rec["open_date"]):
                    raise LookAheadError("matter %s was modeled with %s %s, which closed %s, not before %s"
                                         % (rec["matter_id"], what, cid, other.close_date, rec["open_date"]))
    return True


def _double_ranks(values):
    """Twice the average rank of each value (integers, so ties need no fractions)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = i + j + 2      # 2 x average of ranks i+1 .. j+1
        i = j + 1
    return ranks


def drift_check(dated_values, n_shuffles=DRIFT_SHUFFLES, seed=DRIFT_SEED):
    """Compare the later half of closes with the earlier half. Input: [(close_date, value)].

    The ratio of the two medians is the figure shown. To avoid crying wolf on noise, a seeded
    shuffle test backs it: rank all values, sum the ranks of the later half, and count how many
    random reshuffles of the ranks give a sum at least as far from its expected value. The type
    counts as shifted only when the median ratio is at least DRIFT_RATIO either way and no more
    than DRIFT_MAX_SHUFFLE_SHARE of shuffles are as lopsided. Ranks are integers; no fitted model.
    """
    xs = sorted(dated_values, key=lambda t: t[0])
    n = len(xs)
    half = n // 2
    out = {"n": n, "n_early": half, "n_late": n - half, "median_early": None, "median_late": None,
           "late_over_early": None, "shuffles_as_extreme": None, "n_shuffles": 0, "shifted": False}
    if n < 4:
        return out
    values = [v for _d, v in xs]
    me, ml = stats.quantile(values[:half], P50), stats.quantile(values[half:], P50)
    out["median_early"], out["median_late"] = me, ml
    if me <= 0 or ml <= 0:
        return out
    r = ml / me
    out["late_over_early"] = r.quantize(Decimal("0.01"))
    if n < DRIFT_MIN_N:
        return out
    ranks = _double_ranks(values)
    expected = (n - half) * (n + 1)          # 2 x n_late x (n + 1) / 2
    observed = abs(sum(ranks[half:]) - expected)
    rng = random.Random(seed)
    pool = list(ranks)
    extreme = 0
    for _ in range(n_shuffles):
        rng.shuffle(pool)
        if abs(sum(pool[half:]) - expected) >= observed:
            extreme += 1
    out["shuffles_as_extreme"], out["n_shuffles"] = extreme, n_shuffles
    out["shifted"] = max(r, 1 / r) >= DRIFT_RATIO and extreme <= DRIFT_MAX_SHUFFLE_SHARE * n_shuffles
    return out


def _off_nominal(count, n, nominal_pct):
    """True when count/n is more than the tolerance away from nominal, in whole-number arithmetic."""
    return abs(count * 100 - nominal_pct * n) > COVERAGE_TOLERANCE_PTS * n


def overrun_check(n_over, n, band, over_pct, what="planning"):
    """How often back-tested matters cost more than a predicted upper band, against what the band implies.

    One-sided on purpose: more overruns than implied is the direction that loses money on a fixed
    or capped fee. The judgement is an exact binomial check at 1 in 20 (see OVERRUN_ALPHA): "more"
    when that many overruns or more would turn up less than 1 time in 20 if the band were right.
    "fewer" is the mirror image and is only ever a mild note.
    """
    implied = (n * over_pct + 50) // 100
    judgement = "consistent"
    if n and stats.binomial_tail_at_most(n_over, n, over_pct, 100, *OVERRUN_ALPHA, upper=True):
        judgement = "more"
    elif n and stats.binomial_tail_at_most(n_over, n, over_pct, 100, *OVERRUN_ALPHA, upper=False):
        judgement = "fewer"
    label = ("planning %s" if what == "planning" else "comp %s (descriptive)") % band.upper()
    text = ("At the %s, %d of %d back-tested matters cost more; the band implies about %d."
            % (label, n_over, n, implied)) if n else ""
    return {"band": band, "count": n_over, "n": n, "implied_pct": over_pct, "implied_count": implied,
            "judgement": judgement, "text": text}


PLAN_KEYS = {"inside_p25_p75": "plan_inside_p25_p75", "at_or_under_p25": "plan_at_or_under_p25",
             "at_or_under_p50": "plan_at_or_under_p50", "at_or_under_p75": "plan_at_or_under_p75",
             "at_or_under_p90": "plan_at_or_under_p90"}


def _coverage_block(tested, what="planning"):
    """Counts against the planning bands (what='planning') or the descriptive comp quantiles."""
    key = (lambda k: PLAN_KEYS[k]) if what == "planning" else (lambda k: k)
    n = len(tested)
    cov = {k: {"count": sum(1 for r in tested if r[key(k)]), "n": n, "nominal_pct": NOMINAL[k]} for k in NOMINAL}
    under = {b: {"count": sum(1 for r in tested if r[key("at_or_under_" + b)]), "n": n, "nominal_pct": pct}
             for b, pct in UNDER_BANDS}
    overruns = {b: overrun_check(n - under[b]["count"], n, b, 100 - pct, what)
                for b, pct in UNDER_BANDS if b in ("p75", "p90")}
    return cov, under, overruns


def _verdict(n, cov, overruns, min_comps, what="planning", shift=None):
    """(headline, full text, upper-band status). The upper bands are judged one-sided."""
    name = "Planning bands" if what == "planning" else "Comp quantiles"
    if n == 0:
        head = "Not back-tested: no matter of this type ever had %d earlier closed matters to model from." % min_comps
        return head, head, "not_tested"
    counts = "%s %s" % (overruns["p75"]["text"], overruns["p90"]["text"])
    more = [b.upper() for b in ("p75", "p90") if overruns[b]["judgement"] == "more"]
    fewer = [b.upper() for b in ("p75", "p90") if overruns[b]["judgement"] == "fewer"]
    notes = []
    if n < MIN_TESTED_TO_JUDGE:
        head, status = "Too few back-tested matters (n=%d) to judge the bands." % n, "too_few"
    elif more:
        head = ("%s understate overruns at %s (n=%d): more back-tested matters exceeded the band than chance "
                "would explain. Do not read that figure as a true %s."
                % (name, " and ".join(more), n, " or ".join(more)))
        status = "understated"
    else:
        head = "Overruns at P75 and P90 are within what chance would explain at n=%d." % n
        status = "consistent"
        if fewer:
            notes.append("Fewer overruns than implied at %s; that band may be wider than needed." % " and ".join(fewer))
    if n >= MIN_TESTED_TO_JUDGE:
        mid = cov["inside_p25_p75"]
        if _off_nominal(mid["count"], n, 50):
            notes.append("Middle band: %d of %d inside P25 to P75 against a nominal 50%%." % (mid["count"], n))
    if shift:
        notes.append(shift)
    return head, " ".join([head, counts] + notes), status


def _block(tested, min_comps, what, shift=None):
    cov, under, overruns = _coverage_block(tested, what)
    head, verdict, status = _verdict(len(tested), cov, overruns, min_comps, what, shift)
    return {"n_tested": len(tested), "coverage": cov, "under_band": under, "overruns": overruns,
            "upper_band_status": status, "verdict_headline": head, "verdict": verdict}


def old_drift_rule(clean, tested, book, rate_card):
    """The first drift rule, kept only so the two can be compared: (half-split result, flag).

    Flag = later half of closes vs earlier half differs by DRIFT_RATIO with a shuffle test behind it,
    and the descriptive P75 coverage is more than 15 points off nominal on at least 10 tested matters.
    """
    old = drift_check([(m.close_date, book.cost(m.matter_id).value_total(rate_card)) for m in clean])
    n = len(tested)
    under = sum(1 for r in tested if r["at_or_under_p75"])
    return old, bool(old["shifted"] and n >= MIN_TESTED_TO_JUDGE and _off_nominal(under, n, 75))


def shift_text(scan):
    """One sentence on a flagged change in a type's costs, or None."""
    if not scan or not scan.get("flagged"):
        return None
    return ("Costs appear to have %s: the %d matters opened from %s cost %sx the %d opened before, at the same "
            "rates. A prompt to look, not a finding. Each planning band is the higher of the recent-only and "
            "whole-history versions, so the flag can raise a band but not lower it."
            % ("risen" if scan["after_over_before"] > 1 else "fallen", scan["n_after"], scan["change_date"],
               scan["after_over_before"], scan["n_before"]))


def summarize_backtest(records, dataset, book, rate_card, min_comps=DEFAULT_MIN_COMPS):
    """By matter type: how the planning bands held up, the descriptive comp quantiles beside them,
    whether the type's costs changed over time, and a plain verdict.

    The top-level keys of each row (n_tested, coverage, under_band, overruns, upper_band_status,
    verdict) are for the planning bands. The same keys for the descriptive quantiles are under
    'descriptive'.
    """
    types = sorted({m.matter_type for m in dataset.matters.values()})
    rows = []
    for mtype in types:
        recs = [r for r in records if r["matter_type"] == mtype]
        tested = [r for r in recs if r["tested"]]
        planned = [r for r in recs if r["plan_tested"]]
        clean = clean_closed(dataset, mtype)
        scan = drift.change_point_scan(_drift_items(clean, book, rate_card))
        row = _block(planned, min_comps, "planning", shift_text(scan))
        desc = _block(tested, min_comps, "descriptive")
        ratios = [r["actual_over_p50"] for r in tested if r["actual_over_p50"] is not None]
        old, old_flag = old_drift_rule(clean, tested, book, rate_card)
        row.update({
            "matter_type": mtype, "n_clean_closed": len(clean), "n_skipped": len(recs) - len(planned),
            "descriptive": desc,
            "calibration": {
                "adjusted": sum(1 for r in planned if r["cal_source"] == "type"),
                "unadjusted": sum(1 for r in planned if r["cal_source"] != "type"),
                "flagged_when_modeled": sum(1 for r in planned if r["drift"] and r["drift"]["flagged"]),
                "raised_by_change_check": sum(1 for r in planned if r["drift"] and r["drift"]["raised"]),
            },
            "median_actual_over_p50": stats.quantile(ratios, P50).quantize(Decimal("0.01")) if ratios else None,
            "drift": scan, "drift_flag": bool(scan["flagged"]),
            "drift_old": old, "drift_flag_old": old_flag,
        })
        rows.append(row)
    overall = _block([r for r in records if r["plan_tested"]], min_comps, "planning")
    overall_desc = _block([r for r in records if r["tested"]], min_comps, "descriptive")
    return {"min_comps": min_comps, "tolerance_pts": COVERAGE_TOLERANCE_PTS, "by_type": rows,
            "overall": overall["coverage"], "overall_under_band": overall["under_band"],
            "overall_overruns": overall["overruns"], "overall_upper_band_status": overall["upper_band_status"],
            "overall_headline": overall["verdict_headline"], "overall_verdict": overall["verdict"],
            "overall_descriptive": overall_desc,
            "n_records": len(records), "n_tested": overall["n_tested"],
            "min_cal_history": bands.MIN_CAL_HISTORY,
            "overrun_rule": "Upper bands are judged one-sided with an exact binomial check: a band is said to "
                            "understate overruns when seeing that many matters above it, or more, would happen "
                            "less than 1 time in 20 if the band were right. With about a dozen matter types and "
                            "two bands each, expect the odd flag by chance.",
            "bands_note": "Planning bands: the comp at position ceil((n + 1) x q) among the comps, raised by a "
                          "factor learned from how earlier matters of the type came in against their own bands "
                          "(never lowered; needs %d earlier outcomes, otherwise unadjusted). Comp quantiles "
                          "(descriptive): interpolated quantiles of all earlier closed matters of the type; they "
                          "describe the comps and are shown for comparison." % bands.MIN_CAL_HISTORY,
            "drift_rule": "Change check: matters of a type are put in order of opening and every split with at "
                          "least %d on each side is tried. A type is flagged when no more than %d in %d of %d "
                          "seeded reshuffles of the same costs split as cleanly as the best real split, and the "
                          "medians either side differ by %sx or more. The date of the change is estimated, not "
                          "supplied. It is a prompt to look: it misses real changes and flags types where nothing "
                          "changed (measured rates are in the README). These thresholds are settings of this tool, not industry figures."
                          % (drift.DRIFT_MIN_SEG, drift.DRIFT_ALPHA[0], drift.DRIFT_ALPHA[1], drift.DRIFT_SHUFFLES,
                             drift.DRIFT_MATERIAL),
            "method": "Walk-forward. Each matter is modeled only from same-type matters that closed before it "
                      "opened, using time dated before it opened; the change check and the band adjustment are "
                      "also run as of that day; where the check fires, each band is the higher of the recent-only and "
                      "whole-history versions. Abnormally closed matters are neither tested nor used as comps. "
                      "Amounts are at today's standard rates on both sides."}


def modelability(dataset, book, summary, min_comps=DEFAULT_MIN_COMPS):
    """Which matter types have enough clean history to model."""
    bt = {row["matter_type"]: row for row in summary["by_type"]}
    rows = []
    for mtype in sorted({m.matter_type for m in dataset.matters.values()}):
        ms = [m for m in dataset.matters.values() if m.matter_type == mtype]
        clean = clean_closed(dataset, mtype)
        hours = sum((book.cost(m.matter_id).total_hours for m in clean), ZERO)
        fallback = sum((book.cost(m.matter_id).fallback_hours for m in clean), ZERO)
        coded_pct = ((hours - fallback) * 100 / hours).quantize(Decimal("1")) if hours > 0 else None
        row = bt.get(mtype, {})
        notes = []
        if len(clean) < min_comps:
            verdict = "Not modelable"
            notes.append("%d clean closed matters; %d required. %d more needed."
                         % (len(clean), min_comps, min_comps - len(clean)))
        elif row.get("drift_flag"):
            verdict = "Modelable with care"
            notes.append(shift_text(row["drift"]))
            if row.get("upper_band_status") == "understated":
                notes.append("Planning bands still understate overruns in the back-test.")
        elif row.get("upper_band_status") == "understated":
            verdict = "Modelable, planning bands understate overruns"
        elif len(clean) < THIN_N:
            verdict = "Modelable, thin"
            notes.append("Fewer than %d clean closed matters; intervals will be wide." % THIN_N)
        else:
            verdict = "Modelable"
        if row.get("n_tested"):
            notes.append("Back-test: %s %s" % (row["overruns"]["p75"]["text"], row["overruns"]["p90"]["text"]))
            if row.get("n_tested") < MIN_TESTED_TO_JUDGE:
                notes.append("Too few back-tested matters to judge the bands.")
        elif len(clean) >= min_comps:
            notes.append("Not back-tested.")
        if coded_pct is not None and coded_pct < 80:
            notes.append("Only %s%% of hours carry a usable task code; phase figures are low confidence." % coded_pct)
        rows.append({
            "matter_type": mtype, "n_matters": len(ms),
            "n_open": sum(1 for m in ms if m.status != "closed"),
            "n_closed": sum(1 for m in ms if m.is_closed),
            "n_abnormal": sum(1 for m in ms if m.is_abnormal_close),
            "n_clean_closed": len(clean),
            "first_close": clean[0].close_date if clean else None,
            "last_close": clean[-1].close_date if clean else None,
            "task_coded_hours_pct": coded_pct,
            "n_backtested": row.get("n_tested", 0),
            "coverage_p25_p75": row.get("coverage", {}).get("inside_p25_p75"),
            "overruns": row.get("overruns"), "upper_band_status": row.get("upper_band_status"),
            "backtest_verdict": row.get("verdict"),
            "descriptive_overruns": row.get("descriptive", {}).get("overruns"),
            "drift_flag": bool(row.get("drift_flag")),
            "change_date": row["drift"]["change_date"] if row.get("drift_flag") else None,
            "verdict": verdict, "notes": notes,
        })
    return {"min_comps": min_comps, "rows": rows}
