"""Layouts the four samples do not use. The three documents in tests/layouts were written for these
tests by the same person who wrote the parser, so they show the code paths work; they are not an
accuracy measure. Fictional data."""
import os

import pytest

from desk.rfp import classify_deadline, classify_question, parse_rfp
from desk.util import find_dates, find_time

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(HERE, "layouts", name), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def qa():
    return parse_rfp(load("questions_and_answers.txt"))


@pytest.fixture(scope="module")
def sheet():
    return parse_rfp(load("data_sheet.txt"))


@pytest.fixture(scope="module")
def addfirst():
    return parse_rfp(load("addenda_first.txt"))


def dl(rfp):
    return {d["kind"]: (d["date"], d["time"]) for d in rfp["deadlines"]}


@pytest.mark.parametrize("text,iso", [
    ("7 December 2026", "2026-12-07"), ("Thursday, the 10th of December 2026", "2026-12-10"),
    ("January 14th, 2027", "2027-01-14"), ("10-DEC-2026", "2026-12-10"), ("2026-12-10", "2026-12-10"),
    ("1/5/27", "2027-01-05"), ("Mon., Dec. 14, 2026", "2026-12-14"), ("01/15/2027", "2027-01-15")])
def test_date_forms(text, iso):
    found = find_dates("due " + text + " at the office")
    assert [d["date"] for d in found] == [iso]


def test_two_day_date_and_overlapping_forms_give_one_date():
    d = find_dates("December 14 and 15, 2026")
    assert len(d) == 1 and (d[0]["date"], d[0]["end"]) == ("2026-12-14", "2026-12-15")
    assert len(find_dates("on 21 January 2027, no later than 3:00 p.m.")) == 1


def test_times_twenty_four_hour_and_noon():
    assert find_time("2026-12-11 12:00") == "12:00" and find_time("by 14:00 hours") == "14:00"
    assert find_time("at noon") == "12:00" and find_time("4:30 PM on Friday") == "16:30"
    assert find_time("a ratio of 3 to 1") is None


def test_deadline_kinds_from_varied_wording():
    assert classify_deadline("PROPOSALS DUE") == "submission_due"
    assert classify_deadline("Proposals must be received no later than") == "submission_due"
    assert classify_deadline("Last day to submit written questions") == "questions_due"
    assert classify_deadline("Responses to questions issued") == "answers_issued"
    assert classify_deadline("Board of Trustees consideration") == "award"
    assert classify_deadline("to bring a recommendation to the Board at its meeting of") == "award"
    assert classify_deadline("Request for Proposals issued") == "issued"


def test_dates_in_sentences_one_sentence_two_deadlines_and_a_second_day():
    text = ("AGENCY X DISTRICT\n\n1. SCHEDULE\n\nQuestions must be emailed by 12/15/2026 at 4:00 PM. Proposals must\n"
            "be received no later than 4:30 PM on Friday, 01/15/2027. The District expects to interview firms on\n"
            "02/02/2027 and 02/03/2027, and to bring a recommendation to the Board at its meeting of 02/23/2027.\n"
            "The offices are closed from 24 December 2026 through 1 January 2027.\n")
    rfp = parse_rfp(text)
    assert dl(rfp) == {"questions_due": ("2026-12-15", "16:00"), "submission_due": ("2027-01-15", "16:30"),
                       "interview": ("2027-02-02", None), "award": ("2027-02-23", None)}
    assert next(d for d in rfp["deadlines"] if d["kind"] == "interview")["end_date"] == "2027-02-03"
    assert all(d["confidence"] == "check" for d in rfp["deadlines"])       # sentence dates are for a person to confirm


def test_schedule_rows_with_the_date_first():
    rfp = parse_rfp("X WATER DISTRICT\n\nCALENDAR\n\n  Mon., Dec. 14, 2026     Request for Proposals issued\n"
                    "  Thu., Jan. 7, 2027      Written questions due, 12:00 noon\n"
                    "  Wed., Jan. 27, 2027     Proposals due, 4:00 P.M.\n")
    assert dl(rfp) == {"issued": ("2026-12-14", None), "questions_due": ("2027-01-07", "12:00"),
                       "submission_due": ("2027-01-27", "16:00")}


def test_page_headers_and_table_of_contents_are_ignored():
    text = ("X PORT DISTRICT\n\nTABLE OF CONTENTS\n\n  Part One   Calendar ........ 2\n  Part Two   Proposal Contents ... 3\n\n"
            "RFP 77                                   Page 2 of 3\n\nPART ONE\nCALENDAR\n\n"
            "  Proposals due     January 5, 2027\n\nRFP 77                                   Page 3 of 3\n\n"
            "PART TWO\nPROPOSAL CONTENTS\n\n2.1  The Firm.  Describe the firm.\n2.2  Pricing.  State rates.\n")
    rfp = parse_rfp(text)
    assert [s["kind"] for s in rfp["sections"]] == ["schedule", "content"]
    assert [r["label"] for r in rfp["requirements"]] == ["2.1", "2.2"]
    assert [r["qtype"] for r in rfp["requirements"]] == ["firm_overview", "rates"]
    assert len(rfp["deadlines"]) == 1


def test_lettered_sections_with_roman_items_and_unnumbered_requirements():
    text = ("X COLLEGE DISTRICT\n\nA. CONTENT OF PROPOSAL\n\nProposals shall respond to each item below.\n\n"
            "   (i)    Transmittal Letter. Provide a letter.\n   (ii)   Firm Description. Describe the firm.\n"
            "   (iii)  How would the firm staff two urgent matters in the same\n          week?\n\n"
            "In addition, every proposal must include a one-page organization chart.\n\n"
            "B. GENERAL CONDITIONS\n\n   (i)   The District may cancel this RFP.\n")
    reqs = parse_rfp(text)["requirements"]
    assert [r["label"] for r in reqs] == ["i", "ii", "iii", ""]
    assert [r["qtype"] for r in reqs] == ["cover_letter", "firm_overview", "approach", "team"]
    assert reqs[3]["confidence"] == "check" and "unnumbered" in reqs[3]["check_reason"]


def test_wrapped_line_that_looks_like_a_label_stays_in_its_item():
    text = ("X AUTHORITY\n\nELIGIBILITY\n\n4.1  The Authority will consider only firms that meet all of these\n"
            "     conditions.\n\n     a.  Lead counsel has been licensed to practice law for twelve\n"
            "         (12) or more years.\n     b.  The firm has three (3) or more attorneys.\n")
    mq = parse_rfp(text)["min_quals"]
    assert [(q["check_kind"], q["value"]) for q in mq] == [("years_admitted", 12), ("attorney_count", 3)]
    assert mq[0]["text"].endswith("twelve (12) or more years.")


def test_numbered_paragraphs_with_run_in_titles_become_sections():
    text = ("X PORT DISTRICT\n\n1.  Background.  The Port District needs counsel.\n\n"
            "2.  Who may propose.  A firm must show all of the following. First, the lead attorney must have\n"
            "been admitted to practice for no fewer than fifteen (15) years. Second, the firm must have no fewer\n"
            "than eight (8) attorneys. A firm that cannot show both will not be evaluated.\n\n"
            "3.  How the District will choose.  Experience counts for 60 points out of 100; the team, 30 points;\n"
            "and cost, 10 points.\n\n"
            "4.  Insurance.  The firm must carry professional liability insurance of at least $5,000,000 per\n"
            "claim; and workers' compensation insurance in the amounts the law requires. The District must be\n"
            "named as an additional insured.\n")
    rfp = parse_rfp(text)
    assert [s["kind"] for s in rfp["sections"]] == ["intro", "minquals", "evaluation", "insurance"]
    assert [(q["check_kind"], q["value"]) for q in rfp["min_quals"]] == [("years_admitted", 15), ("attorney_count", 8)]
    assert [(c["name"], c["weight"]) for c in rfp["evaluation"]["criteria"]] == [
        ("Experience", 60), ("the team", 30), ("cost", 10)]
    assert [x["amounts"] for x in rfp["insurance"]] == [["$5,000,000"], []]


def test_numbered_list_inside_a_section_is_not_mistaken_for_run_in_sections():
    text = ("X CITY\n\nPROPOSAL CONTENT\n\n1. Cover letter. Provide a signed letter.\n"
            "2. Team. Identify the attorneys.\n3. Fees. State hourly rates.\n")
    rfp = parse_rfp(text)
    assert len(rfp["sections"]) == 1 and [r["label"] for r in rfp["requirements"]] == ["1", "2", "3"]


def test_weights_in_a_sentence_with_words_and_percent_signs():
    text = ("X DISTRICT\n\nEVALUATION\n\nProposals will be scored as follows: experience in education law,\n"
            "forty percent (40%); qualifications of the attorneys, twenty-five percent (25%); fees, thirty-five\n"
            "percent (35%).\n")
    ev = parse_rfp(text)["evaluation"]
    assert [(c["name"], c["weight"]) for c in ev["criteria"]] == [
        ("experience in education law", 40), ("qualifications of the attorneys", 25), ("fees", 35)]
    assert ev["total"] == 100 and ev["unit"] == "percent"


def test_question_types_from_first_clause_not_from_stray_words():
    assert classify_question("", "Describe the firm: when it was founded and how its litigation group is organized.") == "firm_overview"
    assert classify_question("", "Describe up to six disputes the firm has litigated for public owners.") == "experience"
    assert classify_question("", "How does the firm control litigation cost?") == "approach"
    assert classify_question("", "If the firm is chosen, how would it take over the matter from present counsel?") == "transition"
    assert classify_question("Letter of Interest", "A signed letter.") == "cover_letter"
    assert classify_question("Method of Service", "How the firm would deliver opinions.") == "approach"
    assert classify_question("Litigation", "List cases.") == "disclosure"          # a title still counts


def test_people_need_a_role_and_lists_share_one(qa):
    text = ("WEXFORD COLLEGE DISTRICT\n\nINTRODUCTION\n\nWexford College District (the \"District\") operates Sorrel Canyon College.\n"
            "The Board of Trustees is composed of Board President Nadira Whitcombe, Clerk Imelda Rasmussen, and\n"
            "Trustees Corwin Addai, Livia Montrose and Priya Venkataraman. The Chancellor is Dr. Alaric Fenwick.\n"
            "The Vice Chancellor, Administrative Services, is Marguerite Solberg. The claims administrator is\n"
            "Stonebridge Claims Services, Inc. Faculty are represented by the Sorrel Faculty Association.\n")
    p = {x["name"]: x["category"] for x in parse_rfp(text)["parties"]}
    assert p == {"Wexford College District": "agency", "Nadira Whitcombe": "board", "Imelda Rasmussen": "board",
                 "Corwin Addai": "board", "Livia Montrose": "board", "Priya Venkataraman": "board",
                 "Alaric Fenwick": "staff", "Marguerite Solberg": "staff",
                 "Stonebridge Claims Services, Inc.": "other_organisation", "Sorrel Faculty Association": "adverse"}
    assert {x["name"]: x["category"] for x in qa["parties"]}["Pine Hollow Library Workers Union"] == "adverse"


def test_question_headings_layout(qa):
    kinds = [s["kind"] for s in qa["sections"]]
    assert kinds == ["other", "schedule", "minquals", "content", "forms", "evaluation", "insurance", "submission"]
    assert dl(qa) == {"issued": ("2026-12-01", None), "questions_due": ("2026-12-10", "12:00"),
                      "answers_issued": ("2026-12-15", None), "submission_due": ("2027-01-14", "14:00"),
                      "interview": ("2027-01-26", None), "award": ("2027-02-09", None)}
    assert [r["label"] for r in qa["requirements"]] == ["#1", "#2", "#3", "#4", "#5", "#6", "#7", ""]
    assert [r["qtype"] for r in qa["requirements"]] == ["firm_overview", "team", "experience", "approach",
                                                        "references", "conflicts", "rates", "disclosure"]
    assert [f["name"] for f in qa["forms"]] == ["Signature Sheet", "Non-Collusion Statement"]
    assert [x["amounts"] for x in qa["insurance"]] == [["$1,000,000"], ["$2,000,000"]]
    assert [(q["check_kind"], q["value"]) for q in qa["min_quals"]] == [("years_admitted", 8), ("attorney_count", 4)]
    assert sum(c["weight"] for c in qa["evaluation"]["criteria"]) == 100


def test_data_sheet_layout(sheet):
    assert dl(sheet) == {"issued": ("2026-12-02", None), "questions_due": ("2026-12-11", "12:00"),
                         "answers_issued": ("2026-12-16", None), "submission_due": ("2027-01-12", "15:00"),
                         "interview": ("2027-01-26", None), "award": ("2027-02-09", None)}
    assert [r["label"] for r in sheet["requirements"]] == ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "", ""]
    assert sheet["requirements"][-1]["qtype"] == "disclosure"
    assert [(c["name"], c["weight"]) for c in sheet["evaluation"]["criteria"]] == [
        ("Experience", 40), ("Team", 30), ("Approach", 20), ("Price", 10)]
    assert sheet["evaluation"]["criteria"][0]["printed_as"] == 0.4
    assert [x["amounts"] for x in sheet["insurance"]] == [["$2,000,000"], ["$1,000,000"], []]
    mech = {m["kind"]: m["value"] for m in sheet["mechanics"]}
    assert mech["page_limit"] == 20 and mech["font"] == 11 and mech["packaging"] == "sealed envelope"
    assert {"copies", "delivery", "not_accepted", "page_exclusions"} <= set(mech)
    assert all(m["confidence"] == "check" for m in sheet["mechanics"])
    assert [(q["check_kind"], q["value"]) for q in sheet["min_quals"]] == [("years_admitted", 10), ("attorney_count", 5)]


def test_addenda_placed_before_the_rfp_are_applied_in_number_order(addfirst):
    assert [a["number"] for a in addfirst["addenda"]] == ["1", "2"]
    sub = next(d for d in addfirst["deadlines"] if d["kind"] == "submission_due")
    assert (sub["date"], sub["time"]) == ("2027-01-27", "15:00")
    assert (sub["original_date"], sub["original_time"]) == ("2027-01-13", "16:00")      # as issued, not the first change
    assert sub["changed_by"] == "Addendum 2"
    assert next(d for d in addfirst["deadlines"] if d["kind"] == "issued")["date"] == "2026-12-01"
    pl = next(m for m in addfirst["mechanics"] if m["kind"] == "page_limit")
    assert (pl["value"], pl["original_value"]) == (25, 20)


def test_addendum_deletes_a_requirement_a_form_and_a_criterion_and_changes_weights(addfirst):
    assert [r["label"] for r in addfirst["requirements"]] == ["4.2.1", "4.2.2", "4.2.3", "4.2.4", "4.2.5",
                                                              "4.2.7", "4.2.8"]
    assert [r["label"] for r in addfirst["deleted_requirements"]] == ["4.2.6"]
    assert addfirst["deleted_requirements"][0]["deleted_by"] == "Addendum 2"
    assert [f["name"] for f in addfirst["forms"]] == ["Signature Page", "Non-Collusion Affidavit"]
    assert [(c["name"], c["weight"]) for c in addfirst["evaluation"]["criteria"]] == [
        ("Experience", 40), ("Team", 25), ("Approach", 15), ("Fees", 20)]
    assert addfirst["evaluation"]["total"] == 100
    kinds = [c["kind"] for c in addfirst["addenda"][1]["changes"]]
    assert kinds == ["submission_due", "requirement_deleted", "weight_changed", "weight_changed",
                     "criterion_removed", "form_removed"]


def test_sub_headings_over_their_own_items_are_not_requirements(addfirst):
    labels = [r["label"] for r in addfirst["requirements"]]
    assert "4.1" not in labels and "4.1.1" not in labels and "4.2" not in labels
    assert [q["label"] for q in addfirst["min_quals"]] == ["3.1.1", "3.1.2"]             # "3.1 ... the following" is an intro


def test_one_addendum_sentence_can_move_two_dates_and_insurance_and_delete_by_instruction():
    text = load("addenda_first.txt").replace(
        "4. Form C, Local Business Statement, is no longer required.",
        "4. Interviews are moved to 2/9/27 and the Board award to 2/23/27.\n5. Delete paragraph 4.2.3.\n"
        "6. The professional liability minimum in Section 7.1 is reduced to $1,000,000.\n"
        "7. Proposers are reminded to read the whole RFP.")
    rfp = parse_rfp(text)
    assert dl(rfp)["interview"] == ("2027-02-09", None) and dl(rfp)["award"] == ("2027-02-23", None)
    assert "4.2.3" not in [r["label"] for r in rfp["requirements"]]
    assert rfp["insurance"][0]["amounts"] == ["$1,000,000"] and "$2,000,000" in rfp["insurance"][0]["original_text"]
    notes = rfp["addenda"][1]["notes"]
    assert len(notes) == 1 and "reminded" in notes[0]["text"]                 # what was not applied is listed to read


def test_addendum_replaces_an_item_by_its_number_and_new_date_instead_of_old():
    text = ("X AUTHORITY\n\nCALENDAR\n\n  Proposals due      January 27, 2027, 4:00 p.m.\n"
            "  Interviews         February 18, 2027\n\nINSURANCE\n\n7.1  Professional liability: $2,000,000 each claim.\n"
            "7.4  Cyber liability: $1,000,000 each claim.\n\nADDENDUM NO. 1\nDated January 22, 2027\n\n"
            "  (1)  Proposals are now due on February 10th, 2027 at 2:00 P.M.\n"
            "  (2)  Interviews will be held on Thursday, February 25, 2027 instead of February 18, 2027.\n"
            "  (3)  Paragraph 7.4 is corrected to read: Cyber liability: $2,000,000 each claim.\n")
    rfp = parse_rfp(text)
    assert dl(rfp) == {"submission_due": ("2027-02-10", "14:00"), "interview": ("2027-02-25", None)}
    cyber = rfp["insurance"][1]
    assert cyber["amounts"] == ["$2,000,000"] and cyber["original_text"].startswith("Cyber liability: $1,000,000")
    assert rfp["addenda"][0]["issued"] == "2027-01-22" and rfp["addenda"][0]["notes"] == []


def test_forms_named_in_a_sentence_and_document_rows():
    text = ("X DISTRICT\n\nREQUIRED PAPERWORK\n\n5.1  Each proposal must include the following documents.\n\n"
            "     Document 1    Proposal Cover Sheet\n     Document 2    Certification of Non-Collusion\n\n"
            "5.2  The Authority may reject a proposal that omits any required document.\n\n"
            "The firm must also enclose a completed taxpayer identification form and evidence of insurance as\n"
            "described in Section 9.\n")
    forms = parse_rfp(text)["forms"]
    assert [f["name"] for f in forms] == ["Proposal Cover Sheet", "Certification of Non-Collusion",
                                          "taxpayer identification form", "evidence of insurance"]
    assert [f["confidence"] for f in forms] == ["ok", "ok", "check", "check"]


def test_post_award_duties_and_optional_wording_are_not_submission_requirements():
    text = ("X DISTRICT\n\nINSURANCE\n\nThe selected firm shall provide certificates showing professional liability\n"
            "insurance of not less than $3,000,000 per claim. With its proposal, the firm need only provide a letter\n"
            "from its broker.\n\nGENERAL CONDITIONS\n\n   (i)   A protest must be delivered within five (5) business days.\n"
            "   (ii)  The selected firm must sign the agreement in Appendix 1 within fifteen (15) days.\n")
    rfp = parse_rfp(text)
    assert len(rfp["insurance"]) == 1 and rfp["forms"] == [] and rfp["requirements"] == [] and rfp["deadlines"] == []
