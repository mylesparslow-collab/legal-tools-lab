import datetime as dt

import pytest

import helpers
from kx import acl, search
from kx.schema import Grant, Matter, Person, Wall


@pytest.fixture(scope="module")
def world():
    conn, indexer, source = helpers.build()
    return conn


def test_public_matter_is_visible_to_any_active_person(world):
    for user in ("alice", "bob", "carol", "erin"):
        assert "M_PUB" in acl.visible_matter_ids(world, user)


def test_restricted_matter_needs_a_grant(world):
    assert "M_RES" in acl.visible_matter_ids(world, "alice")       # user grant
    assert "M_RES" in acl.visible_matter_ids(world, "carol")       # group grant
    assert "M_RES" not in acl.visible_matter_ids(world, "bob")
    assert "M_RES" not in acl.visible_matter_ids(world, "erin")


def test_wall_excludes_a_named_person_from_a_public_matter(world):
    assert "M_WALL" not in acl.visible_matter_ids(world, "bob")
    assert "M_WALL" in acl.visible_matter_ids(world, "alice")
    assert "M_WALL" in acl.visible_matter_ids(world, "erin")


def test_wall_exclusion_beats_a_group_grant(world):
    # bob and alice are both in g_corp, which has a grant on M_RW. bob is walled.
    assert "M_RW" in acl.visible_matter_ids(world, "alice")
    assert "M_RW" not in acl.visible_matter_ids(world, "bob")


def test_wall_exclusion_beats_a_direct_user_grant():
    source = helpers.adapter()
    source.grants.append(Grant("M_RW", "user", "bob"))
    conn, _, _ = helpers.build(source)
    assert "M_RW" not in acl.visible_matter_ids(conn, "bob")


def test_unknown_security_value_is_hidden_from_everyone(world):
    for user in ("alice", "bob", "carol", "erin"):
        assert "M_UNK" not in acl.visible_matter_ids(world, user)


def test_empty_security_value_is_hidden_from_everyone():
    source = helpers.adapter()
    source._matters.append(Matter("M_BLANK", "No security recorded", security=""))
    conn, _, _ = helpers.build(source)
    assert all("M_BLANK" not in acl.visible_matter_ids(conn, u) for u in ("alice", "erin"))


def test_unknown_user_sees_nothing(world):
    assert acl.visible_matter_ids(world, "mallory") == set()
    assert acl.visible_matter_ids(world, "") == set()


def test_departed_user_sees_nothing(world):
    assert acl.visible_matter_ids(world, "dave") == set()


def test_person_with_unrecognised_status_sees_nothing():
    source = helpers.adapter()
    source._people.append(Person("zed", "Zed Halvorsby", status="ON-LEAVE?"))
    conn, _, _ = helpers.build(source)
    assert acl.visible_matter_ids(conn, "zed") == set()


def test_document_whose_matter_is_missing_is_invisible():
    source = helpers.adapter()
    source.documents.append(helpers.documents()[0].__class__(
        "d_orphan", "M_NOWHERE", "Memo: orphan quillon", helpers.body("orphan quillon text")))
    conn, _, _ = helpers.build(source)
    assert conn.execute("SELECT COUNT(*) FROM docs WHERE doc_id='d_orphan'").fetchone()[0] == 1
    for user in ("alice", "bob", "carol", "erin"):
        assert "d_orphan" not in acl.visible_doc_ids(conn, user)
        assert search.search(conn, user, "quillon", as_of=helpers.AS_OF)["total"] == 0


def test_wall_that_does_not_say_who_is_excluded_hides_its_matters_from_everyone():
    conn, indexer, _ = helpers.build(helpers.adapter(walls=[Wall("W1", ("M_WALL",), None)]))
    for user in ("alice", "bob", "carol", "erin"):
        assert "M_WALL" not in acl.visible_matter_ids(conn, user)
    assert conn.execute("SELECT acl_ok FROM matters WHERE matter_id='M_WALL'").fetchone()[0] == 0


def test_wall_with_empty_exclusion_list_hides_its_matters_from_everyone():
    conn, _, _ = helpers.build(helpers.adapter(walls=[Wall("W1", ("M_WALL",), ())]))
    assert "M_WALL" not in acl.visible_matter_ids(conn, "alice")


def test_wall_naming_an_unknown_person_hides_its_matters_and_warns():
    source = helpers.adapter(walls=[Wall("W1", ("M_WALL",), ("bob", "b0b-typo"))])
    conn, indexer, _ = helpers.build(source)
    assert "M_WALL" not in acl.visible_matter_ids(conn, "alice")
    with conn:
        report = indexer.apply_permissions(source.permissions())
    assert any("b0b-typo" in w for w in report["warnings"])


def test_restricted_matter_with_no_grants_is_visible_to_nobody():
    source = helpers.adapter()
    source.grants = [g for g in source.grants if g.matter_id != "M_RES"]
    conn, _, _ = helpers.build(source)
    assert all("M_RES" not in acl.visible_matter_ids(conn, u) for u in ("alice", "carol", "erin"))


def test_grant_with_unknown_grantee_kind_grants_nothing():
    source = helpers.adapter()
    source.grants = [Grant("M_RES", "everyone", "*")]
    conn, _, _ = helpers.build(source)
    assert "M_RES" not in acl.visible_matter_ids(conn, "alice")


def test_new_matter_is_invisible_until_permissions_are_evaluated():
    conn, indexer, source = helpers.build()
    with conn:
        conn.execute("INSERT INTO matters(matter_id, name, security) VALUES ('M_NEW','New','public')")
    assert "M_NEW" not in acl.visible_matter_ids(conn, "alice")  # acl_ok defaults to 0
    with conn:
        indexer.apply_permissions(source.permissions())
    assert "M_NEW" in acl.visible_matter_ids(conn, "alice")


def test_nothing_is_visible_before_any_permission_snapshot_is_applied():
    from kx import index
    conn = index.connect(":memory:")
    indexer = index.Indexer(conn)
    with conn:
        indexer.apply_people(helpers.people())
        indexer.apply_matters(helpers.matters())
        for d in helpers.documents():
            indexer.upsert_document(d)
    assert acl.visible_matter_ids(conn, "alice") == set()
    result = search.search(conn, "alice", "earn-out", as_of=helpers.AS_OF)
    assert result["access"] == "unavailable" and result["results"] == []


def test_stale_permission_snapshot_fails_closed():
    clock = lambda: dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc)
    conn, _, _ = helpers.build(clock=clock)
    cfg = dict(search.load_config(), acl_max_age_hours=24)
    fresh = dt.datetime(2026, 6, 1, 20, 0, tzinfo=dt.timezone.utc)
    stale = dt.datetime(2026, 6, 3, 9, 0, tzinfo=dt.timezone.utc)
    assert search.search(conn, "alice", "earn-out", config=cfg, now=fresh, as_of=helpers.AS_OF)["total"] > 0
    result = search.search(conn, "alice", "earn-out", config=cfg, now=stale, as_of=helpers.AS_OF)
    assert result["access"] == "unavailable" and result["total"] == 0 and result["results"] == []
    assert search.suggest(conn, "alice", "ear", config=cfg, now=stale) == []
    with pytest.raises(acl.PermissionDataUnavailable):
        acl.assert_usable(conn, now=stale, max_age_hours=24)


def test_sql_filter_agrees_with_reference_rules_small_world(world):
    matter_ids = [r[0] for r in world.execute("SELECT matter_id FROM matters")] + ["M_NOWHERE"]
    for user in ("alice", "bob", "carol", "dave", "erin", "mallory"):
        visible = acl.visible_matter_ids(world, user)
        for mid in matter_ids:
            assert (mid in visible) == acl.can_see_reference(world, user, mid), (user, mid)


def test_sql_filter_agrees_with_reference_rules_full_corpus(full):
    people = [r[0] for r in full.execute("SELECT person_id FROM people")]
    matter_ids = [r[0] for r in full.execute("SELECT matter_id FROM matters")]
    checked = 0
    for user in people:
        visible = acl.visible_matter_ids(full, user)
        for mid in matter_ids:
            assert (mid in visible) == acl.can_see_reference(full, user, mid), (user, mid)
            checked += 1
    assert checked == len(people) * len(matter_ids)


def test_full_corpus_walls_match_the_generator_ground_truth(full, manifest):
    for wall in manifest["walls"].values():
        for mid in wall["matters"]:
            for user in wall["excluded"]:
                assert mid not in acl.visible_matter_ids(full, user)
