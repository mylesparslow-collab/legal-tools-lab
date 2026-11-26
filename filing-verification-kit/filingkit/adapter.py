"""Adapter for the existing citation checker's JSON output.

Two shapes are accepted, both produced by that tool (package citecheck, engine name
sb574-citecheck 0.1.0):

1. Machine report: what `python -m citecheck.cli DOC --json out.json` writes.
   Top-level keys doc_sha256, filing_date, citations, summary, notice, mirror.
   Each citation has id, text, key, kind, machine_status (PASS / WARN / FAIL / MANUAL),
   checks [{name, status, detail}], quote_results, requires_attorney.

2. Verification certificate: what its build_certificate() returns.
   Top-level keys certificate_type, document {name, sha256, filing_date},
   responsible_attorney, citations [{citation_id, citation_text, key, machine_status,
   checks, verified_by, verified_at, note, ...}], ledger, genai_disclosure.

Both are turned into one normalized structure. A machine status is never turned into
an attorney attestation here: only the certificate's verified_by / verified_at / note
fields (the attorney's own click and note) become an attestation.
"""
from __future__ import annotations

import json

MACHINE_STATUSES = ("PASS", "WARN", "FAIL", "MANUAL")
CHECK_STATUSES = ("pass", "warn", "fail", "manual", "info")


class ReportFormatError(ValueError):
    pass


def _need(obj, key, where):
    if not isinstance(obj, dict) or key not in obj:
        raise ReportFormatError(f"{where}: missing field '{key}'")
    return obj[key]


def _label(c: dict) -> str:
    text = c.get("text") or c.get("citation_text") or ""
    parts = []
    if c.get("case_name") and c.get("form", "full") == "full":
        parts.append(c["case_name"])
    parts.append(text)
    label = " ".join(parts)
    pin = c.get("pin")
    if pin and pin not in text:
        label += f", {pin}"
    return label


def _norm_citation(c: dict, id_field: str, text_field: str, where: str) -> dict:
    cid = _need(c, id_field, where)
    status = _need(c, "machine_status", where)
    if status not in MACHINE_STATUSES:
        raise ReportFormatError(f"{where}: unknown machine_status '{status}'")
    checks = _need(c, "checks", where)
    if not isinstance(checks, list):
        raise ReportFormatError(f"{where}: checks must be a list")
    norm_checks = []
    for k in checks:
        st = _need(k, "status", where)
        if st not in CHECK_STATUSES:
            raise ReportFormatError(f"{where}: unknown check status '{st}'")
        norm_checks.append({"name": _need(k, "name", where), "status": st, "detail": k.get("detail", "")})
    worst = ("FAIL" if any(k["status"] == "fail" for k in norm_checks) else
             "WARN" if any(k["status"] == "warn" for k in norm_checks) else
             "MANUAL" if any(k["status"] == "manual" for k in norm_checks) else "PASS")
    if worst != status:
        raise ReportFormatError(f"{where}: machine_status {status} does not agree with its checks ({worst})")
    return {
        "id": cid,
        "text": _need(c, text_field, where),
        "label": _label({**c, "text": c[text_field]}),
        "key": c.get("key"),
        "kind": c.get("kind"),
        "pin": c.get("pin"),
        "machine_status": status,
        "checks": norm_checks,
        "not_found": [k["detail"] for k in norm_checks if k["name"] == "existence" and k["status"] == "fail"],
        "quote_mismatches": [k["detail"] for k in norm_checks if k["name"] == "quote" and k["status"] == "fail"],
        "other_failures": [f"{k['name']}: {k['detail']}" for k in norm_checks
                           if k["status"] == "fail" and k["name"] not in ("existence", "quote")],
        "warnings": [f"{k['name']}: {k['detail']}" for k in norm_checks if k["status"] == "warn"],
        "manual": [f"{k['name']}: {k['detail']}" for k in norm_checks if k["status"] == "manual"],
        "embedded_attestation": None,
    }


def normalize_report(raw) -> dict:
    """Turn either accepted shape into the kit's normalized report."""
    if not isinstance(raw, dict):
        raise ReportFormatError("report must be a JSON object")
    if "certificate_type" in raw:
        doc = _need(raw, "document", "certificate")
        out = {"source_format": "citecheck-certificate", "doc_sha256": _need(doc, "sha256", "certificate.document"),
               "filing_date": doc.get("filing_date"), "engine": raw.get("engine"),
               "notice": raw.get("good_law_notice"), "summary": raw.get("summary") or {}}
        cits = []
        for i, c in enumerate(_need(raw, "citations", "certificate")):
            n = _norm_citation(c, "citation_id", "citation_text", f"certificate.citations[{i}]")
            if c.get("verified_by"):
                n["embedded_attestation"] = {"citation_id": n["id"], "attorney": c.get("verified_by"),
                                             "attested_at": c.get("verified_at"),
                                             "how_checked": c.get("note") or "",
                                             "resolution": c.get("note") or "",
                                             "source": "citecheck certificate"}
            cits.append(n)
    elif "doc_sha256" in raw and "citations" in raw:
        out = {"source_format": "citecheck-report", "doc_sha256": raw["doc_sha256"],
               "filing_date": raw.get("filing_date"), "engine": None,
               "notice": raw.get("notice"), "summary": raw.get("summary") or {}}
        cits = [_norm_citation(c, "id", "text", f"report.citations[{i}]") for i, c in enumerate(raw["citations"])]
    else:
        raise ReportFormatError("not a citecheck report or certificate (no doc_sha256/citations or certificate_type)")
    sha = out["doc_sha256"]
    if not (isinstance(sha, str) and len(sha) == 64 and all(ch in "0123456789abcdef" for ch in sha)):
        raise ReportFormatError("doc_sha256 is not a SHA-256 hex digest")
    ids = [c["id"] for c in cits]
    if len(ids) != len(set(ids)):
        raise ReportFormatError("duplicate citation ids")
    total = out["summary"].get("total")
    if total is not None and total != len(cits):
        raise ReportFormatError(f"summary.total is {total} but the report lists {len(cits)} citations")
    out["citations"] = cits
    return out


def load_report(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ReportFormatError(f"report is not valid JSON: {e}") from e
    return normalize_report(raw)
