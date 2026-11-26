"""One or more focused tests per rule type, on small hand-built invoices."""

import datetime as dt
from decimal import Decimal

import pytest

from billcheck import guidelines as G
from billcheck.engine import check_invoice
from conftest import mk_expense, mk_guideline, mk_invoice, mk_line, mk_matter, mk_rule

D = Decimal
OCT = lambda day: dt.date(2026, 10, day)  # noqa: E731


def run(lines, rule_type, params=None, matter=None, **kw):
    guide = mk_guideline(mk_rule(rule_type, params, **kw))
    return check_invoice(mk_invoice(lines), guide, matter)


def test_clean_entry_has_no_findings_under_any_single_rule():
    line = mk_line(1)
    matter = mk_matter(TK01="300")
    defaults = {
        "block_billing": {"max_tasks": 1, "min_hours": 0},
        "minimum_increment": {"increment": "0.1"},
        "daily_hour_cap": {"max_hours": 10},
        "vague_description": {"always_phrases": G.DEFAULT_ALWAYS_VAGUE, "bare_phrases": G.DEFAULT_BARE_VAGUE},
        "late_time": {"max_age_days": 60},
        "required_codes": {"require_task": True, "require_activity": True, "require_expense": True},
        "non_billable_task": {"categories": G.DEFAULT_CATEGORY_PHRASES},
        "unapproved_timekeeper": {},
        "rate_above_card": {},
        "duplicate_entries": {},
    }
    for rule_type, params in defaults.items():
        assert run([line], rule_type, params, matter).findings == [], rule_type


def test_minimum_increment():
    result = run([mk_line(1, hours="0.25"), mk_line(2, hours="0.3", narrative="Review lease")], "minimum_increment", {"increment": "0.1"})
    assert [f.line_no for f in result.findings] == [1]
    assert result.findings[0].severity == "reject"


def test_rounding_pattern_needs_enough_entries_and_share():
    def lines(hours):
        return [mk_line(i, hours=h, narrative="Review exhibit %d" % i, date=OCT(i)) for i, h in enumerate(hours, 1)]

    params = {"block": "0.5", "min_entries": 5, "threshold_percent": 80}
    flagged = run(lines(["1.0", "2.0", "0.5", "1.5", "0.7"]), "rounding_pattern", params)  # 4 of 5 = 80%
    assert len(flagged.findings) == 1
    f = flagged.findings[0]
    assert f.line_no is None and f.timekeeper_id == "TK01" and f.severity == "review" and f.amount_at_risk == 0
    assert run(lines(["1.0", "2.0", "0.5", "1.3", "0.7"]), "rounding_pattern", params).findings == []  # 60%
    assert run(lines(["1.0", "2.0", "0.5", "1.5"]), "rounding_pattern", params).findings == []  # too few entries


def test_daily_hour_cap_puts_only_the_excess_at_risk():
    lines = [
        mk_line(1, hours="4.2", narrative="Draft motion for summary judgment"),
        mk_line(2, hours="3.9", narrative="Review deposition transcripts for the motion record"),
        mk_line(3, hours="2.8", narrative="Draft separate statement of undisputed facts"),
        mk_line(4, hours="9.9", narrative="Draft reply brief", date=OCT(7)),
        mk_line(5, hours="6.0", narrative="Draft reply brief", tk="TK02"),
    ]
    result = run(lines, "daily_hour_cap", {"max_hours": 10})
    (f,) = result.findings
    assert f.line_no == 3 and f.amount_at_risk == D("270.00")  # 0.9 h x 300


def test_staffing_matter_limit_and_recorded_approval():
    lines = [mk_line(i, tk="TK0%d" % i, narrative="Review exhibit %d" % i) for i in range(1, 5)]
    assert len(run(lines, "staffing_matter_limit", {"max_timekeepers": 3}).findings) == 1
    assert run(lines[:3], "staffing_matter_limit", {"max_timekeepers": 3}).findings == []
    approved = mk_matter()
    approved["approvals"] = {"staffing": True}
    assert run(lines, "staffing_matter_limit", {"max_timekeepers": 3}, approved).findings == []


def test_staffing_event_limit_keeps_highest_rate_attendee():
    lines = [
        mk_line(1, tk="TK01", rate="500", hours="3.1", narrative="Attend deposition of plant manager"),
        mk_line(2, tk="TK02", rate="300", hours="3.1", narrative="Attend deposition of plant manager"),
        mk_line(3, tk="TK03", rate="300", hours="1.2", narrative="Draft outline for deposition of plant manager"),
        mk_line(4, tk="TK02", rate="300", hours="2.0", narrative="Attend hearing on motion to compel", date=OCT(9)),
    ]
    result = run(lines, "staffing_event_limit", {"max_attendees": 1, "events": ["deposition", "hearing"]})
    (f,) = result.findings
    assert f.line_no == 2 and f.amount_at_risk == D("930.00")
    assert "assumption" in f.explanation


def test_unapproved_timekeeper_and_missing_matter_record():
    lines = [mk_line(1, tk="TK01"), mk_line(2, tk="TK09", narrative="Review lease")]
    result = run(lines, "unapproved_timekeeper", matter=mk_matter(TK01="300"))
    assert [(f.line_no, f.amount_at_risk) for f in result.findings] == [(2, D("360.00"))]
    no_matter = run(lines, "unapproved_timekeeper")
    assert no_matter.findings == [] and "no matter record" in no_matter.not_checked[0]


def test_rate_above_card_puts_the_difference_at_risk():
    result = run([mk_line(1, hours="1.7", rate="240")], "rate_above_card", matter=mk_matter(TK01="225"))
    (f,) = result.findings
    assert f.amount_at_risk == D("25.50") and f.severity == "reduce"
    assert run([mk_line(1, rate="225")], "rate_above_card", matter=mk_matter(TK01="225")).findings == []


def test_rate_increase_notice_period_boundary():
    card = {"approved_rate": "465", "last_billed_rate": "440", "rate_notice_date": "2026-08-20"}
    lines = [
        mk_line(1, rate="465", hours="2.0", date=OCT(18), narrative="Review lease"),  # day 59
        mk_line(2, rate="465", hours="2.0", date=OCT(19), narrative="Review sublease"),  # day 60
        mk_line(3, rate="440", hours="2.0", date=OCT(5), narrative="Review guaranty"),
    ]
    result = run(lines, "rate_increase_notice", {"notice_days": 60}, mk_matter(TK01=card))
    (f,) = result.findings
    assert f.line_no == 1 and f.amount_at_risk == D("50.00") and "2026-10-19" in f.explanation


def test_rate_increase_with_no_notice_on_record():
    card = {"approved_rate": "115", "last_billed_rate": "105"}
    (f,) = run([mk_line(1, rate="115", hours="0.8")], "rate_increase_notice", {"notice_days": 30}, mk_matter(TK01=card)).findings
    assert f.amount_at_risk == D("8.00") and "No notice" in f.explanation


def test_rate_over_the_card_is_reported_once_not_twice():
    guide = mk_guideline(mk_rule("rate_above_card"), mk_rule("rate_increase_notice", {"notice_days": 30}))
    result = check_invoice(mk_invoice([mk_line(1, rate="240")]), guide, mk_matter(TK01="225"))
    assert [f.rule_type for f in result.findings] == ["rate_above_card"]


@pytest.mark.parametrize(
    "narrative,category",
    [
        ("Scanning and bates stamping of medical records", "clerical"),
        ("Training on carrier's e-billing portal", "training"),
        ("Conflicts check for new co-defendant", "conflicts"),
        ("Prepare invoice backup for auditor", "invoice prep"),
    ],
)
def test_non_billable_categories(narrative, category):
    (f,) = run([mk_line(1, narrative=narrative)], "non_billable_task", {"categories": G.DEFAULT_CATEGORY_PHRASES}).findings
    assert category in f.explanation and f.amount_at_risk == D("360.00")


def test_non_billable_phrases_match_whole_words_only():
    line = mk_line(1, narrative="Review restraining order terms with client")  # contains "training" inside a word
    assert run([line], "non_billable_task", {"categories": {"training": ["training"]}}).findings == []


def test_internal_conference_limit_by_phrase_and_by_activity_code():
    lines = [
        mk_line(1, hours="0.8", narrative="Office conference with associate regarding deposition outline"),
        mk_line(2, hours="0.6", narrative="Discuss exhibit list with paralegal", act="A105"),
        mk_line(3, hours="0.3", narrative="Internal conference regarding trial schedule"),
        mk_line(4, hours="0.9", narrative="Telephone conference with client regarding trial schedule", act="A106"),
    ]
    result = run(lines, "internal_conference_limit", {"max_hours_per_entry": "0.3"})
    assert [(f.line_no, f.amount_at_risk) for f in result.findings] == [(1, D("150.00")), (2, D("90.00"))]


def test_research_is_cumulative_and_approval_clears_it():
    lines = [
        mk_line(1, hours="2.4", narrative="Research notice standard", date=OCT(6)),
        mk_line(2, hours="1.8", narrative="Analyze admissibility of prior reports", act="A102", date=OCT(8)),
        mk_line(3, hours="1.0", narrative="Research sanctions standard", date=OCT(9)),
    ]
    result = run(lines, "research_approval", {"max_hours": 3})
    assert [(f.line_no, f.amount_at_risk) for f in result.findings] == [(2, D("360.00")), (3, D("300.00"))]
    matter = mk_matter()
    matter["approvals"] = {"research": True}
    assert run(lines, "research_approval", {"max_hours": 3}, matter).findings == []


def test_travel_at_reduced_rate():
    params = {"billable_percent": 50, "requires_approval": False}
    full = run([mk_line(1, hours="1.4", rate="310", narrative="Travel to deposition")], "travel_time", params, mk_matter(TK01="310"))
    assert full.findings[0].amount_at_risk == D("217.00")
    half = run([mk_line(1, hours="1.4", rate="155", narrative="Travel to deposition")], "travel_time", params, mk_matter(TK01="310"))
    assert half.findings == []


def test_travel_needing_approval():
    params = {"billable_percent": 100, "requires_approval": True}
    line = mk_line(1, hours="1.8", rate="395", narrative="Travel to site inspection")
    (f,) = run([line], "travel_time", params, mk_matter(TK01="395")).findings
    assert f.severity == "reject" and f.amount_at_risk == D("711.00")
    matter = mk_matter(TK01="395")
    matter["approvals"] = {"travel": True}
    assert run([line], "travel_time", params, matter).findings == []


def test_expense_overhead_by_code_and_by_phrase():
    lines = [
        mk_line(1),
        mk_expense(2, "18.40", "Service copies mailed", "E108"),
        mk_expense(3, "45.00", "Database subscription allocation", "E106"),
        mk_expense(4, "386.50", "Deposition transcript", "E115"),
    ]
    params = {"codes": G.DEFAULT_OVERHEAD_CODES, "phrases": G.DEFAULT_OVERHEAD_PHRASES}
    assert [f.line_no for f in run(lines, "expense_overhead", params).findings] == [2, 3]


def test_receipt_threshold_inclusive_exclusive_and_unknown():
    lines = [
        mk_expense(1, "25.00", "Parking", receipt=False),
        mk_expense(2, "24.99", "Parking at court", receipt=False),
        mk_expense(3, "90.00", "Filing fee", receipt=True),
        mk_expense(4, "60.00", "Courier", receipt=None),
    ]
    inclusive = run(lines, "expense_receipt_threshold", {"threshold": "25.00", "inclusive": True})
    assert [f.line_no for f in inclusive.findings] == [1]
    assert "1 expense line(s)" in inclusive.not_checked[0]  # the unknown one is reported, not guessed
    exclusive = run(lines, "expense_receipt_threshold", {"threshold": "25.00", "inclusive": False})
    assert exclusive.findings == []


def test_per_diem_caps():
    lines = [
        mk_expense(1, "84.00", "Lunch during deposition, 1 person", "E111"),
        mk_expense(2, "189.00", "Hotel for site inspection, 2 nights", "E110", units="2"),
        mk_expense(3, "38.00", "Dinner during site inspection", "E111"),
    ]
    result = run(lines, "expense_per_diem", {"caps": {"meal": "50.00", "lodging": "160.00"}})
    assert [(f.line_no, f.amount_at_risk) for f in result.findings] == [(1, D("34.00")), (2, D("58.00"))]


def test_expense_markup_and_unknown_cost():
    lines = [
        mk_expense(1, "96.00", "Outside copy vendor", "E102", cost=D("80.00")),
        mk_expense(2, "50.00", "Courier", "E107", cost=D("50.00")),
        mk_expense(3, "70.00", "Process server", "E113"),
    ]
    result = run(lines, "expense_markup")
    assert [(f.line_no, f.amount_at_risk) for f in result.findings] == [(1, D("16.00"))]
    assert "no cost" in result.not_checked[0]


@pytest.mark.parametrize(
    "narrative,vague",
    [
        ("Attention to file", True),
        ("Attention to file regarding discovery", True),
        ("Review documents", True),
        ("Review documents.", True),
        ("Emails", True),
        ("Review documents produced by vendor in response to subpoena", False),
        ("Draft joint case management statement", False),
    ],
)
def test_vague_descriptions(narrative, vague):
    params = {"always_phrases": G.DEFAULT_ALWAYS_VAGUE, "bare_phrases": G.DEFAULT_BARE_VAGUE, "min_words": 3}
    findings = run([mk_line(1, narrative=narrative)], "vague_description", params).findings
    assert bool(findings) is vague
    if vague:
        assert "Do not fill this in for them" in findings[0].suggested_fix


def test_required_codes():
    lines = [
        mk_line(1, act=""),
        mk_line(2, task="", narrative="Review lease"),
        mk_line(3, narrative="Review sublease"),
        mk_expense(4, code=""),
    ]
    everything = {"require_task": True, "require_activity": True, "require_expense": True}
    assert [f.line_no for f in run(lines, "required_codes", everything).findings] == [1, 2, 4]
    task_only = {"require_task": True, "require_activity": False, "require_expense": False}
    assert [f.line_no for f in run(lines, "required_codes", task_only).findings] == [2]


def test_code_table_check_is_review_only_and_off_by_default():
    params = {"require_task": True, "require_activity": True, "require_expense": False}
    line = mk_line(1, task="L999")
    table = {"task": {"L310"}, "activity": {"A103"}, "expense": set()}
    guide = mk_guideline(mk_rule("required_codes", params))
    assert check_invoice(mk_invoice([line]), guide, code_table=table).findings == []
    guide = mk_guideline(mk_rule("required_codes", dict(params, check_against_sample_table=True)))
    (f,) = check_invoice(mk_invoice([line]), guide, code_table=table).findings
    assert f.severity == "review" and f.amount_at_risk == 0 and "may be a valid code" in f.explanation


def test_late_time_boundary():
    lines = [
        mk_line(1, date=dt.date(2026, 9, 6), narrative="Review lease"),  # 60 days
        mk_line(2, date=dt.date(2026, 9, 5), narrative="Review sublease"),  # 61 days
    ]
    (f,) = run(lines, "late_time", {"max_age_days": 60}).findings
    assert f.line_no == 2 and "61 days" in f.explanation


def test_budget_cap_and_phase_cap():
    lines = [mk_line(1, hours="10", rate="300", task="L310"), mk_line(2, hours="5", rate="300", task="L210", narrative="Draft answer")]
    matter = mk_matter()
    matter["budget"] = {"cap": "60000.00", "billed_to_date": "57350.00", "phases": {
        "L300": {"cap": "20000.00", "billed_to_date": "17640.00"},
        "L200": {"cap": "15000.00", "billed_to_date": "4000.00"},
    }}
    (f,) = run(lines, "budget_cap", matter=matter).findings
    assert f.line_no is None and f.amount_at_risk == D("1850.00")
    (p,) = run(lines, "phase_cap", matter=matter).findings
    assert p.amount_at_risk == D("640.00") and "L300" in p.explanation
    matter["budget"]["billed_to_date"] = "55500.00"  # exactly at the cap
    assert run(lines, "budget_cap", matter=matter).findings == []
    assert "no budget cap" in run(lines, "budget_cap", matter=mk_matter()).not_checked[0]


def test_duplicates_flag_the_later_entry_only():
    lines = [
        mk_line(1), mk_line(2), mk_line(3, tk="TK02"), mk_line(4, hours="1.3"),
        mk_line(5, date=OCT(7)), mk_line(6, narrative="Draft responses to SECOND set of interrogatories."),
    ]
    result = run(lines, "duplicate_entries")
    assert [f.line_no for f in result.findings] == [2, 6]
    assert "line 1" in result.findings[0].explanation


AI = {"disclosure_marker": "[AI-assisted]", "ai_terms": G.DEFAULT_AI_TERMS}


def test_ai_disclosure_rule():
    lines = [
        mk_line(1, narrative="Draft claim chart", ai_assisted=True),
        mk_line(2, narrative="Draft responses to contentions [AI-assisted]", ai_assisted=True),
        mk_line(3, narrative="Review output of generative AI tool for prior art search", ai_assisted=False),
        mk_line(4, narrative="Review email chain regarding retainer", ai_assisted=False),  # "ai" inside words only
    ]
    result = run(lines, "ai_disclosure_required", AI)
    assert [f.line_no for f in result.findings] == [1, 3]
    assert result.not_checked == []


def test_ai_disclosure_says_when_the_file_has_no_flag():
    result = run([mk_line(1, narrative="Draft claim chart")], "ai_disclosure_required", AI)
    assert result.findings == [] and "no AI-assisted flag" in result.not_checked[0]


def test_ai_nonpayable_task_needs_both_ai_and_listed_task():
    params = dict(AI, task_phrases=["summarize", "first-pass document review"])
    lines = [
        mk_line(1, narrative="Summarize deposition transcript of lead engineer [AI-assisted]", ai_assisted=True),
        mk_line(2, narrative="Summarize deposition transcript of chief engineer", ai_assisted=False),
        mk_line(3, narrative="Draft claim chart [AI-assisted]", ai_assisted=True),
    ]
    assert [f.line_no for f in run(lines, "ai_nonpayable_task", params).findings] == [1]


def test_arithmetic_findings_are_built_in_and_cite_no_client_rule():
    inv = mk_invoice([mk_line(1, hours="0.9", rate="110", amount="109.00")], total="209.00")
    result = check_invoice(inv, mk_guideline())
    assert sorted(f.rule_id for f in result.findings) == ["ARITH-LINE", "ARITH-TOTAL"]
    assert all("not a client rule" in f.source_ref for f in result.findings)
    assert {f.line_no: f.amount_at_risk for f in result.findings} == {1: D("10.00"), None: D("100.00")}


def test_guideline_for_another_client_is_refused():
    with pytest.raises(ValueError, match="is for client"):
        check_invoice(mk_invoice([mk_line(1)], client="other"), mk_guideline())


def test_every_finding_carries_rule_quote_explanation_and_fix(results):
    count = 0
    for result in results:
        for f in result.findings:
            count += 1
            assert f.rule_id and f.source_quote and f.source_ref and f.explanation and f.suggested_fix
            assert f.severity in G.SEVERITIES
    assert count > 60
