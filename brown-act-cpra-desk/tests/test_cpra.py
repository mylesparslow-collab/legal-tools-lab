from datetime import date

import pytest

from desk import cpra, rules

T = date(2027, 1, 22)


def test_ten_days_from_receipt():
    r = cpra.deadlines({"id": "x", "received": "2027-01-04"}, T)  # Monday + 10 = Thursday 1/14
    assert r["determination_due"] == "2027-01-14" and r["extension_latest"] == "2027-01-28"


def test_weekend_and_holiday_roll_forward():
    assert cpra.deadlines({"id": "x", "received": "2027-01-06"}, T)["determination_due"] == "2027-01-19"  # Sat 1/16 -> Mon 1/18 holiday -> Tue
    assert cpra.deadlines({"id": "x", "received": "2027-01-08"}, T)["determination_due"] == "2027-01-19"  # Mon 1/18 holiday -> Tue


def test_extension_is_14_days_from_the_unrolled_day_10():
    r = cpra.deadlines({"id": "x", "received": "2027-01-06"}, T)
    assert r["extension_latest"] == "2027-02-01"  # 1/16 + 14 = Sat 1/30 -> Mon 2/1


def test_valid_extension_moves_effective_date():
    r = cpra.deadlines({"id": "x", "received": "2027-01-04", "extension_notice_date": "2027-01-13", "extension_reason": "c2", "extension_to": "2027-01-27"}, T)
    assert r["effective_due"] == "2027-01-27"


@pytest.mark.parametrize("req,code", [
    ({"extension_notice_date": "2027-01-13", "extension_reason": "staffing", "extension_to": "2027-01-27"}, "ext_reason"),
    ({"extension_notice_date": "2027-01-13", "extension_reason": "cite", "extension_to": "2027-01-27"}, "ext_reason"),
    ({"extension_notice_date": "2027-01-15", "extension_reason": "c1", "extension_to": "2027-01-27"}, "ext_late"),
    ({"extension_notice_date": "2027-01-13", "extension_reason": "c1", "extension_to": "2027-01-29"}, "ext_too_long"),
    ({"extension_reason": "c1", "extension_to": "2027-01-27"}, "ext_notice"),
])
def test_bad_extensions_do_not_move_the_date(req, code):
    r = cpra.deadlines({"id": "x", "received": "2027-01-04", **req}, T)
    assert code in {f["code"] for f in r["findings"] if f["level"] == "fail"}
    assert r["effective_due"] == "2027-01-14"


def test_status_text():
    assert cpra.deadlines({"id": "x", "received": "2027-01-04"}, date(2027, 1, 14))["status"] == "due today"
    assert cpra.deadlines({"id": "x", "received": "2027-01-04"}, date(2027, 1, 16))["status"] == "overdue by 2 day(s)"
    assert cpra.deadlines({"id": "x", "received": "2027-01-04", "determination_sent": "2027-01-15"}, T)["status"] == "sent 1 day(s) late"


def test_legacy_map():
    hits = cpra.map_legacy("withheld under Government Code section 6254(k), § 6254.19 and Section 6254(zz); see Labor Code section 2699.")
    assert [(h["old"], h["new"]) for h in hits] == [("6254(k)", "§ 7927.705"), ("6254.19", "§ 7929.210"), ("6254(zz)", None)]


def test_proposals_and_decisions():
    text = "From: A\nTo: B\nHome address: 1 Elm St\nPersonal cell (559) 555-0142\nSSN 123-45-6789\n"
    props = cpra.propose("D1", text)
    assert {p["text"] for p in props} == {"1 Elm St", "(559) 555-0142", "123-45-6789"}
    assert all(p["status"] == "proposed" for p in props)
    assert cpra.privilege_log(props, {}) == []  # nothing approved, nothing logged
    with pytest.raises(ValueError):
        cpra.apply_decisions(props, {props[0]["id"]: {"decision": "approve"}})  # reviewer name required
    done = cpra.apply_decisions(props, {props[0]["id"]: {"decision": "approve", "reviewer": "R"}, props[1]["id"]: {"decision": "reject", "reviewer": "R"}})
    log = cpra.privilege_log(done, {"D1": {"from": "A"}})
    assert len(log) == 1 and log[0]["responsible_person"] == "R"


def test_counsel_message_proposed_as_whole_document():
    text = "From: Pat Lawyer\nTo: GM\n\nMy legal advice is to wait."
    assert any(p["scope"] == "document" for p in cpra.propose("D", text, ("Pat Lawyer",)))
    assert not any(p["scope"] == "document" for p in cpra.propose("D", text, ()))


def test_propagated_approval_marks_same_text_elsewhere():
    a = cpra.propose("A", "Home address: 1 Elm St\n")
    b = cpra.propose("B", "> Home address: 1 Elm St\n")
    done = cpra.propagate_decisions(cpra.apply_decisions(a + b, {a[0]["id"]: {"decision": "approve", "reviewer": "R"}}))
    assert [p["status"] for p in done] == ["approved", "approved"]


def test_every_rule_has_cite_and_status():
    def walk(node, path=""):
        if isinstance(node, dict):
            if "status" in node and "cite" in node:
                assert node["status"] in ("verified", "assumption", "not_modeled"), path
                if node["status"] == "verified":
                    assert node["cite"] and node["source_url"] and node["verified_on"], path
                yield path
            for k, v in node.items():
                yield from walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from walk(v, f"{path}/{i}")
    assert len(list(walk(rules.brown_act()))) > 25 and len(list(walk(rules.cpra()))) >= 6


def test_ics_has_two_events_per_request():
    ics = cpra.to_ics([cpra.deadlines({"id": "x", "received": "2027-01-04"}, T)])
    assert ics.count("BEGIN:VEVENT") == 2 and "DTSTART;VALUE=DATE:20270114" in ics
