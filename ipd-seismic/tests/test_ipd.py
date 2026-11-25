import copy
from decimal import Decimal as D

import pytest

from engine import ipd


def codes(findings, severity="error"):
    return sorted(f.code for f in findings if f.severity == severity)


def test_clean_ledger_has_no_errors(clean):
    states, f = ipd.run_ledger(clean)
    assert codes(f) == []
    s = states[-1]
    assert s["target_cost"] == 421_750_000 and s["icl_total"] == 27_900_000
    assert s["shared_balance"] == 7_100_000 and s["emp"] == 487_150_000


def test_seeded_errors_are_found(seeded):
    _, f = ipd.run_ledger(seeded)
    errs = [(x.code, x.where) for x in f if x.severity == "error"]
    assert ("L3", "Amendment 6") in errs      # shares sum to 99.50%
    assert ("L4", "Amendment 6") in errs      # one member's share is off
    assert ("L2", "Amendment 8") in errs      # restated target cost is $250,000 low
    assert len(errs) == 3


def test_stated_shares_sum_to_100_at_every_amendment(clean):
    states, _ = ipd.run_ledger(clean)
    assert all(s["stated_share_sum"] == D(100) for s in states)


def test_icl_to_unjoined_member_is_flagged(clean):
    bad = copy.deepcopy(clean)
    bad["amendments"][4]["icl_changes"].append({"member": "Ghost Glazing", "delta": 1})
    _, f = ipd.run_ledger(bad)
    assert "L5" in codes(f)


def test_overdrawn_contingency_and_low_emp(clean):
    bad = copy.deepcopy(clean)
    bad["amendments"][5]["draws"]["shared"] = 13_000_000
    bad["amendments"][3]["deltas"]["emp"] = -60_000_000
    _, f = ipd.run_ledger(bad)
    assert "L6" in codes(f) and "L7" in codes(f)


def test_missing_provenance_and_sequence(clean):
    bad = copy.deepcopy(clean)
    bad["amendments"][2]["provenance"]["quote"] = ""
    bad["amendments"][3]["no"] = 7
    _, f = ipd.run_ledger(bad)
    assert "L9" in codes(f) and "L1" in codes(f)


def test_counsel_status_workflow_flag(clean):
    _, f = ipd.run_ledger(clean)
    assert [x.where for x in f if x.code == "L10"] == ["Amendment 6"]


@pytest.fixture
def last(clean):
    return ipd.run_ledger(clean)[0][-1], clean["terms"]


@pytest.mark.parametrize("cost", [380_000_000, 421_750_000, 430_000_000, 441_300_000,
                                   462_150_000, 475_000_000, 490_000_000, 520_000_000])
def test_waterfall_conservation_and_order(last, cost):
    s, terms = last
    w = ipd.waterfall(s, terms, cost)
    tiers = [w["tier1_shared_contingency"], w["tier2_icl"], w["tier3_owner_contingency"], w["tier4_owner_at_cost"]]
    assert sum(tiers) == w["overrun"] and all(t >= 0 for t in tiers)
    # a later tier is touched only when every earlier tier is exhausted
    caps = [s["shared_contingency"], s["icl_total"], s["owner_contingency"]]
    for i in range(1, 4):
        if tiers[i] > 0:
            assert tiers[:i] == caps[:i]
    assert w["owner_total"] == D(cost) + w["icl_pool_final"]
    assert w["team_savings"] + w["owner_savings"] == w["savings"]
    assert abs(sum(w["payouts"].values()) - w["icl_pool_final"]) <= D("0.01") * len(w["payouts"])
    assert w["over_emp"] == (w["owner_total"] > s["emp"])


def test_waterfall_sample_numbers(last):
    s, terms = last
    w = ipd.waterfall(s, terms, 441_300_000)
    assert w["overrun"] == 19_550_000
    assert w["tier1_shared_contingency"] == 12_500_000 and w["tier2_icl"] == 7_050_000
    assert w["icl_pool_final"] == 20_850_000
    assert w["payouts"]["Brightwater Builders"] == D("10253118.28")
    assert w["emp_headroom"] == 25_000_000


def test_savings_split_and_cap(last):
    s, terms = last
    w = ipd.waterfall(s, terms, 401_750_000)          # $20M under target
    assert w["team_savings"] == 10_000_000 and w["owner_savings"] == 10_000_000
    w = ipd.waterfall(s, terms, 341_750_000)          # $80M under: 50% = $40M, cap is 2x ICL
    assert w["icl_pool_final"] == 55_800_000
    assert w["team_savings"] == 27_900_000 and w["owner_savings"] == 52_100_000


def test_over_emp_is_reported_not_allocated(last):
    s, terms = last
    w = ipd.waterfall(s, terms, 490_000_000)
    assert w["over_emp"] and w["icl_pool_final"] == 0
    assert "W1" in [f.code for f in ipd.waterfall_findings(s, w)]
