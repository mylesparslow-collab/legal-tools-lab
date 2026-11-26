"""Clause tracker: classification, guards, offsets, conflicts, and the measured accuracy."""
import copy
import json

import pytest

from clearance import DATA, clauses
from clearance.cli import evaluate_all

AI_HEADING = "Use of artificial intelligence\n\n"


def classes(text, patterns):
    return sorted({h["class"] for h in clauses.classify_document("t", text, patterns)["hits"]})


def test_plain_prohibition_is_classified(patterns):
    assert classes("Outside counsel shall not use generative AI tools on our matters.", patterns) == ["ai_prohibited"]


def test_negation_guard_nothing_in_this_section_prohibits(patterns):
    res = clauses.classify_document("t", "Nothing in this section prohibits the use of AI tools for legal research.", patterns)
    assert res["hits"] == []
    assert res["silent"] is True
    assert res["guarded"] and res["guarded"][0]["guard_kind"] == "negation"


def test_negation_guard_does_not_prohibit(patterns):
    assert classes("This policy does not prohibit counsel from using AI tools that are prohibited elsewhere.", patterns) == []


def test_negation_guard_is_not_prohibited(patterns):
    assert "ai_prohibited" not in classes("The use of generative AI is not prohibited under these guidelines.", patterns)


def test_negation_guard_not_required_to_obtain_consent(patterns):
    got = classes("Counsel is not required to obtain prior written consent before using AI tools.", patterns)
    assert "consent_required" not in got


def test_scope_guard_clients_own_employees(patterns):
    text = "Company employees are prohibited from pasting contracts into AI chatbots."
    res = clauses.classify_document("t", text, patterns)
    assert res["hits"] == []
    assert res["guarded"][0]["guard_kind"] == "scope"


def test_prohibition_with_consent_exception_is_consent_not_prohibition(patterns):
    text = "The Firm shall not use generative AI on Company matters without the prior written consent of the Company."
    assert classes(text, patterns) == ["consent_required"]


def test_unexplained_exception_goes_to_a_person(patterns):
    text = "Counsel must not use AI tools except in exceptional circumstances."
    assert classes(text, patterns) == ["ambiguous"]


def test_negated_permission_is_not_a_permission(patterns):
    got = classes("The Company does not permit outside counsel to use generative AI.", patterns)
    assert got == ["ai_prohibited"]


def test_prohibition_scoped_to_public_tools_is_approved_tools_class(patterns):
    got = classes("Client files must never be uploaded to a publicly available AI service.", patterns)
    assert got == ["approved_tools_only"]


def test_staff_training_is_not_model_training(patterns):
    got = classes("Attorneys must not use AI tools until they complete the Firm's AI training.", patterns)
    assert "no_training" not in got


def test_model_training_clause(patterns):
    assert classes("Company data may not be used to train any AI model.", patterns) == ["no_training"]


def test_sentence_outside_ai_context_is_ignored(patterns):
    text = "Counsel must obtain prior written approval before retaining any expert.\n\nInvoices are due monthly."
    res = clauses.classify_document("t", text, patterns)
    assert res["hits"] == [] and res["silent"]


def test_business_intelligence_is_not_ai(patterns):
    assert classes("Counsel must not disclose business intelligence reports without prior written consent.", patterns) == []


def test_heading_gives_ai_context_to_following_sentences(patterns):
    body = "A licensed attorney must review every output before it is sent to the Company."
    assert classes(body, patterns) == []
    res = clauses.classify_document("t", AI_HEADING + body, patterns)
    assert [h["class"] for h in res["hits"]] == ["human_review_required"]
    assert res["hits"][0]["context"] == "heading"


def test_heading_context_ends_at_next_heading(patterns):
    text = AI_HEADING + "Counsel must tell us before using these tools.\n\nStaffing\n\nCounsel must tell us before adding timekeepers."
    hits = clauses.classify_document("t", text, patterns)["hits"]
    assert len(hits) == 1 and "these tools" in hits[0]["quote"]


def test_one_sentence_can_carry_two_classes(patterns):
    text = "Our information must not be used to train any AI model, and prompts containing it must be deleted within 14 days."
    assert classes(text, patterns) == ["data_residency_retention", "no_training"]


def test_splitter_keeps_abbreviations_and_numbering_together(patterns):
    text = "3.1 Dr. Vale must approve any AI tool. No. 4 applies to vendors. The Firm may use AI tools."
    sents = clauses.split_sentences(text, patterns)
    got = [text[s["start"]:s["end"]] for s in sents]
    assert got == ["3.1 Dr. Vale must approve any AI tool.", "No. 4 applies to vendors.", "The Firm may use AI tools."]


def test_every_hit_offset_reproduces_the_quote(store, patterns):
    n = 0
    for d in store.all_document_entries():
        text = store.document_text(d["id"])
        for h in store.scan(d["id"], patterns)["hits"]:
            assert text[h["start"]:h["end"]] == h["quote"]
            assert h["document_id"] == d["id"] and h["class"] in patterns.class_ids
            n += 1
    assert n >= 50


def test_silent_documents_are_reported_silent(store, patterns):
    for doc in ("drennick-ocg-2025", "drennick-el-2025", "sablemere-el-2025", "ironvale-el-2026"):
        assert store.scan(doc, patterns)["silent"] is True
    s = store.party_summary("drennick", ["drennick-ocg-2025", "drennick-el-2025"], patterns)
    assert s["status"] == "silent" and s["classes"] == ["silent"]


def test_conflicting_documents_surface_for_analyst_review(store, patterns):
    s = store.party_summary("marrowfinch", ["marrowfinch-ocg-2024", "marrowfinch-el-2025"], patterns)
    assert s["status"] == "needs_analyst_review"
    pairs = [c["pair"] for c in s["conflicts"]]
    assert ["ai_prohibited", "ai_permitted"] in pairs
    conflict = s["conflicts"][pairs.index(["ai_prohibited", "ai_permitted"])]
    assert conflict["documents"] == ["marrowfinch-el-2025", "marrowfinch-ocg-2024"]
    # Both sides stay in the summary. Neither is dropped.
    assert "ai_prohibited" in s["classes"] and "ai_permitted" in s["classes"]


def test_each_document_alone_is_not_a_conflict(store, patterns):
    assert store.party_summary("marrowfinch", ["marrowfinch-ocg-2024"], patterns)["status"] == "clear"
    assert store.party_summary("marrowfinch", ["marrowfinch-el-2025"], patterns)["status"] == "clear"


def test_ambiguous_clause_surfaces_for_analyst_review(store, patterns):
    s = store.party_summary("sablemere", ["sablemere-ocg-2025", "sablemere-el-2025"], patterns)
    assert s["status"] == "needs_analyst_review"
    assert len(s["review_hits"]) == 2 and not s["conflicts"]


def test_no_documents_is_not_on_file_not_silent(store, patterns):
    assert store.party_summary("pallister", [], patterns)["status"] == "not_on_file"


def test_analyst_dismissals_are_applied_and_listed(store, patterns):
    raw = store.scan("tessaly-ocg-2025", patterns)
    assert "approved_tools_only" in {h["class"] for h in raw["hits"]}
    s = store.party_summary("tessaly", ["tessaly-ocg-2025", "tessaly-el-2025"], patterns)
    assert "approved_tools_only" not in s["classes"]
    assert len(s["dismissed"]) == 2 and all(d["reason"] for d in s["dismissed"])


def test_pattern_file_rejects_unknown_suppressor_and_class(patterns):
    raw = copy.deepcopy(patterns.raw)
    raw["patterns"][0]["suppress_if"] = ["no_such_suppressor"]
    with pytest.raises(ValueError):
        clauses.Patterns(raw)
    raw = copy.deepcopy(patterns.raw)
    raw["patterns"][0]["class"] = "made_up"
    with pytest.raises(ValueError):
        clauses.Patterns(raw)


# ------------------------------------------------------------ answer key

def test_answer_key_size_offsets_and_hard_negatives(store):
    key = json.loads((DATA / "answer_key.json").read_text())
    labels = key["labels"]
    assert len(labels) >= 60
    assert sum(1 for k in labels if k["label"] == "none") >= 15
    for k in labels:
        assert store.document_text(k["document_id"])[k["start"]:k["end"]] == k["quote"], k["id"]
    assert len({k["id"] for k in labels}) == len(labels)


def test_evaluation_counts_tp_fp_fn():
    key = {"labels": [
        {"id": "a", "document_id": "d", "start": 0, "end": 10, "label": "ai_prohibited", "quote": ""},
        {"id": "b", "document_id": "d", "start": 20, "end": 30, "label": "no_training", "quote": ""},
        {"id": "c", "document_id": "d", "start": 40, "end": 50, "label": "none", "quote": ""},
    ]}
    hit = lambda s, e, c: {"document_id": "d", "start": s, "end": e, "class": c, "quote": "", "pattern_ids": []}
    res = {"d": {"hits": [hit(0, 10, "ai_prohibited"), hit(20, 30, "consent_required"), hit(40, 50, "ai_permitted")]}}
    ev = clauses.evaluate(key, res)
    assert (ev["overall"]["tp"], ev["overall"]["fp"], ev["overall"]["fn"]) == (1, 2, 1)
    assert ev["overall"]["precision"] == 0.333 and ev["overall"]["recall"] == 0.5
    assert ev["hard_negatives_wrongly_classified"] == 1
    assert ev["false_negatives"][0]["key_id"] == "b"


def test_measured_precision_and_recall_on_the_sample_documents(store, patterns):
    ev = evaluate_all(store, patterns)
    o = ev["overall"]
    assert o["tp"] + o["fn"] == ev["positive_spans"]
    assert o["precision"] >= 0.90 and o["recall"] >= 0.85
    # The classifier is not perfect and the report must say so.
    assert len(ev["false_negatives"]) == o["fn"] and len(ev["false_positives"]) == o["fp"]
    assert set(ev["per_split"]) == {"dev", "heldout"}


def test_committed_evaluation_matches_a_fresh_run(store, patterns):
    committed = json.loads((DATA.parent / "output" / "classifier_evaluation.json").read_text())
    assert committed == json.loads(json.dumps(evaluate_all(store, patterns)))
