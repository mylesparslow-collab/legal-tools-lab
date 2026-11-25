"""Statement builder: sections, fallbacks, draft options, approval, length limit, variants."""
import copy
import re

import pytest
from conftest import AS_OF, all_text, printed, tool

from statement import render
from statement.build import (EMPTY_SECTION, PROPOSAL_MAX, WORD_LIMIT, BuildError, build_statement,
                             statement_word_count)
from statement.model import InputError, load_options


def test_fixed_sections_in_order(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    assert [s["id"] for s in stmt["sections"]] == ["use", "purpose", "protect", "check", "billing", "terms", "contact"]


def test_clean_registry_prints_strongest_variants(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    p = printed(stmt)
    assert stmt["downgraded"] == [] and stmt["omitted"] == []
    assert p["no_training"]["variant_id"] == "all_tools"
    assert p["testing"]["variant_id"] == "every_in_use"
    assert p["review_cycle"]["text"].startswith("We review tools every 180 days.")
    assert p["client_terms_check"]["variant_id"] == "each_recent"


def test_every_printed_sentence_is_supported_or_policy(clean, gaps, inputs, inputs_gaps):
    for reg, inp in ((clean, inputs), (gaps, inputs_gaps)):
        for s in printed(build_statement(reg, inp, AS_OF)).values():
            if s["kind"] in ("evidence", "record"):
                assert s["evidence"]["status"] == "SUPPORTED", s["claim_id"]
            else:
                assert s["kind"] == "draft_option"


def test_gaps_registry_downgrades_and_omits(gaps, inputs_gaps):
    stmt = build_statement(gaps, inputs_gaps, AS_OF)
    p = printed(stmt)
    down = {d["claim_id"]: d["printed_variant"] for d in stmt["downgraded"]}
    assert down == {"tools_in_use": "count_only", "named_owner": "count", "no_training": "count",
                    "provider_agreements": "count", "human_review": "count", "testing": "every_firmwide",
                    "review_cycle": "count", "client_terms_check": "count"}
    assert {o["claim_id"] for o in stmt["omitted"]} == {"uses", "no_sensitive_data", "court_citations"}
    assert "court_citations" not in p and "no_sensitive_data" not in p
    assert p["no_training"]["text"].startswith("Three of four tools approved for client confidential information do not")


def test_downgrade_records_the_breaking_entry(gaps, inputs_gaps):
    stmt = build_statement(gaps, inputs_gaps, AS_OF)
    d = next(d for d in stmt["downgraded"] if d["claim_id"] == "review_cycle")
    assert [v["variant_id"] for v in d["stronger"]] == ["registry_interval", "annual"]
    assert d["stronger"][1]["result"]["failing"][0]["entry"] == "brief-drafting"


def test_unsupported_wording_does_not_appear_anywhere(gaps, inputs_gaps):
    stmt = build_statement(gaps, inputs_gaps, AS_OF)
    for out in (render.statement_html(stmt), render.statement_md(stmt), render.proposal_md(stmt)):
        assert "No tool we use allows" not in out
        assert "Every tool in use has a written review step" not in out
        assert "court filing, we have a written step" not in out


def test_singular_grammar_in_count_variants(gaps, inputs_gaps):
    text = all_text(build_statement(gaps, inputs_gaps, AS_OF))
    assert "One of five tools in use is not approved" in text
    assert not re.search(r"\bOne of \w+ tools[^.]*\b(are|have|do)\b", text)


def test_vendors_named_only_when_asked(clean, inputs):
    assert "Clausewise" not in all_text(build_statement(clean, inputs, AS_OF))
    inputs["name_vendors"] = True
    stmt = build_statement(clean, inputs, AS_OF)
    assert "They are: Clausewise Review (fictional) (contract review);" in all_text(stmt)


def test_billing_option_is_required(clean, inputs):
    del inputs["draft_options"]["billing"]
    with pytest.raises(BuildError, match="draft option for 'billing'"):
        build_statement(clean, inputs, AS_OF)
    inputs["draft_options"]["billing"] = "B9"
    with pytest.raises(BuildError, match="B9"):
        build_statement(clean, inputs, AS_OF)


def test_each_billing_option_prints_its_library_text(clean, inputs):
    opts = {o["id"]: o["text"] for o in load_options()["topics"]["billing"]["options"]}
    for oid, text in opts.items():
        inputs["draft_options"]["billing"] = oid
        assert printed(build_statement(clean, inputs, AS_OF))["billing"]["text"] == text


def test_say_nothing_option_prints_nothing(clean, inputs):
    inputs["draft_options"]["court_disclosure"] = "D0"
    stmt = build_statement(clean, inputs, AS_OF)
    assert "court_disclosure" not in printed(stmt)
    assert {"topic": "court_disclosure", "option_id": "D0", "name": "Say nothing on disclosure to courts",
            "printed": False} in stmt["draft_options"]


def test_draft_option_with_evidence_rule_is_refused_when_registry_cannot_back_it(gaps, inputs_gaps):
    inputs_gaps["draft_options"]["confidentiality"] = "C2"
    with pytest.raises(BuildError, match="draft option C2.*intake-assistant"):
        build_statement(gaps, inputs_gaps, AS_OF)


def test_draft_until_approval_matches_the_exact_text(clean, inputs):
    draft = build_statement(clean, inputs, AS_OF)
    assert draft["status"] == "DRAFT"
    html = render.statement_html(draft)
    assert 'class="watermark"' in html and "Draft, not approved" in html
    assert render.statement_md(draft).count("DRAFT. Not approved for release.") == 2

    inputs["approval"] = {"approved_by": "General Counsel (role)", "approved_on": "2026-11-25", "content_hash": ""}
    half = build_statement(clean, inputs, AS_OF)
    assert half["status"] == "DRAFT" and any("approval is on file" in w for w in half["warnings"])

    inputs["approval"]["content_hash"] = draft["content_hash"]
    ok = build_statement(clean, inputs, AS_OF)
    assert ok["status"] == "APPROVED"
    html = render.statement_html(ok)
    assert 'class="watermark"' not in html and "DRAFT" not in html
    assert "Approved for release on 2026-11-25." in html


def test_approval_lapses_when_the_text_changes(clean, inputs):
    draft = build_statement(clean, inputs, AS_OF)
    inputs["approval"] = {"approved_by": "General Counsel (role)", "approved_on": "2026-11-25",
                          "content_hash": draft["content_hash"]}
    tool(clean, "translation")["status"] = "paused"   # one fewer tool in use changes the printed text
    assert build_statement(clean, inputs, AS_OF)["status"] == "DRAFT"


def test_word_ceiling_fails_the_build(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    assert stmt["word_count"] == statement_word_count(stmt) <= WORD_LIMIT
    with pytest.raises(BuildError, match="one-page limit is 200"):
        build_statement(clean, inputs, AS_OF, word_limit=200)


def test_all_sample_statements_are_under_the_ceiling(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
    for stmt in (build_statement(clean, inputs, AS_OF), build_statement(gaps, inputs_gaps, AS_OF),
                 build_statement(clean, inputs, AS_OF, client_consent),
                 build_statement(clean, inputs, AS_OF, client_restricted)):
        assert stmt["word_count"] <= WORD_LIMIT == stmt["word_limit"]


def test_exclude_claims(clean, inputs):
    inputs["exclude_claims"] = ["rollout"]
    stmt = build_statement(clean, inputs, AS_OF)
    assert "rollout" not in printed(stmt)
    assert any(n["claim_id"] == "rollout" and "excluded" in n["reason"] for n in stmt["not_applicable"])
    inputs["exclude_claims"] = ["billing"]
    with pytest.raises(BuildError):
        build_statement(clean, inputs, AS_OF)


def test_no_tools_in_use(clean, inputs):
    for t in clean["tools"]:
        t["status"] = "paused"
    stmt = build_statement(clean, inputs, AS_OF)
    assert printed(stmt)["no_tools_in_use"]["text"] == "We do not use AI-assisted tools in client work as of this date."
    assert "no_training" not in printed(stmt)
    purpose = next(s for s in stmt["sections"] if s["id"] == "purpose")
    assert [s["text"] for s in purpose["sentences"]] == [EMPTY_SECTION]


def test_invalid_registry_and_inputs_are_refused(clean, inputs):
    bad = copy.deepcopy(clean)
    bad["tools"][0]["data_boundary"]["used_for_training"] = "maybe"
    with pytest.raises(InputError, match="used_for_training"):
        build_statement(bad, inputs, AS_OF)
    del inputs["contact"]
    with pytest.raises(InputError, match="contact"):
        build_statement(clean, inputs, AS_OF)


def test_proposal_paragraph_length_and_source(clean, gaps, inputs, inputs_gaps):
    for reg, inp in ((clean, inputs), (gaps, inputs_gaps)):
        stmt = build_statement(reg, inp, AS_OF)
        p = stmt["proposal"]
        assert 100 <= p["words"] <= PROPOSAL_MAX
        ids = set(printed(stmt))
        assert all(s["claim_id"] in ids or s["claim_id"] == "(closing)" for s in p["sentences"])
    assert "No tool we use allows" not in build_statement(gaps, inputs_gaps, AS_OF)["proposal"]["text"]


def test_footer_has_as_of_version_and_registry_date(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    assert stmt["footer"] == "As of 2026-11-25. Version 1.0. Based on the firm's AI tool registry dated 2026-11-25."
    assert stmt["footer"] in render.statement_md(stmt)


def test_contact_is_printed_from_inputs(clean, inputs):
    s = printed(build_statement(clean, inputs, AS_OF))["contact"]
    assert s["text"] == "Questions about this statement go to the Office of General Counsel: aiquestions@examplefirm.example."
    assert s["kind"] == "record"


# ---------- client-specific variant ----------

def test_client_version_adds_for_your_matters_first(clean, inputs, client_consent):
    stmt = build_statement(clean, inputs, AS_OF, client_consent)
    assert stmt["variant"] == "client" and stmt["sections"][0]["label"] == "For your matters"
    assert stmt["subtitle"].endswith("Statement for Client A (fictional).")
    p = printed(stmt)
    assert "We hold your written consent dated 2026-09-14." in p["client_consent_held"]["text"]
    assert p["client_tools_prohibited"]["text"] == "Your terms rule out these tools on your matters: the transcript summaries tool."
    assert p["client_restriction_check"]["variant_id"] == "all_checked_recent"
    assert "in the narrative of the invoice entry" in p["client_disclosure"]["text"]
    assert "client_precedence" in p


def test_client_consent_missing_restricts_every_tool(clean, inputs, client_consent):
    client_consent["consent_on_file"] = None
    stmt = build_statement(clean, inputs, AS_OF, client_consent)
    p = printed(stmt)
    assert "We have no consent from you on file as of this date." in p["client_consent_missing"]["text"]
    assert "client_consent_held" not in p
    # translation has no client-terms check, so the universal wording is not available.
    assert p["client_restriction_check"]["text"].startswith("Three of the four tools your terms restrict are checked")


def test_client_restricted_downgrades_the_check_claim(clean, inputs, client_restricted):
    stmt = build_statement(clean, inputs, AS_OF, client_restricted)
    p = printed(stmt)
    assert p["client_restriction_check"]["text"] == \
        "One of the two tools your terms restrict is checked against your terms before use on a matter."
    assert [d["claim_id"] for d in stmt["downgraded"]] == ["client_restriction_check"]
    assert p["client_data_restrictions"]["text"] == \
        "Your terms bar entering personal data into AI tools. No tool in use is approved to receive it."


def test_client_prohibited_ai(clean, inputs, client_restricted):
    client_restricted.update(ai_use="prohibited", tools_prohibited=[], data_restrictions=[])
    p = printed(build_statement(clean, inputs, AS_OF, client_restricted))
    assert p["client_ai_prohibited"]["text"] == "Your terms prohibit AI-assisted tools on your matters."
    assert "client_ai_permitted" not in p and "client_tools_prohibited" not in p


def test_client_record_validation(clean, inputs, client_consent):
    client_consent["tools_prohibited"] = ["no-such-tool"]
    with pytest.raises(InputError, match="no-such-tool"):
        build_statement(clean, inputs, AS_OF, client_consent)
    client_consent["tools_prohibited"] = []
    client_consent["ai_use"] = "sometimes"
    with pytest.raises(InputError, match="ai_use"):
        build_statement(clean, inputs, AS_OF, client_consent)


def test_firm_version_has_no_client_section(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    assert "For your matters" not in render.statement_html(stmt)
    assert not any(c.startswith("client_") and c != "client_terms_check" for c in printed(stmt))
