from decimal import Decimal

import pytest

from feemodel import stats

D = Decimal
VALUES = [D(x) for x in (1, 2, 3, 4, 5)]


def test_quantiles_by_hand():
    assert stats.quantile(VALUES, D("0.50")) == D(3)
    assert stats.quantile(VALUES, D("0.25")) == D(2)
    assert stats.quantile(VALUES, D("0.90")) == D("4.6")
    assert stats.quantile([D(10), D(20)], D("0.5")) == D(15)
    assert stats.quantile([D(7)], D("0.9")) == D(7)
    assert stats.quantile(VALUES, 0) == D(1) and stats.quantile(VALUES, 1) == D(5)


def test_quantile_is_decimal_and_order_independent():
    q = stats.quantile([D("5.10"), D("1.20"), D("3.30")], D("0.75"))
    assert isinstance(q, Decimal) and q == D("4.20")


def test_quantile_rejects_empty_and_bad_probability():
    with pytest.raises(ValueError):
        stats.quantile([], D("0.5"))
    with pytest.raises(ValueError):
        stats.quantile(VALUES, D("1.5"))


def test_order_stat_guarantees_the_share():
    costs = [D(x) for x in (10, 20, 30, 40, 50)]
    assert stats.order_stat(costs, D("0.80")) == D(40)
    assert stats.order_stat(costs, D("0.81")) == D(50)
    assert stats.share_at_or_below(costs, D(40)) == (4, 5)


def test_bootstrap_is_reproducible_with_a_seed():
    values = [D(x * x) for x in range(1, 31)]
    a = stats.bootstrap_quantiles(values, seed=11, n_boot=300)
    b = stats.bootstrap_quantiles(values, seed=11, n_boot=300)
    c = stats.bootstrap_quantiles(values, seed=12, n_boot=300)
    assert a == b
    assert a != c


def test_bootstrap_interval_brackets_the_point_and_stays_in_range():
    values = [D(x * x) for x in range(1, 31)]
    iv = stats.bootstrap_quantiles(values, seed=3, n_boot=400)
    for p, (lo, hi) in iv.items():
        point = stats.quantile(values, p)
        assert isinstance(lo, Decimal) and isinstance(hi, Decimal)
        assert min(values) <= lo <= point <= hi <= max(values)
    lo50, hi50 = iv[D("0.50")]
    assert lo50 < hi50


def test_summarize_shows_n_and_labels():
    s = stats.summarize(VALUES, n_boot=50, seed=1)
    assert s["n"] == 5 and set(s["quantiles"]) == {"p25", "p50", "p75", "p90"}
    assert set(s["intervals"]) == {"p25", "p50", "p75", "p90"}
    assert s["mean"] == D(3)
    empty = stats.summarize([])
    assert empty["n"] == 0 and empty["quantiles"] == {}


def test_small_sample_warning():
    w = stats.sample_warnings([D(x) for x in range(100, 112)])
    assert len(w) == 1 and "Small sample (n=12)" in w[0]
    assert stats.sample_warnings([D(100 + x) for x in range(40)]) == []


def test_skew_warning():
    values = [D(100)] * 30 + [D(1000)] * 6
    w = stats.sample_warnings(values)
    assert any("Heavily skewed (n=36)" in x for x in w)
