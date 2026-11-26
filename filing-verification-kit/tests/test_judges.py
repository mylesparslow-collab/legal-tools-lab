"""Judge AI-order lookup: schema, staleness, and never reporting 'no order exists'."""
import copy
from datetime import date, timedelta

import pytest

from filingkit import judges

D = date(2027, 1, 12)


@pytest.fixture
def data():
    return judges.load_orders()


def test_sample_file_is_valid_and_labelled_fictional(data):
    assert judges.validate_entries(data) == []
    assert data["fictional"] is True
    for e in data["entries"]:
        assert "fictional" in e["court"].lower()
        assert e["court_id"].startswith("fict-")
        assert "fictional" in e["order_title"].lower()
        assert e["judge"] is None or "fictional" in e["judge"].lower()
        assert "courts.example/" in e["source_url"]


def test_sample_covers_every_requirement_type(data):
    assert {e["requirement_type"] for e in data["entries"]} == set(judges.REQUIREMENT_TYPES)


def test_no_entry_is_not_checked_never_no_order(data):
    res = judges.lookup(data, "fict-alder-ridge", "fict-unlisted", D)
    assert res["status"] == judges.NOT_CHECKED and res["entries"] == []
    assert res["message"].startswith("Not checked")
    assert "does not mean no order exists" in res["message"]


def test_unknown_court_is_not_checked(data):
    assert judges.lookup(data, "fict-elsewhere", None, D)["status"] == judges.NOT_CHECKED


def test_none_known_entry_is_described_as_a_search_not_an_absence(data):
    res = judges.lookup(data, "fict-alder-ridge", "fict-quillon", D)
    assert res["status"] == judges.CURRENT
    assert "not a statement that no order exists" in res["message"]


def test_stale_entry_is_flagged_recheck(data):
    res = judges.lookup(data, "fict-port-selwyn", "fict-marrowby", D)
    assert res["status"] == judges.STALE
    assert res["message"].startswith("Recheck before relying")
    assert [e["entry_id"] for e in res["entries"] if e["stale"]] == ["JO-003"]


def test_staleness_boundary_is_inclusive_of_the_window(data):
    last = date(2027, 1, 8)  # JO-002
    assert judges.lookup(data, "fict-alder-ridge", "fict-ostergaard", last + timedelta(days=30))["status"] == judges.CURRENT
    assert judges.lookup(data, "fict-alder-ridge", "fict-ostergaard", last + timedelta(days=31))["status"] == judges.STALE


def test_staleness_window_is_configurable(data):
    assert judges.lookup(data, "fict-port-selwyn", "fict-marrowby", D, staleness_days=90)["status"] == judges.CURRENT
    assert judges.lookup(data, "fict-alder-ridge", "fict-ostergaard", D, staleness_days=2)["status"] == judges.STALE
    with pytest.raises(ValueError):
        judges.lookup(data, "fict-alder-ridge", "fict-ostergaard", D, staleness_days=-1)


def test_entry_dated_in_the_future_is_not_trusted(data):
    res = judges.lookup(data, "fict-alder-ridge", "fict-ostergaard", date(2026, 12, 1))
    assert res["status"] == judges.STALE


def test_court_wide_entry_is_shown_but_judge_stays_not_checked(data):
    res = judges.lookup(data, "fict-port-selwyn", "fict-unlisted", D)
    assert res["status"] == judges.NOT_CHECKED
    assert [e["entry_id"] for e in res["entries"]] == ["JO-005"]
    assert judges.lookup(data, "fict-port-selwyn", None, D)["status"] == judges.CURRENT


@pytest.mark.parametrize("change,needle", [
    (lambda e: e.__setitem__("requirement_type", "maybe"), "requirement_type"),
    (lambda e: e.pop("checked_by"), "missing field checked_by"),
    (lambda e: e.__setitem__("last_checked", "last week"), "last_checked"),
    (lambda e: e.__setitem__("judge", None), "judge_id and judge"),
    (lambda e: e.__setitem__("required_text", None), "required_text"),
    (lambda e: e.__setitem__("source_url", ""), "source_url"),
])
def test_validation_catches_bad_entries(data, change, needle):
    bad = copy.deepcopy(data)
    change(bad["entries"][1])
    problems = judges.validate_entries(bad)
    assert any(needle in p for p in problems)
