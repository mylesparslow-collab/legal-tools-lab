from datetime import date
import pytest
from prop65 import triage
from prop65.rules import load_rules, rule
from prop65.labelcheck import check_label


def test_every_rule_has_citation_source_and_status():
    for r in load_rules().values():
        assert r["citation"] and r["source"] and r["status"] in {"verified_primary", "verified_mirror", "unverified"}


def test_no_engine_check_relies_on_an_unverified_rule():
    used = ["grace_12_month", "safe_harbor_exemption", "small_business_exemption", "private_action_60_day",
            "special_compliance_cure", "short_form_warning", "long_form_warning", "safe_harbor_not_exclusive"]
    assert all(rule(r)["status"] != "unverified" for r in used)


def test_grace_period_boundary_is_the_anniversary():
    # Vinyl acetate listed 2025-01-03: exempt the day before the anniversary, not on it
    assert triage.grace_period("Vinyl acetate", date(2026, 1, 2))["status"] == "EXEMPT"
    assert triage.grace_period("Vinyl acetate", date(2026, 1, 3))["status"] == "NOT_EXEMPT"


def test_grace_period_is_per_endpoint():
    r = triage.grace_period("BPS", date(2026, 10, 2))
    assert r["status"] == "PARTIAL"
    assert [e["in_grace"] for e in r["detail"]["endpoints"]] == [False, False, True]


def test_grace_unknown_chemical_is_not_guessed():
    assert triage.grace_period("Unobtainium", date(2026, 1, 1))["status"] == "NOT_IN_TABLE"


def test_dose_units():
    assert triage.daily_exposure_ug(0.08, "ppm", 5) == pytest.approx(0.4)
    assert triage.daily_exposure_ug(80, "ppb", 5) == pytest.approx(0.4)
    assert triage.daily_exposure_ug(10, "ug/L", 500) == pytest.approx(5.0)
    with pytest.raises(ValueError):
        triage.daily_exposure_ug(1, "furlongs", 1)


def test_lead_below_madl_and_at_the_line():
    r = triage.safe_harbor("Lead", 0.08, "mg/kg", 5, 1)
    assert r["status"] == "BELOW" and r["detail"]["daily_exposure_ug"] == pytest.approx(0.4)
    assert triage.safe_harbor("Lead", 0.1, "ppm", 5, 1)["status"] == "BELOW"       # exactly 0.5: "does not exceed"
    assert triage.safe_harbor("Lead", 0.11, "ppm", 5, 1)["status"] == "ABOVE"


def test_cadmium_above_madl_and_no_oral_nsrl():
    r = triage.safe_harbor("Cadmium", 1.2, "ppm", 5, 1)
    assert r["status"] == "ABOVE"
    comps = {c["endpoint"]: c for c in r["detail"]["comparisons"]}
    assert comps["reproductive"]["level_ug_day"] == 4.1 and comps["cancer"]["result"] == "NO_LISTED_LEVEL"


def test_small_business_and_government():
    assert triage.business_exemption(9)["status"] == "EXEMPT"
    assert triage.business_exemption(10)["status"] == "NOT_EXEMPT"
    assert triage.business_exemption(500, "district")["status"] == "EXEMPT"
    assert triage.business_exemption(None)["status"] == "NEEDS_INPUT"


def test_sixty_day_clock_mail_and_weekend_roll():
    d = triage.sixty_day_clock(date(2026, 11, 16), "mail_in_ca")["detail"]
    assert d["sixtieth_day"] == "2027-01-20" and d["earliest_filing"] == "2027-01-21"
    d = triage.sixty_day_clock(date(2026, 11, 2), "personal")["detail"]
    assert d["sixtieth_day_raw"] == "2027-01-01"
    d = triage.sixty_day_clock(date(2026, 11, 3), "personal")["detail"]     # 60th day is Saturday 2027-01-02
    assert d["rolled_for_weekend"] and d["sixtieth_day"] == "2027-01-04" and d["earliest_filing"] == "2027-01-05"
    assert triage.sixty_day_clock(date(2026, 11, 16), "mail_out_of_state")["detail"]["extension_days"] == 10


def test_special_compliance():
    ok = triage.special_compliance("parking_engine_exhaust", date(2026, 11, 16), date(2026, 11, 25), facilities=2)
    assert ok["status"] == "ELIGIBLE" and ok["detail"]["total_penalty_usd"] == 1220 and ok["detail"]["pay_by"] == "2026-12-16"
    assert triage.special_compliance("consumer_product", date(2026, 11, 16), date(2026, 11, 25))["status"] == "NOT_ELIGIBLE"
    assert triage.special_compliance("alcohol_on_premises", date(2026, 11, 1), date(2026, 11, 25))["status"] == "WINDOW_CLOSED"
    assert triage.special_compliance("alcohol_on_premises", date(2026, 11, 16), date(2026, 11, 20), used_before_for_same_exposure=True)["status"] == "NOT_ELIGIBLE"
    # no verified amount on file before April 2024 or after the 2029 adjustment: do not guess
    assert triage.special_compliance("alcohol_on_premises", date(2023, 6, 1), date(2023, 6, 5))["status"] == "NEEDS_REVIEW"
    assert triage.special_compliance("alcohol_on_premises", date(2029, 4, 2), date(2029, 4, 5))["status"] == "NEEDS_REVIEW"


def test_labels():
    old = "WARNING: Cancer - www.P65Warnings.ca.gov"
    assert check_label(old, manufactured_labeled="2027-12-31", has_symbol=True)["status"] == "PASS"
    assert check_label(old, manufactured_labeled="2028-01-01", has_symbol=True)["status"] == "FAIL"
    assert check_label(old, has_symbol=True)["status"] == "REVIEW"
    assert check_label(old, category="food")["status"] == "REVIEW"
    new = "CA WARNING: Risk of cancer and reproductive harm from exposure to lead. See www.P65Warnings.ca.gov."
    r = check_label(new, endpoints=("cancer", "reproductive"), chemicals=["Lead"], has_symbol=True, type_size_pt=6)
    assert r["status"] == "PASS" and r["form"] == "short_form_2025"
    assert check_label(new, endpoints=("cancer",), chemicals=["Lead"], has_symbol=True, type_size_pt=5.5)["status"] == "FAIL"
    assert check_label(new, endpoints=("cancer",), chemicals=["Lead"], has_symbol=False)["status"] == "FAIL"
    assert check_label(new, endpoints=("cancer",), chemicals=["Cadmium"], has_symbol=True)["status"] == "REVIEW"
    only_repro = "WARNING: Can expose you to lead, a reproductive toxicant. See www.P65Warnings.ca.gov/food."
    assert check_label(only_repro, category="food", endpoints=("cancer", "reproductive"), chemicals=["Lead"])["status"] == "FAIL"
    assert check_label(only_repro, category="food", endpoints=("reproductive",), chemicals=["Lead"])["status"] == "PASS"
    assert check_label("Contains chemicals.", chemicals=["Lead"])["form"] is None
