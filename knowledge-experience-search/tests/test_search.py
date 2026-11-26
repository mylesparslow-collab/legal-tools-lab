import copy
import dataclasses

import pytest

import helpers
from kx import config as cfg, search
from kx.schema import Document

AS_OF = helpers.AS_OF


@pytest.fixture(scope="module")
def world():
    conn, _, _ = helpers.build()
    return conn


def ids(result):
    return [r["doc_id"] for r in result["results"]]


def test_topical_document_outranks_a_passing_mention(world):
    result = search.search(world, "erin", "earn-out", as_of=AS_OF, limit=20)
    order = ids(result)
    # d_pub_1 is about earn-outs; d_pub_2 mentions the term once in passing.
    assert order.index("d_pub_1") < order.index("d_pub_2")


def all_mode():
    config = copy.deepcopy(cfg.load_config())
    config["match_mode"] = "all"
    return config


def test_full_matches_come_first_and_partial_matches_are_marked(world):
    result = search.search(world, "erin", "earn-out closing", as_of=AS_OF)
    assert ids(result)[0] == "d_pub_2" and result["relaxed"] is False
    shares = [r["share_of_query_matched"] for r in result["results"]]
    assert shares[0] == 1.0 and all(0.5 <= s < 1.0 for s in shares[1:])


def test_a_document_matching_only_the_common_word_of_a_query_is_left_out(world):
    # "memo" is in several documents, "venue" in one. Half the query by weight is the floor.
    result = search.search(world, "erin", "venue memo", as_of=AS_OF, limit=50)
    assert "d_pub_3" in ids(result) and "d_pub_1" not in ids(result)


def test_when_nothing_matches_the_whole_query_the_response_says_so(world):
    result = search.search(world, "erin", "severance venue", as_of=AS_OF)
    assert result["relaxed"] is True and result["total"] >= 1
    assert "match most of the query" in result["message"]


def test_all_mode_requires_every_term(world):
    result = search.search(world, "erin", "earn-out closing", config=all_mode(), as_of=AS_OF)
    assert ids(result) == ["d_pub_2"] and result["relaxed"] is False


def test_all_mode_falls_back_to_any_term_and_says_so(world):
    # Both words occur, never in the same document.
    result = search.search(world, "erin", "severance venue", config=all_mode(), as_of=AS_OF)
    assert result["relaxed"] is True and {"d_fam_v2", "d_pub_3"} <= set(ids(result))
    assert "some of them" in result["message"]


def test_a_word_that_occurs_nowhere_is_dropped_and_named(world):
    result = search.search(world, "erin", "severance platypus", as_of=AS_OF)
    assert "d_fam_v2" in ids(result) and result["relaxed"] is False
    assert result["expansion"]["not_found"] == ["platypus"]
    assert "No document you can open contains: platypus" in result["message"]


def test_phrase_must_be_adjacent(world):
    assert "d_pub_3" in ids(search.search(world, "erin", '"forum selection clause"', as_of=AS_OF))
    assert search.search(world, "erin", '"selection forum"', as_of=AS_OF)["total"] == 0
    # Both words occur in d_pub_3, so the unquoted form matches.
    assert "d_pub_3" in ids(search.search(world, "erin", "selection forum", as_of=AS_OF))


def test_phrase_is_never_relaxed_away(world):
    result = search.search(world, "erin", '"no such phrase" earn-out', as_of=AS_OF)
    assert result["total"] == 0


def test_field_filters_restrict_results(world):
    result = search.search(world, "erin", "earn-out type:checklist", as_of=AS_OF)
    assert ids(result) == ["d_pub_2"]
    result = search.search(world, "erin", "", {"filed": "yes"}, as_of=AS_OF)
    assert ids(result) == ["d_pub_3"]
    result = search.search(world, "erin", "", {"author": "Okonmere", "before": "2024-01-01"}, as_of=AS_OF)
    assert ids(result) == ["d_pub_3"]
    result = search.search(world, "erin", "", {"jurisdiction": "tavish county"}, as_of=AS_OF)
    assert ids(result) == ["d_pub_3"]


def test_metadata_terms_are_searchable(world):
    # "motion" and "tavish" are document type and court, not words in the title alone.
    result = search.search(world, "erin", "tavish motion", as_of=AS_OF, explain=True)
    assert ids(result) == ["d_pub_3"]
    matched = {t["term"]: t["matched_in"] for t in result["results"][0]["explain"]["text"]["terms"]}
    assert "metadata" in matched["tavish"]


def test_facets_count_exactly_the_returned_set(world):
    result = search.search(world, "erin", "earn-out", as_of=AS_OF, limit=50)
    for field, values in result["facets"].items():
        assert sum(v["count"] for v in values) == result["total"], field
    by_type = {v["value"]: v["count"] for v in result["facets"]["doc_type"]}
    assert by_type == {"memo": 2, "checklist": 1}


def test_explain_adds_up_to_the_score(world):
    result = search.search(world, "erin", "earn-out provisions memo", as_of=AS_OF, explain=True)
    assert result["results"]
    for r in result["results"]:
        e = r["explain"]
        total = e["text"]["contribution"] + sum(s["contribution"] for s in e["signals"])
        assert abs(total - r["score"]) < 2e-3
        assert abs(sum(t["bm25"] for t in e["text"]["terms"]) - e["text"]["bm25"]) < 2e-3
        assert {s["signal"] for s in e["signals"]} == {
            "model_form", "is_final", "was_filed", "reuse", "recency"}


def _twins(**changes):
    """Two documents with identical text in different matters; one gets ``changes``."""
    text = helpers.body("This memo addresses the capybara covenant in detail.")
    a = Document("twin_a", "M_PUB", "Memo: capybara covenant", text, "memo", "alice",
                 "2024-01-01", is_final=True, modified="2026-01-01T00:00:00")
    b = dataclasses.replace(a, doc_id="twin_b", **changes)
    source = helpers.adapter()
    source.documents += [a, b]
    conn, _, _ = helpers.build(source, near_dup_threshold=2.0)  # keep both in the list
    return search.search(conn, "erin", "capybara covenant", as_of=AS_OF, explain=True)


@pytest.mark.parametrize("changes", [
    {"model_form": True}, {"was_filed": True}, {"reuse_count": 9}, {"doc_date": "2026-06-01"}])
def test_each_quality_signal_lifts_an_otherwise_identical_document(changes):
    result = _twins(**changes)
    assert ids(result) == ["twin_b", "twin_a"]
    assert result["results"][0]["score"] > result["results"][1]["score"]


def test_final_outranks_non_final_with_identical_text():
    result = _twins(is_final=False)
    assert ids(result) == ["twin_a", "twin_b"]


def test_blend_weights_come_from_config():
    source = helpers.adapter()
    conn, _, _ = helpers.build(source)
    cfg = search.load_config()
    base = ids(search.search(conn, "alice", "earn-out provisions", config=cfg, as_of=AS_OF, limit=20))
    cfg["blend"] = dict(cfg["blend"], model_form=0.0, reuse=0.0, text=1.0, recency=0.0,
                        is_final=0.0, was_filed=0.0)
    text_only = search.search(conn, "alice", "earn-out provisions", config=cfg, as_of=AS_OF,
                              limit=20, explain=True)
    assert all(s["contribution"] == 0 for r in text_only["results"] for s in r["explain"]["signals"])
    assert set(ids(text_only)) == set(base)
    assert text_only["results"][0]["score"] == pytest.approx(1.0)


def test_drafts_collapse_into_the_final_version(world):
    result = search.search(world, "erin", "severance agreement", as_of=AS_OF)
    assert ids(result) == ["d_fam_v2"] and result["total"] == 1
    assert [v["doc_id"] for v in result["results"][0]["other_versions"]] == ["d_fam_v1"]
    assert result["results"][0]["is_final"] is True


def test_draft_is_shown_as_a_draft_when_only_the_draft_matches(world):
    result = search.search(world, "erin", '"left open"', as_of=AS_OF)
    assert ids(result) == ["d_fam_v1"]
    assert result["results"][0]["is_final"] is False and result["results"][0]["other_versions"] == []


def test_near_duplicates_collapse_into_the_higher_ranked_copy(world):
    # alice can see both d_pub_1 and its adapted copy d_wall_2.
    result = search.search(world, "alice", "earn-out milestone payment", as_of=AS_OF, limit=20)
    shown = ids(result)
    assert ("d_pub_1" in shown) != ("d_wall_2" in shown)
    keeper = next(r for r in result["results"] if r["doc_id"] in ("d_pub_1", "d_wall_2"))
    assert len(keeper["near_duplicates"]) == 1
    assert helpers.all_doc_ids(result) >= {"d_pub_1", "d_wall_2"}


def test_pagination_is_stable_and_complete(world):
    everything = ids(search.search(world, "alice", "earn-out", as_of=AS_OF, limit=50))
    paged = []
    for offset in range(0, len(everything), 2):
        page = search.search(world, "alice", "earn-out", as_of=AS_OF, limit=2, offset=offset)
        assert page["total"] == len(everything)
        paged += ids(page)
    assert paged == everything and len(set(paged)) == len(paged)


def test_same_query_gives_the_same_answer_twice(world):
    a = search.search(world, "alice", "earn-out provisions", as_of=AS_OF, explain=True)
    b = search.search(world, "alice", "earn-out provisions", as_of=AS_OF, explain=True)
    assert a == b


def test_filter_only_query_ranks_by_quality_signals(world):
    result = search.search(world, "alice", "", {"type": "memo"}, as_of=AS_OF)
    assert result["results"][0]["doc_id"] == "d_wall_1"  # the model form with reuse
    assert all(r["doc_type"] == "memo" for r in result["results"])


def test_empty_query_asks_for_input_and_returns_nothing(world):
    result = search.search(world, "alice", "   ", as_of=AS_OF)
    assert result["total"] == 0 and result["message"]


def test_snippet_comes_from_the_document_and_marks_query_terms(world):
    r = search.search(world, "erin", "venue", as_of=AS_OF)["results"][0]
    text = r["snippet"]["text"]
    assert text.strip("… ") in helpers.documents()[2].body
    marked = [text[s:e].lower() for s, e in r["snippet"]["highlights"]]
    assert marked and set(marked) == {"venue"}


class _Reverse:
    def __init__(self):
        self.seen = []

    def rerank(self, query, docs):
        self.seen.append([d["doc_id"] for d in docs])
        return [float(i) for i in range(len(docs))]  # reverse the incoming order


def test_reranker_is_off_by_default_and_reorders_when_supplied(world):
    plain = search.search(world, "alice", "earn-out", as_of=AS_OF, limit=20)
    assert plain["reranked"] is False
    rr = _Reverse()
    reranked = search.search(world, "alice", "earn-out", as_of=AS_OF, limit=20, reranker=rr)
    assert reranked["reranked"] is True
    assert ids(reranked) == list(reversed(ids(plain)))
    assert rr.seen == [ids(plain)]


def test_suggest_completes_from_titles(world):
    assert "provision" in search.suggest(world, "erin", "earn-out prov")
    assert search.suggest(world, "erin", "e") == []        # too short
    assert search.suggest(world, "erin", "earn ") == []    # nothing being typed
