"""The held-out scorer, on a made-up batch. It never reads heldout/."""
import json

import helpers
from kx import heldout


def test_scoring_is_strict_lenient_and_hit_at_ten_with_unlisted_results_unjudged(tmp_path):
    conn, _, _ = helpers.build()
    key = {"queries": [
        {"id": "Q1", "category": "topic and document type", "query": "earn-out", "as_user": "erin",
         "relevant": ["d_pub_1"], "same_topic_not_listed": ["d_pub_2"]},
        {"id": "Q2", "category": "different vocabulary", "query": "platypus", "as_user": "erin",
         "relevant": ["d_pub_3"]}],
        "experience_queries": [
            {"id": "W1", "query": "contract dispute", "as_user": "erin",
             "strongest": [{"user_id": "carol"}], "should_rank_near_top": [{"user_id": "nobody"}]}]}
    (tmp_path / "ANSWER_KEY.json").write_text(json.dumps(key), encoding="utf-8")
    report = heldout.run(conn, tmp_path, {}, helpers.AS_OF)
    q1, q2 = report["per_query"]
    assert q1["strict_precision_at_5"] == 0.2 and q1["lenient_precision_at_5"] == 0.4
    assert q1["listed_document_in_top_10"] is True and q1["first_listed_rank"] in (1, 2)
    assert q2["strict_precision_at_5"] == 0.0 and q2["listed_document_in_top_10"] is False
    docs = report["document_queries"]
    assert docs["all"]["queries"] == 2 and docs["all"]["share_with_a_listed_document_in_top_10"] == 0.5
    assert docs["different words"]["queries"] == 1 and docs["documents' own words"]["queries"] == 1
    assert "recall" not in json.dumps(docs)
    who = report["who_has_done_this"]
    assert who["queries_with_every_strongest_person_in_top_3"] == 1
    assert who["expected_people_in_top_5"] == 1 and who["expected_people"] == 2
    assert set(report["tool_state"]) == {"ranking_config_sha256", "thesaurus_sha256"}


def test_equivalent_copies_count_once(tmp_path):
    conn, _, _ = helpers.build()
    key = {"queries": [{"id": "Q1", "category": "exact phrase", "query": "severance agreement",
                        "as_user": "erin", "relevant": ["d_fam_v1"]}]}
    (tmp_path / "ANSWER_KEY.json").write_text(json.dumps(key), encoding="utf-8")
    report = heldout.run(conn, tmp_path, {"d_fam_v1": "FAM1", "d_fam_v2": "FAM1"}, helpers.AS_OF)
    assert report["per_query"][0]["listed_document_in_top_10"] is True
