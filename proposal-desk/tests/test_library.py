import copy
import datetime as dt

from conftest import AS_OF, RFPS
from desk.library import BM25, fill_placeholders, is_stale, provenance, provenance_text, rank_answers
from desk.util import tokens

META = {"agency": "Redwood Flats Water District", "agency_type": "special_district", "practice": "general_counsel",
        "subjects": ["water"]}
TODAY = dt.date(2026, 11, 25)


def make(id_, **kw):
    base = {"id": id_, "proposal_id": "P-X", "proposal_agency": "Some Agency", "agency_type": "special_district",
            "practice": "general_counsel", "submitted": "2025-06-01", "outcome": "won", "question_type": "approach",
            "question_text": "Describe your approach.", "answer_text": "We attend every board meeting and review contracts.",
            "approved": True, "approver": "Lead", "review_by": "2028-01-01", "tags": []}
    base.update(kw)
    return base


def test_bm25_ranks_the_document_that_shares_the_query_terms():
    docs = [tokens("water rates and charges hearing"), tokens("collective bargaining impasse"), tokens("design build claims")]
    bm = BM25(docs)
    scores = bm.scores(tokens("advice on water rates"))
    assert scores[0] > 0 and scores[1] == 0 and scores[2] == 0
    assert BM25([]).scores(["x"]) == []


def test_bm25_rare_terms_count_more_than_common_ones():
    docs = [tokens("board meeting groundwater"), tokens("board meeting agenda"), tokens("board meeting minutes")]
    bm = BM25(docs)
    assert bm.idf["groundwater"] > bm.idf["board"]


def test_winning_answer_ranks_above_identical_losing_answer():
    r = rank_answers([make("A1", outcome="lost"), make("A2", outcome="won"), make("A3", outcome="pending")],
                     "approach", "board meeting contracts", META, TODAY)
    assert [c["answer"]["id"] for c in r] == ["A2", "A3", "A1"]


def test_recent_answer_ranks_above_identical_older_answer():
    r = rank_answers([make("A1", submitted="2021-06-01"), make("A2", submitted="2026-06-01")],
                     "approach", "board meeting contracts", META, TODAY)
    assert r[0]["answer"]["id"] == "A2" and r[0]["factors"]["recency"] > r[1]["factors"]["recency"]


def test_approved_answer_ranks_above_identical_unapproved_answer():
    r = rank_answers([make("A1", approved=False, approver=""), make("A2")], "approach", "board meeting", META, TODAY)
    assert r[0]["answer"]["id"] == "A2"
    assert "not approved by the practice lead" in r[1]["reasons"]


def test_same_agency_type_and_practice_are_preferred():
    r = rank_answers([make("A1", agency_type="city"), make("A2"), make("A3", practice="labor")],
                     "approach", "board meeting", META, TODAY)
    assert r[0]["answer"]["id"] == "A2"


def test_only_answers_of_the_same_question_type_are_candidates():
    r = rank_answers([make("A1", question_type="team"), make("A2")], "approach", "board meeting", META, TODAY)
    assert [c["answer"]["id"] for c in r] == ["A2"]
    assert rank_answers([make("A1")], "transition", "x", META, TODAY) == []


def test_stale_answer_is_returned_and_flagged():
    a = make("A1", review_by="2026-11-24")
    assert is_stale(a, TODAY) and not is_stale(make("A2", review_by="2026-11-25"), TODAY)
    r = rank_answers([a], "approach", "board meeting", META, TODAY)
    assert r[0]["stale"] and any("stale" in x for x in r[0]["reasons"])


def test_stale_answers_are_never_inserted_in_any_sample_draft(built, data):
    by_id = {a["id"]: a for a in data.answers}
    inserted = 0
    for name in RFPS:
        for sec in built[name]["sections"]:
            for p in sec["parts"]:
                if p["type"] == "passage":
                    inserted += 1
                    assert by_id[p["provenance"]["answer_id"]]["review_by"] >= AS_OF
    assert inserted >= 20


def test_only_stale_content_means_no_content_found(data):
    from conftest import rfp_text
    from desk.pipeline import build
    d = copy.copy(data)
    d.answers = [dict(a, review_by="2020-01-01") for a in data.answers]
    res = build(rfp_text("city_attorney_marlow_ridge"), d, AS_OF)
    sec = next(s for s in res["sections"] if s["qtype"] == "approach")
    assert sec["status"] == "no_content"
    assert "Stale answers exist and were not inserted" in sec["parts"][0]["text"]
    assert any(alt["stale"] for alt in sec["alternatives"])       # still shown to the proposal lead


def test_every_inserted_passage_carries_source_proposal_date_and_approver(built):
    for name in RFPS:
        for sec in built[name]["sections"]:
            for p in sec["parts"]:
                if p["type"] == "passage":
                    pv = p["provenance"]
                    assert pv["answer_id"] and pv["proposal_id"] and pv["submitted"] and pv["review_by"]
                    assert pv["approver"] or not pv["approved"]
                    text = provenance_text(pv)
                    assert pv["proposal_id"] in text and pv["submitted"] in text


def test_provenance_text_says_when_an_answer_is_not_approved():
    assert "NOT approved" in provenance_text(provenance(make("A1", approved=False, approver="")))


def test_placeholders_are_filled_from_the_rfp_and_firm_facts(data, ctx):
    text = fill_placeholders("{AGENCY_SHORT} is served by {FIRM_ATTORNEYS} attorneys in {FIRM_OFFICE_COUNT} offices: "
                             "{FIRM_OFFICES}. We serve {AGENCY} and report to the {GOVERNING_BODY}. Ask {AGENCY_SHORT}.", ctx)
    assert text == ("The District is served by 46 attorneys in three offices: Alder Bay, Stonemill and Port Verity. "
                    "We serve Redwood Flats Water District and report to the Board of Directors. Ask the District.")


def test_unknown_placeholder_is_left_for_the_fact_guard(ctx):
    assert "{MYSTERY}" in fill_placeholders("See {MYSTERY}.", ctx)


def test_library_has_the_planned_shape(data):
    assert len(data.answers) >= 120
    assert len({a["proposal_id"] for a in data.answers}) >= 12
    assert sum(1 for a in data.answers if a["review_by"] < AS_OF) >= 10      # some stale
    assert sum(1 for a in data.answers if not a["approved"]) >= 5            # some unapproved
    assert {a["outcome"] for a in data.answers} == {"won", "lost", "pending"}
