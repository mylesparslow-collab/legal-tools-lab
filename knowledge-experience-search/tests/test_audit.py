import datetime as dt
import json

import pytest

import helpers
from kx import audit, index
from kx.service import Service


class Clock:
    def __init__(self):
        self.t = dt.datetime(2026, 6, 30, 9, 0, tzinfo=dt.timezone.utc)

    def __call__(self):
        self.t += dt.timedelta(minutes=1)
        return self.t


@pytest.fixture()
def service(tmp_path):
    db = tmp_path / "w.sqlite"
    conn = index.connect(db)
    index.Indexer(conn).sync(helpers.adapter(), full=True)
    conn.close()
    return Service(db, tmp_path / "audit.jsonl", clock=Clock(), as_of=helpers.AS_OF)


def test_every_query_is_logged_with_user_time_filters_and_result_ids(service):
    result = service.search("alice", "earn-out type:memo", {"final": "yes"})
    service.who("carol", "asset purchase")
    entries = audit.read_entries(service.audit.path)
    assert [e["action"] for e in entries] == ["search", "who"]
    first = entries[0]
    assert first["user"] == "alice" and first["query"] == "earn-out type:memo"
    assert first["filters"] == {"doc_type": "memo", "is_final": 1}
    assert first["result_ids"] == [r["doc_id"] for r in result["results"]] != []
    assert first["result_count"] == len(first["result_ids"])
    assert first["time"] == "2026-06-30T09:01:00+00:00"
    assert entries[1]["result_ids"] and all(":" in x for x in entries[1]["result_ids"])


def test_denied_and_empty_queries_are_logged_too(service):
    service.search("dave", "earn-out")
    service.search("bob", "zephyrine")
    entries = audit.read_entries(service.audit.path)
    assert entries[0]["access"] == "denied" and entries[0]["result_count"] == 0
    assert entries[1]["access"] == "ok" and entries[1]["result_count"] == 0


def test_chain_verifies_and_continues_across_restarts(service):
    for q in ("earn-out", "forum selection", "severance"):
        service.search("alice", q)
    again = Service(service.db_path, service.audit.path, clock=Clock(), as_of=helpers.AS_OF)
    again.search("carol", "venue")
    verdict = audit.verify(service.audit.path)
    assert verdict["ok"] is True and verdict["entries"] == 4
    entries = audit.read_entries(service.audit.path)
    assert [e["seq"] for e in entries] == [1, 2, 3, 4]
    assert entries[0]["prev_hash"] == audit.GENESIS
    assert all(entries[i]["prev_hash"] == entries[i - 1]["hash"] for i in range(1, 4))
    assert verdict["head_hash"] == entries[-1]["hash"]


def _lines(service):
    for q in ("earn-out", "forum selection", "severance", "venue"):
        service.search("alice", q)
    return service.audit.path.read_text(encoding="utf-8").splitlines()


def test_editing_an_entry_breaks_the_chain(service):
    lines = _lines(service)
    entry = json.loads(lines[1])
    entry["user"] = "bob"   # pretend someone else ran the query
    lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    service.audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    verdict = audit.verify(service.audit.path)
    assert verdict["ok"] is False and verdict["first_bad_seq"] == 2


def test_removing_an_entry_breaks_the_chain(service):
    lines = _lines(service)
    del lines[1]
    service.audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    verdict = audit.verify(service.audit.path)
    assert verdict["ok"] is False and verdict["first_bad_seq"] == 3


def test_reordering_entries_breaks_the_chain(service):
    lines = _lines(service)
    lines[1], lines[2] = lines[2], lines[1]
    service.audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert audit.verify(service.audit.path)["ok"] is False


def test_recomputing_one_hash_after_an_edit_is_still_caught(service):
    lines = _lines(service)
    entry = json.loads(lines[1])
    entry["query"] = "something innocent"
    body = {k: v for k, v in entry.items() if k != "hash"}
    entry["hash"] = audit._entry_hash(entry["prev_hash"], body)   # forger fixes this entry
    lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    service.audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    verdict = audit.verify(service.audit.path)
    assert verdict["ok"] is False and verdict["first_bad_seq"] == 3  # the next link no longer fits


def test_garbage_line_is_reported_not_raised(service):
    _lines(service)
    with open(service.audit.path, "a", encoding="utf-8") as fh:
        fh.write("not json\n")
    verdict = audit.verify(service.audit.path)
    assert verdict["ok"] is False and "line 5" in verdict["reason"]


def test_no_results_are_returned_if_the_audit_log_cannot_be_written(service, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("a file where a folder is needed", encoding="utf-8")
    service.audit.path = blocker / "audit.jsonl"
    with pytest.raises(OSError):
        service.search("alice", "earn-out")


def test_zero_result_report_groups_and_ranks_missed_queries(service):
    service.search("alice", "Escheat  Procedure")
    service.search("bob", "escheat procedure")
    service.search("alice", "escheat procedure")
    service.search("alice", "platypus")
    service.search("alice", "severance platypus")       # partial matches only
    service.search("alice", "earn-out")                 # found: not in the report
    service.search("dave", "escheat procedure")         # denied: not a content gap
    service.who("alice", "maritime salvage")
    rows = audit.zero_result_report(audit.read_entries(service.audit.path))
    assert rows[0] == {"action": "search", "query": "escheat procedure", "kind": "nothing",
                       "filters": {}, "times": 3, "distinct_users": 2,
                       "first_seen": "2026-06-30T09:01:00+00:00",
                       "last_seen": "2026-06-30T09:03:00+00:00"}
    kinds = {(r["action"], r["query"]): r["kind"] for r in rows}
    assert kinds[("search", "platypus")] == "nothing"
    assert kinds[("search", "severance platypus")] == "partial matches only"
    assert kinds[("who", "maritime salvage")] == "nothing"
    assert ("search", "earn-out") not in kinds and len(rows) == 4
    text = audit.format_zero_result_report(rows)
    assert "3x by 2 user(s)" in text and "escheat procedure" in text


def test_suggestions_are_not_logged(service):
    service.suggest("alice", "ear")
    assert audit.read_entries(service.audit.path) == []
