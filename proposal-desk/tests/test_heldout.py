"""The held-out scorer, and the recorded held-out results. Nothing here opens heldout/batch_b:
that batch was run once and only its recorded result is read."""
import json
import os
import re

import pytest

import run_heldout
from desk.heldout_score import combine, evaluate, match_requirements
from desk.rfp import parse_rfp

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "heldout_results")

RFP = """EXAMPLE VALLEY WATER DISTRICT

Example Valley Water District (the "District") seeks counsel. The General Manager is Tamsin Okoro.
Staff are represented by the Example Valley Employees Union.

A. SCHEDULE

   Proposals due ............ 21 January 2027, 3:00 p.m.
   Interviews ............... 8 February 2027
   Start of services ........ 1 April 2027

B. CONTENT OF PROPOSAL

   (i)   Firm Description. Describe the firm.
   (ii)  Fee Proposal. State hourly rates.
   (iii) Training Program. Describe a training program.

Every proposal must include a one-page organization chart.

C. EVALUATION

   Experience ........ 60 points
   Training .......... 10 points
   Fees .............. 30 points

D. SUBMISSION

Proposals shall not exceed twenty (20) pages.

ADDENDUM NO. 1
Dated January 5, 2027

  (1)  The proposal due date is moved from 21 January 2027 to 28 January 2027.
  (2)  Item (iii) is deleted.
  (3)  The 10 points for Training are removed and Experience is now worth 70 points.
"""


def make_key():
    return {
        "agency": "Example Valley Water District",
        "deadlines": [{"kind": "submission_due", "date": "2027-01-28", "time": "15:00"},
                      {"kind": "interview", "date": "2027-02-08", "time": None},
                      {"kind": "start_of_services", "date": "2027-04-01", "time": None,
                       "kind_not_in_existing_keys": True}],
        "addendum_changes": [
            {"addendum": 1, "kind": "submission_due", "from": "2027-01-21", "to": "2027-01-28"},
            {"addendum": 1, "kind": "requirement_deleted", "from": "B(iii)", "to": None},
            {"addendum": 1, "kind": "criterion_removed", "from": "Training", "to": None},
            {"addendum": 1, "kind": "weight_changed", "criterion": "Experience", "from": 60, "to": 70}],
        "requirements": [
            {"label": "B(i)", "alt_labels": ["(i)", "i"], "qtype": "firm_overview", "numbered": True,
             "text": "Firm Description. Describe the firm."},
            {"label": "B(ii)", "alt_labels": ["(ii)", "ii"], "qtype": "other", "alt_qtypes": ["rates"],
             "numbered": True, "text": "Fee Proposal. State hourly rates."},
            {"label": "B-unnumbered-1", "qtype": "team", "alt_qtypes": ["other"], "numbered": False,
             "text": "Every proposal must include a one-page organization chart."}],
        "deleted_requirements": [{"label": "B(iii)", "alt_labels": ["iii"], "text": "Training Program. Describe a training program."}],
        "forms": [], "evaluation": [{"name": "Experience", "weight": 70}, {"name": "Fees", "weight": 30}],
        "min_quals": [], "insurance": [],
        "mechanics": {"page_limit": 20, "font_pt": None, "margin_in": None, "kinds": ["page_limit"]},
        "parties": [{"name": "Example Valley Water District", "category": "agency"},
                    {"name": "Tamsin Okoro", "category": "staff"},
                    {"name": "Example Valley Employees Union", "category": "other_organisation"}],
        "party_notes": "either category is acceptable for the union",
        "dates_that_are_not_deadlines": ["January 5, 2027 (date of the addendum)"],
    }


@pytest.fixture(scope="module")
def scored():
    return evaluate(parse_rfp(RFP), make_key())


def test_scorer_full_marks_when_parse_matches_key(scored):
    assert scored["overall"] == {"tp": 12, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0}
    assert scored["agency_correct"] and scored["submission_deadline"]["correct"] and scored["page_limit"]["correct"]


def test_alt_labels_and_text_matching_for_unnumbered_requirements(scored):
    assert scored["requirements"]["numbered_found"] == "2 of 2"
    assert scored["requirements"]["unnumbered_found"] == "1 of 1"


def test_alt_qtypes_are_accepted_and_scored_apart_from_finding(scored):
    assert scored["question_type"] == {"correct": 3, "of_found": 3, "of": 3, "wrong": []}
    key = make_key()
    key["requirements"][1]["alt_qtypes"] = []                    # the parser says rates, the key now says other only
    res = evaluate(parse_rfp(RFP), key)
    assert res["question_type"]["correct"] == 2 and res["requirements"]["tp"] == 3


def test_deadline_kind_outside_existing_keys_is_neither_hit_nor_extra(scored):
    assert scored["deadlines"]["tp"] == 2 and scored["deadlines"]["fp"] == 0
    assert scored["deadline_kinds_outside_existing_keys"] == [
        {"kind": "start_of_services", "date": "2027-04-01", "found": True}]


def test_party_either_category_only_where_the_key_says_so(scored):
    assert scored["parties"]["fp"] == 0
    key = make_key()
    del key["party_notes"]
    res = evaluate(parse_rfp(RFP), key)
    assert res["parties"]["fp"] == 1 and res["parties"]["fn"] == 1


def test_addendum_handling_is_its_own_line_and_not_in_overall(scored):
    ad = scored["addendum_handling"]
    assert (ad["passed"], ad["of"]) == (5, 5)
    assert [c["check"] for c in ad["checks"]] == [
        "submission_due: date as issued (2027-01-21) still shown", "submission_due in force 2027-01-28",
        "requirement B(iii) deleted", "criterion removed: Training", "weight of Experience now 70"]
    assert sum(scored[c]["tp"] for c in ("deadlines", "requirements", "forms", "evaluation", "min_quals",
                                         "insurance", "mechanics", "parties")) == scored["overall"]["tp"]


def test_deleted_requirement_still_parsed_is_an_extra_and_a_failed_check():
    body = RFP.replace("  (2)  Item (iii) is deleted.\n", "")
    res = evaluate(parse_rfp(body), make_key())
    assert res["requirements"]["fp"] == 1 and res["addendum_handling"]["deleted_requirements_still_parsed"] == ["B(iii)"]
    assert not next(c for c in res["addendum_handling"]["checks"] if c["check"].startswith("requirement"))["ok"]
    assert res["negatives_hit"]["requirements"]


def test_date_that_is_not_a_deadline_is_counted_and_named():
    parsed = parse_rfp(RFP)
    parsed["deadlines"].append(dict(parsed["deadlines"][0], kind="award", date="2027-01-05", time=None))
    res = evaluate(parsed, make_key())
    assert res["deadlines"]["fp"] == 1 and res["negatives_hit"]["deadlines"] == ["award 2027-01-05"]


def test_wrong_time_is_a_miss_and_is_reported_as_date_right():
    key = make_key()
    key["deadlines"][0]["time"] = "14:00"
    res = evaluate(parse_rfp(RFP), key)
    assert res["deadlines"]["fn"] == 1 and res["deadlines"]["fp"] == 1
    assert res["deadlines"]["date_right_time_or_kind_wrong"] == 1 and not res["submission_deadline"]["correct"]


def test_label_match_does_not_steal_a_different_item_with_the_same_short_label():
    parsed = [{"label": "i", "text": "Scope item about meetings.", "qtype": "other"},
              {"label": "i", "text": "Firm Description. Describe the firm.", "qtype": "firm_overview"}]
    key = [{"label": "E(i)", "alt_labels": ["i"], "numbered": True, "text": "Firm Description. Describe the firm."}]
    pairs, extra, missed = match_requirements(parsed, key)
    assert pairs[0][0]["qtype"] == "firm_overview" and len(extra) == 1 and not missed


def test_combine_adds_counts_across_rfps(scored):
    both = combine({"a": scored, "b": scored})
    assert both["overall"]["tp"] == 24 and both["addendum_handling"] == {"passed": 10, "of": 10}
    assert both["page_limit"] == {"correct": 2, "of": 2}


def load(tag):
    with open(os.path.join(RESULTS, tag + ".json"), encoding="utf-8") as f:
        return json.load(f)


def test_three_recorded_runs_exist_with_three_rfps_each():
    for tag in ("batch_a_first_run", "batch_a_after_fixes", "batch_b_final"):
        d = load(tag)
        assert len(d["per_rfp"]) == 3 and os.path.exists(os.path.join(RESULTS, tag + ".md"))
    assert load("batch_b_final")["batch"] == "b" and load("batch_b_final")["run"] == "final"


def test_recorded_first_run_found_no_requirements():
    c = load("batch_a_first_run")["combined"]
    assert c["requirements"]["tp"] == 0 and c["requirements"]["fn"] == 36 and c["overall"]["recall"] == 0.132


def test_batch_a_rerun_matches_the_recorded_after_fixes_result():
    fresh = combine(run_heldout.score_batch("a"))
    assert fresh == load("batch_a_after_fixes")["combined"]


def test_recorded_runs_are_not_overwritten(capsys):
    assert run_heldout.main(["b", "final"]) == 1                # refuses before it reads anything
    assert "Already recorded" in capsys.readouterr().out
    assert run_heldout.main(["a", "first_run"]) == 1
    assert run_heldout.main(["c", "final"]) == 2


def test_readme_leads_with_the_batch_b_figures_and_keeps_the_earlier_ones_labelled(root):
    text = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    b = load("batch_b_final")["combined"]
    a0, a1 = load("batch_a_first_run")["combined"], load("batch_a_after_fixes")["combined"]
    for c in (b, a0, a1):
        assert "%.3f | %.3f" % (c["requirements"]["precision"], c["requirements"]["recall"]) in text
        assert "%.3f | %.3f" % (c["overall"]["precision"], c["overall"]["recall"]) in text
    head = text[:text.index("## What it does")]
    assert "%.3f" % b["requirements"]["recall"] in head and "%.3f" % b["overall"]["recall"] in head
    assert "0.995" in text and "0.825" in text and "0.667" in text and "0.136" in text
    assert re.search(r"in-sample", text) and "batch B" in text
