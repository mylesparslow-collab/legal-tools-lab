"""Empirical quantiles and bootstrap intervals. No fitted models.

Quantiles and the bootstrap run on Decimal values end to end: the interpolation is Decimal
arithmetic and resampling only draws integer indexes. No float appears in this module; the
ratios behind the skew warning are Decimal too.
"""

import math
import random
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from .money import D, ZERO

DEFAULT_PROBS = (Decimal("0.25"), Decimal("0.50"), Decimal("0.75"), Decimal("0.90"))
PROB_LABELS = {Decimal("0.10"): "p10", Decimal("0.25"): "p25", Decimal("0.50"): "p50",
               Decimal("0.75"): "p75", Decimal("0.90"): "p90"}
SMALL_SAMPLE_N = 20
SKEW_P90_TO_P50 = Decimal("2.5")
SKEW_MEAN_TO_MEDIAN = Decimal("1.3")


def label(prob):
    prob = D(prob)
    return PROB_LABELS.get(prob, "p%s" % (prob * 100).normalize())


def quantile(values, prob, presorted=False):
    """Empirical quantile with linear interpolation between order statistics."""
    if not values:
        raise ValueError("quantile of an empty sample")
    prob = D(prob)
    if prob < 0 or prob > 1:
        raise ValueError("probability must be between 0 and 1")
    xs = values if presorted else sorted(values)
    n = len(xs)
    if n == 1:
        return xs[0]
    h = (n - 1) * prob
    lo = int(h.to_integral_value(rounding=ROUND_FLOOR))
    if lo >= n - 1:
        return xs[-1]
    return xs[lo] + (h - lo) * (xs[lo + 1] - xs[lo])


def order_stat(values, prob):
    """Smallest observed value v such that at least `prob` of the sample is <= v."""
    if not values:
        raise ValueError("order statistic of an empty sample")
    xs = sorted(values)
    k = int((D(prob) * len(xs)).to_integral_value(rounding=ROUND_CEILING))
    k = max(1, min(k, len(xs)))
    return xs[k - 1]


def mean(values):
    if not values:
        raise ValueError("mean of an empty sample")
    return sum(values, ZERO) / len(values)


def share_at_or_below(values, threshold):
    """(count, n) of values at or below the threshold."""
    return sum(1 for v in values if v <= threshold), len(values)


def bootstrap_quantiles(values, probs=DEFAULT_PROBS, n_boot=1000, seed=0, level=Decimal("0.90")):
    """Percentile bootstrap interval for each quantile. Seeded, so a rerun gives the same numbers."""
    xs = sorted(values)
    n = len(xs)
    if n < 2:
        return {D(p): (xs[0], xs[0]) if xs else None for p in probs}
    rng = random.Random(seed)
    draws = {D(p): [] for p in probs}
    for _ in range(n_boot):
        sample = sorted(xs[rng.randrange(n)] for _ in range(n))
        for p in draws:
            draws[p].append(quantile(sample, p, presorted=True))
    tail = (1 - D(level)) / 2
    out = {}
    for p, vals in draws.items():
        vals.sort()
        out[p] = (quantile(vals, tail, presorted=True), quantile(vals, 1 - tail, presorted=True))
    return out


def summarize(values, probs=DEFAULT_PROBS, n_boot=1000, seed=0, with_intervals=True):
    """n, mean, quantiles and (optionally) bootstrap intervals for a sample of Decimals."""
    xs = sorted(values)
    out = {"n": len(xs), "mean": None, "min": None, "max": None, "quantiles": {}, "intervals": {},
           "interval_level": "0.90", "n_boot": n_boot if with_intervals else 0, "seed": seed}
    if not xs:
        return out
    out["mean"] = mean(xs)
    out["min"], out["max"] = xs[0], xs[-1]
    for p in probs:
        out["quantiles"][label(p)] = quantile(xs, p, presorted=True)
    if with_intervals and len(xs) >= 2:
        for p, iv in bootstrap_quantiles(xs, probs, n_boot=n_boot, seed=seed).items():
            out["intervals"][label(p)] = iv
    return out


def sample_warnings(values):
    """Plain-language cautions about a sample. Returns a list of strings."""
    xs = sorted(values)
    n = len(xs)
    warnings = []
    if n == 0:
        return ["No matters in the sample."]
    if n < SMALL_SAMPLE_N:
        warnings.append(
            "Small sample (n=%d). The P90 rests on the one or two most expensive matters; "
            "treat the upper figures as rough." % n)
    p50 = quantile(xs, Decimal("0.50"), presorted=True)
    p90 = quantile(xs, Decimal("0.90"), presorted=True)
    if p50 > 0:
        m = mean(xs)
        if p90 / p50 >= SKEW_P90_TO_P50 or m / p50 >= SKEW_MEAN_TO_MEDIAN:
            warnings.append(
                "Heavily skewed (n=%d): the P90 is %sx the median and the mean is %sx the median. "
                "A few expensive matters dominate; an average would mislead."
                % (n, (p90 / p50).quantize(Decimal("0.1")), (m / p50).quantize(Decimal("0.1"))))
    return warnings


def binomial_tail_at_most(k, n, p_num, p_den, alpha_num=1, alpha_den=20, upper=True):
    """Exact one-sided binomial check in whole numbers.

    For X ~ Binomial(n, p_num/p_den): is P(X >= k) (upper) or P(X <= k) (lower) at most
    alpha_num/alpha_den? Everything is integer arithmetic, so there is no rounding to argue about.
    """
    if n <= 0:
        return False
    q = p_den - p_num
    span = range(max(k, 0), n + 1) if upper else range(0, min(k, n) + 1)
    tail = sum(math.comb(n, i) * p_num ** i * q ** (n - i) for i in span)
    return tail * alpha_den <= alpha_num * p_den ** n
