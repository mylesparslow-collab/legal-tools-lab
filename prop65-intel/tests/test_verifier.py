import json
from datetime import date
from pathlib import Path
import pytest
from prop65.verifier import Record, verify_draft, verify_claims, quote_regex
from prop65.triage import triage_case
from prop65.ledger import Ledger

S = Path(__file__).resolve().parent.parent / "sample"


@pytest.fixture(scope="module")
def rec():
    return Record(S / "record" / "record_index.json")


def run(rec, name):
    rep = verify_draft((S / "drafts" / f"{name}.md").read_text(encoding="utf-8"), rec, name)
    return rep, {r["cite"]: r for r in rep["results"]}


def codes(r):
    return [i.get("code") for i in r["items"] if i["status"] != "PASS"]


def test_tender_letter_answer_key(rec):
    rep, by = run(rec, "coverage_tender_letter")
    assert rep["counts"] == {"PASS": 5, "WARN": 2, "FAIL": 2, "MANUAL": 0}
    assert codes(by["POL-0003:8-9"]) == ["SUPERSEDED"]                 # base exclusion replaced by Endorsement 1
    assert codes(by["POL-0004:8"]) == ["VALUE_OTHER_LINE"]             # $500,000 is the aggregate, line 8 says $250,000
    assert "$250,000" in by["POL-0004:8"]["items"][0]["message"]
    assert codes(by["POL-0004:13"]) == ["QUOTE_NOT_IN_RECORD"]         # "shall defend" vs "will defend"
    assert {"draft": "shall", "record": "We will"} in by["POL-0004:13"]["items"][0]["closest"]["diff"]
    assert codes(by["POL-0006:6"]) == ["PAGE_NOT_IN_RECORD"]


def test_trial_brief_answer_key(rec):
    rep, by = run(rec, "trial_brief_excerpt")
    assert rep["counts"] == {"PASS": 6, "WARN": 0, "FAIL": 4, "MANUAL": 0}
    assert codes(by["CHART-0002:12"]) == ["VALUE_NOT_ON_PAGE"]         # 20:40 in the draft, 21:40 in the chart
    assert "03/14/2026 21:40" in by["CHART-0002:12"]["items"][0]["on_page_instead"]
    assert set(codes(by["CHART-0004:15"])) == {"LINE_NOT_ON_PAGE", "WRONG_PAGE"}
    assert codes(by["CHART-0003:10"]) == ["QUOTE_NOT_IN_RECORD"]       # "and time" added
    assert by["CHART-0003:13-14"]["status"] == "PASS"                  # bracketed [was] is allowed
    assert codes(by[None]) == ["QUOTE_WITHOUT_CITE"]


def test_memo_catches_transposed_lab_value(rec):
    rep, by = run(rec, "prop65_response_memo")
    assert codes(by["COA-0001:8-9"]) == ["VALUE_NOT_ON_PAGE"]
    assert by["NOV-0001:9"]["status"] == "MANUAL"                      # nothing checkable: a person reads the page


def test_quote_matching_rules(rec):
    p = rec.pages["POL-0002"]
    assert p.locate(quote_regex("right and duty to defend the insured"))
    assert p.locate(quote_regex("We will pay those sums ... to which this insurance applies"))
    assert p.locate(quote_regex("right and duty to defend the Insured")) is None      # case matters


def test_claims_gate_blocks_unanchored_values(rec):
    good = verify_claims(json.loads((S / "cases" / "kelp_crisps_case.json").read_text()), rec)
    assert all(c["anchor_status"] == "VERIFIED" for c in good["claims"].values())
    t = triage_case(good, date(2026, 11, 25))
    st = {(c["check"], c["status"]) for c in t["checks"]}
    assert ("safe_harbor", "BELOW") in st and ("safe_harbor", "ABOVE") in st and not t["blocked_claims"]

    bad = verify_claims(json.loads((S / "cases" / "kelp_crisps_case_bad_anchor.json").read_text()), rec)
    assert bad["claims"]["cadmium_ppm"]["anchor_status"] == "FAILED"
    t = triage_case(bad, date(2026, 11, 25))
    assert t["blocked_claims"] == ["cadmium_ppm"]
    assert [c["status"] for c in t["checks"] if c["check"] == "safe_harbor"] == ["BLOCKED"]


def test_claim_without_anchor_is_blocked():
    case = {"claims": {"service_date": {"value": "2026-11-16"}}}
    assert triage_case(case, date(2026, 11, 25))["checks"][0]["status"] == "BLOCKED"


def test_ledger_requires_note_and_detects_tampering(rec, tmp_path):
    rep, by = run(rec, "coverage_tender_letter")
    led = Ledger(tmp_path / "log.jsonl")
    led.sign(by["POL-0001:4"], "reviewer@example.test")
    with pytest.raises(ValueError):
        led.sign(by["POL-0004:13"], "reviewer@example.test")
    led.sign(by["POL-0004:13"], "reviewer@example.test", "Corrected the draft to 'will defend'.")
    assert led.intact() and len(led.outstanding(rep)) == len(rep["results"]) - 2
    lines = led.path.read_text().splitlines()
    led.path.write_text("\n".join([lines[0].replace("PASS", "FAIL")] + lines[1:]) + "\n")
    assert not led.intact()
