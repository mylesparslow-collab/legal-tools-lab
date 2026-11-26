import pytest

import helpers
from kx import experience
from kx.schema import Matter, TeamMember, TimeEntry
from kx.search import QueryError

AS_OF = helpers.AS_OF


def _world(extra_matters=(), extra_team=(), extra_time=()):
    source = helpers.adapter()
    source._matters += list(extra_matters)
    source._team += list(extra_team)
    source._time += list(extra_time)
    conn, _, _ = helpers.build(source)
    return conn


def _matter(mid, opened="2025-01-01", mtype="loan workout"):
    return Matter(mid, f"Client {mid}: {mtype}", "C9", "retail", "Finance", mtype,
                  "State of Caldmoor", "Caldmoor", opened, "", f"{mtype} for a retail client.",
                  "public")


@pytest.fixture(scope="module")
def workouts():
    matters = [_matter(f"W{i}") for i in range(1, 5)]
    team = [TeamMember("W1", "alice", "lead"), TeamMember("W2", "alice", "lead"),
            TeamMember("W3", "alice", "lead"),
            TeamMember("W1", "bob", "support"), TeamMember("W2", "bob", "support"),
            TeamMember("W3", "bob", "support"),
            TeamMember("W4", "dave", "lead"), TeamMember("W3", "dave", "support"),
            TeamMember("W4", "erin", "support")]
    time = [TimeEntry(f"x{i}", m, p, d, h) for i, (m, p, d, h) in enumerate([
        ("W1", "alice", "2026-03-01", 40), ("W2", "alice", "2026-02-01", 40),
        ("W3", "alice", "2026-01-01", 40),
        ("W1", "bob", "2026-03-01", 40), ("W2", "bob", "2026-02-01", 40),
        ("W3", "bob", "2026-01-01", 40),
        ("W4", "dave", "2025-06-01", 60), ("W3", "dave", "2025-06-01", 30),
        ("W4", "erin", "2025-06-01", 3)])]
    return _world(matters, team, time)


def test_lead_ranks_above_support_with_the_same_matters_and_hours(workouts):
    result = experience.who(workouts, "carol", "loan workout", as_of=AS_OF)
    order = [p["person_id"] for p in result["people"]]
    assert result["confident"] is True
    assert order.index("alice") < order.index("bob")
    alice = result["people"][order.index("alice")]
    assert alice["rank"] == 1 and alice["matters"] == 3 and alice["lead_matters"] == 3
    assert alice["hours"] == 120.0 and alice["last_activity"] == "2026-03-01"


def test_visible_matters_are_listed_as_evidence(workouts):
    result = experience.who(workouts, "carol", "loan workout", as_of=AS_OF)
    alice = next(p for p in result["people"] if p["person_id"] == "alice")
    assert [e["matter_id"] for e in alice["evidence"]] == ["W1", "W2", "W3"]  # most recent first
    assert all(e["role"] == "lead" and e["matched_on"] == "matter type or practice"
               for e in alice["evidence"])
    assert sum(e["points"] for e in alice["evidence"]) == pytest.approx(alice["score"], abs=1e-3)


def test_departed_people_are_flagged_not_hidden(workouts):
    result = experience.who(workouts, "carol", "loan workout", as_of=AS_OF)
    dave = next(p for p in result["people"] if p["person_id"] == "dave")
    assert dave["departed"] is True and "left the firm" in dave["status_note"]
    assert all(p["departed"] is False for p in result["people"] if p["person_id"] != "dave")


def test_thin_evidence_is_labelled_and_not_given_a_rank(workouts):
    result = experience.who(workouts, "carol", "loan workout", as_of=AS_OF)
    erin = next(p for p in result["people"] if p["person_id"] == "erin")
    assert erin["evidence_level"] == "thin" and erin["rank"] is None
    assert "one matter only" in erin["evidence_note"] and "hours" in erin["evidence_note"]
    ranked = [p for p in result["people"] if p["rank"]]
    assert [p["rank"] for p in ranked] == list(range(1, len(ranked) + 1))
    # Thin entries are listed after everyone with solid evidence.
    levels = [p["evidence_level"] for p in result["people"]]
    assert levels == sorted(levels, key=lambda v: v != "ok")


def test_recent_work_counts_for_more_than_old_work():
    matters = [_matter("N1"), _matter("O1", opened="2016-01-01"),
               _matter("N2"), _matter("O2", opened="2016-02-01"), _matter("N3")]
    team = [TeamMember("N1", "alice", "lead"), TeamMember("N2", "alice", "lead"),
            TeamMember("O1", "bob", "lead"), TeamMember("O2", "bob", "lead"),
            TeamMember("N3", "erin", "lead")]
    time = [TimeEntry("a", "N1", "alice", "2026-05-01", 20), TimeEntry("b", "N2", "alice", "2026-04-01", 20),
            TimeEntry("c", "O1", "bob", "2016-05-01", 20), TimeEntry("d", "O2", "bob", "2016-06-01", 20),
            TimeEntry("e", "N3", "erin", "2026-01-01", 20)]
    result = experience.who(_world(matters, team, time), "carol", "loan workout", as_of=AS_OF)
    by_id = {p["person_id"]: p for p in result["people"]}
    assert by_id["alice"]["score"] > 4 * by_id["bob"]["score"]
    assert by_id["alice"]["rank"] < by_id["bob"]["rank"]


def test_more_hours_count_for_more_with_a_cap():
    matters = [_matter("H1"), _matter("H2"), _matter("H3")]
    team = [TeamMember(m, p, "support") for m in ("H1", "H2") for p in ("alice", "bob", "erin")]
    time = []
    for m in ("H1", "H2"):
        time += [TimeEntry(f"{m}a", m, "alice", "2026-05-01", 5),
                 TimeEntry(f"{m}b", m, "bob", "2026-05-01", 80),
                 TimeEntry(f"{m}e", m, "erin", "2026-05-01", 5000)]
    result = experience.who(_world(matters, team, time), "carol", "loan workout", as_of=AS_OF)
    by_id = {p["person_id"]: p for p in result["people"]}
    assert by_id["bob"]["score"] > by_id["alice"]["score"]
    assert by_id["erin"]["score"] < 1.5 * by_id["bob"]["score"]   # 60x the hours, capped


def test_too_few_matters_is_reported_as_leads_not_a_ranking():
    result = experience.who(_world(), "alice", "contract dispute", as_of=AS_OF)
    assert result["confident"] is False and result["matters_matched"] == 1
    assert "too little to rank on" in result["message"] and "leads to ask" in result["message"]
    # Still put in order of recorded involvement, which is more use than the alphabet.
    scores = [p["score"] for p in result["people"]]
    assert scores == sorted(scores, reverse=True)
    assert [p["rank"] for p in result["people"]] == list(range(1, len(scores) + 1))


def test_no_match_says_so():
    result = experience.who(_world(), "alice", "maritime salvage", as_of=AS_OF)
    assert result["people"] == [] and "No matching matters" in result["message"]


def test_matter_filters_apply_and_document_filters_are_refused(workouts):
    result = experience.who(workouts, "carol", "", {"practice": "Finance"}, as_of=AS_OF)
    assert result["matters_matched"] == 4
    result = experience.who(workouts, "carol", "loan workout office:Nowhere", as_of=AS_OF)
    assert result["matters_matched"] == 0
    with pytest.raises(QueryError):
        experience.who(workouts, "carol", "loan workout type:memo", as_of=AS_OF)


def test_terms_from_different_fields_do_not_combine_into_a_match():
    # "caldmoor" is in a court name, which is not evidence of a kind of work.
    # It is reported as not found; it does not pair up with "merger".
    result = experience.who(_world(), "alice", "caldmoor merger", as_of=AS_OF)
    assert result["not_found"] == ["caldmoor"]
    assert all("merger" in e["matter_type"] for p in result["people"] for e in p["evidence"])
    assert experience.who(_world(), "alice", "caldmoor", as_of=AS_OF)["matters_matched"] == 0


def test_document_titles_can_supply_the_match(workouts):
    result = experience.who(workouts, "alice", "forum selection clause", as_of=AS_OF)
    assert result["matters_matched"] == 1
    carol = result["people"][0]
    assert carol["person_id"] == "carol"
    assert carol["evidence"][0]["matched_on"] in ("matter description", "document titles in the matter")


def test_full_corpus_finds_practice_leaders_for_a_common_matter_type(full, key, config):
    result = experience.who(full, key["eval_user"], "asset purchase", config=config,
                            as_of=key["as_of"], limit=5)
    assert result["confident"] is True and result["matters_matched"] >= 5
    assert all(p["practice"] == "Corporate and M&A" for p in result["people"])
    assert result["people"][0]["rank"] == 1 and result["people"][0]["lead_matters"] >= 1
    scores = [p["score"] for p in result["people"] if p["rank"]]
    assert scores == sorted(scores, reverse=True)
