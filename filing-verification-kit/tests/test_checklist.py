"""Pre-filing checklist: what passes, what blocks, and why."""
import os

import pytest

from conftest import NOW, item, read_json, save_json
from filingkit.checklist import ATTENTION, FAIL, NA, PASS, STATUSES, DescriptorError, load_descriptor, run_checklist
from filingkit.policy import PolicyError, load_policy


def test_clean_filing_is_clear(filing, ctx):
    r = filing("F-2027-001").check(ctx)
    assert r["clear_to_file"] and r["result"] == "CLEAR TO FILE" and r["blocking_items"] == []
    assert r["counts"][FAIL] == 0 and r["counts"][ATTENTION] == 0


def test_machine_pass_without_attestation_blocks(filing, ctx):
    f = filing("F-2027-001")
    f.edit("attestations.json", lambda a: a.__setitem__("attestations", []))
    r = f.check(ctx)
    assert all(c["machine_status"] == "PASS" for c in r["citations"])
    it = item(r, "citations_attested")
    assert it["status"] == FAIL and it["blocking"] and not r["clear_to_file"]
    assert "not attorney verification" in it["reason"]
    assert len(it["details"]) == 3


def test_one_missing_attestation_names_the_citation(filing, ctx):
    r = filing("F-2027-002").check(ctx)
    it = item(r, "citations_attested")
    assert r["blocking_items"] == ["citations_attested"]
    assert len(it["details"]) == 1 and "977 F.4th 1180" in it["details"][0]


@pytest.mark.parametrize("change,needle", [
    (lambda a: a.__setitem__("attorney", "Jun Tessaro (fictional paralegal)"), "not the responsible attorney"),
    (lambda a: a.__setitem__("attorney", "sb574-citecheck"), "a tool, not an attorney"),
    (lambda a: a.__setitem__("attorney", " "), "does not name who"),
    (lambda a: a.__setitem__("how_checked", "ok"), "how the citation was checked"),
    (lambda a: a.pop("attested_at"), "no valid date"),
    (lambda a: a.__setitem__("attested_at", "yesterday"), "no valid date"),
])
def test_incomplete_attestation_does_not_count(filing, ctx, change, needle):
    f = filing("F-2027-001")
    f.edit("attestations.json", lambda a: change(a["attestations"][0]))
    it = item(f.check(ctx), "citations_attested")
    assert it["status"] == FAIL and needle in it["details"][0]


def test_attestations_for_another_version_do_not_count(filing, ctx):
    f = filing("F-2027-001")
    f.edit("attestations.json", lambda a: a.__setitem__("doc_sha256", "0" * 64))
    it = item(f.check(ctx), "citations_attested")
    assert it["status"] == FAIL and "different version" in it["reason"]


def test_document_edit_after_check_breaks_the_report_match(filing, ctx):
    f = filing("F-2027-001")
    with open(f.file("document.txt"), "a", encoding="utf-8") as fh:
        fh.write("One more sentence.\n")
    r = f.check(ctx)
    assert item(r, "report_matches_document")["status"] == FAIL and not r["clear_to_file"]


def test_missing_report_blocks(filing, ctx):
    f = filing("F-2027-001")
    os.remove(f.file("citation_report.json"))
    r = f.check(ctx)
    assert item(r, "citation_report_present")["status"] == FAIL
    assert item(r, "citations_attested")["status"] == FAIL


def test_unusable_report_blocks(filing, ctx):
    f = filing("F-2027-001")
    save_json(f.file("citation_report.json"), {"something": "else"})
    it = item(f.check(ctx), "citation_report_present")
    assert it["status"] == FAIL and "not usable" in it["reason"]


def test_missing_document_blocks(filing, ctx):
    f = filing("F-2027-001")
    os.remove(f.file("document.txt"))
    assert item(f.check(ctx), "document_present")["status"] == FAIL


def test_not_found_and_quote_mismatch_block_even_with_attorney_notes(filing, ctx):
    r = filing("F-2027-008").check(ctx)
    assert item(r, "citations_attested")["status"] == PASS  # the attorney did attest; that is not enough
    nf, qm = item(r, "citations_resolved"), item(r, "quotes_match")
    assert nf["status"] == FAIL and "NOT FOUND" in nf["details"][0] and "940 Cal.App.5th 1312" in nf["details"][0]
    assert qm["status"] == FAIL and "912 Cal.App.5th 455" in qm["details"][0]
    assert set(r["blocking_items"]) == {"citations_resolved", "quotes_match"}


def test_override_policy_turns_flags_into_visible_non_blocking_items(filing, ctx):
    r = filing("F-2027-008").check(ctx, allow_attorney_override_not_found=True,
                                   allow_attorney_override_quote_mismatch=True)
    for id_ in ("citations_resolved", "quotes_match"):
        it = item(r, id_)
        assert it["status"] == ATTENTION and not it["blocking"] and "Attorney note" in it["details"][0]
    assert r["clear_to_file"]


def test_override_needs_a_real_resolution_note(filing, ctx):
    f = filing("F-2027-008")
    f.edit("attestations.json", lambda a: [x.pop("resolution", None) for x in a["attestations"]])
    r = f.check(ctx, allow_attorney_override_not_found=True, allow_attorney_override_quote_mismatch=True)
    assert item(r, "citations_resolved")["status"] == FAIL and item(r, "quotes_match")["status"] == FAIL


def test_real_checker_report_with_17_citations(brief_filing, ctx):
    desc, base = load_descriptor(brief_filing())
    r = run_checklist(desc, base, now=NOW, **ctx)
    assert item(r, "report_matches_document")["status"] == PASS
    assert item(r, "citations_attested")["status"] == PASS
    assert item(r, "machine_warnings")["status"] == PASS and len(item(r, "machine_warnings")["details"]) == 3
    assert item(r, "citations_resolved")["status"] == FAIL
    assert sum("NOT FOUND" in d for d in item(r, "citations_resolved")["details"]) == 3
    assert len(item(r, "quotes_match")["details"]) == 2
    assert not r["clear_to_file"]


def test_warnings_and_manual_citations_need_the_attorney(brief_filing, ctx):
    desc, base = load_descriptor(brief_filing(attest=False))
    r = run_checklist(desc, base, now=NOW, **ctx)
    assert item(r, "machine_warnings")["status"] == FAIL
    assert any("could not check this source" in d for d in item(r, "citations_resolved")["details"])


def test_certificate_from_existing_checker_is_accepted_as_input(brief_filing, ctx):
    desc, base = load_descriptor(brief_filing("citecheck_certificate.sample.json", attest=False))
    r = run_checklist(desc, base, now=NOW, **ctx)
    assert r["report"]["source_format"] == "citecheck-certificate"
    assert item(r, "report_matches_document")["status"] == PASS
    att = item(r, "citations_attested")
    # the certificate names who and when for all 17, but has a note (how checked) only for flagged ones
    assert att["status"] == FAIL and len(att["details"]) == 8
    assert all("how the citation was checked" in d for d in att["details"])
    assert sum(c["attested"] for c in r["citations"]) == 9


def test_ai_use_answer_is_required(filing, ctx):
    f = filing("F-2027-002")
    f.edit("filing.json", lambda d: d.__setitem__("genai", {}))
    r = f.check(ctx)
    assert item(r, "ai_use_recorded")["status"] == FAIL
    assert item(r, "ai_disclosure_decision")["blocking"]


def test_ai_not_used_makes_ai_items_not_applicable(filing, ctx):
    r = filing("F-2027-006").check(ctx)
    assert item(r, "ai_use_recorded")["status"] == PASS
    assert {item(r, i)["status"] for i in ("ai_output_verified", "protected_info_check", "ai_disclosure_decision")} == {NA}


def test_ai_used_without_disclosure_decision_blocks(filing, ctx):
    r = filing("F-2027-005").check(ctx)
    assert r["blocking_items"] == ["ai_disclosure_decision"]
    assert item(r, "ai_disclosure_decision")["status"] == FAIL


def test_disclosure_text_with_placeholder_blocks(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d["disclosure"].__setitem__("text", "Counsel used AI for [describe use]."))
    it = item(f.check(ctx), "ai_disclosure_decision")
    assert it["status"] == ATTENTION and it["blocking"] and "placeholder" in it["reason"]


def test_non_disclosure_needs_reason_and_approver(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d.__setitem__("disclosure", {"decision": "do_not_disclose", "decided_by": "X"}))
    assert item(f.check(ctx), "ai_disclosure_decision")["status"] == FAIL
    f.edit("filing.json", lambda d: d["disclosure"].__setitem__("reason", "A reason that is long enough to count."))
    it = item(f.check(ctx), "ai_disclosure_decision")
    assert it["status"] == ATTENTION and it["blocking"]
    f.edit("filing.json", lambda d: d["disclosure"].__setitem__("approved_by", "Calla Wintermoor (fictional General Counsel)"))
    it = item(f.check(ctx), "ai_disclosure_decision")
    assert it["status"] == ATTENTION and not it["blocking"]


def test_ai_output_review_must_be_by_the_responsible_attorney(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d["genai"]["output_verified"].__setitem__("by", "Jun Tessaro (fictional paralegal)"))
    it = item(f.check(ctx), "ai_output_verified")
    assert it["status"] == FAIL and it["blocking"]
    f.edit("filing.json", lambda d: d["genai"].pop("output_verified"))
    assert item(f.check(ctx), "ai_output_verified")["status"] == FAIL


def test_protected_information_answer(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d["genai"].pop("protected_info_entered"))
    assert item(f.check(ctx), "protected_info_check")["blocking"]
    f.edit("filing.json", lambda d: d["genai"].__setitem__("protected_info_entered", True))
    assert item(f.check(ctx), "protected_info_check")["blocking"]
    f.edit("filing.json", lambda d: d["genai"].__setitem__("protected_info_review_by", "Calla Wintermoor (fictional General Counsel)"))
    it = item(f.check(ctx), "protected_info_check")
    assert it["status"] == ATTENTION and not it["blocking"]


def test_discovery_paper_is_advisory_by_default(filing, ctx):
    r = filing("F-2027-004").check(ctx)
    assert item(r, "document_scope")["status"] == NA
    assert "ccp_128_7_g" in item(r, "document_scope")["authority_keys"]
    att = item(r, "citations_attested")
    assert att["status"] == ATTENTION and not att["blocking"] and att["reason"].startswith("Advisory only")
    assert r["clear_to_file"]


def test_discovery_paper_blocks_when_policy_says_same_as_filings(filing, ctx):
    r = filing("F-2027-004").check(ctx, discovery_mode="same_as_filings")
    assert item(r, "citations_attested")["status"] == FAIL and not r["clear_to_file"]


def test_discovery_paper_still_needs_the_ai_items(filing, ctx):
    f = filing("F-2027-004")
    f.edit("filing.json", lambda d: d["genai"].pop("output_verified"))
    r = f.check(ctx)
    assert r["blocking_items"] == ["ai_output_verified"]


def test_discovery_motion_is_treated_as_a_filing_by_default(filing, ctx):
    f = filing("F-2027-004")
    f.edit("filing.json", lambda d: d["document"].__setitem__("type", "discovery_motion"))
    r = f.check(ctx)
    assert item(r, "document_scope")["status"] == PASS and item(r, "citations_attested")["status"] == FAIL


def test_unknown_document_type_blocks(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d["document"].__setitem__("type", "letter"))
    it = item(f.check(ctx), "document_scope")
    assert it["status"] == ATTENTION and it["blocking"]


def test_certification_order_needs_a_recorded_response(filing, ctx):
    f = filing("F-2027-006")
    assert item(f.check(ctx), "judge_order_complied")["status"] == PASS
    f.edit("filing.json", lambda d: d.pop("judge_order_response"))
    it = item(f.check(ctx), "judge_order_complied")
    assert it["status"] == FAIL and "Required text" in it["details"][0]
    f.edit("filing.json", lambda d: d.__setitem__("judge_order_response", {"order_id": "JO-999", "text_included": True}))
    assert item(f.check(ctx), "judge_order_complied")["status"] == FAIL


def test_stale_judge_entry_blocks_until_rechecked(filing, ctx):
    f = filing("F-2027-007")
    r = f.check(ctx)
    it = item(r, "judge_order_checked")
    assert it["status"] == ATTENTION and it["blocking"] and "Recheck before relying" in it["reason"]
    assert r["blocking_items"] == ["judge_order_checked"]
    f.edit("filing.json", lambda d: d.__setitem__("judge_order_check", {
        "checked_by": "Jun Tessaro (fictional paralegal)", "checked_on": "2027-01-12", "result": "no_order_found"}))
    r = f.check(ctx)
    assert item(r, "judge_order_checked")["status"] == PASS and r["clear_to_file"]


def test_old_manual_recheck_does_not_clear_a_stale_entry(filing, ctx):
    f = filing("F-2027-007")
    f.edit("filing.json", lambda d: d.__setitem__("judge_order_check", {
        "checked_by": "Jun Tessaro (fictional paralegal)", "checked_on": "2026-10-01", "result": "no_order_found"}))
    assert item(f.check(ctx), "judge_order_checked")["blocking"]


def test_staleness_follows_the_policy_window(filing, ctx):
    r = filing("F-2027-007").check(ctx, judge_entry_staleness_days=120)
    assert item(r, "judge_order_checked")["status"] == PASS


def test_judge_without_entry_is_not_checked_and_blocks(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d.__setitem__("judge_id", "fict-unlisted"))
    r = f.check(ctx)
    it = item(r, "judge_order_checked")
    assert it["status"] == ATTENTION and it["blocking"] and it["reason"].startswith("Not checked")
    assert item(r, "judge_order_complied")["status"] == NA
    assert "no requirement could be applied" in item(r, "judge_order_complied")["reason"]


def test_prohibition_order_with_ai_use_fails(filing, ctx):
    f = filing("F-2027-007")
    f.edit("filing.json", lambda d: d.__setitem__("judge_id", "fict-haldane"))
    it = item(f.check(ctx), "judge_order_complied")
    assert it["status"] == FAIL and "Escalate" in it["details"][0]
    f.edit("filing.json", lambda d: d.__setitem__("genai", {"used": False}))
    assert item(f.check(ctx), "judge_order_complied")["status"] == PASS


def test_missing_responsible_attorney_fails(filing, ctx):
    f = filing("F-2027-001")
    f.edit("filing.json", lambda d: d.pop("responsible_attorney"))
    r = f.check(ctx)
    assert item(r, "responsible_attorney")["status"] == FAIL and not r["clear_to_file"]


def test_every_item_is_well_formed_and_keyed_to_known_authorities(filing, ctx):
    known = set(ctx["authorities"].items)
    for fid in sorted(os.listdir(os.path.join(os.path.dirname(__file__), "..", "sample_filings"))):
        r = filing(fid).check(ctx)
        assert len(r["items"]) == 15
        for it in r["items"]:
            assert it["status"] in STATUSES and it["reason"].strip()
            assert set(it["authority_keys"]) <= known
            if it["status"] in (PASS, NA):
                assert not it["blocking"]
            if it["status"] == FAIL:
                assert it["blocking"]
        assert r["clear_to_file"] == (not any(i["blocking"] for i in r["items"]))


def test_bad_descriptor_and_bad_policy_are_rejected(tmp_path):
    p = tmp_path / "f.json"
    save_json(p, {"filing_id": "X"})
    with pytest.raises(DescriptorError):
        load_descriptor(str(p))
    with pytest.raises(PolicyError):
        load_policy(overrides={"discovery_mode": "ignore"})
    with pytest.raises(PolicyError):
        load_policy(overrides={"judge_entry_staleness_days": -3})
