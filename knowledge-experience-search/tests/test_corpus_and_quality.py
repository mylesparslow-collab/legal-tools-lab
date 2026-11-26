import csv
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from kx import config as cfg
from kx import evaluate

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def report(full, key, config):
    return evaluate.evaluate(full, key, config)


@pytest.fixture(scope="module")
def keyword_only(full, key, config):
    return evaluate.evaluate(full, key, config, expand=False)


def test_corpus_has_the_stated_shape(data_dir, manifest):
    counts = manifest["counts"]
    assert counts["documents"] == 1500 and counts["matters"] == 250 and counts["people"] == 120
    assert counts["practices"] == 10 and counts["offices"] == 8 and counts["walls"] == 3
    assert counts["restricted_matters"] >= 10 and counts["planted_near_duplicates"] == 30
    assert counts["draft_documents"] >= 150
    with open(data_dir / "matters.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len({r["PracticeArea"] for r in rows}) == 10
    assert Counter(r["SecurityCode"] for r in rows)["R"] == counts["restricted_matters"]
    with open(data_dir / "people.csv", encoding="utf-8", newline="") as fh:
        people = list(csv.DictReader(fh))
    assert len({p["Office"] for p in people}) == 8
    assert Counter(p["Status"] for p in people)["D"] == 6


def test_generator_is_deterministic(tmp_path, data_dir):
    from synth.generate import generate
    generate(tmp_path)
    for name in ("documents.jsonl", "matters.csv", "ANSWER_KEY.json", "wall_members.csv"):
        assert (tmp_path / name).read_bytes() == (data_dir / name).read_bytes(), name


def test_document_text_is_varied(canonical):
    bodies = [d.body for d in canonical["documents"]]
    assert len(set(bodies)) > 0.97 * len(bodies)
    vocabulary = {w for b in bodies for w in b.lower().split()}
    assert len(vocabulary) > 800
    assert not any("lorem" in b.lower() for b in bodies)


def test_answer_key_is_large_enough_and_well_formed(key, canonical):
    doc_ids = {d.doc_id for d in canonical["documents"]}
    assert len(key["queries"]) >= 30
    assert len({q["category"] for q in key["queries"]}) == 5
    for q in key["queries"]:
        assert q["relevant"] and set(q["relevant"]) <= doc_ids
        if q["category"] != "different vocabulary":
            assert 5 <= len(q["relevant"]) <= 10
    assert len(key["wall_tests"]) == 4 and len(key["restricted_tests"]) >= 10
    for t in key["wall_tests"] + key["restricted_tests"]:
        assert t["denied_users"] and set(t["must_never_appear"]) <= doc_ids


def test_retrieval_quality_on_queries_in_the_corpus_vocabulary(report):
    same = report["queries_using_the_corpus_vocabulary"]
    assert same["queries"] >= 30
    assert same["precision_at_5"] >= 0.85
    assert same["recall_at_10"] >= 0.90


def test_best_example_queries_put_the_model_form_first_most_of_the_time(report):
    best = report["by_category"]["best example"]
    assert best["best_example_queries"] >= 5
    assert best["best_example_ranked_first"] >= best["best_example_queries"] - 1


def test_keyword_search_alone_is_weak_on_different_vocabulary_and_the_report_shows_it(keyword_only):
    """The known limit of keyword search, reported separately instead of averaged away."""
    other = keyword_only["by_category"]["different vocabulary"]
    assert other["queries"] >= 5 and other["recall_at_10"] < 0.2


def test_bridging_helps_different_vocabulary_without_hurting_the_rest(report, keyword_only):
    on, off = report["by_category"], keyword_only["by_category"]
    assert on["different vocabulary"]["recall_at_10"] > off["different vocabulary"]["recall_at_10"]
    assert on["different vocabulary"]["precision_at_5"] > off["different vocabulary"]["precision_at_5"]
    same_on = report["queries_using_the_corpus_vocabulary"]
    same_off = keyword_only["queries_using_the_corpus_vocabulary"]
    assert same_on["precision_at_5"] >= same_off["precision_at_5"] - 0.02
    assert same_on["recall_at_10"] >= same_off["recall_at_10"] - 0.02
    # Still far from solved, and the report must keep saying so.
    assert on["different vocabulary"]["recall_at_10"] < report["queries_using_the_corpus_vocabulary"]["recall_at_10"]


def test_evaluation_permission_checks_find_no_leaks(report):
    assert report["permission_checks"]["checks_run"] >= 100
    assert report["permission_checks"]["leaks"] == []


def test_committed_quality_output_and_readme_match_a_fresh_run(report, keyword_only):
    for name, fresh in (("retrieval_quality.json", report),
                        ("retrieval_quality_keyword_only.json", keyword_only)):
        committed = json.loads((ROOT / "output" / name).read_text(encoding="utf-8"))
        assert committed["all_queries"] == fresh["all_queries"], name
        assert committed["by_category"] == fresh["by_category"], name
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    same, everything = report["queries_using_the_corpus_vocabulary"], report["all_queries"]
    for number in (same["precision_at_5"], same["recall_at_10"],
                   everything["precision_at_5"], everything["recall_at_10"],
                   report["by_category"]["different vocabulary"]["precision_at_5"],
                   report["by_category"]["different vocabulary"]["recall_at_10"],
                   keyword_only["by_category"]["different vocabulary"]["recall_at_10"]):
        assert re.search(rf"\b{re.escape(f'{number:.3f}'.rstrip('0'))}", readme), number


def test_ranking_config_weights_are_documented_and_sane():
    config = cfg.load_config()
    blend = config["blend"]
    assert set(blend) == {"text", "model_form", "is_final", "was_filed", "reuse", "recency"}
    assert abs(sum(blend.values()) - 1.0) < 1e-9
    assert blend["text"] > max(v for k, v in blend.items() if k != "text")
    assert config["acl_max_age_hours"] is None  # demo data is static; see README
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "config/ranking.json" in readme
