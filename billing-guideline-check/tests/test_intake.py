import os

import pytest

from billcheck import guidelines as G
from billcheck import intake
from billcheck.engine import check_invoice
from billcheck.model import dec
from conftest import DATA, mk_invoice, mk_line

DOC = """SAMPLE CLIENT
Billing terms

[Page 1]

1. Time

Time must be recorded in increments of 0.1 hour. Block billing is not permitted. The Company will not pay for more than 10 hours billed by one timekeeper in a single day.

[Page 2]

2.1 Other terms

Time entries more than 60 days old on the invoice date will not be paid. A receipt must accompany any single expense of $25.00 or more. Travel time is billed at 50% of the approved hourly rate. Duplicate entries will be rejected.
"""


def proposals(text=DOC):
    return intake.propose_rules(text, "sample", "Sample Client")


def by_type(text=DOC):
    return {r["type"]: r for r in proposals(text)["rules"]}


def test_every_candidate_is_proposed_and_says_it_needs_confirmation():
    rules = proposals()["rules"]
    assert len(rules) == 7
    for rule in rules:
        assert rule["status"] == "proposed"
        assert rule["confidence"] == "proposed, needs confirmation"
        assert "confirmed_by" not in rule


def test_candidates_carry_the_exact_sentence_and_its_section_and_page():
    rules = by_type()
    assert rules["daily_hour_cap"]["source_quote"] == "The Company will not pay for more than 10 hours billed by one timekeeper in a single day."
    assert rules["daily_hour_cap"]["source_ref"] == "1. Time, page 1"
    assert rules["late_time"]["source_ref"] == "2.1 Other terms, page 2"


@pytest.mark.parametrize(
    "rule_type,param,expected",
    [
        ("minimum_increment", "increment", "0.1"),
        ("daily_hour_cap", "max_hours", "10"),
        ("late_time", "max_age_days", "60"),
        ("expense_receipt_threshold", "threshold", "25.00"),
        ("travel_time", "billable_percent", "50"),
        ("block_billing", "min_hours", "0"),
    ],
)
def test_numbers_are_extracted_from_the_sentence(rule_type, param, expected):
    assert dec(by_type()[rule_type]["params"][param]) == dec(expected)


def test_intake_output_is_a_valid_guideline_file():
    assert G.validate(proposals()) == []


def test_unconfirmed_rules_are_not_enforced():
    """The whole intake output, loaded as a guideline, must produce no rule findings."""
    guide = G.from_dict(dict(proposals(), client_id="testco"))
    bad = mk_invoice([
        mk_line(1, hours="0.25"),  # breaks the increment rule
        mk_line(2, hours="11.5", narrative="Review lease; draft demand letter"),  # block billed, over daily cap
        mk_line(3, hours="11.5", narrative="Review lease; draft demand letter"),  # duplicate
    ])
    result = check_invoice(bad, guide)
    assert result.findings == []
    assert result.rules_run == []
    assert len(result.rules_not_enforced) == 7


def test_confirming_one_rule_enforces_only_that_rule():
    data = dict(proposals(), client_id="testco")
    for rule in data["rules"]:
        if rule["type"] == "minimum_increment":
            rule.update(status="confirmed", confirmed_by="billing manager", confirmed_on="2026-09-15")
    guide = G.from_dict(data)
    bad = mk_invoice([mk_line(1, hours="0.25"), mk_line(2, hours="11.5", narrative="Review lease; draft demand letter")])
    result = check_invoice(bad, guide)
    assert [f.rule_type for f in result.findings] == ["minimum_increment"]
    assert len(result.rules_run) == 1


def test_sample_proposed_rule_is_not_enforced_until_confirmed(by_invoice, answer_key, guides, data_dir):
    result = by_invoice["INV-P-5001"]
    assert result.rules_not_enforced == ["PBS-LATE-01"]
    (case,) = answer_key["not_enforced"]
    assert not [f for f in result.findings if f.line_no == case["line_no"]]
    assert not [f for f in result.findings if f.rule_type == "late_time"]
    # the same invoice with the rule confirmed does flag the old entry
    data = guides["pellwick"].to_dict()
    for rule in data["rules"]:
        if rule["rule_id"] == "PBS-LATE-01":
            rule.update(status="confirmed", confirmed_by="billing manager", confirmed_on="2026-11-20")
    confirmed = check_invoice(result.invoice, G.from_dict(data), result.matter)
    assert case["line_no"] in {f.line_no for f in confirmed.findings if f.rule_type == "late_time"}


def test_sentence_splitting_keeps_decimals_and_quotes_together():
    text = 'Entries like "review documents" are not enough. Bill in 0.1 hour units. Costs over $25.00 need a receipt.'
    assert intake.split_sentences(text) == [
        'Entries like "review documents" are not enough.',
        "Bill in 0.1 hour units.",
        "Costs over $25.00 need a receipt.",
    ]


def test_paragraph_reference_when_document_has_no_headings():
    with open(os.path.join(DATA, "guideline_docs", "pellwick.txt"), "r", encoding="utf-8") as handle:
        text = handle.read()
    assert intake.locate(text, "Send a receipt with any expense over $75.00.") == "page 1, paragraph 4"
    rule = by_type(text)["expense_receipt_threshold"]
    assert rule["params"]["inclusive"] is False


def test_quoted_vague_phrases_are_picked_up():
    text = '1. Narratives\n\nVague entries such as "attention to file" or "checked emails" will not be paid.\n'
    params = by_type(text)["vague_description"]["params"]
    assert "attention to file" in params["always_phrases"]
    assert "checked emails" in params["bare_phrases"]


@pytest.mark.parametrize("client", ["brackenmoor", "luminqa", "ostervane", "pellwick", "quillfeather"])
def test_intake_finds_the_sample_rules_in_the_sample_documents(client, guides):
    """The patterns were written alongside these five documents, so this is a regression check, not a recall claim."""
    with open(os.path.join(DATA, "guideline_docs", client + ".txt"), "r", encoding="utf-8") as handle:
        proposed = intake.propose_rules(handle.read(), client)
    summary = intake.compare_with_guideline(proposed, guides[client])
    assert summary["missed"] == []
    assert summary["extra"] == 0


@pytest.mark.parametrize(
    "sentence",
    [
        "Please keep your time in six-minute units.",
        "Lawyers should not record several activities in a single narrative.",
        "Anything billed over two months late is at your own risk.",
    ],
)
def test_known_gap_reworded_sentences_are_missed(sentence):
    """Documents the limit of pattern matching: a person must still read the whole document."""
    assert proposals("1. Terms\n\n" + sentence + "\n")["rules"] == []
