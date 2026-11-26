"""Round 2 tests: wider wording, harder block-billing cases, new document layouts, the held-out scorer.

All text here was invented for these tests. None of it is copied from the held-out sets.
"""
import datetime as dt
import os
import re
import sys

import pytest

from billcheck import intake
from billcheck import lexicon as LX
from billcheck.blockbilling import count_tasks
from billcheck.engine import check_invoice
from conftest import ROOT, mk_expense, mk_guideline, mk_invoice, mk_line, mk_matter, mk_rule

sys.path.insert(0, ROOT)
import score_heldout  # noqa: E402


def types_found(lines, *rules, matter=None):
    result = check_invoice(mk_invoice(lines), mk_guideline(*rules), matter)
    return sorted({(f.line_no, f.rule_type) for f in result.findings})


# ---------------------------------------------------------------- travel


@pytest.mark.parametrize("narrative", [
    "Drive to county courthouse for motion hearing",
    "Flight to regional office for witness interviews",
    "Return trip from site inspection",
    "Travel to and from deposition of plant engineer",
])
def test_travel_in_ordinary_words(narrative):
    assert LX.is_travel(narrative)


@pytest.mark.parametrize("narrative", [
    "Review client travel policy and expense records",
    "Draft letter regarding witness travel arrangements",
    "Drive settlement discussions forward with opposing counsel by letter",
])
def test_travel_as_a_subject_is_not_travel_time(narrative):
    assert not LX.is_travel(narrative)


# ---------------------------------------------------------------- research


@pytest.mark.parametrize("narrative", [
    "Research statute of limitations for indemnity claims",
    "Review case law on waiver of subrogation",
    "Analyze appellate decisions on notice requirements",
])
def test_research_in_ordinary_words(narrative):
    assert LX.research_match(narrative)


@pytest.mark.parametrize("narrative", [
    "Prepare table of authorities for reply brief",
    "Review plaintiff's document production for privilege",
])
def test_not_research(narrative):
    assert not LX.research_match(narrative)


def test_research_over_the_limit_is_flagged_when_worded_without_the_word_research():
    rule = mk_rule("research_approval", {"max_hours": "2"})
    lines = [mk_line(1, hours="3.5", narrative="Review case law on waiver of subrogation"),
             mk_line(2, hours="3.5", narrative="Review plaintiff's document production for privilege")]
    assert types_found(lines, rule) == [(1, "research_approval")]


# ---------------------------------------------------------------- internal conferences


def test_internal_conference_recognised_from_the_matter_roster():
    rule = mk_rule("internal_conference_limit", {"max_hours_per_entry": "0.5"})
    matter = mk_matter(TK01="300", TK02="250")
    matter["timekeepers"]["TK02"]["name"] = "Pell Ardwick"
    lines = [
        mk_line(1, hours="1.2", narrative="Meet with P. Ardwick regarding deposition outline", name="Test Person"),
        mk_line(2, hours="1.2", narrative="Meet with claims adjuster regarding deposition outline"),
        mk_line(3, hours="1.2", narrative="Team meeting on trial strategy"),
        mk_line(4, hours="0.4", narrative="Team meeting on trial strategy"),
    ]
    assert types_found(lines, rule, matter=matter) == [(1, "internal_conference_limit"), (3, "internal_conference_limit")]


def test_meeting_with_an_outside_person_is_not_internal():
    never = re.compile(r"(?!x)x")
    assert not LX.internal_conference_match("Conference with client and team regarding budget", "", never, None)
    assert LX.internal_conference_match("Conference with case team regarding budget", "", never, None)


# ---------------------------------------------------------------- attendance


def test_attendance_must_be_the_activity_not_the_subject():
    rx = LX.attendance_regex("deposition")
    assert rx.search("Attend deposition of plant manager")
    assert rx.search("Appear at and defend deposition of site supervisor")
    assert not rx.search("Prepare outline for deposition of plant manager")
    assert not rx.search("Review transcript after attending to pre-deposition exhibits")


# ---------------------------------------------------------------- non-billable categories


@pytest.mark.parametrize("category, narrative", [
    ("clerical", "Scan and save exhibits to the document system"),
    ("clerical", "Assemble and label hearing binders"),
    ("training", "Bring new associate up to speed on case background"),
    ("conflicts", "Run conflict search on new parties"),
    ("invoice_prep", "Revise September bill at client request"),
])
def test_non_billable_work_in_ordinary_words(category, narrative):
    assert LX.CATEGORY_WIDE[category].search(narrative)


@pytest.mark.parametrize("phrase, narrative", [
    ("filing", "Draft opposition and review court filing by co-defendant"),
    ("training", "Review training records produced by employer"),
    ("calendaring", "Analyze calendaring order and advise client of deadlines"),
])
def test_listed_phrase_guards(phrase, narrative):
    assert not LX.listed_phrase_allowed(phrase, narrative)


def test_substantive_work_about_training_is_not_flagged():
    rule = mk_rule("non_billable_task", {"categories": {"training": ["training"], "clerical": ["filing"]}})
    lines = [mk_line(1, narrative="Review training records produced by employer"),
             mk_line(2, narrative="Attend firm training on new document system")]
    assert types_found(lines, rule) == [(2, "non_billable_task")]


# ---------------------------------------------------------------- expenses, AI, vague


def test_overhead_expansion_needs_the_base_phrase_on_the_client_list():
    assert not LX.overhead_wide_match("Deposition transcript", ["postage"])


def test_lodging_and_meal_words():
    assert LX.LODGING.search("Hotel, two nights, for trial")
    assert LX.MEAL.search("Working dinner with expert")
    assert not LX.MEAL.search("Deposition transcript")


def test_ai_use_in_ordinary_words():
    assert LX.AI_WIDE.search("Used generative AI tool to prepare first draft of chronology")
    assert not LX.AI_WIDE.search("Email to client regarding retainer")


@pytest.mark.parametrize("narrative", ["Review documents", "Work on matter", "Attention to file", "Review and analyze correspondence"])
def test_generic_narratives_are_vague(narrative):
    assert LX.vague_wide_match(narrative)


@pytest.mark.parametrize("narrative", [
    "Review lease amendment for assignment clause",
    "Draft reply brief on standing",
])
def test_specific_narratives_are_not_vague(narrative):
    assert not LX.vague_wide_match(narrative)


def test_ai_rule_reports_cannot_be_checked_when_the_file_has_no_flag():
    rule = mk_rule("ai_disclosure_required", {"disclosure_marker": "[AI-assisted]", "ai_terms": ["ai tool"]})
    result = check_invoice(mk_invoice([mk_line(1)]), mk_guideline(rule))
    assert not result.findings
    assert any("AI" in note or "ai" in note for note in result.not_checked)


# ---------------------------------------------------------------- block billing hard cases


@pytest.mark.parametrize("narrative, tasks", [
    ("Prepare exhibit list and e-file with clerk", 2),
    ("Negotiate protective order terms with opposing counsel and brief the client on outcome", 2),
    ("Draft motion and draft proposed order", 2),
    ("Called adjuster about reserves, then outlined mediation statement", 2),
    ("Reviewed lease, amendment and estoppel certificate", 1),
    ("Discuss settlement range with client and advise on next steps", 1),
    ("Review and respond to email chain from co-counsel", 1),
])
def test_block_billing_hard_cases(narrative, tasks):
    assert count_tasks(narrative) == tasks


# ---------------------------------------------------------------- intake: new layouts

GRID = """TALLOWMERE FREIGHT - OUTSIDE COUNSEL TERMS
Page 1 of 1

No.  Topic              What we require                                                        If not followed
---  -----------------  ---------------------------------------------------------------------  ------------------
1    Time units         Record time in six-minute units.                                       Entry reduced
2    Task detail        Do not bundle several tasks into one entry; state each task separately Entry returned
                        with its own time.
3    Daily limit        No individual may bill in excess of nine (9) hours in a day.           Excess not paid
4    Depositions        We pay for one (1) attorney at any deposition or hearing.              Others not paid
5    Team size          Limit of five (5) timekeepers per matter.                              Queried
6    Research           Research beyond two (2) hours needs our consent first.                 Excess not paid
7    Travel             Transit time is paid at half the standard rate.                        Reduced
8    Receipts           Receipts are needed for any expense in excess of $50.                  Not reimbursed
9    Old time           Time more than ninety (90) days old will not be paid.                  Not paid
10   Invoices           Send invoices monthly, within thirty (30) days of month end.           -
"""

CLAUSES = """SCHEDULE C - FEES AND EXPENSES

- 1 -

(a) Counsel shall record time in increments of one-tenth (0.1) of an hour, and no entry shall aggregate multiple tasks.

(b) Only those persons identified in the staffing plan are authorised to bill, and no person shall bill at a rate above the rate sheet annexed hereto.

(c) Counsel shall give not less than sixty (60) days written notice of any rate increase.

(d) Intra-office conferences shall not exceed one-half hour per entry. Clerical and secretarial tasks, conflicts clearance and the preparation of invoices are not billable.

- 2 -

(e) Meals shall not exceed forty dollars ($40.00) per person per day and lodging shall not exceed two hundred dollars ($200.00) per night. Expenses shall be passed through at actual cost, without mark-up.

(f) Firm overhead is not reimbursable, including word processing, postage and local telephone.

(g) Total fees shall not exceed the maximum compensation stated in the engagement letter. Fees for a phase shall not exceed the budget assigned to that phase.

(h) Each time entry must carry a task code and an activity code. The same work shall not be billed twice.

(i) Counsel shall maintain professional liability insurance of not less than five million dollars ($5,000,000).
"""

EMAIL = """Hi Renny,

Thanks for taking this on. A few things about how we like bills done.

Please don't lump things together - if you did three things, give me three entries. I also can't do anything with entries that just say "work on file" or "attention to matter"; they are too vague and I'll send them back.

We keep time in quarter-hours here, so nothing smaller than that please. If anyone on your team uses AI tools on our work I need to see it flagged with "(AI)" in the entry, and we won't pay for AI summaries of documents.

I would rather not pay for internal meetings among your own team over half an hour. And please don't bill us for getting new associates up to speed - training is not billable.

Copies are 10 cents a page. Let's catch up Thursday.

Dane
"""


def proposed(text):
    return {r["type"]: r for r in intake.propose_rules(text, "x")["rules"]}


def test_intake_reads_a_grid_with_a_consequences_column():
    rules = proposed(GRID)
    assert sorted(rules) == sorted([
        "minimum_increment", "block_billing", "daily_hour_cap", "staffing_event_limit", "staffing_matter_limit",
        "research_approval", "travel_time", "expense_receipt_threshold", "late_time",
    ])
    assert rules["minimum_increment"]["params"] == {"increment": "0.1"}
    assert rules["minimum_increment"]["source_quote"] == "Record time in six-minute units."
    assert rules["minimum_increment"]["source_ref"] == "Time units, page 1"
    assert rules["block_billing"]["source_quote"].endswith("separately with its own time.")
    assert rules["block_billing"]["severity"] == "reject"  # from the consequences column
    assert rules["staffing_matter_limit"]["severity"] == "review"
    assert rules["daily_hour_cap"]["params"] == {"max_hours": "9"}
    assert rules["staffing_event_limit"]["params"] == {"max_attendees": 1, "events": ["deposition", "hearing"]}
    assert rules["staffing_matter_limit"]["params"] == {"max_timekeepers": 5}
    assert rules["research_approval"]["params"] == {"max_hours": "2"}
    assert rules["travel_time"]["params"] == {"billable_percent": 50, "requires_approval": False}
    assert rules["expense_receipt_threshold"]["params"] == {"threshold": "50", "inclusive": False}
    assert rules["late_time"]["params"] == {"max_age_days": 90}


def test_intake_reads_lettered_clauses_with_numbers_in_words():
    rules = proposed(CLAUSES)
    assert sorted(rules) == sorted([
        "block_billing", "minimum_increment", "unapproved_timekeeper", "rate_above_card", "rate_increase_notice",
        "internal_conference_limit", "non_billable_task", "expense_per_diem", "expense_markup", "expense_overhead",
        "budget_cap", "phase_cap", "required_codes", "duplicate_entries",
    ])
    assert rules["rate_increase_notice"]["params"] == {"notice_days": 60}
    assert rules["internal_conference_limit"]["params"] == {"max_hours_per_entry": "0.5"}
    assert sorted(rules["non_billable_task"]["params"]["categories"]) == ["clerical", "conflicts", "invoice_prep"]
    assert rules["expense_per_diem"]["params"] == {"caps": {"meal": "40.00", "lodging": "200.00"}}
    assert rules["required_codes"]["params"] == {"require_task": True, "require_activity": True, "require_expense": False}
    assert "local telephone" in rules["expense_overhead"]["params"]["phrases"]
    assert rules["budget_cap"]["source_ref"] == "clause g, SCHEDULE C - FEES AND EXPENSES, page 2"


def test_intake_reads_a_chatty_email_and_marks_preferences():
    rules = proposed(EMAIL)
    assert sorted(rules) == sorted([
        "block_billing", "vague_description", "minimum_increment", "ai_disclosure_required", "ai_nonpayable_task",
        "internal_conference_limit", "non_billable_task",
    ])
    assert rules["minimum_increment"]["params"] == {"increment": "0.25"}
    assert rules["ai_disclosure_required"]["params"]["disclosure_marker"] == "(AI)"
    assert rules["ai_nonpayable_task"]["params"]["disclosure_marker"] == "(AI)"
    assert "work on file" in rules["vague_description"]["params"]["bare_phrases"] + rules["vague_description"]["params"]["always_phrases"]
    assert intake.PREFERENCE_NOTE in rules["internal_conference_limit"]["notes"]
    assert intake.PREFERENCE_NOTE not in rules["block_billing"]["notes"]
    assert list(rules["non_billable_task"]["params"]["categories"]) == ["training"]


@pytest.mark.parametrize("sentence", [
    "Copies are charged at 10 cents a page.",
    "Send invoices monthly, within thirty (30) days of month end.",
    "Invoices will be paid within 45 days of receipt.",
    "Counsel shall maintain professional liability insurance of not less than five million dollars ($5,000,000).",
    "This policy does not impose a ceiling on the hours a lawyer may work in a day.",
    "Please send a budget estimate for each new matter.",
])
def test_sentences_that_are_not_rules_are_not_proposed(sentence):
    assert intake.propose_rules("1. Terms\n\n" + sentence + "\n")["rules"] == []


@pytest.mark.parametrize("text, expected", [
    ("four (4) hours", "4 hours"),
    ("forty dollars ($40.00)", "$40.00"),
    ("seventy-five days", "75 days"),
    ("one hundred and twenty days", "120 days"),
    ("six-minute units", "0.1 hour units"),
    ("half the standard rate", "50% of the standard rate"),
    ("quarter-hour increments", "0.25 hour increments"),
])
def test_number_words_are_normalised_for_matching(text, expected):
    assert " ".join(intake.normalise(text).split()) == expected


def test_every_new_layout_candidate_is_only_a_proposal():
    for text in (GRID, CLAUSES, EMAIL):
        for rule in intake.propose_rules(text, "x")["rules"]:
            assert rule["status"] == "proposed" and rule["confidence"] == "proposed, needs confirmation"
            if text is GRID:  # a wrapped table cell is rejoined, so compare word by word
                assert set(rule["source_quote"].split()) <= set(text.split())
            else:
                assert rule["source_quote"] in " ".join(text.split())


# ---------------------------------------------------------------- held-out scorer


def _result(lines, *rules):
    return check_invoice(mk_invoice(lines), mk_guideline(*rules))


def _key(planted, must_not=(), alternates=(), hard=()):
    return {
        "planted": planted, "must_not_flag": {"INV-T-1": list(must_not)}, "alternate_lines": list(alternates),
        "hard_cases_clean": list(hard), "not_enforced": [],
    }


def _planted(line, rule_type, **extra):
    row = {"invoice_id": "INV-T-1", "line_no": line, "timekeeper_id": "TK01", "rule_type": rule_type, "rule_id": "T",
           "expected_status": "open", "difficulty": "easy"}
    row.update(extra)
    return row


def test_scorer_honours_alternate_lines_before_must_not_flag():
    rule = mk_rule("staffing_event_limit", {"max_attendees": 1, "events": ["deposition"]})
    lines = [mk_line(1, tk="TK01", narrative="Attend deposition of plant manager"),
             mk_line(2, tk="TK02", narrative="Attend deposition of plant manager")]
    result = _result(lines, rule)
    flagged = {f.line_no for f in result.findings}
    assert len(flagged) == 1
    other = ({1, 2} - flagged).pop()
    key = _key([_planted(other, "staffing_event_limit")], must_not=sorted(flagged),
               alternates=[{"invoice_id": "INV-T-1", "line_no": other, "also_acceptable_lines": sorted(flagged)}])
    score = score_heldout.score_engine(key, {"INV-T-1": result})
    assert score["planted_found"] == 1 and score["false_positive_findings"] == 0


def test_scorer_counts_a_finding_on_a_must_not_flag_line_as_a_false_positive():
    rule = mk_rule("vague_description", {"always_phrases": ["attention to"], "bare_phrases": [], "min_words": 3})
    result = _result([mk_line(1, narrative="Attention to file")], rule)
    score = score_heldout.score_engine(_key([], must_not=[1]), {"INV-T-1": result})
    assert score["false_positive_findings"] == 1 and score["must_not_flag_lines_flagged"] == 1


def test_scorer_excludes_schema_limit_items_from_recall_and_reports_them():
    result = _result([mk_line(1)])
    key = _key([_planted(1, "staffing_event_limit", schema_limit=True), _planted(1, "late_time")])
    score = score_heldout.score_engine(key, {"INV-T-1": result})
    assert score["planted_total"] == 2 and score["planted_counted"] == 1
    assert len(score["excluded_from_recall"]) == 1 and score["planted_missed"] == 1


def test_scorer_does_not_judge_a_different_rule_on_a_planted_line():
    vague = mk_rule("vague_description", {"always_phrases": ["attention to"], "bare_phrases": [], "min_words": 3})
    late = mk_rule("late_time", {"max_age_days": 10})
    result = _result([mk_line(1, narrative="Attention to file", date=dt.date(2026, 9, 1))], vague, late)
    score = score_heldout.score_engine(_key([_planted(1, "late_time")]), {"INV-T-1": result})
    assert score["planted_found"] == 1 and score["unjudged_extra_findings_on_planted_lines"] == 1
    assert score["false_positive_findings"] == 0


def test_scorer_compares_category_names_not_keyword_lists():
    assert score_heldout._same({"clerical": ["scanning"], "training": ["training"]}, ["training", "clerical"])
    assert not score_heldout._same({"clerical": ["scanning"]}, ["training", "clerical"])
    assert score_heldout._same("0.50", "0.5") and not score_heldout._same(True, 1)


def test_first_run_result_is_kept():
    path = os.path.join(ROOT, "heldout_results", "batch_a_first_run.json")
    assert os.path.isfile(path)
