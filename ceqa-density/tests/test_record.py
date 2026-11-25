"""Hand-computed checks of the record clock and the document dispositions."""
import json, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import record as rc

SD = Path(rc.ROOT) / "sample_data"
CASE = json.loads((SD / "record_case.json").read_text())
DC = json.loads((SD / "record_case_distribution_center.json").read_text())
DOC = dict(e_category="10", privilege_flag="none", internal_agency_comm="Y", electronic="Y", staff_notes="N", logistical="N",
           presented_to_decisionmaking_body="N", reviewed_by="none", draft_env_doc="N", released_for_public_review="N")
disp = lambda branch, **k: rc.disposition({**DOC, **k}, branch)[0]


def test_clock():
    c = rc.record_clock(CASE)                       # filed Fri Oct 16, 2026; served Fri Oct 23
    d = {label: dt for label, dt, _ in c["rows"]}
    assert d["Last day to personally serve the request on the agency (10 business days)"] == date(2026, 10, 30)
    assert c["due"] == date(2026, 12, 22)           # Oct 23 + 60 days
    assert d["Case management conference to be held by (30 days from filing)"] == date(2026, 11, 15)
    assert c["days_remaining"] == 27 and not c["flags"]


def test_clock_runs_from_service_of_request_not_filing():
    assert rc.record_clock({**CASE, "request_served": "2026-10-19"})["due"] == date(2026, 12, 18)


def test_late_service_and_extensions():
    c = rc.record_clock({**CASE, "request_served": "2026-11-02", "extensions": [{"type": "stipulation", "days": 30}, {"type": "court_order", "days": 75}]})
    assert c["due"] == date(2027, 4, 16)            # Nov 2 + 60 = Jan 1; +30 = Jan 31; +75 = Apr 16
    assert any("after the 10-business-day" in f for f in c["flags"]) and any("over 60 days" in f for f in c["flags"])
    ok = rc.record_clock({**CASE, "extensions": [{"type": "court_order", "days": 75, "public_interest_finding": True}]})
    assert not any("over 60 days" in f for f in ok["flags"])


def test_weekend_due_date_is_flagged_not_moved():
    c = rc.record_clock({**CASE, "request_served": "2026-10-20"})    # + 60 = Sat Dec 19, 2026
    assert c["due"] == date(2026, 12, 19) and c["due_if_rolled"] == date(2026, 12, 21) and c["flags"]


def test_business_days_skip_listed_holidays():
    assert rc.add_business_days(date(2026, 11, 20), 5) == date(2026, 12, 1)   # skips Nov 26-27 and two weekends


def test_scope_branch():
    assert rc.scope_branch(CASE)[0] == "B" and rc.scope_branch(DC)[0] == "A"
    small = json.loads(json.dumps(DC)); small["project"]["distribution_center_sqft"] = 49999
    assert rc.scope_branch(small)[0] == "B"
    og = json.loads(json.dumps(CASE)); og["project"]["includes_oil_gas_infrastructure"] = True
    assert rc.scope_branch(og)[0] == "A"


def test_internal_email_dispositions():
    assert disp("B") == rc.OPTIONAL                                             # unpresented internal email
    assert disp("A") == rc.INCLUDE                                              # same email, distribution center project
    assert disp("B", presented_to_decisionmaking_body="Y") == rc.INCLUDE
    for who in ("lead_agency_executive", "local_agency_executive", "supervisory_official"):
        assert disp("B", reviewed_by=who) == rc.INCLUDE
    assert disp("B", electronic="N") == rc.INCLUDE                              # paper memorandum
    assert disp("B", electronic="N", staff_notes="Y") == rc.REVIEW
    assert disp("A", electronic="N", staff_notes="Y") == rc.INCLUDE


def test_exclusions_apply_on_both_branches():
    for b in "AB":
        assert disp(b, logistical="Y") == rc.LOGISTICAL
        assert disp(b, privilege_flag="attorney_client") == rc.PRIV
        assert disp(b, internal_agency_comm="N", draft_env_doc="Y") == rc.REVIEW
        assert disp(b, internal_agency_comm="N", e_category="6") == rc.INCLUDE  # outside comment email is not an internal communication
    assert disp("B", e_category="12") == rc.REVIEW


def test_sample_run(tmp_path):
    for case, counts in ((CASE, {"INCLUDE": 29, "NOT_REQUIRED": 3, "EXCLUDE_DUPLICATE": 3, "EXCLUDE_LOGISTICAL": 2, "WITHHOLD_PENDING_PRIVILEGE_REVIEW": 3, "ATTORNEY_REVIEW": 2}),
                         (DC, {"INCLUDE": 33, "EXCLUDE_DUPLICATE": 3, "EXCLUDE_LOGISTICAL": 2, "WITHHOLD_PENDING_PRIVILEGE_REVIEW": 3, "ATTORNEY_REVIEW": 1})):
        res = rc.process(case, rc.load_docs(SD / "documents.csv"), SD)
        s = rc.compile_record(res, case, SD, tmp_path / case["case_number"][:13])
        assert s["counts"] == counts
        inc = sorted((d for d in res["docs"] if d["disposition"] == rc.INCLUDE), key=lambda d: d["first_page"])
        assert inc[0]["first_page"] == 1 and inc[0]["doc_type"] == "notice_of_determination"      # rule 3.2205(a)(1)(A) first
        assert all(a["last_page"] + 1 == b["first_page"] for a, b in zip(inc, inc[1:]))            # no gaps or overlaps
        assert [d["rule_group"] for d in inc] == sorted(d["rule_group"] for d in inc)
        assert inc[-1]["last_page"] == s["pages"] == s["volumes"][-1]["last"]
        dupes = [d for d in res["docs"] if d["disposition"] == rc.DUP]
        assert all(d["doc_id"].startswith("CB-D") for d in dupes)                                  # the later copy is the one dropped


def test_volumes_are_searchable_and_capped(tmp_path):
    from pypdf import PdfReader
    res = rc.process(CASE, rc.load_docs(SD / "documents.csv"), SD)
    s = rc.compile_record(res, CASE, SD, tmp_path, pages_per_volume=120)
    total = 0
    for vol in s["volumes"]:
        r = PdfReader(tmp_path / vol["file"])
        assert len(r.pages) <= 120 and len(r.pages) == vol["last"] - vol["first"] + 1
        assert f"AR{vol['first']:06d}" in r.pages[0].extract_text() and len(r.outline) >= 1
        total += len(r.pages)
    assert total == s["pages"]
    assert "AR_Vol_01.pdf#page=1" in (tmp_path / "index.html").read_text()


def test_include_optional_flag():
    res = rc.process(CASE, rc.load_docs(SD / "documents.csv"), SD, include_optional=True)
    assert not [d for d in res["docs"] if d["disposition"] == rc.OPTIONAL]
