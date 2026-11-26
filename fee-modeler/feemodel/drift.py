"""Change-point scan: has the cost of a matter type shifted, and from when?

No change date is supplied. Matters are put in order of opening. Every split that leaves at
least DRIFT_MIN_SEG matters on each side is tried; for each, the ranks of the later matters
are summed and compared with what no change would give, scaled by the split's own spread.
The most lopsided split is the estimated change point. Because many splits are tried, the
significance check reshuffles the ranks (seeded) and repeats the whole scan each time, so the
search over splits is paid for. Ranks and counts are integers; no model is fitted.

A type is flagged when both hold:
- no more than DRIFT_ALPHA of reshuffles produce a scan as lopsided as the real one, and
- the median after the estimated change point differs from the median before it by at least
  DRIFT_MATERIAL either way (a shift too small to matter for pricing is not flagged).
"""

import random
from decimal import Decimal

from . import stats

P50 = Decimal("0.50")
DRIFT_MIN_SEG = 8                    # fewest matters allowed on either side of a split
DRIFT_ALPHA = (1, 20)                # share of reshuffles allowed to be as lopsided: 1 in 20
DRIFT_MATERIAL = Decimal("1.25")     # after/before median ratio that counts as a shift worth acting on
DRIFT_SHUFFLES = 1000
DRIFT_SEED = 7


def double_ranks(values):
    """Twice the average rank of each value (integers, so ties need no fractions)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = i + j + 2
        i = j + 1
    return ranks


def _scan(ranks, total, n, min_seg):
    """Most lopsided split as (numerator, denominator, k): dev^2 / (n1 * n2), compared exactly."""
    best_num, best_den, best_k = 0, 1, None
    late = sum(ranks[min_seg:])
    for k in range(min_seg, n - min_seg + 1):
        dev = late * n - total * (n - k)
        num, den = dev * dev, k * (n - k)
        if best_k is None or num * best_den > best_num * den:
            best_num, best_den, best_k = num, den, k
        late -= ranks[k]
    return best_num, best_den, best_k


def change_point_scan(items, min_seg=DRIFT_MIN_SEG, alpha=DRIFT_ALPHA, material=DRIFT_MATERIAL,
                      n_shuffles=DRIFT_SHUFFLES, seed=DRIFT_SEED):
    """items: [(open_date, matter_id, value)]. Returns a dict; 'flagged' says whether to act."""
    xs = sorted(items, key=lambda t: (t[0], t[1]))
    n = len(xs)
    out = {"n": n, "judged": False, "flagged": False, "change_date": None, "n_before": None, "n_after": None,
           "median_before": None, "median_after": None, "after_over_before": None,
           "shuffles_as_extreme": None, "n_shuffles": 0, "min_segment": min_seg}
    if n < 2 * min_seg:
        return out
    out["judged"] = True
    values = [v for _d, _i, v in xs]
    ranks = double_ranks(values)
    total = sum(ranks)
    num, den, k = _scan(ranks, total, n, min_seg)
    before, after = values[:k], values[k:]
    mb, ma = stats.quantile(before, P50), stats.quantile(after, P50)
    out.update({"change_date": xs[k][0], "n_before": k, "n_after": n - k, "median_before": mb, "median_after": ma})
    if mb <= 0 or ma <= 0:
        return out
    ratio = ma / mb
    out["after_over_before"] = ratio.quantize(Decimal("0.01"))
    if max(ratio, 1 / ratio) < material:
        return out
    # Quick exit: if even this one split, taken alone, is unremarkable, a scan over many cannot be.
    # (z^2 = 3 * dev^2 / (n^2 * n1 * n2 * (n + 1)) with doubled ranks; below 4 is under two standard errors.)
    if 3 * num < 4 * den * n * n * (n + 1):
        return out
    rng = random.Random(seed)
    pool = list(ranks)
    extreme = 0
    for _ in range(n_shuffles):
        rng.shuffle(pool)
        pnum, pden, _k = _scan(pool, total, n, min_seg)
        if pnum * den >= num * pden:
            extreme += 1
    out["shuffles_as_extreme"], out["n_shuffles"] = extreme, n_shuffles
    out["flagged"] = extreme * alpha[1] <= alpha[0] * n_shuffles
    return out
