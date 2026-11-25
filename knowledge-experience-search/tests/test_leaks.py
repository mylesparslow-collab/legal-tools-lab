"""One test per channel through which a hidden document could show itself.

In the small world, bob is excluded by wall W1 from M_WALL (public) and M_RW
(restricted, with a grant to bob's own group). "zephyrine", "sennamar" and
"aerospace" occur only behind that wall. erin has no grant on M_RES or M_RW.
"""
import json
import re
from pathlib import Path

import pytest

import helpers
from kx import acl, experience, search
from kx.schema import Document, Wall
from kx.service import Service

AS_OF = helpers.AS_OF
HIDDEN_FROM_BOB = {"d_wall_1", "d_wall_2", "d_rw_1", "d_res_1", "d_unk_1"}
PROBES = ["zephyrine", "project zephyrine", "earn-out provisions", "earn-out", "memo",
          "agreement", "side letter", '"earn-out provisions"', "sennamar", "aerospace",
          "quasar", "zephyrine earn-out", "type:memo", "model:yes", "industry:aerospace",
          'jurisdiction:"Province of Sennamar"', "author:carol", "after:2025-01-01"]


@pytest.fixture(scope="module")
def world():
    conn, _, _ = helpers.build()
    return conn


@pytest.fixture(scope="module")
def world_without_wall():
    """The same world as if the documents bob cannot see had never existed."""
    hidden_matters = {"M_WALL", "M_RW", "M_RES", "M_UNK"}
    source = helpers.adapter()
    source._matters = [m for m in source._matters if m.matter_id not in hidden_matters]
    source.documents = [d for d in source.documents if d.matter_id not in hidden_matters]
    source._team = [t for t in source._team if t.matter_id not in hidden_matters]
    source._time = [t for t in source._time if t.matter_id not in hidden_matters]
    source.grants = []
    source.walls = []
    conn, _, _ = helpers.build(source)
    return conn


def dump(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# -- channel: results and snippets ------------------------------------------
def test_hidden_documents_never_appear_in_results(world):
    for q in PROBES:
        result = search.search(world, "bob", q, as_of=AS_OF, limit=100, explain=True)
        assert not (helpers.all_doc_ids(result) & HIDDEN_FROM_BOB), q


def test_no_text_from_hidden_documents_reaches_the_user(world):
    """Nothing in the whole response mentions a word that exists only behind the wall."""
    for q in PROBES:
        result = search.search(world, "bob", q, as_of=AS_OF, limit=100, explain=True)
        payload = dump({k: v for k, v in result.items() if k not in ("query", "filters")}).lower()
        for secret in ("zephyrine", "sennamar", "aerospace", "side letter", "lodestar", "quasar"):
            assert secret not in payload, (q, secret)


def test_control_user_does_see_the_walled_documents(world):
    result = search.search(world, "alice", "zephyrine", as_of=AS_OF, limit=100)
    assert {"d_wall_1", "d_rw_1"} <= helpers.all_doc_ids(result)


# -- channel: counts ---------------------------------------------------------
def test_total_counts_only_visible_documents(world):
    bob = search.search(world, "bob", "earn-out", as_of=AS_OF, limit=100)
    alice = search.search(world, "alice", "earn-out", as_of=AS_OF, limit=100)
    assert bob["total"] == len(bob["results"]) == 2
    assert alice["total"] > bob["total"]
    assert search.search(world, "bob", "zephyrine", as_of=AS_OF)["total"] == 0


def test_response_has_no_hidden_result_counter(world):
    result = search.search(world, "bob", "zephyrine", as_of=AS_OF)
    assert set(result) == {"user", "query", "filters", "access", "message", "relaxed",
                           "reranked", "total", "offset", "results", "facets"}
    assert "hidden" not in dump(result).lower() and "restricted" not in dump(result).lower()


def test_no_results_message_is_the_same_for_walled_and_nonexistent_terms(world):
    walled = search.search(world, "bob", "zephyrine", as_of=AS_OF)
    absent = search.search(world, "bob", "xylophone", as_of=AS_OF)
    strip = lambda r: {k: v for k, v in r.items() if k != "query"}
    assert strip(walled) == strip(absent)


# -- channel: facets ---------------------------------------------------------
def test_facets_are_computed_on_the_permitted_set_only(world):
    bob = search.search(world, "bob", "earn-out", as_of=AS_OF, limit=100)
    values = {f: {v["value"] for v in vs} for f, vs in bob["facets"].items()}
    assert "Province of Sennamar" not in values["jurisdiction"]
    assert "aerospace" not in values["client_industry"]
    assert "2025" not in values["year"]
    for field, vs in bob["facets"].items():
        assert sum(v["count"] for v in vs) == bob["total"], field


def test_filtering_on_a_value_that_exists_only_behind_the_wall_finds_nothing(world):
    for flt in ({"jurisdiction": "Province of Sennamar"}, {"industry": "aerospace"},
                {"mtype": "acquisition finance"}):
        assert search.search(world, "bob", "", flt, as_of=AS_OF)["total"] == 0
        assert search.search(world, "alice", "", flt, as_of=AS_OF)["total"] > 0


# -- channel: autocomplete ---------------------------------------------------
def test_autocomplete_offers_only_terms_from_visible_documents(world):
    assert search.suggest(world, "bob", "zep") == []
    assert search.suggest(world, "bob", "senn") == []
    assert search.suggest(world, "bob", "aero") == []
    assert search.suggest(world, "alice", "zep") == ["zephyrine"]
    assert search.suggest(world, "mallory", "ear") == []
    assert search.suggest(world, "dave", "ear") == []


def test_autocomplete_order_does_not_count_hidden_documents(world, world_without_wall):
    for prefix in ("ea", "pr", "me", "ag", "mo", "ch", "fo", "se"):
        assert search.suggest(world, "bob", prefix) == search.suggest(world_without_wall, "bob", prefix)


# -- channel: ranking statistics ---------------------------------------------
def test_scores_are_identical_with_and_without_the_hidden_documents(world, world_without_wall):
    """Document frequencies, document count and average lengths come from the
    visible set. If any came from the whole corpus, scores here would differ."""
    for q in PROBES:
        with_wall = search.search(world, "bob", q, as_of=AS_OF, limit=100, explain=True)
        without = search.search(world_without_wall, "bob", q, as_of=AS_OF, limit=100, explain=True)
        assert dump(with_wall) == dump(without), q


def test_explain_reports_visible_document_frequency(world):
    bob = search.search(world, "bob", "earn-out", as_of=AS_OF, explain=True)
    alice = search.search(world, "alice", "earn-out", as_of=AS_OF, explain=True)
    df = lambda r: r["results"][0]["explain"]["text"]["terms"][0]["documents_you_can_see_with_term"]
    assert df(bob) == 2 and df(alice) == 5
    assert "5 documents you can open" in bob["results"][0]["explain"]["statistics_scope"]


def test_a_term_that_exists_only_behind_the_wall_does_not_change_matching(world, world_without_wall):
    # "all terms" matching falls back to "any term" only when nothing matches.
    # The fallback must trigger exactly as it would if the term did not exist.
    a = search.search(world, "bob", "zephyrine earn-out", as_of=AS_OF)
    b = search.search(world_without_wall, "bob", "zephyrine earn-out", as_of=AS_OF)
    assert a["relaxed"] is True and dump(a) == dump(b)


# -- channel: near-duplicate and version collapse ----------------------------
def test_near_duplicate_behind_the_wall_is_not_listed_or_counted(world):
    # d_wall_2 is an adapted copy of d_pub_1. bob sees d_pub_1 with no trace of the copy.
    result = search.search(world, "bob", "earn-out milestone payment", as_of=AS_OF)
    top = result["results"][0]
    assert top["doc_id"] == "d_pub_1" and top["near_duplicates"] == []


def test_collapse_never_hides_a_visible_document_behind_a_hidden_one(world):
    # For alice the two copies fold together. For bob the open copy must still be there.
    assert "d_pub_1" in [r["doc_id"] for r in
                         search.search(world, "bob", "earn-out", as_of=AS_OF)["results"]]


def test_version_family_spanning_a_wall_shows_no_pointer_to_the_hidden_version():
    source = helpers.adapter()
    text = helpers.body("This form addresses the pangolin warranty schedule.")
    source.documents += [
        Document("fam_draft", "M_PUB", "Form: pangolin warranty", text, "form", "alice",
                 "2025-01-01", family_id="FAMX", version_no=1, is_final=False,
                 modified="2026-01-01T00:00:00"),
        Document("fam_final", "M_WALL", "Form: pangolin warranty", text, "form", "carol",
                 "2025-02-01", family_id="FAMX", version_no=2, is_final=True,
                 modified="2026-01-01T00:00:00")]
    conn, _, _ = helpers.build(source)
    bob = search.search(conn, "bob", "pangolin", as_of=AS_OF)
    assert [r["doc_id"] for r in bob["results"]] == ["fam_draft"]
    assert bob["results"][0]["other_versions"] == [] and bob["results"][0]["near_duplicates"] == []
    alice = search.search(conn, "alice", "pangolin", as_of=AS_OF)
    assert [r["doc_id"] for r in alice["results"]] == ["fam_final"]
    assert [v["doc_id"] for v in alice["results"][0]["other_versions"]] == ["fam_draft"]


# -- channel: experience finder ----------------------------------------------
def test_experience_finder_gives_no_credit_for_walled_matters(world):
    bob = experience.who(world, "bob", "asset purchase", as_of=AS_OF)
    alice = experience.who(world, "alice", "asset purchase", as_of=AS_OF)
    assert {p["person_id"] for p in alice["people"]} >= {"carol", "dave"}
    assert {p["person_id"] for p in bob["people"]} == {"alice", "bob", "erin"}
    assert bob["matters_matched"] == 1 and alice["matters_matched"] == 2
    listed = {e["matter_id"] for p in bob["people"] for e in p["evidence"]}
    assert listed == {"M_PUB"}


def test_experience_finder_hours_and_dates_exclude_walled_matters(world, world_without_wall):
    for q in ("asset purchase", "earn-out provisions", "corporate", "zephyrine",
              "acquisition finance", "practice:Corporate"):
        assert dump(experience.who(world, "bob", q, as_of=AS_OF)) == \
               dump(experience.who(world_without_wall, "bob", q, as_of=AS_OF)), q


def test_experience_finder_cannot_be_probed_by_walled_matter_names(world):
    for q in ("zephyrine", "acquisition finance", "industry:aerospace"):
        result = experience.who(world, "bob", q, as_of=AS_OF)
        assert result["people"] == [] and result["matters_matched"] == 0
    assert experience.who(world, "alice", "acquisition finance", as_of=AS_OF)["people"]


# -- channel: who is asking ---------------------------------------------------
def test_unknown_and_departed_users_get_an_empty_answer_with_no_detail(world):
    for user in ("mallory", "dave", ""):
        s = search.search(world, user, "earn-out", as_of=AS_OF)
        w = experience.who(world, user, "asset purchase", as_of=AS_OF)
        assert s["access"] == "denied" and s["results"] == [] and s["total"] == 0
        assert all(v == [] for v in s["facets"].values())
        assert w["access"] == "denied" and w["people"] == []


# -- channel: optional reranker -------------------------------------------------
def test_reranker_receives_only_permitted_documents(world):
    class Spy:
        seen = []

        def rerank(self, query, docs):
            Spy.seen += [d["doc_id"] for d in docs]
            assert all("zephyrine" not in (d["title"] + d["body"]).lower() for d in docs)
            return [0.0] * len(docs)

    for q in ("earn-out", "memo", "agreement"):
        search.search(world, "bob", q, as_of=AS_OF, limit=100, reranker=Spy())
    assert Spy.seen and not (set(Spy.seen) & HIDDEN_FROM_BOB)


# -- channel: audit log and service -------------------------------------------
def test_audit_entries_list_only_documents_the_user_saw(tmp_path):
    db = tmp_path / "w.sqlite"
    from kx import index
    conn = index.connect(db)
    index.Indexer(conn).sync(helpers.adapter(), full=True)
    conn.close()
    service = Service(db, tmp_path / "audit.jsonl", as_of=AS_OF)
    service.search("bob", "earn-out")
    service.search("bob", "zephyrine")
    service.who("bob", "asset purchase")
    text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    for hidden in HIDDEN_FROM_BOB | {"M_WALL", "M_RW"}:
        assert hidden not in text


# -- permission changes --------------------------------------------------------
def test_a_new_wall_takes_effect_on_the_next_query_without_reindexing():
    conn, indexer, source = helpers.build()
    assert "d_pub_3" in helpers.all_doc_ids(search.search(conn, "erin", "forum selection", as_of=AS_OF))
    postings = conn.execute("SELECT COUNT(*), SUM(tf) FROM postings").fetchone()
    doc_state = conn.execute("SELECT doc_pk, content_hash FROM docs ORDER BY doc_pk").fetchall()
    source.walls.append(Wall("W2", ("M_PUB2",), ("erin",)))
    report = indexer.sync_permissions(source)          # no document is read
    assert "documents_added" not in report
    assert search.search(conn, "erin", "forum selection", as_of=AS_OF)["total"] == 0
    assert search.suggest(conn, "erin", "foru") == []
    assert experience.who(conn, "erin", "contract dispute", as_of=AS_OF)["people"] == []
    assert conn.execute("SELECT COUNT(*), SUM(tf) FROM postings").fetchone() == postings
    assert conn.execute("SELECT doc_pk, content_hash FROM docs ORDER BY doc_pk").fetchall() == doc_state
    # Other users are unaffected, and lifting the wall restores access.
    assert search.search(conn, "carol", "forum selection", as_of=AS_OF)["total"] == 1
    source.walls.pop()
    indexer.sync_permissions(source)
    assert search.search(conn, "erin", "forum selection", as_of=AS_OF)["total"] == 1


def test_removing_a_grant_or_a_group_membership_takes_effect_on_the_next_query():
    conn, indexer, source = helpers.build()
    assert search.search(conn, "carol", "merger agreement", as_of=AS_OF)["total"] == 1
    source.group_members.remove(("g_lit", "carol"))
    indexer.sync_permissions(source)
    after = search.search(conn, "carol", "merger agreement", as_of=AS_OF, limit=50)
    assert "d_res_1" not in helpers.all_doc_ids(after)
    assert search.search(conn, "carol", "", {"mtype": "merger"}, as_of=AS_OF)["total"] == 0


def test_a_person_who_leaves_loses_access_on_the_next_query():
    import dataclasses
    conn, indexer, source = helpers.build()
    assert search.search(conn, "erin", "earn-out", as_of=AS_OF)["total"] > 0
    source._people = [dataclasses.replace(p, status="departed") if p.person_id == "erin" else p
                      for p in source._people]
    indexer.sync_permissions(source)
    assert search.search(conn, "erin", "earn-out", as_of=AS_OF)["access"] == "denied"


# -- structure -----------------------------------------------------------------
def test_every_document_reading_statement_is_permission_scoped():
    """Each SQL statement in the query modules that touches a protected table
    must contain the visibility filter. Guards against a later edit adding an
    unfiltered query."""
    root = Path(__file__).resolve().parent.parent / "kx"
    protected = re.compile(r"\b(docs|postings|near_dups|time_entries|matter_team|matters)\b")
    checked = 0
    for name in ("search.py", "experience.py"):
        source = (root / name).read_text(encoding="utf-8")
        for match in re.finditer(r"conn\.execute\((.*?)\)(?:\.fetch|\)|:|\n)", source, re.S):
            statement = match.group(1)
            if "FROM" not in statement or not protected.search(statement.split("FROM", 1)[1]):
                continue
            checked += 1
            assert "acl.VISIBLE_CTE" in statement and "FROM vis" in statement, statement[:200]
    assert checked >= 8
    assert "people u" in acl.VISIBLE_CTE and "wall_exclusions" in acl.VISIBLE_CTE
