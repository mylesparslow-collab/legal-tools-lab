"""Per-filing verification record and sign-off.

sign_filing() runs the checklist, refuses if anything blocks, and otherwise writes:
  * <filing_id>.record.json   the record, with its own SHA-256
  * <filing_id>.record.html   a printable one-page view
  * two ledger entries        checklist_run and record_signed

verify_record() answers one question: can this record still be relied on?
It cannot if the document file has changed since sign-off, if the record was
altered, or if the ledger no longer holds a matching, intact entry.
"""
from __future__ import annotations

import os

from . import __version__, KIT_NAME, dochash
from .checklist import run_checklist
from .ledger import Ledger, verify_ledger
from .render import record_html
from .util import canonical_hash, load_json, now_iso, same_person, write_json

RECORD_TYPE = "Filing verification record"
SIGNER_STATEMENT = ("I am the attorney responsible for this filing. I personally verified each citation listed "
                    "in this record, in the way stated next to it. I reviewed the generative AI output used in "
                    "preparing this document, if any, and corrected what needed correcting. The answers in this "
                    "record are mine.")


class SignError(RuntimeError):
    """Sign-off refused. .result holds the checklist when there is one."""

    def __init__(self, message, result=None):
        super().__init__(message)
        self.result = result


def log_checklist(ledger: Ledger, result: dict, now: str | None = None) -> dict:
    return ledger.append({"event": "checklist_run", "filing_id": result["filing_id"],
                          "doc_sha256": result["document"]["sha256"], "clear_to_file": result["clear_to_file"],
                          "blocking_items": result["blocking_items"], "counts": result["counts"],
                          "kit": f"{KIT_NAME} {__version__}"}, now=now)


def build_record(desc: dict, result: dict, signer: str, signed_at: str) -> dict:
    genai = desc.get("genai") or {}
    d = desc.get("disclosure") or {}
    rec = {
        "record_type": RECORD_TYPE,
        "record_version": 1,
        "kit": f"{KIT_NAME} {__version__}",
        "notice": "Personal portfolio demo with fictional data. Not legal advice. Not reviewed by an attorney.",
        "filing_id": desc["filing_id"],
        "matter": desc.get("matter"),
        "court_id": desc.get("court_id"),
        "court": desc.get("court"),
        "judge_id": desc.get("judge_id"),
        "planned_filing_date": desc.get("planned_filing_date"),
        "responsible_attorney": desc.get("responsible_attorney"),
        "document": result["document"],
        "citation_report": result["report"],
        "citations": [{"id": c["id"], "citation": c["label"], "key": c["key"], "machine_status": c["machine_status"],
                       "machine_flags": c["not_found"] + c["quote_mismatches"] + c["other_failures"] + c["warnings"] + c["manual"],
                       "attested_by": (c["attestation"] or {}).get("attorney"),
                       "attested_at": (c["attestation"] or {}).get("attested_at"),
                       "how_checked": (c["attestation"] or {}).get("how_checked"),
                       "resolution": (c["attestation"] or {}).get("resolution") or None,
                       "attestation_counts": c["attested"]}
                      for c in result["citations"]],
        "ai_use": {"used": genai.get("used"), "tools": genai.get("tools") or [], "purposes": genai.get("purposes") or [],
                   "output_verified": genai.get("output_verified"),
                   "protected_info_entered": genai.get("protected_info_entered"),
                   "protected_info_review_by": genai.get("protected_info_review_by")},
        "disclosure": {"decision": d.get("decision"), "option_id": d.get("option_id"), "text": d.get("text"),
                       "decided_by": d.get("decided_by"), "decided_on": d.get("decided_on"),
                       "reason": d.get("reason"), "approved_by": d.get("approved_by"),
                       "wording_status": "DRAFT wording, not approved" if d.get("text") else None},
        "judge_order_snapshot": result["judge_lookup"],
        "judge_order_check": desc.get("judge_order_check"),
        "judge_order_response": desc.get("judge_order_response"),
        "checklist": {"generated_at": result["generated_at"], "policy_version": result["policy_version"],
                      "result": result["result"], "clear_to_file": result["clear_to_file"],
                      "counts": result["counts"], "items": result["items"]},
        "authorities": result["authorities"],
        "signer": {"name": signer, "statement": SIGNER_STATEMENT},
        "signed_at": signed_at,
    }
    rec["record_sha256"] = canonical_hash(rec)
    return rec


def sign_filing(desc: dict, base_dir: str, *, signer: str, attest: bool, out_dir: str, ledger_path: str,
                judge_orders: dict, policy: dict, authorities, now: str | None = None) -> dict:
    """Run the checklist and, if clear, write the signed record. Returns {record, paths, ledger_entry}."""
    if not attest:
        raise SignError("Sign-off needs the signer's explicit attestation (--attest).")
    if not (signer or "").strip():
        raise SignError("Sign-off needs the signer's name.")
    ts = now_iso(now)
    ledger = Ledger(ledger_path)
    result = run_checklist(desc, base_dir, judge_orders=judge_orders, policy=policy, authorities=authorities, now=ts)
    log_checklist(ledger, result, now=ts)
    responsible = (desc.get("responsible_attorney") or {}).get("name")
    if not result["clear_to_file"]:
        raise SignError("Not clear to file. Blocking items: " + ", ".join(result["blocking_items"]), result)
    if policy["signer_must_be_responsible_attorney"] and not same_person(signer, responsible):
        ledger.append({"event": "sign_refused", "filing_id": desc["filing_id"], "signer": signer,
                       "reason": "signer is not the responsible attorney"}, now=ts)
        raise SignError(f"Signer '{signer}' is not the responsible attorney ({responsible}).", result)
    record = build_record(desc, result, signer.strip(), ts)
    entry = ledger.append({"event": "record_signed", "filing_id": record["filing_id"],
                           "doc_sha256": record["document"]["sha256"], "record_sha256": record["record_sha256"],
                           "signer": record["signer"]["name"], "kit": record["kit"]}, now=ts)
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"{record['filing_id']}.record.json")
    html_path = os.path.join(out_dir, f"{record['filing_id']}.record.html")
    write_json(json_path, record)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(record_html(record, ledger_entry=entry))
    return {"record": record, "json_path": json_path, "html_path": html_path, "ledger_entry": entry,
            "checklist": result}


def verify_record(record: dict, *, document_path: str | None = None, ledger_path: str | None = None) -> dict:
    """Check a record against the document as it is now and against the ledger.

    Returns {status, valid, problems, checks}. status is VALID, INVALID or INCOMPLETE
    (INCOMPLETE: nothing wrong was found, but the document or the ledger was not checked).
    """
    problems, checks = [], {}

    body = {k: v for k, v in record.items() if k != "record_sha256"}
    checks["record_intact"] = canonical_hash(body) == record.get("record_sha256")
    if not checks["record_intact"]:
        problems.append("The record file has been altered: its content does not match its own hash.")
    if not (record.get("checklist") or {}).get("clear_to_file"):
        checks["record_intact"] = False
        problems.append("The record does not show a clear checklist.")

    if document_path is None:
        checks["document_unchanged"] = None
    else:
        try:
            current = dochash.file_sha256(document_path)
            checks["document_unchanged"] = current == record["document"]["sha256"]
            if not checks["document_unchanged"]:
                problems.append("The document was changed after sign-off. This record no longer covers it. "
                                f"Signed hash {record['document']['sha256']}; current hash {current}. "
                                "Run the citation check, the attestations and the sign-off again.")
        except OSError as e:
            checks["document_unchanged"] = False
            problems.append(f"Cannot read the document: {e}")

    if ledger_path is None:
        checks["ledger_intact"] = checks["in_ledger"] = None
    else:
        lv = verify_ledger(ledger_path)
        checks["ledger_intact"] = lv["ok"]
        if not lv["ok"]:
            problems.append("The ledger chain is broken: " + "; ".join(
                f"line {p['line']}: {p['problem']}" for p in lv["problems"]))
            checks["in_ledger"] = False
        else:
            match = Ledger(ledger_path).find(event="record_signed", record_sha256=record.get("record_sha256"))
            checks["in_ledger"] = bool(match)
            if not match:
                problems.append("The ledger has no record_signed entry for this record.")

    if problems:
        status = "INVALID"
    elif None in checks.values():
        status = "INCOMPLETE"
    else:
        status = "VALID"
    return {"filing_id": record.get("filing_id"), "record_sha256": record.get("record_sha256"),
            "status": status, "valid": status == "VALID", "checks": checks, "problems": problems}


def load_record(path: str) -> dict:
    rec = load_json(path)
    if not isinstance(rec, dict) or rec.get("record_type") != RECORD_TYPE:
        raise ValueError("not a filing verification record")
    return rec
