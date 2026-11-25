import copy
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from sideletter import cli, gate, memo, mfn  # noqa: E402
from sideletter.quotes import sentences, verify_quote  # noqa: E402

SD = os.path.join(HERE, "sample_data")
J = lambda n: json.load(open(os.path.join(SD, n), encoding="utf-8"))
T = lambda n: open(os.path.join(SD, n), encoding="utf-8").read()
RULES = gate.load_rules(os.path.join(HERE, "rules", "statutory_rules.json"))
REG = gate.load_registry(os.path.join(SD, "lobbyist_registry_snapshot.csv"))
FUND, STATE, COUNTY = J("fund.json"), J("investor_state.json"), J("investor_county.json")
DRAFT, COMP = T("draft_side_letter.txt"), T("mfn_compendium.txt")
TERMS = FUND["mfn_terms"]


def g(investor=STATE, fund=FUND, draft=DRAFT):
    return gate.run_gate(RULES, investor, fund, draft, REG)


def by(fs, rule, status=None):
    return [f for f in fs if f["rule_id"] == rule and (status is None or f["status"] == status)]


def prov(n, investor=STATE, terms=TERMS):
    p = {x["id"]: x for x in mfn.parse_compendium(COMP)}[n]
    return mfn.decide(p, investor, terms)


# ---- rules file ----
def test_every_rule_has_source_and_status():
    ok = set(RULES["_meta"]["statuses"])
    for r in RULES["rules"]:
        assert r["verification_status"] in ok
        assert r["correction"] and r["report_claim"]
        if r["verification_status"] != "unverified":
            assert r["source_url"].startswith("https://leginfo.legislature.ca.gov/") and r["quote"]
        else:
            assert r["quote"] is None


# ---- quote verification ----
def test_verify_quote_is_exact():
    assert verify_quote("prior written  consent of the General Partner", DRAFT)  # whitespace only
    assert not verify_quote("prior written approval of the General Partner", DRAFT)
    assert not verify_quote("", DRAFT)


def test_sentences_do_not_split_on_lp():
    s = sentences('Harbor Crest V, L.P. (the "Fund") agrees. The Investor agrees.')
    assert len(s) == 2


# ---- gate ----
def test_fee_reporting_flags_and_gap():
    fs = g()
    quotes = " ".join(f["quote"] for f in by(fs, "GOV-7514.7", "FLAG"))
    assert "without incremental expense" in quotes and "commercially reasonable efforts" in quotes
    gap = by(fs, "GOV-7514.7", "GAP")[0]["why"]
    assert "(a)(1)" in gap and "(a)(4)" in gap and "(a)(3)" not in gap


def test_public_records_nine_item_coverage_and_stale_cite():
    fs = g()
    gap = by(fs, "GOV-7928.710", "GAP")[0]["why"]
    for missing in ("(c)(5)", "(c)(7)", "(c)(8)", "(c)(9)"):
        assert missing in gap
    for present in ("(c)(1)", "(c)(2)", "(c)(3)", "(c)(4)", "(c)(6)"):
        assert present not in gap
    whys = " ".join(f["why"] for f in by(fs, "GOV-7928.710", "FLAG"))
    assert "consent" in whys and "opinion" in whys and "pre-2023" in whys


def test_fund_type_outside_definition_goes_to_review():
    f2 = dict(FUND, fund_type="real_estate")
    fs = g(fund=f2)
    assert [f["status"] for f in by(fs, "GOV-7514.7")] == ["REVIEW"]


def test_pre_2017_contract_goes_to_review():
    fs = g(fund=dict(FUND, subscription_date="2016-06-01"))
    assert [f["status"] for f in by(fs, "GOV-7514.7")] == ["REVIEW"]


def test_state_only_rules_do_not_reach_county_system():
    fs = g(investor=COUNTY)
    assert by(fs, "GOV-86205(f)")[0]["status"] == "NOT_APPLICABLE"
    assert by(fs, "GOV-7513.86")[0]["status"] == "NOT_APPLICABLE"
    assert by(fs, "GOV-7513.87")[0]["status"] == "REVIEW"
    assert by(g(), "GOV-7513.87")[0]["status"] == "NOT_APPLICABLE"


def test_contingent_fee_flag_for_state_system():
    fl = by(g(), "GOV-86205(f)", "FLAG")
    assert fl and all("payable upon the admission" in f["quote"] for f in fl)


def test_registry_cross_check():
    st = {f["why"].split(" (")[0]: f["status"] for f in by(g(), "GOV-7513.86")}
    assert st == {"Dana Whitlock": "ADDRESSED", "Marcus Oyelaran": "FLAG", "Priya Venkataraman": "REVIEW"}


def test_terminated_registration_is_flagged():
    f2 = copy.deepcopy(FUND)
    f2["placement_agents"] = [{"name": "Helen Akintola", "firm": "Stonebridge", "claims_exemption": None}]
    f = by(g(fund=f2), "GOV-7513.86")[0]
    assert f["status"] == "FLAG" and "Terminated" in f["why"]


def test_policy_agreement_missing_then_addressed():
    assert by(g(), "GOV-7513.85")[0]["status"] == "MISSING"
    fixed = DRAFT.replace("No portion of such fee shall be borne by the Investor.",
                          "No portion of such fee shall be borne by the Investor. The General Partner agrees to comply with the Investor's placement agent disclosure policy.")
    f = by(g(draft=fixed), "GOV-7513.85")[0]
    assert f["status"] == "ADDRESSED" and "comply" in f["quote"]


def test_clean_clause_reports_addressed_not_compliant():
    clean = DRAFT.replace("without limitation as to amount", "to the extent permitted by applicable law and in an amount not to exceed its unfunded Commitment")
    f = by(g(draft=clean), "CONST-XVI-6")
    assert [x["status"] for x in f] == ["ADDRESSED"] and "not a finding of compliance" in f[0]["why"]


def test_unverified_rule_is_labelled():
    assert all(f["verification_status"] == "unverified" for f in by(g(), "SOVEREIGN-IMMUNITY"))
    assert len(by(g(), "SOVEREIGN-IMMUNITY", "FLAG")) == 3


# ---- MFN ----
def test_compendium_parse():
    ps = mfn.parse_compendium(COMP)
    assert len(ps) == 36 and ps[0]["page"] == 1 and ps[-1]["page"] == 12 and ps[8]["page"] == 3


def test_tiers_with_affiliate_aggregation():
    assert mfn.aggregated_commitment(STATE, TERMS) == 125_000_000
    assert prov(2)["verdict"] == "ELECTABLE"       # $50M
    assert prov(3)["verdict"] == "ELECTABLE"       # $100M, met only by aggregation
    assert prov(4)["verdict"] == "NOT_ELECTABLE"   # $250M


def test_aggregation_switch_changes_100m_tier():
    t = dict(TERMS, aggregate_affiliates=False)
    assert mfn.aggregated_commitment(STATE, t) == 85_000_000
    assert prov(3, terms=t)["verdict"] == "NOT_ELECTABLE"


def test_threshold_is_inclusive():
    inv = dict(STATE, commitment=100_000_000, affiliates=[])
    assert prov(3, investor=inv)["verdict"] == "ELECTABLE"
    inv = dict(STATE, commitment=99_999_999, affiliates=[])
    assert prov(3, investor=inv)["verdict"] == "NOT_ELECTABLE"


def test_status_filters():
    assert prov(5)["verdict"] == "NOT_ELECTABLE"   # ERISA
    assert prov(6)["verdict"] == "ELECTABLE"       # governmental plan
    assert prov(7)["verdict"] == "ELECTABLE"       # public records
    assert prov(8)["verdict"] == "NOT_ELECTABLE"   # BHCA
    assert prov(15)["verdict"] == "NOT_ELECTABLE"  # Texas instrumentality
    assert prov(17)["verdict"] == "ELECTABLE"      # any-of list
    assert prov(26)["verdict"] == "ELECTABLE" and prov(26, investor=COUNTY)["verdict"] == "NOT_ELECTABLE"


def test_carve_outs_and_closing_and_gp_affiliate():
    assert prov(11)["verdict"] == "NOT_ELECTABLE" and prov(11)["category"] == "lpac_seat"
    assert prov(12)["verdict"] == "ELECTABLE" and prov(12)["category"] == "lpac_observer"
    assert prov(25)["verdict"] == "NOT_ELECTABLE"  # transfer
    assert prov(18)["verdict"] == "NOT_ELECTABLE"  # initial closing
    assert prov(18, investor=dict(STATE, admitted_at_initial_closing=True))["verdict"] == "ELECTABLE"
    assert prov(19)["verdict"] == "NOT_ELECTABLE"  # GP affiliate


def test_unreadable_lead_ins_go_to_review_not_a_guess():
    assert prov(31)["verdict"] == "REVIEW"
    assert prov(32)["verdict"] == "REVIEW"


def test_every_reason_quote_is_in_its_provision():
    for p in mfn.parse_compendium(COMP):
        for r in mfn.decide(p, STATE, TERMS)["reasons"]:
            if r["quote"]:
                assert verify_quote(r["quote"], p["text"])


def test_deadline_calendar_roll_and_business_days():
    d = mfn.election_deadline(TERMS, "2026-11-16")
    assert (d["raw_deadline"], d["deadline"], d["rolled"]) == ("2026-12-06", "2026-12-07", True)
    assert mfn.election_deadline(dict(TERMS, roll_forward_if_weekend=False), "2026-11-16")["deadline"] == "2026-12-06"
    assert mfn.election_deadline(TERMS, "2026-11-17")["deadline"] == "2026-12-07"  # Monday, no roll
    assert mfn.election_deadline(dict(TERMS, day_type="business"), "2026-11-16")["deadline"] == "2026-12-14"


# ---- bounded model layer ----
def test_model_items_are_quote_checked():
    ps = mfn.parse_compendium(COMP)
    ok, bad = mfn.verify_model_items(J("model_output.json"), ps)
    assert [a["provision_id"] for a in ok] == [30, 36]
    assert {b["provision_id"]: b["rejected"].split(" (")[0] for b in bad} == {
        2: "quote not found verbatim in the provision", 9: "page mismatch", 13: "category not in the fixed list"}


def test_model_cannot_change_eligibility_arithmetic():
    ps = mfn.parse_compendium(COMP)
    items = [{"provision_id": 4, "page": 2, "category": "other", "quote": "reduced by 40 basis points per annum"}]
    ok, _ = mfn.verify_model_items(items, ps)
    ds = mfn.apply_model_items([mfn.decide(p, STATE, TERMS) for p in ps], ok, TERMS, STATE, ps)
    d = {x["id"]: x for x in ds}[4]
    assert d["category"] == "other" and d["verdict"] == "NOT_ELECTABLE"  # $250M tier still not met


def test_model_moving_out_of_carve_out_goes_to_review():
    ps = mfn.parse_compendium(COMP)
    inv = dict(STATE, commitment=300_000_000)
    items = [{"provision_id": 11, "page": 4, "category": "other", "quote": "may appoint one member to the Advisory Committee"}]
    ok, _ = mfn.verify_model_items(items, ps)
    d = {x["id"]: x for x in mfn.apply_model_items([mfn.decide(p, inv, TERMS) for p in ps], ok, TERMS, inv, ps)}[11]
    assert d["verdict"] == "REVIEW"


# ---- end to end ----
def test_end_to_end_counts_and_outputs(tmp_path):
    r = cli.main(["--model-output", os.path.join(SD, "model_output.json"), "-o", str(tmp_path)])
    assert r["counts"] == {"ELECTABLE": 21, "REVIEW": 2, "NOT_ELECTABLE": 13}
    for n in ("results.json", "Election_Memo.md", "Election_Memo.docx", "MFN_Election_Deadline.ics"):
        assert os.path.getsize(tmp_path / n) > 0
    md = (tmp_path / "Election_Memo.md").read_text(encoding="utf-8")
    assert "Not legal advice" in md and "2026-12-07" in md
    assert "DTSTART;VALUE=DATE:20261207" in (tmp_path / "MFN_Election_Deadline.ics").read_text()
    from docx import Document
    txt = "\n".join(c.text for t in Document(str(tmp_path / "Election_Memo.docx")).tables for row in t.rows for c in row.cells)
    assert "without incremental expense" in txt


def test_memo_refuses_a_quote_that_is_not_in_the_source():
    r = cli.run(STATE, FUND, DRAFT, COMP, REG, RULES)
    r["gate"][0]["quote"] = "The General Partner shall always comply."
    with pytest.raises(AssertionError):
        memo.assert_quotes(r, DRAFT, COMP)


def test_county_run_differs():
    r = cli.run(COUNTY, FUND, DRAFT, COMP, REG, RULES)
    assert r["aggregated_commitment"] == 60_000_000
    assert r["counts"] == {"ELECTABLE": 16, "REVIEW": 2, "NOT_ELECTABLE": 18}
