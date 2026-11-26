"""Pre-filing checklist engine.

Input: a filing descriptor (JSON), the citation checker's report, the attorney's
per-citation attestations, the judge orders file and the firm policy file.
Output: a list of items, each PASS / FAIL / NEEDS ATTENTION / NOT APPLICABLE with a
reason, and a single answer: clear to file, or not.

Rules that matter:
* A machine result is never attorney verification. Only an attestation entry
  (who, when, how checked) counts, one per citation.
* An item marked blocking stops the filing. The filing is clear only when no
  blocking item remains.
* Legal statements are not written here. Items carry authority keys that point
  into data/authorities.json.
"""
from __future__ import annotations

import os

from . import adapter, disclosure as disclosure_mod, dochash, judges
from .util import is_ts, load_json, now_iso, parse_date, parse_ts, same_person

PASS = "PASS"
FAIL = "FAIL"
ATTENTION = "NEEDS ATTENTION"
NA = "NOT APPLICABLE"
STATUSES = (PASS, FAIL, ATTENTION, NA)

MACHINE_NOT_ATTORNEY = ("A machine result, including PASS or 'found', is not attorney verification. "
                        "The responsible attorney must attest each citation.")


class DescriptorError(ValueError):
    pass


def load_descriptor(path: str):
    """Read a filing descriptor. Returns (descriptor, base_dir)."""
    desc = load_json(path)
    validate_descriptor(desc)
    return desc, os.path.dirname(os.path.abspath(path))


def validate_descriptor(desc) -> None:
    if not isinstance(desc, dict):
        raise DescriptorError("filing descriptor must be a JSON object")
    for key in ("filing_id", "matter", "court_id", "document"):
        if not desc.get(key):
            raise DescriptorError(f"filing descriptor is missing '{key}'")
    doc = desc["document"]
    if not isinstance(doc, dict) or not doc.get("path") or not doc.get("type"):
        raise DescriptorError("document needs 'path' and 'type'")


def load_attestations(path: str) -> dict:
    """Read an attestations file: {doc_sha256, attestations: [{citation_id, attorney, attested_at, how_checked, resolution?}]}."""
    raw = load_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("attestations"), list):
        raise DescriptorError("attestations file needs an 'attestations' list")
    return raw


def _item(items, id_, title, status, reason, *, blocking=None, authority_keys=(), details=()):
    if blocking is None:
        blocking = status == FAIL
    if status in (PASS, NA):
        blocking = False
    items.append({"id": id_, "title": title, "status": status, "blocking": bool(blocking), "reason": reason,
                  "authority_keys": list(authority_keys), "details": list(details)})


def _attestation_problems(att, citation, responsible, policy) -> list:
    """Why this attestation does not count. Empty list means it counts."""
    if not att:
        return ["no attorney attestation"]
    out = []
    who = (att.get("attorney") or "").strip()
    if not who:
        out.append("attestation does not name who verified")
    elif who.casefold() in [n.casefold() for n in policy["non_human_attestors"]]:
        out.append(f"attested by '{who}', which is a tool, not an attorney")
    elif policy["attestor_must_be_responsible_attorney"] and not same_person(who, responsible):
        out.append(f"attested by {who}, not the responsible attorney")
    if not is_ts(att.get("attested_at")):
        out.append("attestation has no valid date and time")
    how = (att.get("how_checked") or "").strip()
    if len(how) < policy["min_how_checked_chars"]:
        out.append("attestation does not say how the citation was checked")
    return out


def _resolved(att, policy) -> bool:
    return bool(att) and len((att.get("resolution") or "").strip()) >= policy["min_resolution_chars"]


def run_checklist(desc: dict, base_dir: str, *, judge_orders: dict, policy: dict, authorities,
                  now: str | None = None) -> dict:
    validate_descriptor(desc)
    generated_at = now_iso(now)
    as_of = parse_ts(generated_at).date()
    items: list = []

    doc_meta = desc["document"]
    doc_type = doc_meta["type"]
    is_discovery = doc_type in policy["discovery_document_types"]
    is_filing = doc_type in policy["filing_document_types"]
    advisory = is_discovery and policy["discovery_mode"] == "advisory"
    attorney = (desc.get("responsible_attorney") or {}).get("name") or ""

    def cite_item(id_, title, status, reason, *, blocking=None, details=()):
        """Citation items are downgraded for discovery papers when policy says advisory."""
        keys = ["ccp_128_7_b2A", "bpc_6068_1_a3Bi"]
        if advisory and status in (FAIL, ATTENTION):
            status, blocking = ATTENTION, False
            reason = ("Advisory only for a discovery paper (ccp_128_7_g; policy discovery_mode=advisory). " + reason)
            keys.append("ccp_128_7_g")
        _item(items, id_, title, status, reason, blocking=blocking, authority_keys=keys, details=details)

    # 1. scope ------------------------------------------------------------
    operative = authorities.operative_date()
    planned = desc.get("planned_filing_date")
    early = ""
    if planned and is_ts(planned) and parse_date(planned) < parse_date(operative):
        early = (f" Planned filing date {planned} is before the operative date {operative} (sb574_enactment); "
                 "firm policy applies the standard anyway.")
    if is_filing:
        _item(items, "document_scope", "Document type is in scope", PASS,
              f"'{doc_type}' is treated as a paper filed in court. Every citation needs personal verification.{early}",
              authority_keys=["ccp_128_7_b2A", "sb574_enactment"])
    elif is_discovery:
        mode = policy["discovery_mode"]
        tail = ("Citation items are reported but do not block." if mode == "advisory"
                else "Firm policy applies the same blocking citation items anyway.")
        _item(items, "document_scope", "Document type is in scope", NA,
              f"'{doc_type}' is a discovery paper. Policy discovery_mode={mode}: {tail} "
              f"The AI-use items still apply.{early}",
              authority_keys=["ccp_128_7_g", "bpc_6068_1_a3Bi"])
    else:
        _item(items, "document_scope", "Document type is in scope", ATTENTION,
              f"Document type '{doc_type}' is not in the policy lists. Classify it before filing.", blocking=True)

    # 2. responsible attorney --------------------------------------------
    if attorney.strip():
        _item(items, "responsible_attorney", "Responsible attorney named", PASS,
              f"Responsible attorney: {attorney}.", authority_keys=["ccp_128_7_b2A"])
    else:
        _item(items, "responsible_attorney", "Responsible attorney named", FAIL,
              "No responsible attorney is named in the filing descriptor.", authority_keys=["ccp_128_7_b2A"])

    # 3. document ---------------------------------------------------------
    doc_path = os.path.join(base_dir, doc_meta["path"])
    hashes = None
    try:
        hashes = dochash.document_hashes(doc_path)
        _item(items, "document_present", "Document found and hashed", PASS,
              f"SHA-256 of file: {hashes['sha256']}.")
    except (OSError, dochash.DocumentError) as e:
        _item(items, "document_present", "Document found and hashed", FAIL, f"Cannot read the document: {e}")

    # 4. citation report --------------------------------------------------
    report = None
    rel = desc.get("citation_report")
    if not rel:
        cite_item("citation_report_present", "Citation report present", FAIL,
                  "No citation-check report is listed for this filing.")
    else:
        try:
            report = adapter.load_report(os.path.join(base_dir, rel))
            s = report["summary"]
            cite_item("citation_report_present", "Citation report present", PASS,
                      f"{report['source_format']}, citations listed: {len(report['citations'])} "
                      f"(machine: {s.get('PASS', 0)} pass, {s.get('WARN', 0)} warn, {s.get('FAIL', 0)} fail, "
                      f"{s.get('MANUAL', 0)} manual).")
        except OSError as e:
            cite_item("citation_report_present", "Citation report present", FAIL, f"Cannot read the report: {e}")
        except adapter.ReportFormatError as e:
            cite_item("citation_report_present", "Citation report present", FAIL, f"Report is not usable: {e}")

    # 5. report matches document -----------------------------------------
    report_current = False
    if report is None or hashes is None:
        cite_item("report_matches_document", "Report matches the document", FAIL,
                  "Cannot compare: the report or the document is missing.")
    elif report["doc_sha256"] == hashes["verifier_text_sha256"]:
        report_current = True
        cite_item("report_matches_document", "Report matches the document", PASS,
                  "The report's document hash equals the hash of the document text as it is now.")
    else:
        cite_item("report_matches_document", "Report matches the document", FAIL,
                  "The document text has changed since the citation check, or the report belongs to another "
                  "document. Run the citation check again and redo the attestations.",
                  details=[f"report doc_sha256: {report['doc_sha256']}",
                           f"document text hash: {hashes['verifier_text_sha256']}"])

    # attestations --------------------------------------------------------
    att_by_id, att_note = {}, ""
    att_rel = desc.get("attestations")
    if report is not None:
        for c in report["citations"]:
            if c["embedded_attestation"]:
                att_by_id[c["id"]] = c["embedded_attestation"]
        if att_rel:
            try:
                att_file = load_attestations(os.path.join(base_dir, att_rel))
                if att_file.get("doc_sha256") != report["doc_sha256"]:
                    att_note = ("The attestations file was made for a different version of the document "
                                "(doc_sha256 differs from the report), so none of its entries count.")
                else:
                    for a in att_file["attestations"]:
                        if isinstance(a, dict) and a.get("citation_id"):
                            att_by_id[a["citation_id"]] = {**a, "source": "attestations file"}
            except (OSError, ValueError) as e:
                att_note = f"Cannot read the attestations file: {e}"

    citations = []
    for c in (report["citations"] if report else []):
        att = att_by_id.get(c["id"])
        problems = _attestation_problems(att, c, attorney, policy)
        citations.append({**{k: c[k] for k in ("id", "label", "text", "key", "machine_status", "not_found",
                                               "quote_mismatches", "other_failures", "warnings", "manual")},
                          "attestation": att, "attested": not problems, "attestation_problems": problems})

    # 6-9. citation items -------------------------------------------------
    if report is None:
        for id_, title in (("citations_attested", "Every citation attested by the attorney"),
                           ("citations_resolved", "No unresolved or not-found citations"),
                           ("quotes_match", "No quote mismatches"),
                           ("machine_warnings", "Machine warnings resolved")):
            cite_item(id_, title, FAIL, "Cannot evaluate without a usable citation report.")
    elif not citations:
        for id_, title in (("citations_attested", "Every citation attested by the attorney"),
                           ("citations_resolved", "No unresolved or not-found citations"),
                           ("quotes_match", "No quote mismatches"),
                           ("machine_warnings", "Machine warnings resolved")):
            _item(items, id_, title, NA, "The report lists no citations.")
    else:
        # attested
        missing = [f"{c['label']}: {'; '.join(c['attestation_problems'])}" for c in citations if not c["attested"]]
        n = len(citations)
        if missing:
            reason = f"{len(missing)} of {n} citations lack a valid attorney attestation. {MACHINE_NOT_ATTORNEY}"
            if att_note:
                reason += " " + att_note
            cite_item("citations_attested", "Every citation attested by the attorney", FAIL, reason, details=missing)
        else:
            cite_item("citations_attested", "Every citation attested by the attorney", PASS,
                      f"All {n} citations have an attestation by {attorney} with date and method.")

        # unresolved / not found
        blocked, overridden = [], []
        for c in citations:
            if c["not_found"]:
                if policy["allow_attorney_override_not_found"] and c["attested"] and _resolved(c["attestation"], policy):
                    overridden.append(f"{c['label']}: not found by the checker. Attorney note: {c['attestation']['resolution']}")
                else:
                    blocked.append(f"{c['label']}: NOT FOUND. {c['not_found'][0]}")
            for f in c["other_failures"]:
                if c["attested"] and _resolved(c["attestation"], policy):
                    overridden.append(f"{c['label']}: {f} Attorney note: {c['attestation']['resolution']}")
                else:
                    blocked.append(f"{c['label']}: {f} No attorney resolution note.")
            if c["manual"] and not c["attested"]:
                blocked.append(f"{c['label']}: the checker could not check this source and no attorney attestation covers it.")
        if blocked:
            fix = ("" if policy["allow_attorney_override_not_found"] else
                   " Policy does not allow sign-off over a not-found citation: correct or remove it and run the check again.")
            cite_item("citations_resolved", "No unresolved or not-found citations", FAIL,
                      f"{len(blocked)} unresolved citation problem(s).{fix}", details=blocked + overridden)
        elif overridden:
            cite_item("citations_resolved", "No unresolved or not-found citations", ATTENTION,
                      f"{len(overridden)} machine failure(s) resolved by attorney note. Shown on the record.",
                      blocking=False, details=overridden)
        else:
            hand = sum(1 for c in citations if c["manual"])
            cite_item("citations_resolved", "No unresolved or not-found citations", PASS,
                      "No citation is unresolved or not found." +
                      (f" {hand} could not be machine-checked and rest on the attorney's attestation." if hand else ""))

        # quotes
        blocked, overridden = [], []
        for c in citations:
            for q in c["quote_mismatches"]:
                if policy["allow_attorney_override_quote_mismatch"] and c["attested"] and _resolved(c["attestation"], policy):
                    overridden.append(f"{c['label']}: {q} Attorney note: {c['attestation']['resolution']}")
                else:
                    blocked.append(f"{c['label']}: {q}")
        if blocked:
            cite_item("quotes_match", "No quote mismatches", FAIL,
                      f"{len(blocked)} quotation(s) do not match the source. Correct the quotation and run the check again.",
                      details=blocked + overridden)
        elif overridden:
            cite_item("quotes_match", "No quote mismatches", ATTENTION,
                      f"{len(overridden)} quote mismatch(es) resolved by attorney note. Shown on the record.",
                      blocking=False, details=overridden)
        else:
            cite_item("quotes_match", "No quote mismatches", PASS, "No quotation was reported as a mismatch.")

        # warnings
        open_w, closed_w = [], []
        for c in citations:
            for w in c["warnings"]:
                if c["attested"] and _resolved(c["attestation"], policy):
                    closed_w.append(f"{c['label']}: {w} Attorney note: {c['attestation']['resolution']}")
                else:
                    open_w.append(f"{c['label']}: {w} No attorney resolution note.")
        if open_w:
            cite_item("machine_warnings", "Machine warnings resolved", FAIL,
                      f"{len(open_w)} machine warning(s) have no attorney resolution note.", details=open_w + closed_w)
        else:
            cite_item("machine_warnings", "Machine warnings resolved", PASS,
                      f"{len(closed_w)} warning(s), each resolved by attorney note." if closed_w else "No machine warnings.",
                      details=closed_w)

    # 10-13. AI use -------------------------------------------------------
    genai = desc.get("genai") or {}
    used = genai.get("used")
    if not isinstance(used, bool):
        _item(items, "ai_use_recorded", "AI-use answer recorded", FAIL,
              "The filing descriptor does not say whether generative AI was used. Answer yes or no.",
              authority_keys=["bpc_6068_1_a3Bi"])
    elif used and not (genai.get("tools") and genai.get("purposes")):
        _item(items, "ai_use_recorded", "AI-use answer recorded", ATTENTION,
              "Generative AI was used, but the tools or the purposes are not listed.", blocking=True,
              authority_keys=["bpc_6068_1_a3Bi"])
    elif used:
        _item(items, "ai_use_recorded", "AI-use answer recorded", PASS,
              f"Generative AI used. Tools: {'; '.join(genai['tools'])}. Purposes: {'; '.join(genai['purposes'])}.",
              authority_keys=["bpc_6068_1_a3Bi"])
    else:
        _item(items, "ai_use_recorded", "AI-use answer recorded", PASS, "Recorded answer: generative AI was not used.")

    if used is True:
        ov = genai.get("output_verified") or {}
        probs = []
        if not (ov.get("by") or "").strip():
            probs.append("no name")
        elif policy["attestor_must_be_responsible_attorney"] and not same_person(ov["by"], attorney):
            probs.append(f"reviewed by {ov['by']}, not the responsible attorney")
        if not is_ts(ov.get("on")):
            probs.append("no valid date")
        if len((ov.get("how") or "").strip()) < policy["min_how_checked_chars"]:
            probs.append("no description of how the output was checked")
        if probs:
            _item(items, "ai_output_verified", "AI output reviewed and corrected", FAIL,
                  "No complete attorney statement that the AI output was verified and corrected: " + "; ".join(probs) + ".",
                  authority_keys=["bpc_6068_1_a3Bi", "bpc_6068_1_a3Bii"])
        else:
            _item(items, "ai_output_verified", "AI output reviewed and corrected", PASS,
                  f"{ov['by']} on {ov['on']}: {ov['how']}", authority_keys=["bpc_6068_1_a3Bi", "bpc_6068_1_a3Bii"])

        entered = genai.get("protected_info_entered")
        title = "Protected information question answered"
        if not isinstance(entered, bool):
            _item(items, "protected_info_check", title, ATTENTION,
                  "Firm policy: record whether any information in the listed categories was entered into an AI tool. "
                  "No answer is recorded.", blocking=True, authority_keys=["bpc_6068_1_b2"])
        elif not entered:
            _item(items, "protected_info_check", title, PASS,
                  "Recorded answer: no information in the listed categories was entered into an AI tool.",
                  authority_keys=["bpc_6068_1_b2"])
        elif (genai.get("protected_info_review_by") or "").strip():
            _item(items, "protected_info_check", title, ATTENTION,
                  f"Recorded answer: yes. Reviewed by {genai['protected_info_review_by']}. Kept on the record.",
                  blocking=False, authority_keys=["bpc_6068_1_b2"])
        else:
            _item(items, "protected_info_check", title, ATTENTION,
                  "Recorded answer: yes. Firm policy requires a named reviewer before filing; none is recorded.",
                  blocking=True, authority_keys=["bpc_6068_1_b2"])

        d = desc.get("disclosure") or {}
        title = "AI-use disclosure decision recorded"
        keys = ["bpc_6068_1_a3C"]
        decision = d.get("decision")
        if decision not in ("disclose", "do_not_disclose"):
            _item(items, "ai_disclosure_decision", title, FAIL,
                  "Generative AI was used and no disclosure decision is recorded. Record 'disclose' with the "
                  "wording chosen, or 'do_not_disclose' with a reason and approval.", authority_keys=keys)
        elif not (d.get("decided_by") or "").strip():
            _item(items, "ai_disclosure_decision", title, FAIL,
                  "The disclosure decision does not say who made it.", authority_keys=keys)
        elif decision == "disclose":
            text = (d.get("text") or "").strip()
            known = disclosure_mod.load_options()
            opt = d.get("option_id")
            if not text:
                _item(items, "ai_disclosure_decision", title, FAIL,
                      "Decision is to disclose, but no disclosure text is recorded.", authority_keys=keys)
            elif disclosure_mod.has_placeholder(text):
                _item(items, "ai_disclosure_decision", title, ATTENTION,
                      "The disclosure text still contains a bracketed placeholder. Fill it in.", blocking=True,
                      authority_keys=keys)
            elif opt not in known and opt != "custom":
                _item(items, "ai_disclosure_decision", title, ATTENTION,
                      f"Disclosure option '{opt}' is not one of the listed drafts. Use a listed id or 'custom'.",
                      blocking=True, authority_keys=keys)
            else:
                _item(items, "ai_disclosure_decision", title, PASS,
                      f"Decision: disclose, using draft option {opt}, decided by {d['decided_by']}. "
                      "The wording is a draft until the General Counsel approves it.", authority_keys=keys)
        else:
            reason = (d.get("reason") or "").strip()
            approved = (d.get("approved_by") or "").strip()
            if len(reason) < policy["min_resolution_chars"]:
                _item(items, "ai_disclosure_decision", title, FAIL,
                      "Decision is not to disclose, but no reason is recorded.", authority_keys=keys)
            elif policy["non_disclosure_needs_approval"] and not approved:
                _item(items, "ai_disclosure_decision", title, ATTENTION,
                      "Decision is not to disclose. Firm policy requires a named approver; none is recorded.",
                      blocking=True, authority_keys=keys)
            else:
                _item(items, "ai_disclosure_decision", title, ATTENTION,
                      f"Decision: do not disclose. Reason: {reason}" + (f" Approved by {approved}." if approved else "")
                      + " Kept on the record.", blocking=False, authority_keys=keys)
    else:
        why = ("Generative AI was not used." if used is False else "Depends on the AI-use answer, which is missing.")
        for id_, title in (("ai_output_verified", "AI output reviewed and corrected"),
                           ("protected_info_check", "Protected information question answered"),
                           ("ai_disclosure_decision", "AI-use disclosure decision recorded")):
            if used is False:
                _item(items, id_, title, NA, why)
            else:
                _item(items, id_, title, ATTENTION, why, blocking=True)

    # 14-15. judge order --------------------------------------------------
    look = judges.lookup(judge_orders, desc["court_id"], desc.get("judge_id"), as_of,
                         policy["judge_entry_staleness_days"])
    manual = desc.get("judge_order_check") or {}
    manual_ok, manual_text = False, ""
    if manual:
        if (manual.get("checked_by") or "").strip() and is_ts(manual.get("checked_on")) and (manual.get("result") or "").strip():
            age = (as_of - parse_date(manual["checked_on"])).days
            if 0 <= age <= policy["judge_entry_staleness_days"]:
                manual_ok = manual["result"] == "no_order_found"
                manual_text = (f"Manual check recorded for this filing: {manual['checked_by']} on {manual['checked_on']}, "
                               f"result '{manual['result']}'" + (f", source {manual['source_url']}" if manual.get("source_url") else "") + ".")
                if not manual_ok:
                    manual_text += " An order was found: add it to the orders file so its requirement can be applied."
            else:
                manual_text = f"The manual check dated {manual['checked_on']} is outside the staleness window."
        else:
            manual_text = "The manual check entry is incomplete (needs checked_by, checked_on, result)."
    title = "Judge and court AI orders checked"
    if look["status"] == judges.CURRENT:
        _item(items, "judge_order_checked", title, PASS, look["message"])
    elif manual_ok:
        _item(items, "judge_order_checked", title, PASS, look["message"] + " " + manual_text)
    else:
        blocks = policy["judge_check_blocks_when_stale"] if look["status"] == judges.STALE else policy["judge_check_blocks_when_not_checked"]
        _item(items, "judge_order_checked", title, ATTENTION, (look["message"] + " " + manual_text).strip(),
              blocking=blocks)

    resp = desc.get("judge_order_response") or {}
    title = "Judge order requirement met"
    reqs = [e for e in look["entries"] if e["requirement_type"] != "none_known"]
    if not reqs:
        _item(items, "judge_order_complied", title, NA,
              "No requirement is on file for this judge or court." if look["entries"]
              else "No entry on file, so no requirement could be applied. See the item above.")
    else:
        bad, ok = [], []
        for e in reqs:
            applies = e["applies_when"] == "always" or used is True or used is None
            head = f"{e['entry_id']} ({e['requirement_type']}): {e['order_title']}"
            if not applies:
                ok.append(f"{head}. Applies only when generative AI is used; recorded answer is no.")
            elif e["requirement_type"] == "prohibition":
                bad.append(f"{head}. Generative AI use is recorded for this filing. Escalate to the General Counsel.")
            elif resp.get("order_id") == e["entry_id"] and resp.get("text_included") is True:
                ok.append(f"{head}. Response recorded: {resp.get('action', 'text included')}.")
            else:
                bad.append(f"{head}. No response recorded. Required text: {e['required_text']}")
        if bad:
            _item(items, "judge_order_complied", title, FAIL,
                  f"{len(bad)} order requirement(s) not met.", details=bad + ok)
        else:
            _item(items, "judge_order_complied", title, PASS, "Each order requirement on file has a recorded response.",
                  details=ok)

    blocking = [i["id"] for i in items if i["blocking"]]
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    used_keys = sorted({k for i in items for k in i["authority_keys"]})
    return {
        "filing_id": desc["filing_id"],
        "generated_at": generated_at,
        "policy_version": policy.get("policy_version"),
        "document": {"path": doc_meta["path"], "title": doc_meta.get("title"), "type": doc_type,
                     "sha256": hashes["sha256"] if hashes else None,
                     "verifier_text_sha256": hashes["verifier_text_sha256"] if hashes else None},
        "report": ({"source_format": report["source_format"], "doc_sha256": report["doc_sha256"],
                    "matches_document": report_current, "summary": report["summary"]} if report else None),
        "items": items,
        "counts": counts,
        "blocking_items": blocking,
        "clear_to_file": not blocking,
        "result": "CLEAR TO FILE" if not blocking else "BLOCKED",
        "citations": citations,
        "judge_lookup": look,
        "authorities": authorities.snapshot(used_keys),
    }


def format_text(result: dict) -> str:
    """Plain-text checklist for the terminal."""
    lines = [f"Filing {result['filing_id']}  ({result['document']['type']})  checked {result['generated_at']}", ""]
    for i in result["items"]:
        flag = " [blocks]" if i["blocking"] else ""
        lines.append(f"  {i['status']:<15} {i['title']}{flag}")
        lines.append(f"                  {i['reason']}")
        for d in i["details"]:
            lines.append(f"                  - {d}")
    lines += ["", f"Result: {result['result']}"]
    if result["blocking_items"]:
        lines.append("Blocking items: " + ", ".join(result["blocking_items"]))
    return "\n".join(lines)
