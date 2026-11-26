"""Whole-corpus leak tests.

The main test is noninterference: for a user behind a wall, every output of
the tool must be byte-for-byte what it would be if the documents and matters
that user cannot see had never been indexed. That one property covers
results, snippets, counts, facets, scores, explain output, suggestions,
collapse lists and experience-finder evidence at once.
"""
import json

import pytest

import helpers
from kx import acl, experience, search

WHO_QUERIES = ["asset purchase", "stock purchase", "contract dispute", "syndicated loan",
               "loan workout", "earn-out provisions", "preliminary injunction",
               "practice:\"Commercial litigation\"", "merger", "financial covenants"]
PREFIXES = ["ha", "ci", "ta", "or", "ea", "in", "fo", "pr", "ar", "co", "bo", "gu", "se", "cl"]


def dump(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _queries(key):
    out = [q["query"] for q in key["queries"]]
    for t in key["wall_tests"] + key["restricted_tests"]:
        out += t["queries"]
    out += ["type:memo", "model:yes", "filed:yes type:motion", "agreement", "memo"]
    return sorted(set(out))


def _walled_users(manifest):
    return [manifest["walls"][w]["excluded"][0] for w in ("W1", "W2", "W3")]


def test_walled_users_really_are_missing_documents(full, manifest):
    total = full.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    for user in _walled_users(manifest):
        assert 0 < len(acl.visible_doc_ids(full, user)) < total


@pytest.mark.parametrize("wall", ["W1", "W2", "W3"])
def test_search_output_is_identical_to_a_corpus_without_the_hidden_documents(
        wall, full, key, manifest, world_without_hidden, config):
    user = manifest["walls"][wall]["excluded"][0]
    clean = world_without_hidden(user)
    compared = 0
    for q in _queries(key):
        a = search.search(full, user, q, config=config, as_of=key["as_of"], limit=25, explain=True)
        b = search.search(clean, user, q, config=config, as_of=key["as_of"], limit=25, explain=True)
        assert dump(a) == dump(b), (user, q)
        compared += 1
    assert compared >= 60


@pytest.mark.parametrize("wall", ["W1", "W2", "W3"])
def test_suggestions_are_identical_to_a_corpus_without_the_hidden_documents(
        wall, full, manifest, world_without_hidden):
    user = manifest["walls"][wall]["excluded"][0]
    clean = world_without_hidden(user)
    for prefix in PREFIXES:
        assert search.suggest(full, user, prefix, limit=20) == \
               search.suggest(clean, user, prefix, limit=20), (user, prefix)


@pytest.mark.parametrize("wall", ["W1", "W2", "W3"])
def test_experience_output_is_identical_to_a_corpus_without_the_hidden_matters(
        wall, full, key, manifest, world_without_hidden, config):
    user = manifest["walls"][wall]["excluded"][0]
    clean = world_without_hidden(user)
    codenames = [c.lower() for w in manifest["walls"].values() for c in w["codenames"]]
    for q in WHO_QUERIES + codenames:
        a = experience.who(full, user, q, config=config, as_of=key["as_of"], limit=50)
        b = experience.who(clean, user, q, config=config, as_of=key["as_of"], limit=50)
        assert dump(a) == dump(b), (user, q)


def test_answer_key_documents_never_appear_for_denied_users(full, key, config):
    checks = 0
    for t in key["wall_tests"] + key["restricted_tests"]:
        hidden = set(t["must_never_appear"])
        assert hidden
        for user in t["denied_users"]:
            for q in t["queries"] + ["type:memo", "agreement"]:
                result = search.search(full, user, q, config=config, as_of=key["as_of"], limit=2000)
                assert not (helpers.all_doc_ids(result) & hidden), (t["id"], user, q)
                checks += 1
    assert checks >= 200


def test_control_users_do_see_the_walled_documents(full, key, config):
    """The wall tests would pass trivially if the documents could not be found at all."""
    for t in key["wall_tests"] + key["restricted_tests"]:
        result = search.search(full, t["control_user"], t["canary_term"], config=config,
                               as_of=key["as_of"], limit=2000)
        seen = helpers.all_doc_ids(result) & set(t["must_never_appear"])
        assert len(seen) >= 3, t["id"]


def test_canary_terms_are_never_suggested_to_denied_users(full, key):
    for t in key["wall_tests"] + key["restricted_tests"]:
        canary = t["canary_term"]
        assert canary in search.suggest(full, t["control_user"], canary[:4], limit=50)
        for user in t["denied_users"]:
            for n in (2, 3, 4, len(canary)):
                assert canary not in search.suggest(full, user, canary[:n], limit=50), (user, canary)


def test_canary_terms_find_nothing_and_look_like_nonexistent_words(full, key, config):
    for t in key["wall_tests"]:
        for user in t["denied_users"]:
            walled = search.search(full, user, t["canary_term"], config=config, as_of=key["as_of"])
            absent = search.search(full, user, "qqxyzzy", config=config, as_of=key["as_of"])
            assert walled["total"] == 0
            text = lambda r, word: json.dumps(r, sort_keys=True).replace(word, "WORD")
            assert text(walled, t["canary_term"]) == text(absent, "qqxyzzy")


def test_experience_finder_lists_no_walled_matter_for_denied_users(full, key, manifest, config):
    matter_type = {r[0]: r[1] for r in full.execute("SELECT matter_id, matter_type FROM matters")}
    for t in key["wall_tests"]:
        mid = t["matter_id"]
        q = matter_type[mid]
        control = experience.who(full, t["control_user"], q, config=config, as_of=key["as_of"], limit=500)
        listed = {e["matter_id"] for p in control["people"] for e in p["evidence"]}
        assert mid in listed, "control user should see the matter as evidence"
        for user in t["denied_users"]:
            result = experience.who(full, user, q, config=config, as_of=key["as_of"], limit=500)
            listed = {e["matter_id"] for p in result["people"] for e in p["evidence"]}
            assert mid not in listed, (user, mid)
            assert mid not in dump(result)


def test_lead_of_a_walled_matter_gets_less_credit_from_a_denied_asker(full, key, config):
    matter_type = {r[0]: r[1] for r in full.execute("SELECT matter_id, matter_type FROM matters")}
    t = key["wall_tests"][0]
    lead, q = t["control_user"], matter_type[t["matter_id"]]

    def row(asker):
        result = experience.who(full, asker, q, config=config, as_of=key["as_of"], limit=500)
        return next((p for p in result["people"] if p["person_id"] == lead), None)

    seen_by_control = row(lead)
    seen_by_denied = row(t["denied_users"][0])
    assert seen_by_control is not None
    if seen_by_denied is None:
        return  # the walled matter was the lead's only matching work
    assert seen_by_denied["matters"] == seen_by_control["matters"] - 1
    assert seen_by_denied["hours"] < seen_by_control["hours"]
    assert seen_by_denied["score"] < seen_by_control["score"]
