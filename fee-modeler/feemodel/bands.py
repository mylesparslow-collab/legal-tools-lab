"""Planning bands: quantiles meant to hold up on the next matter, not just describe the comps.

Two steps, both using only the past:

1. Finite-sample prediction quantile. With n comps, the q band is the comp at position
   ceil((n + 1) * q) in sorted order (the largest comp when that position is past the end).
   If the next matter is like the comps, it falls at or under that comp at least q of the time.
   An interpolated quantile of the comps does not have that property; it under-covers.

2. Walk-forward adjustment, upward only. For earlier matters of the same type whose cost is
   already known, take the ratio actual / step-1 band, as that band would have been set the day
   each one opened. The factor is the ceil((m + 1) * q)-th of those m ratios, and never less
   than 1. If the step-1 bands have been right, the factor is about 1; if matters of this type
   have been running over them, it is above 1 and the band is raised. It needs at least
   MIN_CAL_HISTORY such ratios; with fewer, the band is step 1 only and is labelled unadjusted.

Why this shape (chosen on generator seeds 101 to 110, then checked on other seeds; see the
README and `python -m feemodel calibration-study`):
- Upward only, because the costly error is a band that is too low. Letting the factor go below
  1 brought overall overruns closer to nominal but left more matter types understating.
- Same type only. Pooling ratios across matter types was tried and was worse per type.

The descriptive quantiles "of the comps" (interpolated) are still computed and shown beside
these, labelled as descriptive.
"""

from decimal import Decimal, ROUND_CEILING

from .money import D

BANDS = (("p25", Decimal("0.25")), ("p50", Decimal("0.50")), ("p75", Decimal("0.75")), ("p90", Decimal("0.90")))
BAND_PCT = {"p25": 25, "p50": 50, "p75": 75, "p90": 90}
MIN_CAL_HISTORY = 12


def position(n, q):
    """1-based position ceil((n + 1) * q), and whether it lies within the sample."""
    k = int(((n + 1) * D(q)).to_integral_value(rounding=ROUND_CEILING))
    return max(1, min(k, n)), 1 <= k <= n


def finite_sample_quantile(sorted_values, q):
    """(value, reachable). reachable is False when n is too small for the band and the maximum is used."""
    if not sorted_values:
        raise ValueError("no values")
    k, ok = position(len(sorted_values), q)
    return sorted_values[k - 1], ok


def finite_sample_bands(values, bands=BANDS):
    xs = sorted(values)
    out, reachable = {}, {}
    for name, q in bands:
        out[name], reachable[name] = finite_sample_quantile(xs, q)
    return out, reachable


def adjustment(type_ratios, q, min_history=MIN_CAL_HISTORY):
    """(factor, source, m). source is 'type' or 'none'. The factor is never below 1."""
    if len(type_ratios) >= min_history:
        factor, _ok = finite_sample_quantile(sorted(type_ratios), q)
        return max(factor, Decimal(1)), "type", len(type_ratios)
    return Decimal(1), "none", len(type_ratios)


def planning_bands(values, type_scores, bands=BANDS, min_history=MIN_CAL_HISTORY):
    """Planning bands for one set of comps.

    type_scores: {band name: [past actual / step-1 band ratios for this matter type]}.
    Returns dict with 'base' (step 1), 'plan', 'factor', 'source', 'm', 'reachable', 'calibrated'.
    """
    base, reachable = finite_sample_bands(values, bands)
    plan, factor, source, m = {}, {}, {}, {}
    floor = None
    for name, q in bands:
        f, src, count = adjustment(type_scores.get(name, []), q, min_history)
        value = base[name] * f
        if floor is not None and value < floor:      # keep the bands in order
            value = floor
        floor = value
        plan[name], factor[name], source[name], m[name] = value, f, src, count
    sources = set(source.values())
    return {"base": base, "plan": plan, "factor": factor, "source": source, "m": m, "reachable": reachable,
            "calibrated": sources != {"none"},
            "source_summary": "type" if sources == {"type"} else "none"}


def higher_of(a, b):
    """Band by band, the higher of two sets of planning figures."""
    return {name: max(a[name], b[name]) for name in a}
