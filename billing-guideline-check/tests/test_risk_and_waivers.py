import datetime as dt
from decimal import Decimal

import pytest

from billcheck import guidelines as G
from billcheck.engine import check_invoice
from billcheck.model import DataError
from billcheck.waivers import waiver_from_dict
from conftest import mk_guideline, mk_invoice, mk_line, mk_matter, mk_rule

D = Decimal


def waiver(**changes):
    data = {
        "waiver_id": "W-T", "client_id": "testco", "matter_id": "M-1", "rule_id": "T-MINIMUM_INCREMENT",
        "approved_by": "Client contact", "approved_on": "2026-10-01", "reference": "Email of 2026-10-01",
        "expires_on": "2026-12-31",
    }
    data.update(changes)
    return waiver_from_dict(data)


GUIDE = mk_guideline(
    mk_rule("minimum_increment", {"increment": "0.1"}),
    mk_rule("rate_above_card"),
    mk_rule("non_billable_task", {"categories": {"training": ["training"]}}),
)


def test_entry_with_several_findings_counts_once_at_the_largest():
    # 0.25 h at 240 = 60.00. Trips increment (60.00), training (60.00) and rate (0.25 x 15 = 3.75).
    line = mk_line(1, hours="0.25", rate="240", narrative="Training on new portal")
    result = check_invoice(mk_invoice([line, mk_line(2, rate="225", narrative="Review lease")]), GUIDE, mk_matter(TK01="225"))
    assert len(result.findings) == 3
    assert sum(f.amount_at_risk for f in result.findings) == D("123.75")  # naive sum would double count
    assert result.entry_at_risk == {1: D("60.00")}
    assert result.total_at_risk == D("60.00")


def test_entry_risk_is_the_max_reduction_not_always_the_full_amount():
    line = mk_line(1, hours="2.0", rate="240")
    result = check_invoice(mk_invoice([line]), GUIDE, mk_matter(TK01="225"))
    assert result.entry_at_risk == {1: D("30.00")} and result.total_at_risk == D("30.00")


def test_no_finding_exceeds_its_entry_and_total_never_exceeds_invoice(results):
    for result in results:
        amounts = {ln.line_no: ln.amount for ln in result.invoice.lines}
        for f in result.findings:
            if f.line_no is not None:
                assert f.amount_at_risk <= amounts[f.line_no]
        for line_no, risk in result.entry_at_risk.items():
            assert D("0") <= risk <= amounts[line_no]
        assert result.total_at_risk <= result.invoice.line_total
        assert result.entry_risk_total == sum(result.entry_at_risk.values(), D("0"))


def test_sample_totals_do_not_double_count(by_invoice):
    result = by_invoice["INV-Q-1002"]
    naive = sum((f.amount_at_risk for f in result.open_findings), D("0"))
    assert naive > result.total_at_risk  # line 8 trips two rules
    two_rule_lines = [n for n in result.entry_at_risk if len([f for f in result.open_findings if f.line_no == n]) > 1]
    assert two_rule_lines
    for n in two_rule_lines:
        assert result.entry_at_risk[n] == max(f.amount_at_risk for f in result.open_findings if f.line_no == n)


def test_invoice_level_amount_overlaps_with_entry_amounts(by_invoice):
    result = by_invoice["INV-B-2001"]
    assert result.invoice_level_risk == D("1850.00")
    assert result.entry_risk_total == D("2378.50")
    assert result.total_at_risk == max(result.entry_risk_total, result.invoice_level_risk)


def test_invoice_level_amount_wins_when_larger():
    guide = mk_guideline(mk_rule("budget_cap"), mk_rule("minimum_increment", {"increment": "0.1"}))
    matter = mk_matter()
    matter["budget"] = {"cap": "1000.00", "billed_to_date": "900.00"}
    inv = mk_invoice([mk_line(1, hours="0.25", rate="400"), mk_line(2, hours="2", rate="400", narrative="Review lease")])
    result = check_invoice(inv, guide, matter)
    assert result.entry_risk_total == D("100.00") and result.invoice_level_risk == D("800.00")
    assert result.total_at_risk == D("800.00")


def test_waiver_suppresses_the_matching_finding_and_is_shown():
    inv = mk_invoice([mk_line(1, hours="0.25")])
    result = check_invoice(inv, GUIDE, mk_matter(TK01="300"), [waiver()])
    (f,) = result.findings
    assert f.status == "waived"
    assert f.waiver["approved_by"] == "Client contact" and f.waiver["reference"] == "Email of 2026-10-01"
    assert "Expires 2026-12-31" in f.note
    assert result.open_findings == [] and result.total_at_risk == 0


def test_expired_waiver_does_not_suppress_and_says_so():
    inv = mk_invoice([mk_line(1, hours="0.25", date=dt.date(2026, 10, 6))])
    result = check_invoice(inv, GUIDE, mk_matter(TK01="300"), [waiver(expires_on="2026-10-05")])
    (f,) = result.findings
    assert f.status == "open" and "expired on 2026-10-05" in f.note
    assert result.total_at_risk == D("75.00")


def test_waiver_expiry_is_inclusive_of_the_last_day():
    inv = mk_invoice([mk_line(1, hours="0.25", date=dt.date(2026, 10, 6))])
    result = check_invoice(inv, GUIDE, mk_matter(TK01="300"), [waiver(expires_on="2026-10-06")])
    assert result.findings[0].status == "waived"


@pytest.mark.parametrize(
    "changes",
    [
        {"rule_id": "T-OTHER"},
        {"client_id": "someone-else"},
        {"matter_id": "M-2"},
        {"timekeeper_id": "TK02"},
        {"invoice_id": "INV-OTHER"},
        {"line_no": 7},
        {"effective_from": "2026-10-07"},
    ],
)
def test_waiver_that_does_not_match_leaves_the_finding_open(changes):
    inv = mk_invoice([mk_line(1, hours="0.25", date=dt.date(2026, 10, 6))])
    result = check_invoice(inv, GUIDE, mk_matter(TK01="300"), [waiver(**changes)])
    assert result.findings[0].status == "open" and result.findings[0].note == ""


def test_waiver_must_say_who_when_and_reference():
    for missing in ("approved_by", "approved_on", "reference", "expires_on"):
        with pytest.raises(DataError, match=missing):
            waiver(**{missing: ""})


def test_sample_waiver_covers_only_the_approved_hearing(by_invoice):
    result = by_invoice["INV-Q-1001"]
    event = [f for f in result.findings if f.rule_id == "QMI-EVENT-01"]
    assert sorted((f.entry_date.isoformat(), f.status) for f in event) == [("2026-10-20", "open"), ("2026-10-27", "waived")]
    waived = next(f for f in event if f.status == "waived")
    assert waived.waiver["waiver_id"] == "W-001"
    assert waived.line_no not in result.entry_at_risk


def test_sample_expired_waiver_is_reported_on_the_open_finding(by_invoice):
    result = by_invoice["INV-O-3001"]
    (f,) = [f for f in result.findings if f.rule_id == "OIH-RESEARCH-01"]
    assert f.status == "open" and "W-002 expired on 2026-09-30" in f.note
