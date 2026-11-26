import copy
import datetime as dt

import pytest

from conftest import AS_OF, RFPS, rfp_text
from desk import facts as F
from desk.pipeline import (ANSWERED, DONE, FAILED, NO_CONTENT, PARTIAL, PERSON, build, detect_terms,
                           match_standard_form)
from desk.util import shift_business_days


@pytest.mark.parametrize("name", RFPS)
def test_draft_follows_the_rfp_order_and_numbering(name, built, parsed):
    assert [s["label"] for s in built[name]["sections"]] == [r["label"] for r in parsed[name]["requirements"]]
    for sec, req in zip(built[name]["sections"], parsed[name]["requirements"]):
        assert sec["rfp_text"] == req["text"]


@pytest.mark.parametrize("name", RFPS)
def test_conflicts_section_is_never_auto_written(name, built):
    sec = next(s for s in built[name]["sections"] if s["qtype"] == "conflicts")
    assert sec["status"] == PERSON and sec["owner"] == "Conflicts team"
    assert [p["type"] for p in sec["parts"]] == ["person"]
    assert "never written by the tool" in sec["parts"][0]["text"]


@pytest.mark.parametrize("name", RFPS)
def test_pricing_cover_letter_and_disclosures_are_left_to_a_person(name, built):
    for sec in built[name]["sections"]:
        if sec["qtype"] in ("rates", "cover_letter", "disclosure"):
            assert sec["status"] == PERSON
            assert all(p["type"] == "person" for p in sec["parts"])


def test_past_conflicts_and_rates_answers_are_never_inserted(built, data):
    banned = {a["id"] for a in data.answers if a["question_type"] in ("conflicts", "rates")}
    used = {p["provenance"]["answer_id"] for name in RFPS for s in built[name]["sections"]
            for p in s["parts"] if p["type"] == "passage"}
    assert banned and not (banned & used)


def test_conflicts_party_list_covers_agency_board_staff_and_adverse(built):
    parties = built["special_counsel_tannery_creek_transit"]["parties"]
    cats = {p["category"] for p in parties}
    assert {"agency", "staff", "adverse"} <= cats and len(parties) == 8
    cats = {p["category"] for p in built["general_counsel_redwood_flats"]["parties"]}
    assert {"agency", "staff", "board"} <= cats


@pytest.mark.parametrize("name", RFPS)
def test_every_requirement_form_and_qualification_has_a_matrix_row(name, built, parsed):
    ids = {r["id"] for r in built[name]["matrix"]}
    rfp = parsed[name]
    for item in rfp["requirements"] + rfp["forms"] + rfp["min_quals"] + rfp["insurance"]:
        assert item["id"] in ids
    for r in built[name]["matrix"]:
        assert r["owner"] and r["where"] and r["status"] in (ANSWERED, PARTIAL, NO_CONTENT, PERSON, FAILED, DONE)


@pytest.mark.parametrize("name", RFPS)
def test_disqualifier_panel_lists_every_mandatory_item_not_satisfied(name, built):
    res = built[name]
    expect = {r["id"] for r in res["matrix"] if r["mandatory"] and r["status"] not in (ANSWERED, DONE)}
    assert {r["id"] for r in res["disqualifiers"]} == expect
    assert res["go_no_go"]["open_disqualifiers"] == len(expect) > 0
    assert all(f["id"] in expect for f in res["rfp"]["forms"] if f["mandatory"])   # unsigned forms are always open


def test_due_dates_work_back_from_the_deadline_in_business_days(built, data):
    res = built["general_counsel_redwood_flats"]          # deadline Thursday 17 December 2026 after the addendum
    deadline = dt.date(2026, 12, 17)
    lead = data.workplan["lead_days"]
    due = {r["id"]: r["due"] for r in res["matrix"]}
    assert due["DEADLINE"] == "2026-12-17"
    assert due["R-G"] == shift_business_days(deadline, -lead["conflicts"]).isoformat() == "2026-12-03"
    assert due["R-B"] == shift_business_days(deadline, -lead["content"]).isoformat() == "2026-12-09"
    assert due["F1"] == "2026-12-14"
    for r in res["matrix"]:
        assert dt.date.fromisoformat(r["due"]).weekday() < 5


def test_holiday_file_moves_due_dates_and_is_reported(data):
    text = rfp_text("special_counsel_tannery_creek_transit")
    plain = build(text, data, AS_OF)
    hol = frozenset({dt.date(2026, 12, 24), dt.date(2026, 12, 25), dt.date(2027, 1, 1)})
    with_h = build(text, data, AS_OF, hol)
    a = next(r for r in plain["matrix"] if r["id"] == "R-C.2.6")["due"]
    b = next(r for r in with_h["matrix"] if r["id"] == "R-C.2.6")["due"]
    assert a == "2026-12-25" and b == "2026-12-22"
    assert plain["go_no_go"]["holidays_supplied"] is False and with_h["go_no_go"]["holidays_supplied"] is True
    assert "Holidays are not skipped unless a holiday file is supplied" in plain["go_no_go"]["holiday_note"]
    assert with_h["go_no_go"]["deadline"]["business_days_left"] == plain["go_no_go"]["deadline"]["business_days_left"] - 3


def test_due_date_already_passed_is_marked_late(data):
    res = build(rfp_text("labor_negotiator_quillfeather_usd"), data, "2026-12-08")
    late = [r["id"] for r in res["matrix"] if r["late"]]
    assert "R-Q6" in late and res["go_no_go"]["late_items"] >= 1
    after = build(rfp_text("labor_negotiator_quillfeather_usd"), data, "2026-12-14")
    assert after["go_no_go"]["deadline"]["passed"] is True


def test_status_file_marks_items_done_and_closes_the_disqualifier(data):
    text = rfp_text("general_counsel_redwood_flats")
    res = build(text, data, AS_OF, status={"F1": {"done": True, "by": "Coordinator"}, "ZZ": {"done": True}})
    row = next(r for r in res["matrix"] if r["id"] == "F1")
    assert row["status"] == DONE and row["auto_status"] == PERSON and "Coordinator" in row["detail"]
    assert "F1" not in {r["id"] for r in res["disqualifiers"]}
    assert res["go_no_go"]["unknown_status_marks"] == ["ZZ"]
    assert res["go_no_go"]["open_disqualifiers"] == build(text, data, AS_OF)["go_no_go"]["open_disqualifiers"] - 1


def test_coverage_counts_add_up(built):
    for name in RFPS:
        c = built[name]["go_no_go"]["coverage"]
        assert c["answered"] + c["partial"] + c["no_content"] + c["person"] == c["requirements"]
        assert c["pct"] == round(100 * c["answered_of_answerable"] / c["library_answerable"])
        assert 0 < c["pct"] <= 100


def test_page_limit_check_fails_when_the_estimate_is_over(data):
    d = copy.copy(data)
    d.workplan = dict(data.workplan, words_per_page=20)
    res = build(rfp_text("labor_negotiator_quillfeather_usd"), d, AS_OF)
    row = next(r for r in res["matrix"] if r["category"] == "submission" and "exceed 10 pages" in r["requirement"])
    assert row["status"] == FAILED and row in res["disqualifiers"]
    assert res["page"]["estimated_pages"] > res["page"]["limit"] == 10


def test_page_limit_is_only_an_estimate_while_sections_are_empty(built):
    res = built["general_counsel_redwood_flats"]
    row = next(r for r in res["matrix"] if r["category"] == "submission" and "fifteen (15) pages" in r["requirement"])
    assert row["status"] == PARTIAL and "estimate" in row["detail"] and "still empty" in row["detail"]
    assert res["page"]["limit"] == 15


def test_formatting_rules_reach_the_matrix_and_print_style(built):
    from desk import render
    res = built["city_attorney_marlow_ridge"]
    kinds = [r["detail"] for r in res["matrix"] if r["where"] == "draft.html print style"]
    assert any("12 point" in k for k in kinds) and any("1.0 inch" in k for k in kinds)
    html = render.draft_html(res)
    assert "@page{margin:1.0in}" in html and "font-size:12pt" in html


def test_blocking_flag_makes_the_section_partial_and_shows_in_go_no_go(built):
    res = built["labor_negotiator_quillfeather_usd"]
    sec = next(s for s in res["sections"] if s["label"] == "Q2")
    assert sec["status"] == PARTIAL and "blocking fact flags" in sec["notes"][0]
    flags = res["go_no_go"]["blocking_flags"]
    assert len(flags) == 1 and "Corwin Halloway" in flags[0]["message"]


def test_clean_answer_is_preferred_over_a_higher_ranked_flagged_one(built):
    sec = next(s for s in built["general_counsel_redwood_flats"]["sections"] if s["label"] == "B")
    passage = sec["parts"][0]
    assert not F.has_blocking(passage["flags"]) and sec["status"] == ANSWERED
    assert any("passed over" in n and "attorney count" in n for n in sec["notes"])
    assert any(alt["blocking"] for alt in sec["alternatives"])


def test_unapproved_answer_can_only_give_a_partial_status(data):
    d = copy.copy(data)
    d.answers = [dict(a, approved=False, approver="") for a in data.answers]
    res = build(rfp_text("city_attorney_marlow_ridge"), d, AS_OF)
    lib = [s for s in res["sections"] if any(p["type"] == "passage" for p in s["parts"])]
    assert lib and all(s["status"] == PARTIAL for s in lib)
    assert res["go_no_go"]["coverage"]["pct"] == 0


def test_too_few_references_with_consent_is_a_visible_gap(built):
    sec = next(s for s in built["labor_negotiator_quillfeather_usd"]["sections"] if s["qtype"] == "references")
    part = next(p for p in sec["parts"] if p["type"] == "references")
    assert sec["status"] == PARTIAL and part["needed"] == 3 and len(part["items"]) == 2
    assert any("the RFP asks for 3" in n for n in sec["notes"])


def test_reference_note_separates_the_two_kinds_of_missing_consent(built):
    sec = next(s for s in built["general_counsel_redwood_flats"]["sections"] if s["qtype"] == "references")
    note = next(n for n in sec["notes"] if "were not listed" in n)
    assert "without the contact's consent to be listed" in note and "without the client's consent to be named" in note


def test_references_required_count_comes_from_the_rfp(built):
    sec = next(s for s in built["general_counsel_redwood_flats"]["sections"] if s["qtype"] == "references")
    assert next(p for p in sec["parts"] if p["type"] == "references")["needed"] == 4


def test_unrecognised_question_is_a_gap_not_a_guess(built):
    sec = next(s for s in built["labor_negotiator_quillfeather_usd"]["sections"] if s["label"] == "Q8")
    assert sec["status"] == NO_CONTENT and sec["parts"][0]["type"] == "gap"


def test_terms_come_from_the_rfp_even_across_a_line_break(built):
    assert built["general_counsel_redwood_flats"]["terms"] == {"governing_body": "Board of Directors", "chief_exec": "General Manager"}
    assert built["city_attorney_marlow_ridge"]["terms"]["governing_body"] == "City Council"
    assert detect_terms("The agency has a director.", {}) == ("", "")


def test_no_inserted_passage_in_any_sample_names_another_agency_unflagged(built, data):
    for name in RFPS:
        res = built[name]
        agency = res["rfp"]["meta"]["agency"]
        for sec in res["sections"]:
            for p in sec["parts"]:
                if p["type"] != "passage":
                    continue
                found = F.find_wrong_agency(p["text"], agency, F.known_agencies(data))
                flagged = [f for f in p["flags"] if f["kind"] == "wrong_agency"]
                assert len(found) == len(flagged)
                if found:
                    assert sec["status"] == PARTIAL


def test_model_hook_is_off_by_default_and_its_output_is_fact_checked(data, monkeypatch):
    from drafting import llm_hook
    assert llm_hook.ENABLED is False
    assert llm_hook.rewrite("text", "req", {}) == "text"
    text = rfp_text("city_attorney_marlow_ridge")
    before = build(text, data, AS_OF)
    assert not any(p.get("rewritten") for s in before["sections"] for p in s["parts"])

    def bad(passage, requirement_text, context):
        return passage + " We did the same for Harlan Springs Fire Protection District with our 60 attorneys."
    monkeypatch.setattr(llm_hook, "ENABLED", True)
    monkeypatch.setattr(llm_hook, "rewrite", bad)
    after = build(text, data, AS_OF)
    passages = [(s, p) for s in after["sections"] for p in s["parts"] if p["type"] == "passage"]
    assert passages
    for sec, p in passages:
        kinds = {f["kind"] for f in p["flags"]}
        assert p["rewritten"] and {"wrong_agency", "fact_mismatch", "rewritten"} <= kinds
        assert sec["status"] == PARTIAL
    assert after["go_no_go"]["coverage"]["pct"] == 0


def test_standard_form_matching():
    forms = [{"id": "SF-01", "name": "Non-Collusion Declaration", "aliases": ["Non-Collusion Affidavit"]},
             {"id": "SF-05", "name": "Addendum Acknowledgment", "aliases": ["Acknowledgment of Addenda"]}]
    assert match_standard_form("Non-Collusion Affidavit", forms)["id"] == "SF-01"
    assert match_standard_form("Acknowledgment of Addenda", forms)["id"] == "SF-05"
    assert match_standard_form("Campaign Contribution Disclosure", forms) is None


def test_agency_form_with_no_standard_answers_is_no_content(built):
    rows = {r["requirement"]: r for r in built["special_counsel_tannery_creek_transit"]["matrix"] if r["category"] == "form"}
    assert rows["Campaign Contribution Disclosure"]["status"] == NO_CONTENT
    assert rows["Non-Collusion Declaration"]["status"] == PERSON and "SF-01" in rows["Non-Collusion Declaration"]["detail"]
    assert "Added by Addendum 1" in rows["Addendum Acknowledgment"]["detail"]


def test_missing_deadline_is_a_failed_mandatory_row(data):
    text = rfp_text("city_attorney_marlow_ridge").replace("Proposals due                       December 18, 2026 at 4:00 p.m.\n", "")
    res = build(text, data, AS_OF)
    row = next(r for r in res["matrix"] if r["id"] == "DEADLINE")
    assert row["status"] == FAILED and res["go_no_go"]["deadline"] is None
    assert all(r["due"] == "" for r in res["matrix"])


def test_old_firm_facts_are_reported(data):
    res = build(rfp_text("city_attorney_marlow_ridge"), data, "2027-08-01")
    assert res["go_no_go"]["facts_old"] is True
    assert build(rfp_text("city_attorney_marlow_ridge"), data, AS_OF)["go_no_go"]["facts_old"] is False
