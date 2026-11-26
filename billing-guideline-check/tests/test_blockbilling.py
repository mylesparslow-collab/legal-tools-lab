import pytest

from billcheck.blockbilling import analyze, count_tasks
from billcheck.engine import check_invoice
from conftest import mk_guideline, mk_invoice, mk_line, mk_rule

ONE_TASK = [
    # a single task described with semicolons
    "Draft motion to compel; sections on relevance; proportionality; and meet-and-confer history",
    # lists of documents
    "Review plaintiff's production: invoices, purchase orders, and shipping records",
    "Review invoices, purchase orders, and shipping records produced by plaintiff",
    "Review call logs, meeting notes and research memo from prior counsel",
    # "and" inside one task
    "Review and revise draft protective order",
    "Research and analyze case law on spoliation sanctions",
    "Telephone conference with client and adjuster regarding settlement authority",
    "Meet with client and discuss settlement posture",
    "Prepare for and attend deposition of plant manager",
    "Draft and file notice of appearance",
    # abbreviations and initials with full stops
    "Telephone conference with J. Okonjo regarding exhibits",
    "Review 2.5 GB document production for privilege",
]

BLOCKS = [
    ("Review deposition transcript of store manager; draft summary for adjuster; telephone conference with adjuster regarding reserves", 3),
    ("Draft discovery responses, call with client regarding document collection, and research privilege issues", 3),
    ("Review file. Draft status report to client. Email to adjuster regarding trial date.", 3),
    ("Draft motion to compel; draft proposed order", 2),
    ("Draft motion to dismiss and research statute of limitations", 2),
    ("Email to agency counsel regarding site access; review reply", 2),
]


@pytest.mark.parametrize("narrative", ONE_TASK)
def test_hard_cases_count_as_one_task(narrative):
    result = analyze(narrative)
    assert result["task_count"] == 1, result


@pytest.mark.parametrize("narrative,expected", BLOCKS)
def test_block_billed_narratives_are_counted(narrative, expected):
    assert count_tasks(narrative) == expected


def test_analysis_explains_each_decision():
    result = analyze("Review and revise order; sections on scope; email to client regarding draft")
    assert result["task_count"] == 2
    notes = " ".join(result["notes"])
    assert "shares its object" in notes
    assert "does not begin with a task word" in notes
    assert 'begins with the task word "email to"' in notes


def test_detected_tasks_are_pieces_of_the_original_text_only():
    narrative = "Review deposition transcript of store manager; draft summary for adjuster; telephone conference with adjuster regarding reserves"
    for task in analyze(narrative)["tasks"]:
        assert task in narrative


def _guide(min_hours):
    return mk_guideline(mk_rule("block_billing", {"max_tasks": 1, "min_hours": min_hours}))


def test_threshold_exempts_short_entries():
    narrative = "Email to opposing counsel regarding extension; review stipulation"
    short = mk_invoice([mk_line(1, hours="0.8", narrative=narrative)])
    longer = mk_invoice([mk_line(1, hours="1.1", narrative=narrative)])
    assert check_invoice(short, _guide("1.0")).findings == []
    assert len(check_invoice(longer, _guide("1.0")).findings) == 1
    assert len(check_invoice(short, _guide(0)).findings) == 1


def test_finding_prompts_a_split_and_never_rewrites_or_allocates_time():
    narrative = "Review lease; draft demand letter to lessor"
    inv = mk_invoice([mk_line(1, hours="2.0", narrative=narrative)])
    (f,) = check_invoice(inv, _guide(0)).findings
    assert inv.lines[0].narrative == narrative  # invoice untouched
    assert f.entry_narrative == narrative
    assert "(1) Review lease." in f.suggested_fix and "(2) draft demand letter to lessor." in f.suggested_fix
    assert "does not rewrite" in f.suggested_fix
    assert "1.0" not in f.suggested_fix  # no proposed time split
    assert f.amount_at_risk == inv.lines[0].amount


def test_every_clean_pool_narrative_is_one_task():
    import generate_data

    for narrative, _, _ in generate_data.POOL:
        assert count_tasks(narrative) == 1, narrative
