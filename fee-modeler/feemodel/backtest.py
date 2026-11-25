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

from . import stats
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


def walk_forward(dataset, book, rate_card, min_comps=DEFAULT_MIN_COMPS):
    """Return one record per clean closed matter, in order of opening."""
    by_type = {}
    for m in clean_closed(dataset):
        by_type.setdefault(m.matter_type, []).append(m)
    records = []
    for mtype in sorted(by_type):
        history = by_type[mtype]
        for target in sorted(history, key=lambda m: (m.open_date, m.matter_id)):
            cutoff = target.open_date - timedelta(days=1)   # last day whose data may be used
            prior = [m for m in history if m.close_date < target.open_date and m.matter_id != target.matter_id]
            rec = {"matter_id": target.matter_id, "matter_type": mtype, "open_date": target.open_date,
                   "close_date": target.close_date, "n_comps": len(prior),
                   "comp_ids": [m.matter_id for m in prior],
                   "latest_comp_close": max((m.close_date for m in prior), default=None),
                   "data_cutoff": cutoff, "tested": False}
            if len(prior) >= min_comps:
                values = sorted(book.cost_as_of(m.matter_id, cutoff).value_total(rate_card) for m in prior)
                bands = {k: stats.quantile(values, p, presorted=True)
                         for k, p in (("p25", P25), ("p50", P50), ("p75", P75), ("p90", P90))}
                actual = book.cost(target.matter_id).value_total(rate_card)
                rec.update(bands)
                rec.update({
                    "tested": True, "actual": actual,
                    "inside_p25_p75": bands["p25"] <= actual <= bands["p75"],
                    "at_or_under_p25": actual <= bands["p25"],
                    "at_or_under_p50": actual <= bands["p50"],
                    "at_or_under_p75": actual <= bands["p75"],
                    "at_or_under_p90": actual <= bands["p90"],
                    "actual_over_p50": ratio(actual, bands["p50"], "0.01") if bands["p50"] > 0 else None,
                })
            records.append(rec)
    verify_no_lookahead(records, dataset)
    return records


def verify_no_lookahead(records, dataset):
    """Fail loudly if any prediction used a matter that had not closed before the target opened."""
    for rec in records:
        for cid in rec["comp_ids"]:
            comp = dataset.matters[cid]
            if cid == rec["matter_id"] or comp.close_date is None or not (comp.close_date < rec["open_date"]):
                raise LookAheadError("matter %s was modeled with comp %s, which closed %s, not before %s"
                                     % (rec["matter_id"], cid, comp.close_date, rec["open_date"]))
            if not (rec["data_cutoff"] < rec["open_date"]):
                raise LookAheadError("data cutoff for %s is not before it opened" % rec["matter_id"])
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


def overrun_check(n_over, n, band, over_pct):
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
    label = band.upper()
    text = ("At the %s figure, %d of %d back-tested matters cost more; the band implies about %d."
            % (label, n_over, n, implied)) if n else ""
    return {"band": band, "count": n_over, "n": n, "implied_pct": over_pct, "implied_count": implied,
            "judgement": judgement, "text": text}


def _coverage_block(tested):
    n = len(tested)
    cov = {k: {"count": sum(1 for r in tested if r[k]), "n": n, "nominal_pct": NOMINAL[k]} for k in NOMINAL}
    under = {b: {"count": sum(1 for r in tested if r["at_or_under_" + b]), "n": n, "nominal_pct": pct}
             for b, pct in UNDER_BANDS}
    overruns = {b: overrun_check(n - under[b]["count"], n, b, 100 - pct) for b, pct in UNDER_BANDS if b in ("p75", "p90")}
    return cov, under, overruns


def _verdict(n, cov, overruns, drift, drift_flag, min_comps):
    """(headline, full text, upper-band status). The upper bands are judged one-sided."""
    if n == 0:
        head = "Not back-tested: no matter of this type ever had %d earlier closed matters to model from." % min_comps
        return head, head, "not_tested"
    counts = "%s %s" % (overruns["p75"]["text"], overruns["p90"]["text"])
    more = [b.upper() for b in ("p75", "p90") if overruns[b]["judgement"] == "more"]
    fewer = [b.upper() for b in ("p75", "p90") if overruns[b]["judgement"] == "fewer"]
    notes = []
    if n < MIN_TESTED_TO_JUDGE:
        head, status = "Too few back-tested matters (n=%d) to judge the bands." % n, "too_few"
    elif drift_flag:
        head = ("Costs shifted over time (later closes %sx earlier ones) and bands built from older matters "
                "missed. Restrict comps to recent closes and re-test." % drift["late_over_early"])
        status = "understated" if more else "shifted"
    elif more:
        head = ("Bands understate overruns at %s (n=%d): more back-tested matters exceeded the band than chance "
                "would explain. Do not read that figure as a true %s." % (" and ".join(more), n, " or ".join(more)))
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
    return head, " ".join([head, counts] + notes), status


def summarize_backtest(records, dataset, book, rate_card, min_comps=DEFAULT_MIN_COMPS):
    """Coverage by matter type, overrun counts at the upper bands, a drift flag and a plain verdict."""
    types = sorted({m.matter_type for m in dataset.matters.values()})
    rows = []
    for mtype in types:
        recs = [r for r in records if r["matter_type"] == mtype]
        tested = [r for r in recs if r["tested"]]
        n = len(tested)
        cov, under, overruns = _coverage_block(tested)
        ratios = [r["actual_over_p50"] for r in tested if r["actual_over_p50"] is not None]
        clean = clean_closed(dataset, mtype)
        drift = drift_check([(m.close_date, book.cost(m.matter_id).value_total(rate_card)) for m in clean])
        # The drift flag keeps its own two-sided 15-point rule at P75; it is not part of the overrun judgement.
        misses = [k for k in NOMINAL if n and _off_nominal(cov[k]["count"], n, NOMINAL[k])]
        drift_flag = bool(drift["shifted"] and n >= MIN_TESTED_TO_JUDGE and "at_or_under_p75" in misses)
        head, verdict, status = _verdict(n, cov, overruns, drift, drift_flag, min_comps)
        rows.append({
            "matter_type": mtype, "n_clean_closed": len(clean), "n_tested": n, "n_skipped": len(recs) - n,
            "coverage": cov, "under_band": under, "overruns": overruns,
            "median_actual_over_p50": stats.quantile(ratios, P50).quantize(Decimal("0.01")) if ratios else None,
            "drift": drift, "drift_flag": drift_flag, "coverage_misses": misses,
            "upper_band_status": status, "verdict_headline": head, "verdict": verdict,
        })
    tested_all = [r for r in records if r["tested"]]
    cov, under, overruns = _coverage_block(tested_all)
    head, verdict, status = _verdict(len(tested_all), cov, overruns, {"late_over_early": None}, False, min_comps)
    return {"min_comps": min_comps, "tolerance_pts": COVERAGE_TOLERANCE_PTS, "by_type": rows, "overall": cov,
            "overall_under_band": under, "overall_overruns": overruns, "overall_upper_band_status": status,
            "overall_headline": head, "overall_verdict": verdict, "n_records": len(records), "n_tested": len(tested_all),
            "overrun_rule": "Upper bands are judged one-sided with an exact binomial check: a band is said to "
                            "understate overruns when seeing that many matters above it, or more, would happen "
                            "less than 1 time in 20 if the band were right. With about a dozen matter types and "
                            "two bands each, expect the odd flag by chance.",
            "method": "Walk-forward. Each matter is modeled only from same-type matters that closed before it "
                      "opened, using time dated before it opened. Abnormally closed matters are neither tested "
                      "nor used as comps. Amounts are at today's standard rates on both sides."}


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
            notes.append("Costs shifted over time; use recent comps only and re-test.")
        elif row.get("upper_band_status") == "understated":
            verdict = "Modelable, bands understate overruns"
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
            "drift_flag": bool(row.get("drift_flag")),
            "verdict": verdict, "notes": notes,
        })
    return {"min_comps": min_comps, "rows": rows}
