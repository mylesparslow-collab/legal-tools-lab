import json
import os

import pytest

from conftest import RFPS, rfp_text
from desk.evaluate import evaluate
from desk.rfp import classify_min_qual, classify_question, page_limit, parse_rfp, submission_deadline

MINI = """HOLLOWBROOK CEMETERY DISTRICT

REQUEST FOR PROPOSALS
GENERAL COUNSEL SERVICES

1. SCHEDULE

Proposals due                 %s
Something else entirely       March 3, 2027

2. PROPOSAL CONTENT

2.1 Firm Overview. Describe the firm.
2.2 Describe your favourite colour scheme for the cemetery map.
2.3 References. Provide two (3) references. This item is optional.

3. SUBMISSION INSTRUCTIONS

Proposals must not exceed ten (12) pages.
"""


def key(name, root):
    with open(os.path.join(root, "data", "answer_keys", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("name", RFPS)
def test_recall_and_precision_against_answer_key(name, parsed, root):
    res = evaluate(parsed[name], key(name, root))
    assert res["overall"]["recall"] >= 0.98, res
    assert res["overall"]["precision"] >= 0.95, res
    assert res["agency_correct"]


@pytest.mark.parametrize("name", RFPS)
def test_every_requirement_is_separate_with_number_and_exact_text(name, parsed):
    text = " ".join(rfp_text(name).split())
    reqs = parsed[name]["requirements"]
    assert len({r["label"] for r in reqs}) == len(reqs)
    for r in reqs:
        assert r["label"]
        assert r["text"] in text            # exact words of the RFP, only whitespace joined


@pytest.mark.parametrize("name", RFPS)
def test_every_deadline_quotes_its_source_line(name, parsed):
    lines = rfp_text(name).expandtabs(4).splitlines()
    for d in parsed[name]["deadlines"]:
        assert " ".join(lines[d["source"]["line"] - 1].split()) == d["source"]["text"]


def test_addendum_changes_submission_deadline_and_keeps_the_old_one(parsed):
    rfp = parsed["general_counsel_redwood_flats"]
    d = submission_deadline(rfp)
    assert (d["date"], d["time"]) == ("2026-12-17", "14:00")
    assert d["changed_by"] == "Addendum 1" and d["original_date"] == "2026-12-10"
    assert "changed from" in d["change_source"]["text"]
    interview = next(x for x in rfp["deadlines"] if x["kind"] == "interview")
    assert interview["date"] == "2027-01-07" and interview["original_date"] == "2026-12-17"


def test_addendum_item_that_is_not_understood_is_kept_for_a_person(parsed):
    rfp = parsed["general_counsel_redwood_flats"]
    notes = rfp["addenda"][0]["notes"]
    assert len(notes) == 1 and "acknowledge this addendum" in notes[0]["text"]
    assert any(c["category"] == "addendum" for c in rfp["checks"])


def test_addendum_changes_page_limit_extends_question_date_and_adds_a_form(parsed):
    rfp = parsed["special_counsel_tannery_creek_transit"]
    pl = page_limit(rfp)
    assert pl["value"] == 25 and pl["original_value"] == 30 and pl["changed_by"] == "Addendum 1"
    q = next(d for d in rfp["deadlines"] if d["kind"] == "questions_due")
    assert q["date"] == "2026-12-11" and q["original_date"] == "2026-12-08"
    added = [f for f in rfp["forms"] if f.get("added_by")]
    assert [f["name"] for f in added] == ["Addendum Acknowledgment"]


def test_addendum_whose_old_date_disagrees_with_schedule_is_marked_check():
    text = rfp_text("general_counsel_redwood_flats").replace(
        "is changed from\n   December 10, 2026", "is changed from\n   December 9, 2026")
    d = submission_deadline(parse_rfp(text))
    assert d["date"] == "2026-12-17" and d["confidence"] == "check"
    assert "old date" in d["check_reason"]


def test_awkward_formatting_tabs_wrapped_lines_and_week_of(parsed):
    rfp = parsed["labor_negotiator_quillfeather_usd"]
    award = next(d for d in rfp["deadlines"] if d["kind"] == "award")
    assert award["date"] == "2027-01-26"                       # the line with tabs
    interview = next(d for d in rfp["deadlines"] if d["kind"] == "interview")
    assert interview["confidence"] == "check" and "approximate" in interview["check_reason"]
    q4 = next(r for r in rfp["requirements"] if r["label"] == "Q4")
    assert q4["text"].endswith("communicating with employees during bargaining.")   # four wrapped lines joined


def test_unrecognised_question_is_kept_and_marked_check(parsed):
    q8 = next(r for r in parsed["labor_negotiator_quillfeather_usd"]["requirements"] if r["label"] == "Q8")
    assert q8["qtype"] == "other" and q8["confidence"] == "check" and q8["mandatory"] is False


def test_forms_listed_as_bullets_outside_a_forms_section_are_kept_as_check(parsed):
    forms = parsed["labor_negotiator_quillfeather_usd"]["forms"]
    assert len(forms) == 3 and all(f["confidence"] == "check" for f in forms)
    assert forms[0]["ref"] == "Attachment 1" and forms[0]["signature"]


def test_form_flags_signature_and_notary(parsed):
    forms = {f["name"]: f for f in parsed["general_counsel_redwood_flats"]["forms"]}
    assert forms["Non-Collusion Affidavit"]["notarized"]
    assert forms["Proposer Certification"]["signature"]
    city = parsed["city_attorney_marlow_ridge"]["forms"]
    assert all(f["signature"] for f in city)                   # "must be completed, signed and submitted"


def test_exhibit_to_complete_named_outside_the_forms_list_is_check_not_dropped(parsed):
    text = MINI % "March 1, 2027" + "\nComplete and return Exhibit 4 with the proposal.\n"
    extra = [f for f in parse_rfp(text)["forms"] if f["ref"] == "Exhibit 4"]
    assert len(extra) == 1 and extra[0]["confidence"] == "check" and extra[0]["mandatory"] is False
    # an agreement that is only referred to is not a form to send in
    assert not [f for f in parsed["general_counsel_redwood_flats"]["forms"] if f["ref"] == "Exhibit 2"]
    later = MINI % "March 1, 2027" + "\nThe selected firm must sign the agreement in Exhibit 5 after award.\n"
    assert not [f for f in parse_rfp(later)["forms"] if f["ref"] == "Exhibit 5"]


def test_evaluation_weights_percent_points_and_missing_weight(parsed):
    ev = parsed["city_attorney_marlow_ridge"]["evaluation"]
    assert ev["unit"] == "percent" and ev["total"] == 100 and ev["confidence"] == "ok"
    ev = parsed["special_counsel_tannery_creek_transit"]["evaluation"]
    assert ev["unit"] == "points" and ev["total_stated"] == 100 and len(ev["criteria"]) == 5
    ev = parsed["labor_negotiator_quillfeather_usd"]["evaluation"]
    assert ev["confidence"] == "check" and ev["criteria"][-1]["weight"] is None


def test_submission_mechanics(parsed):
    mech = {m["kind"]: m["value"] for m in parsed["general_counsel_redwood_flats"]["mechanics"]}
    assert mech["page_limit"] == 15 and mech["font"] == 11
    assert "six (6) bound copies" in mech["copies"] and mech["packaging"] == "sealed envelope"
    assert "transmittal letter" in mech["page_exclusions"]
    assert "email or fax" in mech["not_accepted"]
    mech = {m["kind"]: m["value"] for m in parsed["city_attorney_marlow_ridge"]["mechanics"]}
    assert mech["margins"] == 1.0 and mech["font"] == 12 and mech["delivery"].startswith("email to cityclerk@")


def test_insurance_statements_are_kept_as_text_with_amounts(parsed):
    ins = parsed["general_counsel_redwood_flats"]["insurance"]
    assert len(ins) == 3
    assert ins[0]["amounts"] == ["$1,000,000", "$2,000,000"] and "errors and omissions" in ins[0]["text"]


def test_parties_agency_board_staff_and_adverse(parsed):
    p = {x["name"]: x for x in parsed["special_counsel_tannery_creek_transit"]["parties"]}
    assert p["Tannery Creek Transit Authority"]["category"] == "agency"
    assert p["Saoirse Delacroix-Tan"]["role"] == "Contracting Officer"
    assert p["Granite Spur Constructors, Inc."]["category"] == "adverse"
    assert p["Hollis Yard Properties LP"]["category"] == "adverse"
    p = {x["name"]: x for x in parsed["city_attorney_marlow_ridge"]["parties"]}
    assert p["Imani Castellanos"]["category"] == "board" and p["Imani Castellanos"]["role"] == "Vice Mayor"
    assert p["Halvard Brennan"]["category"] == "staff"


def test_min_qual_classification():
    assert classify_min_qual("must have been admitted to practice law for at least ten (10) years.") == ("years_admitted", 10)
    assert classify_min_qual("The firm must maintain an office within Larkspur County.") == ("office_location", "Larkspur County")
    assert classify_min_qual("an office in the Authority's service area or commit to attend")[0] == "not_checkable"
    assert classify_min_qual("at least five (5) years of experience advising a city council")[0] == "not_checkable"
    assert classify_min_qual("The firm shall have at least three (3) attorneys available") == ("attorney_count", 3)


def test_question_type_rules():
    assert classify_question("Staffing Continuity and Transition", "") == "transition"
    assert classify_question("", "Who would be our chief negotiator?") == "team"
    assert classify_question("Cost Proposal", "Submit hourly rates") == "rates"
    assert classify_question("", "What is your favourite colour?") == "other"


def test_missing_deadline_and_missing_requirements_are_reported():
    rfp = parse_rfp("SOME AGENCY\n\nREQUEST FOR PROPOSALS\nLEGAL SERVICES\n\nPlease send us a proposal.\n")
    reasons = [c["reason"] for c in rfp["checks"]]
    assert "no submission deadline found" in reasons
    assert "no numbered proposal requirements found" in reasons
    assert submission_deadline(rfp) is None


def test_invalid_date_unknown_date_kind_and_word_number_mismatch_are_marked_check():
    rfp = parse_rfp(MINI % "February 30, 2027 at 3:00 p.m.")
    due = rfp["deadlines"][0]
    assert due["kind"] == "submission_due" and due["confidence"] == "check" and due["date"] is None
    assert submission_deadline(rfp) is None                     # an unreadable date is not used as a deadline
    assert rfp["deadlines"][1]["kind"] == "unknown" and rfp["deadlines"][1]["confidence"] == "check"
    pl = page_limit(rfp)
    assert pl["value"] == 12 and pl["confidence"] == "check"
    labels = {r["label"]: r for r in rfp["requirements"]}
    assert labels["2.2"]["qtype"] == "other" and labels["2.2"]["confidence"] == "check"
    assert labels["2.3"]["mandatory"] is False
    assert rfp["meta"]["agency"] == "Hollowbrook Cemetery District" and rfp["meta"]["agency_confidence"] == "check"


def test_parser_is_deterministic():
    text = rfp_text("special_counsel_tannery_creek_transit")
    assert json.dumps(parse_rfp(text), sort_keys=True) == json.dumps(parse_rfp(text), sort_keys=True)


def test_evaluator_notices_a_missed_and_an_extra_item(parsed, root):
    import copy
    p = copy.deepcopy(parsed["city_attorney_marlow_ridge"])
    p["requirements"].pop()
    p["forms"].append(dict(p["forms"][0], name="Imaginary Form"))
    res = evaluate(p, key("city_attorney_marlow_ridge", root))
    assert res["requirements"]["fn"] == 1 and res["forms"]["fp"] == 1
    assert res["overall"]["recall"] < 1 and res["overall"]["precision"] < 1


def test_held_out_first_run_is_recorded_and_was_poor(root):
    with open(os.path.join(root, "data", "holdout", "first_run_result.json"), encoding="utf-8") as f:
        first = json.load(f)
    assert first["overall"]["recall"] < 0.2          # the honest first-run figure stays on file
