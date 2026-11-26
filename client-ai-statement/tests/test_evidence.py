"""Evidence engine: SUPPORTED / NOT SUPPORTED / CANNOT TELL, with the entries and fields that break a claim."""
from datetime import date

import pytest
from conftest import AS_OF, ctx_for, tool, variant_rule

from statement import evidence
from statement.evidence import CANNOT_TELL, NOT_SUPPORTED, SUPPORTED


def run(claims, reg, claim_id, variant_id, **kw):
    return evidence.evaluate_rule(variant_rule(claims, claim_id, variant_id), ctx_for(reg, claims, **kw))


def test_no_training_supported_on_clean_registry(clean, claims):
    r = run(claims, clean, "no_training", "all_tools")
    assert r["status"] == SUPPORTED
    assert r["scope"] == ["contract-review", "research-drafting", "transcript-summary", "translation"]
    assert r["passing"] == r["scope"]


def test_proposed_tool_is_out_of_scope_even_though_it_trains_unknown(clean, claims):
    # meeting-notes is 'proposed' with training 'unknown'; it must not affect claims about tools in use.
    r = run(claims, clean, "no_training", "all_tools")
    assert "meeting-notes" not in r["scope"]


def test_training_yes_is_not_supported_and_names_entry_and_field(clean, claims):
    tool(clean, "transcript-summary")["data_boundary"]["used_for_training"] = "yes"
    r = run(claims, clean, "no_training", "all_tools")
    assert r["status"] == NOT_SUPPORTED
    assert [(f["entry"], f["field"], f["actual"]) for f in r["failing"]] == [
        ("transcript-summary", "data_boundary.used_for_training", "yes")]


def test_training_unknown_is_cannot_tell(clean, claims):
    tool(clean, "research-drafting")["data_boundary"]["used_for_training"] = "unknown"
    r = run(claims, clean, "no_training", "all_tools")
    assert r["status"] == CANNOT_TELL
    assert r["unknown"][0]["entry"] == "research-drafting"
    assert not evidence.is_printable(r)


def test_missing_field_is_cannot_tell_not_false(clean, claims):
    del tool(clean, "translation")["human_review"]
    r = run(claims, clean, "human_review", "every")
    assert r["status"] == CANNOT_TELL
    assert r["unknown"][0]["field"] == "human_review"


def test_a_contradiction_outranks_an_unknown(clean, claims):
    tool(clean, "translation")["data_boundary"]["used_for_training"] = "unknown"
    tool(clean, "contract-review")["data_boundary"]["used_for_training"] = "yes"
    assert run(claims, clean, "no_training", "all_tools")["status"] == NOT_SUPPORTED


def test_client_conf_scope_ignores_tools_not_approved_for_client_data(clean, claims):
    # translation is not approved for client confidential data, so the narrower claim survives.
    tool(clean, "translation")["data_boundary"]["used_for_training"] = "yes"
    assert run(claims, clean, "no_training", "all_tools")["status"] == NOT_SUPPORTED
    r = run(claims, clean, "no_training", "client_conf_tools")
    assert r["status"] == SUPPORTED and "translation" not in r["scope"]


def test_testing_requires_scored_passing_and_dated(clean, claims):
    assert run(claims, clean, "testing", "every_in_use")["status"] == SUPPORTED
    tool(clean, "transcript-summary")["golden_set"]["passes"] = False
    r = run(claims, clean, "testing", "every_in_use")
    assert r["status"] == NOT_SUPPORTED
    assert {f["field"] for f in r["failing"]} == {"golden_set.passes"}


def test_testing_not_applicable_tools_are_out_of_scope(clean, claims):
    r = run(claims, clean, "testing", "every_in_use")
    assert "translation" not in r["scope"]


def test_test_date_after_as_of_is_cannot_tell(clean, claims):
    tool(clean, "contract-review")["golden_set"]["run_date"] = "2026-12-01"
    r = run(claims, clean, "testing", "every_in_use")
    assert r["status"] == CANNOT_TELL
    assert "after the as-of date" in r["unknown"][0]["reason"]


def test_review_within_interval_boundary_days(clean, claims):
    # 180-day interval: a review exactly 180 days before as-of passes, 181 days fails.
    tool(clean, "translation")["last_review"] = "2026-05-29"
    assert (AS_OF - date(2026, 5, 29)).days == 180
    assert run(claims, clean, "review_cycle", "registry_interval")["status"] == SUPPORTED
    tool(clean, "translation")["last_review"] = "2026-05-28"
    r = run(claims, clean, "review_cycle", "registry_interval")
    assert r["status"] == NOT_SUPPORTED
    assert "181 days" in r["failing"][0]["reason"]


def test_as_of_is_explicit_same_registry_different_dates(clean, claims):
    assert run(claims, clean, "review_cycle", "annual", as_of=date(2026, 11, 25))["status"] == SUPPORTED
    assert run(claims, clean, "review_cycle", "annual", as_of=date(2028, 1, 1))["status"] == NOT_SUPPORTED


def test_review_interval_longer_than_a_year_blocks_the_interval_wording(clean, claims):
    clean["review_interval_days"] = 400
    r = run(claims, clean, "review_cycle", "registry_interval")
    assert r["status"] == NOT_SUPPORTED
    assert any(f["field"] == "registry.review_interval_days" for f in r["failing"])


def test_missing_registry_setting_is_cannot_tell(clean, claims):
    del clean["ocg_check_max_age_days"]
    r = run(claims, clean, "client_terms_check", "each_recent")
    assert r["status"] == CANNOT_TELL
    assert "registry.ocg_check_max_age_days is not set" in r["unknown"][0]["reason"]


def test_court_rule_flags_missing_log(gaps, claims):
    r = run(claims, gaps, "court_citations", "each")
    assert r["status"] == NOT_SUPPORTED
    assert {(f["entry"], f["field"]) for f in r["failing"]} == {("brief-drafting", "sb574_log.mechanism")}
    assert {(u["entry"], u["field"]) for u in r["unknown"]} == {("brief-drafting", "sb574_log.log_location")}


def test_universal_rule_with_empty_scope_is_not_supported(clean, claims):
    for t in clean["tools"]:
        t["sb574_log"]["court_filing_use"] = "no"
    r = run(claims, clean, "court_citations", "each")
    assert r["status"] == NOT_SUPPORTED and r["scope"] == [] and "nothing to base it on" in r["note"]


def test_at_least_counts_and_unknown_handling(gaps, claims):
    r = run(claims, gaps, "no_training", "count")
    assert r["status"] == SUPPORTED
    assert (len(r["passing"]), len(r["scope"])) == (3, 4)
    for t in gaps["tools"]:
        t["data_boundary"]["used_for_training"] = "unknown"
    assert run(claims, gaps, "no_training", "count")["status"] == CANNOT_TELL
    for t in gaps["tools"]:
        t["data_boundary"]["used_for_training"] = "yes"
    assert run(claims, gaps, "no_training", "count")["status"] == NOT_SUPPORTED


def test_none_quantifier(clean, claims):
    r = run(claims, clean, "no_tools_in_use", "none")
    assert r["status"] == NOT_SUPPORTED and len({f["entry"] for f in r["failing"]}) == 4
    for t in clean["tools"]:
        t["status"] = "retired"
    assert run(claims, clean, "no_tools_in_use", "none")["status"] == SUPPORTED


def test_owner_placeholder_is_case_insensitive(clean, claims):
    tool(clean, "translation")["business_owner"] = "TBD"
    assert run(claims, clean, "named_owner", "each")["status"] == NOT_SUPPORTED


def test_is_universal_flag(claims):
    assert evidence.is_universal(variant_rule(claims, "no_training", "all_tools"))
    assert evidence.is_universal(variant_rule(claims, "review_cycle", "registry_interval"))
    assert not evidence.is_universal(variant_rule(claims, "no_training", "count"))
    assert not evidence.is_universal(variant_rule(claims, "contact", "role"))


def test_unknown_operator_and_scope_raise(clean, claims):
    ctx = ctx_for(clean, claims)
    with pytest.raises(evidence.RuleError):
        evidence.evaluate_rule({"scope": ["in_use"], "quantifier": "all",
                                "require": [{"field": "status", "op": "looks_fine"}]}, ctx)
    with pytest.raises(evidence.RuleError):
        evidence.evaluate_rule({"scope": ["nope"], "quantifier": "all", "require": []}, ctx)


def test_every_library_rule_evaluates_on_every_sample(clean, gaps, later, claims, inputs, client_restricted):
    for reg in (clean, gaps, later):
        ctx = ctx_for(reg, claims, inputs=inputs, client=client_restricted if reg is clean else None)
        for c in claims["claims"]:
            for v in c.get("variants", []):
                assert evidence.evaluate_rule(v["rule"], ctx)["status"] in (SUPPORTED, NOT_SUPPORTED, CANNOT_TELL)
