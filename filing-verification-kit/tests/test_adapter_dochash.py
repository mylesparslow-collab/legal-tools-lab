"""Adapter for the existing citation checker's output, and document hashing."""
import copy
import os
import zipfile

import pytest

from conftest import FIX, read_json
from filingkit import adapter, dochash

REPORT = os.path.join(FIX, "citecheck_report.sample.json")
CERT = os.path.join(FIX, "citecheck_certificate.sample.json")


def test_loads_real_machine_report():
    r = adapter.load_report(REPORT)
    assert r["source_format"] == "citecheck-report"
    assert len(r["citations"]) == 17
    counts = {s: sum(1 for c in r["citations"] if c["machine_status"] == s) for s in adapter.MACHINE_STATUSES}
    assert counts == {"PASS": 7, "WARN": 2, "FAIL": 7, "MANUAL": 1}


def test_machine_report_never_yields_an_attestation():
    r = adapter.load_report(REPORT)
    assert all(c["embedded_attestation"] is None for c in r["citations"])


def test_loads_real_certificate_with_attorney_entries():
    r = adapter.load_report(CERT)
    assert r["source_format"] == "citecheck-certificate"
    assert len(r["citations"]) == 17
    assert all(c["embedded_attestation"]["attorney"] == "Fictional Counsel" for c in r["citations"])
    assert r["doc_sha256"] == adapter.load_report(REPORT)["doc_sha256"]


def test_not_found_and_quote_mismatch_are_extracted():
    r = adapter.load_report(REPORT)
    by_text = {c["text"]: c for c in r["citations"]}
    assert by_text["940 Cal.App.5th 1312"]["not_found"]
    assert by_text["912 Cal.App.5th 455"]["quote_mismatches"]
    assert not by_text["97 Cal.5th 210"]["not_found"] and not by_text["97 Cal.5th 210"]["quote_mismatches"]
    assert [c for c in r["citations"] if c["machine_status"] == "MANUAL"][0]["manual"]


def _raw():
    return read_json(REPORT)


@pytest.mark.parametrize("breaker,needle", [
    (lambda r: r["citations"][0].__setitem__("machine_status", "FOUND"), "unknown machine_status"),
    (lambda r: r["citations"][0].__setitem__("machine_status", "FAIL"), "does not agree"),
    (lambda r: r["citations"][1].__setitem__("id", r["citations"][0]["id"]), "duplicate"),
    (lambda r: r.__setitem__("doc_sha256", "abc"), "SHA-256"),
    (lambda r: r["citations"].pop(), "summary.total"),
    (lambda r: r["citations"][0].pop("checks"), "missing field 'checks'"),
])
def test_rejects_malformed_reports(breaker, needle):
    raw = _raw()
    breaker(raw)
    with pytest.raises(adapter.ReportFormatError, match=needle):
        adapter.normalize_report(raw)


def test_rejects_unrelated_json():
    with pytest.raises(adapter.ReportFormatError):
        adapter.normalize_report({"hello": "world"})
    with pytest.raises(adapter.ReportFormatError):
        adapter.normalize_report([1, 2])


def test_text_hash_matches_the_checkers_hash_for_txt():
    text = dochash.extract_text(os.path.join(FIX, "citecheck_sample_brief.txt"))
    assert dochash.verifier_text_hash(text) == _raw()["doc_sha256"]


def test_text_hash_matches_the_checkers_hash_for_docx():
    text = dochash.extract_text(os.path.join(FIX, "citecheck_sample_brief.docx"))
    assert dochash.verifier_text_hash(text) == _raw()["doc_sha256"]


def test_text_hash_ignores_only_what_the_checker_ignores():
    base = dochash.verifier_text_hash('He said "stop" - twice.')
    assert dochash.verifier_text_hash("He  said “stop” –\n twice.") == base
    assert dochash.verifier_text_hash('He said "stop" - thrice.') != base


def test_file_hash_changes_on_whitespace_edit(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("Some text.\n", encoding="utf-8")
    before = dochash.document_hashes(str(p))
    p.write_text("Some text. \n", encoding="utf-8")
    after = dochash.document_hashes(str(p))
    assert before["sha256"] != after["sha256"]
    assert before["verifier_text_sha256"] == after["verifier_text_sha256"]


def test_docx_with_dtd_is_refused(tmp_path):
    p = tmp_path / "evil.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/document.xml", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')
    with pytest.raises(dochash.DocumentError):
        dochash.extract_text(str(p))


def test_non_docx_zip_is_refused(tmp_path):
    p = tmp_path / "not.docx"
    p.write_bytes(b"plain bytes")
    with pytest.raises(dochash.DocumentError):
        dochash.extract_text(str(p))
