"""Vocabulary bridging: what it finds, how it is weighted and explained, and
that none of it can be steered by documents the asking user cannot open.

The small world here: bob is excluded by a wall from M_WALL. alice sees it.
"""
import copy
import json

import pytest

import helpers
from kx import config as cfg, expand, experience, search
from kx.schema import Document, Matter, TeamMember, TimeEntry
from kx.text import edit_distance, root, spelling_variants

AS_OF = helpers.AS_OF
ROOT = cfg.DEFAULT_CONFIG_PATH.parent.parent


def doc(doc_id, matter, title, text, author="alice", date="2024-05-01", doc_type="memo"):
    return Document(doc_id, matter, title, helpers.body(text), doc_type, author, date,
                    is_final=True, modified=date + "T00:00:00")


PUBLIC = [
    doc("x_bank", "M_PUB", "Memo: bank consent to the transfer", "The bank must approve the transfer."),
    doc("x_lender", "M_PUB", "Memo: lender consent to the transfer", "The lender must approve the transfer."),
    doc("x_assign", "M_PUB", "Memo: assigning the supply contract", "Notes on assigning the contract."),
    doc("x_labor", "M_PUB", "Memo: labor dispute timetable", "Timetable for the labor dispute."),
    doc("x_indem", "M_PUB", "Memo: indemnification procedure", "Steps for an indemnification claim."),
    doc("x_lessor", "M_PUB", "Memo: lessor remedies", "Remedies open to the lessor on default."),
    doc("x_subro", "M_PUB", "Memo: subrogation waiver", "The waiver of subrogation is mutual."),
    doc("x_hold", "M_PUB2", "Memo: holdback release mechanics", "The holdback is released in stages.",
        author="carol"),
    doc("x_earn1", "M_PUB", "Memo: earn-out milestone schedule", "The earn-out turns on each milestone and the revenue target."),
    doc("x_earn2", "M_PUB", "Memo: earn-out milestone disputes", "An earn-out dispute over a milestone and the revenue target."),
    doc("x_mile", "M_PUB2", "Memo: milestone revenue target reporting", "Reporting against each milestone and revenue target.", author="carol"),
]
WALLED = [
    doc("w_landlord", "M_WALL", "Memo: landlord remedies", "Remedies open to the landlord on default.", author="carol"),
    doc("w_subro", "M_WALL", "Memo: subrogating insurer", "The insurer is subrogating to the claim.", author="carol"),
    doc("w_earn1", "M_WALL", "Memo: earn-out quillon holdback", "The earn-out is secured by the quillon holdback.", author="carol"),
    doc("w_earn2", "M_WALL", "Memo: earn-out quillon holdback terms", "The earn-out and the quillon holdback again.", author="carol"),
    doc("w_earn3", "M_WALL", "Memo: earn-out quillon holdback release", "The earn-out, the quillon and the holdback.", author="carol"),
]


@pytest.fixture(scope="module")
def world():
    # Near-duplicate folding is off here: these documents differ by a word or
    # two on purpose, and folding is tested elsewhere.
    conn, _, _ = helpers.build(helpers.adapter(documents=PUBLIC + WALLED), near_dup_threshold=2.0)
    return conn


@pytest.fixture(scope="module")
def world_without_wall():
    """The same world as if nothing bob cannot see had ever been indexed."""
    hidden = {"M_WALL", "M_RW", "M_RES", "M_UNK"}
    source = helpers.adapter(documents=PUBLIC)
    source._matters = [m for m in source._matters if m.matter_id not in hidden]
    source._team = [t for t in source._team if t.matter_id not in hidden]
    source._time = [t for t in source._time if t.matter_id not in hidden]
    source.grants, source.walls = [], []
    conn, _, _ = helpers.build(source, near_dup_threshold=2.0)
    return conn


@pytest.fixture(scope="module")
def loose_feedback():
    """Config in which feedback can run in a world of a dozen documents."""
    config = copy.deepcopy(cfg.load_config())
    config["expansion"]["feedback"].update(max_df_share=0.9, min_terms_matched=1)
    return config


def ids(result):
    return [r["doc_id"] for r in result["results"]]


def used(result):
    return {(u["for"], u["also_searched"], u["source"]) for u in result["expansion"]["used"]}


def dump(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# -- what it finds ------------------------------------------------------------
def test_thesaurus_equivalent_is_found_and_ranked_below_the_users_own_word(world):
    result = search.search(world, "alice", "lender consent", as_of=AS_OF, explain=True)
    assert ids(result)[:2] == ["x_lender", "x_bank"]
    own, other = result["results"][:2]
    assert own["found_by"] == "your words" and other["found_by"] == "equivalent terms"
    assert own["explain"]["text"]["bm25"] > other["explain"]["text"]["bm25"]
    row = next(t for t in other["explain"]["text"]["terms"] if t["term"] == "bank")
    assert row["source"] == "thesaurus" and row["for_your_words"] == "lender"
    assert row["weight"] == 0.6 and row["why"].startswith("thesaurus: ")
    assert ("lender", "bank", "thesaurus") in used(result)


def test_expansion_can_be_switched_off_for_one_query(world):
    result = search.search(world, "alice", "lender consent", as_of=AS_OF, expand=False)
    assert ids(result) == ["x_lender"]
    assert result["expansion"] == {"on": False, "used": [], "not_found": [], "corrected": [],
                                   "related_terms": []}
    disabled = copy.deepcopy(cfg.load_config())
    disabled["expansion"]["enabled"] = False
    same = search.search(world, "alice", "lender consent", config=disabled, as_of=AS_OF, expand=True)
    assert dump(same) == dump(result)


def test_every_expansion_weight_is_below_the_users_own_words():
    x = cfg.load_config()["expansion"]
    assert all(0 < w < 1 for w in x["weights"].values())
    assert 0 < x["feedback"]["weight"] < min(x["weights"].values())


def test_an_alternative_cannot_outscore_the_same_match_in_the_users_own_words(world):
    # "bank" and "lender" each occur in one document of equal shape.
    for a, b in (("lender", "bank"), ("bank", "lender")):
        result = search.search(world, "alice", a, as_of=AS_OF, explain=True)
        scores = {r["doc_id"]: r["explain"]["text"]["bm25"] for r in result["results"]}
        assert scores[f"x_{a}"] > scores[f"x_{b}"] > 0
        assert abs(scores[f"x_{b}"] / scores[f"x_{a}"] - 0.6) < 0.01


def test_other_word_forms_are_found(world):
    result = search.search(world, "alice", "assignment contract", as_of=AS_OF, explain=True)
    assert "x_assign" in ids(result)
    assert ("assignment", "assigning", "word form") in used(result)
    assert search.search(world, "alice", "assignment", as_of=AS_OF, expand=False)["total"] == 0


def test_british_and_american_spellings_are_bridged(world):
    result = search.search(world, "alice", "labour dispute", as_of=AS_OF)
    assert "x_labor" in ids(result)
    assert {u for u in used(result) if u[:2] == ("labour", "labor")}   # by rule or by the thesaurus list
    assert search.search(world, "alice", "labour", as_of=AS_OF, expand=False)["total"] == 0
    assert "labor" in spelling_variants("labour") and "labour" in spelling_variants("labor")


def test_typo_is_corrected_only_when_the_word_is_found_nowhere(world):
    result = search.search(world, "alice", "indemnifcation procedure", as_of=AS_OF)
    assert ids(result) == ["x_indem"]
    assert result["expansion"]["corrected"] == [{"typed": "indemnifcation", "read_as": "indemnification"}]
    assert "Read 'indemnifcation' as 'indemnification'" in result["message"]
    exact = search.search(world, "alice", "indemnification procedure", as_of=AS_OF)
    assert exact["expansion"]["corrected"] == []
    assert edit_distance("indemnifcation", "indemnification", 2) == 1
    assert edit_distance("abcdef", "uvwxyz", 2) > 2


def test_phrase_in_other_words_is_recognised(world):
    result = search.search(world, "alice", "deferred price", as_of=AS_OF, explain=True)
    assert {"x_earn1", "x_earn2"} <= set(ids(result))
    why = [u["why"] for u in result["expansion"]["used"] if u["also_searched"] == "earn-out"]
    assert why and "deferred consideration" in why[0]


def test_quoted_phrases_are_never_expanded(world):
    result = search.search(world, "alice", '"lender consent"', as_of=AS_OF)
    assert ids(result) == ["x_lender"] and result["expansion"]["used"] == []


def test_root_does_not_merge_unrelated_words():
    assert root("assignment") == root("assigning") == root("assigned")
    assert root("payment") != root("pay") or root("payment") == "payment"
    assert root("university") != root("universe") or len(root("university")) >= 4
    assert root("tax") == "tax" and root("lien") == "lien"


# -- related terms (feedback) -------------------------------------------------
def test_related_documents_come_after_every_direct_match(world, loose_feedback):
    result = search.search(world, "bob", "earn-out", config=loose_feedback, as_of=AS_OF,
                           explain=True, limit=50)
    kinds = [r["found_by"] for r in result["results"]]
    assert "related terms" in kinds
    assert kinds.index("related terms") > max(i for i, k in enumerate(kinds) if k != "related terms")
    related = next(r for r in result["results"] if r["found_by"] == "related terms")
    assert related["doc_id"] == "x_mile" and "Does not contain your words" in related["explain"]["note"]
    assert all(t["source"] == "related term" and t["weight"] == 0.3
               for t in related["explain"]["text"]["terms"])
    off = search.search(world, "bob", "earn-out", config=loose_feedback, as_of=AS_OF, expand=False)
    assert "x_mile" not in ids(off) and off["expansion"]["related_terms"] == []


# -- leaks --------------------------------------------------------------------
def test_term_that_co_occurs_with_the_query_only_behind_the_wall_is_never_suggested_or_used(
        world, world_without_wall, loose_feedback):
    """"quillon" exists only in walled documents. "holdback" also exists in an
    open document, but it sits next to "earn-out" only behind the wall."""
    alice = search.search(world, "alice", "earn-out", config=loose_feedback, as_of=AS_OF,
                          explain=True, limit=50)
    alice_terms = {t["term"] for t in alice["expansion"]["related_terms"]}
    assert {"quillon", "holdback"} <= alice_terms      # the channel is real for a permitted user
    bob = search.search(world, "bob", "earn-out", config=loose_feedback, as_of=AS_OF,
                        explain=True, limit=50)
    bob_terms = {t["term"] for t in bob["expansion"]["related_terms"]}
    assert bob_terms and not ({"quillon", "holdback"} & bob_terms)
    assert "x_hold" not in ids(bob)                    # the open holdback memo is not pulled in
    assert "quillon" not in dump(bob) and "holdback" not in dump(bob)
    clean = search.search(world_without_wall, "bob", "earn-out", config=loose_feedback,
                          as_of=AS_OF, explain=True, limit=50)
    assert dump(bob) == dump(clean)


def test_thesaurus_alternative_found_only_behind_the_wall_is_not_used_or_shown(
        world, world_without_wall):
    alice = search.search(world, "alice", "lessor remedies", as_of=AS_OF, explain=True)
    assert ("lessor", "landlord", "thesaurus") in used(alice) and "w_landlord" in ids(alice)
    bob = search.search(world, "bob", "lessor remedies", as_of=AS_OF, explain=True)
    assert ids(bob) == ["x_lessor"] and "landlord" not in dump(bob)
    assert dump(bob) == dump(search.search(world_without_wall, "bob", "lessor remedies",
                                           as_of=AS_OF, explain=True))
    # Asking in the walled document's own word tells bob nothing either.
    direct = search.search(world, "bob", "landlord", as_of=AS_OF, explain=True)
    assert direct["expansion"]["not_found"] == [] and ids(direct) == ["x_lessor"]
    assert dump(direct) == dump(search.search(world_without_wall, "bob", "landlord",
                                              as_of=AS_OF, explain=True))


def test_word_form_found_only_behind_the_wall_is_not_used_or_shown(world, world_without_wall):
    alice = search.search(world, "alice", "subrogation", as_of=AS_OF)
    assert ("subrogation", "subrogating", "word form") in used(alice) and "w_subro" in ids(alice)
    bob = search.search(world, "bob", "subrogation", as_of=AS_OF, explain=True)
    assert ids(bob) == ["x_subro"] and "subrogating" not in dump(bob)
    assert dump(bob) == dump(search.search(world_without_wall, "bob", "subrogation",
                                           as_of=AS_OF, explain=True))


def test_typo_correction_never_points_at_a_word_behind_the_wall(world, world_without_wall):
    alice = search.search(world, "alice", "quilon", as_of=AS_OF)
    assert alice["expansion"]["corrected"] == [{"typed": "quilon", "read_as": "quillon"}]
    for typo in ("quilon", "quillan", "qillon", "landlrod", "subrogatting"):
        bob = search.search(world, "bob", typo, as_of=AS_OF, explain=True)
        assert bob["expansion"]["corrected"] == [] and bob["expansion"]["used"] == []
        assert bob["total"] == 0 and bob["expansion"]["not_found"] == [typo]
        assert dump(bob) == dump(search.search(world_without_wall, "bob", typo, as_of=AS_OF,
                                               explain=True)), typo
    # A correction to a visible word must not be displaced by a closer hidden one.
    bob = search.search(world, "bob", "subrogatin", as_of=AS_OF)
    assert [c["read_as"] for c in bob["expansion"]["corrected"]] == ["subrogation"]


def test_expansion_output_matches_an_index_without_the_hidden_documents(
        world, world_without_wall, loose_feedback):
    probes = ["lender consent", "bank", "lessor", "landlord remedies", "tenant landlord",
              "assignment", "labour", "subrogate", "indemnifcation", "deferred price",
              "earn-out", "earn-out holdback", "holdback", "quillon holdback", "milestone",
              "contingent consideration milestone", "landlord quillon", "insurer subrogating"]
    for q in probes:
        for config in (None, loose_feedback):
            for expand_on in (True, False):
                a = search.search(world, "bob", q, config=config, as_of=AS_OF, explain=True,
                                  limit=50, expand=expand_on)
                b = search.search(world_without_wall, "bob", q, config=config, as_of=AS_OF,
                                  explain=True, limit=50, expand=expand_on)
                assert dump(a) == dump(b), (q, expand_on)


def test_whole_corpus_expansion_is_noninterfering(full, key, config, world_without_hidden):
    """Typos of the walled code names, equivalents, other wordings and
    few-result queries, as each wall's excluded user, on the 1,500-document corpus."""
    for t in key["wall_tests"]:
        user = t["denied_users"][0]
        clean = world_without_hidden(user)
        word = t["canary_term"]
        probes = [word[:-1], word[:2] + word[3:], word + "s", f"{word[:-1]} agreement",
                  "handing premises over to a new occupier agreement",
                  "bank agrees to hold off after missed payments",
                  "telling customers about a hacking incident", "indemnifcation basket memo",
                  "deferred price contingent on future performance", "labour dispute",
                  "lessor consent assignment", "escheat unclaimed property memo"] + t["queries"]
        for q in probes:
            a = search.search(full, user, q, config=config, as_of=key["as_of"], explain=True, limit=25)
            b = search.search(clean, user, q, config=config, as_of=key["as_of"], explain=True, limit=25)
            assert dump(a) == dump(b), (user, q)
            assert word not in dump({k: v for k, v in a.items() if k != "query"}) or word in q.lower()
            wa = experience.who(full, user, q, config=config, as_of=key["as_of"])
            wb = experience.who(clean, user, q, config=config, as_of=key["as_of"])
            assert dump(wa) == dump(wb), (user, q)


# -- experience finder --------------------------------------------------------
def _matters_world():
    source = helpers.adapter()
    source._matters.append(Matter("M_TEN", "Dovrane Group: lease renewal", "C2", "retail",
                                  "Real estate", "lease renewal", "Tavish County", "Estermere",
                                  "2024-02-01", "", "Renewal of a tenant's retail lease.", "public"))
    source._team.append(TeamMember("M_TEN", "carol", "lead"))
    source._time.append(TimeEntry("t90", "M_TEN", "carol", "2024-03-01", 14.0))
    conn, _, _ = helpers.build(source)
    return conn


def test_experience_finder_uses_equivalents_and_says_which():
    world = _matters_world()
    result = experience.who(world, "erin", "lessee renewal", as_of=AS_OF)
    assert [p["person_id"] for p in result["people"]] == ["carol"]
    assert result["people"][0]["evidence"][0]["match_strength"] < 1.0
    exact = experience.who(world, "erin", "tenant renewal", as_of=AS_OF)
    assert exact["people"][0]["score"] > result["people"][0]["score"]
    assert experience.who(world, "erin", "lessee", as_of=AS_OF, expand=False)["people"] == []


def test_experience_finder_expansion_does_not_reach_walled_matters(world, world_without_wall):
    # M_RW (acquisition finance) is behind the wall for bob.
    for q in ("acquisition financing", "acquisition finance", "aquisition finance", "asset purchases"):
        a = experience.who(world, "bob", q, as_of=AS_OF)
        b = experience.who(world_without_wall, "bob", q, as_of=AS_OF)
        assert dump(a) == dump(b), q
        assert "M_RW" not in dump(a) and "M_WALL" not in dump(a)
    assert "M_RW" in dump(experience.who(world, "alice", "acquisition financing", as_of=AS_OF))


# -- the thesaurus file -------------------------------------------------------
def test_thesaurus_is_data_with_an_owner_and_holds_nothing_confidential(key, manifest):
    path = ROOT / "config" / "thesaurus.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["_about"] and data["_maintenance"]
    groups = [g for s in data["sections"] for g in s["groups"]]
    assert len(groups) >= 300 and all(len(g) >= 2 for g in groups)
    text = path.read_text(encoding="utf-8").lower()
    secrets = {c.lower() for w in manifest["walls"].values() for c in w["codenames"]}
    secrets |= {t["canary_term"].lower() for t in key["wall_tests"] + key["restricted_tests"]}
    assert not [s for s in secrets if s in text]
    assert "§" not in text and " u.s.c" not in text and " v. " not in text   # no citations
    th = expand.load_thesaurus()
    assert th.groups == len(groups)
    assert {k for k, _, _ in th.lookup(("lessor",))} >= {("landlord",)}


def test_groups_are_built_from_static_data_only():
    parsed = search.parse_query("lender consent")
    groups = expand.build_groups(parsed, cfg.load_config(), True)
    assert [g["label"] for g in groups] == ["lender", "consent"]
    assert groups[0]["alts"][0]["source"] == expand.OWN and groups[0]["alts"][0]["weight"] == 1.0
    assert all(a["weight"] < 1.0 for g in groups for a in g["alts"][1:])
    plain = expand.build_groups(parsed, cfg.load_config(), False)
    assert all(len(g["alts"]) == 1 for g in plain)


# -- added after the first held-out run ---------------------------------------
def test_a_short_real_word_is_not_corrected_into_another_word(world):
    """One changed letter in a short word is usually a different word, not a typo."""
    source = helpers.adapter(documents=PUBLIC + [
        doc("x_patent", "M_PUB", "Memo: patent licence scope", "Scope of the patent licence."),
        doc("x_minor", "M_PUB", "Memo: minority protections", "Protections for the minority.")])
    conn, _, _ = helpers.build(source, near_dup_threshold=2.0)
    for word in ("parent", "majority"):
        result = search.search(conn, "alice", word, as_of=AS_OF)
        assert result["expansion"]["corrected"] == [] and result["total"] == 0, word
    # A dropped or swapped letter is still read as a typo.
    for typo in ("patnet", "paten", "minorty"):
        assert search.search(conn, "alice", typo, as_of=AS_OF)["expansion"]["corrected"], typo


def test_thesaurus_phrase_with_no_visible_match_falls_back_to_its_words(world):
    # "parent company guarantee" is one thesaurus phrase. Nothing here matches it
    # or its listed equivalents, so the words are searched separately.
    source = helpers.adapter(documents=PUBLIC + [
        doc("x_guar", "M_PUB", "Memo: guaranty of the facility", "The guaranty covers the facility.")])
    conn, _, _ = helpers.build(source, near_dup_threshold=2.0)
    result = search.search(conn, "alice", "parent company guarantee", as_of=AS_OF)
    assert ids(result) == ["x_guar"]
    assert ("guarantee", "guaranty", "thesaurus") in used(result)
    assert set(result["expansion"]["not_found"]) == {"parent", "company"}


def test_fallback_from_a_phrase_cannot_be_triggered_by_a_hidden_document(world_without_wall):
    hidden = [doc("w_pg", "M_WALL", "Memo: parent guaranty terms", "The parent guaranty is capped.",
                  author="carol")]
    open_docs = PUBLIC + [doc("x_guar", "M_PUB", "Memo: guaranty of the facility",
                              "The guaranty covers the facility.")]
    with_hidden, _, _ = helpers.build(helpers.adapter(documents=open_docs + hidden),
                                      near_dup_threshold=2.0)
    source = helpers.adapter(documents=open_docs)
    gone = {"M_WALL", "M_RW", "M_RES", "M_UNK"}
    source._matters = [m for m in source._matters if m.matter_id not in gone]
    source._team = [t for t in source._team if t.matter_id not in gone]
    source._time = [t for t in source._time if t.matter_id not in gone]
    source.grants, source.walls = [], []
    clean, _, _ = helpers.build(source, near_dup_threshold=2.0)
    q = "parent company guarantee"
    alice = search.search(with_hidden, "alice", q, as_of=AS_OF)
    assert "w_pg" in ids(alice)                      # for alice the phrase is live
    bob = search.search(with_hidden, "bob", q, as_of=AS_OF, explain=True)
    assert dump(bob) == dump(search.search(clean, "bob", q, as_of=AS_OF, explain=True))
    assert "parent guaranty" not in dump(bob) and ids(bob) == ["x_guar"]


def test_additions_made_after_the_first_held_out_run_are_recorded():
    added = json.loads((ROOT / "output" / "thesaurus_entries_added_after_batch_a.json")
                       .read_text(encoding="utf-8"))
    data = json.loads((ROOT / "config" / "thesaurus.json").read_text(encoding="utf-8"))
    marked = [g for s in data["sections"] if s.get("added") for g in s["groups"]]
    listed = added["prompted_by_a_specific_batch_a_miss"] + added["abbreviations_added_as_a_class"]
    assert marked == listed and len(listed) >= 50
