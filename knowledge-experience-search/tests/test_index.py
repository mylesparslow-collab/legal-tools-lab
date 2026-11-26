import dataclasses

import pytest

import helpers
from kx import acl, index, search
from kx.schema import Document, Matter
from sources.base import SourceError


def count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def test_full_corpus_is_indexed_completely(full, manifest):
    assert count(full, "SELECT COUNT(*) FROM docs") == manifest["counts"]["documents"]
    assert count(full, "SELECT COUNT(*) FROM matters") == manifest["counts"]["matters"]
    assert count(full, "SELECT COUNT(*) FROM matters WHERE acl_ok = 0") == 0
    assert count(full, "SELECT COUNT(DISTINCT field) FROM postings") == 3


def test_resync_with_no_changes_touches_nothing():
    conn, indexer, source = helpers.build()
    before = count(conn, "SELECT COUNT(*) FROM postings")
    report = indexer.sync(source)
    assert report["documents_added"] == 0 and report["documents_updated"] == 0
    # Only documents stamped at the cursor are re-read (">=" so nothing with an
    # equal stamp is missed); their content hash shows they are unchanged.
    assert 1 <= report["documents_unchanged"] < len(source.documents)
    assert count(conn, "SELECT COUNT(*) FROM postings") == before


def test_incremental_sync_reads_only_changes_since_the_cursor():
    conn, indexer, source = helpers.build()
    source.documents.append(Document(
        "d_new", "M_PUB", "Memo: wombat indemnity", helpers.body("A wombat indemnity memo."),
        "memo", "alice", "2026-06-01", is_final=True, modified="2026-06-01T00:00:00"))
    report = indexer.sync(source)
    assert report["mode"] == "incremental" and report["documents_added"] == 1
    assert report["documents_unchanged"] <= 1  # only the document stamped at the cursor is re-read
    assert search.search(conn, "alice", "wombat", as_of=helpers.AS_OF)["total"] == 1


def test_changed_document_replaces_its_old_terms():
    conn, indexer, source = helpers.build()
    old = source.documents[1]
    source.documents[1] = dataclasses.replace(
        old, title="Checklist: ocelot deliverables", modified="2026-06-02T00:00:00")
    report = indexer.sync(source)
    assert report["documents_updated"] == 1
    assert search.search(conn, "alice", "ocelot", as_of=helpers.AS_OF)["total"] == 1
    assert search.search(conn, "alice", '"closing deliverables"', as_of=helpers.AS_OF)["total"] == 0
    assert count(conn, "SELECT COUNT(*) FROM docs") == len(source.documents)


def test_tombstone_removes_document_postings_and_edges():
    conn, indexer, source = helpers.build()
    pk = count(conn, "SELECT doc_pk FROM docs WHERE doc_id='d_pub_3'")
    source.deleted_doc_ids.append("d_pub_3")
    report = indexer.sync(source)
    assert report["documents_deleted"] == 1
    assert count(conn, "SELECT COUNT(*) FROM docs WHERE doc_id='d_pub_3'") == 0
    assert count(conn, "SELECT COUNT(*) FROM postings WHERE doc_pk=?", pk) == 0
    assert count(conn, "SELECT COUNT(*) FROM dup_keys WHERE doc_pk=?", pk) == 0
    assert search.search(conn, "carol", '"forum selection clause"', as_of=helpers.AS_OF)["total"] == 0
    assert search.search(conn, "carol", "forum", as_of=helpers.AS_OF)["total"] == 0
    assert "forum" not in search.suggest(conn, "carol", "for")


def test_full_sync_removes_documents_the_source_no_longer_lists():
    conn, indexer, source = helpers.build()
    source.documents = [d for d in source.documents if d.doc_id != "d_pub_2"]
    assert indexer.sync(source)["documents_deleted"] == 0       # incremental cannot notice
    assert indexer.sync(source, full=True)["documents_deleted"] == 1
    assert count(conn, "SELECT COUNT(*) FROM docs WHERE doc_id='d_pub_2'") == 0


def test_removing_a_matter_removes_its_documents():
    conn, indexer, source = helpers.build()
    source._matters = [m for m in source._matters if m.matter_id != "M_PUB2"]
    report = indexer.sync(source)
    assert report["matters_removed"] == 1 and report["documents_removed_with_matters"] == 1
    assert count(conn, "SELECT COUNT(*) FROM docs WHERE matter_id='M_PUB2'") == 0


def test_matter_metadata_change_updates_the_metadata_field():
    conn, indexer, source = helpers.build()
    assert search.search(conn, "alice", "zirconium", as_of=helpers.AS_OF)["total"] == 0
    source._matters[0] = dataclasses.replace(source._matters[0], client_industry="zirconium mining")
    indexer.sync(source)
    hits = search.search(conn, "alice", "zirconium", as_of=helpers.AS_OF, explain=True)
    assert hits["total"] >= 1
    assert all(r["matter_id"] == "M_PUB" for r in hits["results"])
    assert "metadata" in hits["results"][0]["explain"]["text"]["terms"][0]["matched_in"]


def test_document_with_its_own_security_is_refused():
    conn, indexer, source = helpers.build()
    source.documents.append(Document(
        "d_special", "M_PUB", "Memo: narwhal", helpers.body("narwhal memo"), "memo",
        modified="2026-06-03T00:00:00", security_override="PRIVATE"))
    report = indexer.sync(source)
    assert count(conn, "SELECT COUNT(*) FROM docs WHERE doc_id='d_special'") == 0
    assert report["documents_rejected"] and report["documents_rejected"][0][0] == "d_special"
    assert search.search(conn, "alice", "narwhal", as_of=helpers.AS_OF)["total"] == 0


def test_document_that_gains_its_own_security_is_removed_from_the_index():
    conn, indexer, source = helpers.build()
    source.documents[0] = dataclasses.replace(
        source.documents[0], security_override="PRIVATE", modified="2026-06-04T00:00:00")
    indexer.sync(source)
    assert count(conn, "SELECT COUNT(*) FROM docs WHERE doc_id='d_pub_1'") == 0


def test_failed_permission_read_rolls_the_whole_sync_back():
    conn, indexer, source = helpers.build()
    docs_before = count(conn, "SELECT COUNT(*) FROM docs")
    walls_before = count(conn, "SELECT COUNT(*) FROM wall_exclusions")
    source.permissions_available = False
    source.documents.append(Document("d_x", "M_PUB", "Memo: yak", helpers.body("yak"),
                                     modified="2026-06-05T00:00:00"))
    source._people.append(helpers.people()[0].__class__("newbie", "New Person", status="active"))
    with pytest.raises(SourceError):
        indexer.sync(source)
    assert count(conn, "SELECT COUNT(*) FROM docs") == docs_before
    assert count(conn, "SELECT COUNT(*) FROM wall_exclusions") == walls_before
    assert count(conn, "SELECT COUNT(*) FROM people WHERE person_id='newbie'") == 0
    assert "M_WALL" not in acl.visible_matter_ids(conn, "bob")   # the old wall still holds


def test_sketch_similarity_is_high_for_light_edits_and_low_for_unrelated_text():
    from kx.text import tokenize
    base = helpers.body("This memo addresses earn-out provisions for the asset purchase.")
    edited = base.replace("reworked", "revised").replace("Open", "Remaining")
    other = ("Quarterly staffing note covering holiday rota, parking permits, kitchen "
             "refurbishment, fire drill timings and the new visitor badge procedure for "
             "the reception desk during the summer period across all floors.")
    s = lambda text: index.make_sketch(tokenize(text))
    assert index.sketch_similarity(s(base), s(edited)) >= 0.6
    assert index.sketch_similarity(s(base), s(other)) < 0.1
    assert index.sketch_similarity(s(base), s(base)) == 1.0


def test_planted_near_duplicates_are_found(full, manifest):
    found = 0
    for copy_id, original_id in manifest["near_duplicates"]:
        found += count(
            full, "SELECT COUNT(*) FROM near_dups n JOIN docs a ON a.doc_pk=n.doc_a "
                  "JOIN docs b ON b.doc_pk=n.doc_b WHERE (a.doc_id=? AND b.doc_id=?) "
                  "OR (a.doc_id=? AND b.doc_id=?)", copy_id, original_id, original_id, copy_id)
    assert found >= 0.9 * len(manifest["near_duplicates"])


def test_near_duplicate_edges_link_only_related_documents(full, key):
    """Every edge joins two documents the generator made from the same original."""
    eq = key["equivalents"]
    rows = full.execute("SELECT a.doc_id, b.doc_id FROM near_dups n "
                        "JOIN docs a ON a.doc_pk=n.doc_a JOIN docs b ON b.doc_pk=n.doc_b").fetchall()
    assert rows
    unrelated = [(a, b) for a, b in rows if eq.get(a, a) != eq.get(b, b)]
    assert len(unrelated) <= 0.02 * len(rows), unrelated[:5]


def test_fts5_probe_reports_a_boolean_and_index_has_no_fts_tables(full):
    conn = index.connect(":memory:")
    assert index.fts5_available(conn) in (True, False)
    names = [r[0] for r in full.execute("SELECT name FROM sqlite_master")]
    assert not any("fts" in n.lower() for n in names)
