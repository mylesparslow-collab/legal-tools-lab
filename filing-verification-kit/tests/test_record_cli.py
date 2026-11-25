"""Sign-off, the per-filing record, its invalidation, and the command line."""
import json
import os
import subprocess
import sys

import pytest

from conftest import NOW, ROOT, read_json, save_json
from filingkit.checklist import load_descriptor
from filingkit.cli import main
from filingkit.ledger import Ledger, verify_ledger
from filingkit.record import SignError, load_record, sign_filing, verify_record

ASHGROVE = "Perrin Ashgrove (fictional attorney)"


def sign(f, ctx, tmp_path, signer=ASHGROVE, attest=True):
    desc, base = load_descriptor(f.path)
    return sign_filing(desc, base, signer=signer, attest=attest, out_dir=str(tmp_path / "rec"),
                       ledger_path=str(tmp_path / "ledger.jsonl"), now=NOW, **ctx)


def test_sign_writes_record_html_and_ledger_entries(filing, ctx, tmp_path):
    out = sign(filing("F-2027-001"), ctx, tmp_path)
    assert os.path.exists(out["json_path"]) and os.path.exists(out["html_path"])
    events = [e["event"] for e in Ledger(str(tmp_path / "ledger.jsonl")).entries()]
    assert events == ["checklist_run", "record_signed"]
    assert out["ledger_entry"]["record_sha256"] == out["record"]["record_sha256"]


def test_record_captures_what_the_standard_lists(filing, ctx, tmp_path):
    f = filing("F-2027-001")
    rec = sign(f, ctx, tmp_path)["record"]
    import hashlib
    assert rec["document"]["sha256"] == hashlib.sha256(open(f.file("document.txt"), "rb").read()).hexdigest()
    assert len(rec["citations"]) == 3
    for c in rec["citations"]:
        assert c["attested_by"] == ASHGROVE and c["attested_at"] and c["how_checked"] and c["attestation_counts"]
    assert rec["ai_use"]["used"] is True and rec["ai_use"]["purposes"]
    assert rec["disclosure"]["decision"] == "disclose" and rec["disclosure"]["text"]
    assert "DRAFT" in rec["disclosure"]["wording_status"]
    assert rec["judge_order_snapshot"]["entries"][0]["entry_id"] == "JO-001"
    assert rec["checklist"]["clear_to_file"] and len(rec["checklist"]["items"]) == 15
    assert rec["signer"]["name"] == ASHGROVE and rec["signed_at"] == NOW
    assert all(a["verified_on"] == "2026-11-25" for a in rec["authorities"])


@pytest.mark.parametrize("fid", ["F-2027-002", "F-2027-005", "F-2027-007", "F-2027-008"])
def test_blocked_filing_cannot_be_signed(filing, ctx, tmp_path, fid):
    signer = read_json(os.path.join(ROOT, "sample_filings", fid, "filing.json"))["responsible_attorney"]["name"]
    with pytest.raises(SignError, match="Not clear to file"):
        sign(filing(fid), ctx, tmp_path, signer=signer)
    assert not os.path.exists(tmp_path / "rec")
    entries = Ledger(str(tmp_path / "ledger.jsonl")).entries()
    assert [e["event"] for e in entries] == ["checklist_run"] and entries[0]["clear_to_file"] is False


def test_only_the_responsible_attorney_can_sign(filing, ctx, tmp_path):
    with pytest.raises(SignError, match="not the responsible attorney"):
        sign(filing("F-2027-001"), ctx, tmp_path, signer="Jun Tessaro (fictional paralegal)")
    assert Ledger(str(tmp_path / "ledger.jsonl")).entries()[-1]["event"] == "sign_refused"


def test_sign_needs_explicit_attestation(filing, ctx, tmp_path):
    with pytest.raises(SignError, match="attest"):
        sign(filing("F-2027-001"), ctx, tmp_path, attest=False)


def test_record_is_valid_until_the_document_changes(filing, ctx, tmp_path):
    f = filing("F-2027-003")
    out = sign(f, ctx, tmp_path, signer="Odalys Verhoeven (fictional attorney)")
    led = str(tmp_path / "ledger.jsonl")
    assert verify_record(out["record"], document_path=f.file("document.txt"), ledger_path=led)["status"] == "VALID"
    with open(f.file("document.txt"), "a", encoding="utf-8") as fh:
        fh.write("A sentence added after sign-off.\n")
    res = verify_record(out["record"], document_path=f.file("document.txt"), ledger_path=led)
    assert res["status"] == "INVALID" and res["checks"]["document_unchanged"] is False
    assert "changed after sign-off" in res["problems"][0]


def test_even_a_one_character_edit_invalidates_the_record(filing, ctx, tmp_path):
    f = filing("F-2027-001")
    out = sign(f, ctx, tmp_path)
    data = open(f.file("document.txt"), "rb").read()
    open(f.file("document.txt"), "wb").write(data + b" ")
    assert verify_record(out["record"], document_path=f.file("document.txt"),
                         ledger_path=str(tmp_path / "ledger.jsonl"))["status"] == "INVALID"


def test_altered_record_is_invalid(filing, ctx, tmp_path):
    f = filing("F-2027-001")
    out = sign(f, ctx, tmp_path)
    rec = read_json(out["json_path"])
    rec["citations"][0]["attested_by"] = "Someone Else"
    res = verify_record(rec, document_path=f.file("document.txt"), ledger_path=str(tmp_path / "ledger.jsonl"))
    assert res["status"] == "INVALID" and res["checks"]["record_intact"] is False


def test_record_with_recomputed_hash_is_not_in_the_ledger(filing, ctx, tmp_path):
    from filingkit.util import canonical_hash
    f = filing("F-2027-001")
    out = sign(f, ctx, tmp_path)
    rec = read_json(out["json_path"])
    rec["signer"]["name"] = "Someone Else"
    rec["record_sha256"] = canonical_hash({k: v for k, v in rec.items() if k != "record_sha256"})
    res = verify_record(rec, document_path=f.file("document.txt"), ledger_path=str(tmp_path / "ledger.jsonl"))
    assert res["status"] == "INVALID" and res["checks"]["in_ledger"] is False


def test_tampered_ledger_invalidates_the_record(filing, ctx, tmp_path):
    f = filing("F-2027-001")
    out = sign(f, ctx, tmp_path)
    led = str(tmp_path / "ledger.jsonl")
    text = open(led, encoding="utf-8").read().replace('"clear_to_file": true', '"clear_to_file": false')
    open(led, "w", encoding="utf-8").write(text)
    res = verify_record(out["record"], document_path=f.file("document.txt"), ledger_path=led)
    assert res["status"] == "INVALID" and res["checks"]["ledger_intact"] is False


def test_record_check_without_document_or_ledger_is_incomplete(filing, ctx, tmp_path):
    out = sign(filing("F-2027-001"), ctx, tmp_path)
    res = verify_record(out["record"])
    assert res["status"] == "INCOMPLETE" and res["valid"] is False


def test_html_record_escapes_field_content(filing, ctx, tmp_path):
    f = filing("F-2027-006")
    evil = "<script>alert(1)</script>"
    f.edit("filing.json", lambda d: d["matter"].__setitem__("caption", evil))
    out = sign(f, ctx, tmp_path)
    html = open(out["html_path"], encoding="utf-8").read()
    assert evil not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script" not in html and "http" not in html.replace("https://courts.example/", "")


def test_html_record_shows_attestations_and_sign_off(filing, ctx, tmp_path):
    out = sign(filing("F-2027-001"), ctx, tmp_path)
    html = open(out["html_path"], encoding="utf-8").read()
    rec = out["record"]
    assert rec["document"]["sha256"] in html and rec["record_sha256"] in html
    assert html.count(ASHGROVE) >= 5 and "CLEAR TO FILE" in html
    assert "Not legal advice" in html and rec["disclosure"]["text"][:60] in html


def test_load_record_rejects_other_json(tmp_path):
    p = tmp_path / "x.json"
    save_json(p, {"record_type": "something else"})
    with pytest.raises(ValueError):
        load_record(str(p))


# ---- command line ---------------------------------------------------------

def test_cli_check_exit_codes(filing, capsys):
    assert main(["check", filing("F-2027-001").path, "--as-of", NOW]) == 0
    assert "CLEAR TO FILE" in capsys.readouterr().out
    assert main(["check", filing("F-2027-002").path, "--as-of", NOW]) == 2
    assert "BLOCKED" in capsys.readouterr().out


def test_cli_full_flow_sign_record_verify_ledger(filing, tmp_path, capsys):
    f = filing("F-2027-001")
    led, out = str(tmp_path / "l.jsonl"), str(tmp_path / "out")
    assert main(["sign", f.path, "--signer", ASHGROVE, "--attest", "--out-dir", out, "--ledger", led, "--as-of", NOW]) == 0
    rec = os.path.join(out, "F-2027-001.record.json")
    assert main(["record", rec, "--document", f.file("document.txt"), "--ledger", led]) == 0
    assert main(["record", rec]) == 4
    assert main(["verify-ledger", led]) == 0
    with open(f.file("document.txt"), "a", encoding="utf-8") as fh:
        fh.write("edit\n")
    capsys.readouterr()
    assert main(["record", rec, "--document", f.file("document.txt"), "--ledger", led, "--log", "--as-of", NOW]) == 3
    assert "INVALID" in capsys.readouterr().out
    assert Ledger(led).entries()[-1]["event"] == "record_verification"
    text = open(led, encoding="utf-8").read().replace(ASHGROVE, "Another Name", 1)
    open(led, "w", encoding="utf-8").write(text)
    assert main(["verify-ledger", led]) == 3
    assert "TAMPERING" in capsys.readouterr().out


def test_cli_sign_refuses_blocked_filing(filing, tmp_path, capsys):
    rc = main(["sign", filing("F-2027-005").path, "--signer", ASHGROVE, "--attest", "--out-dir", str(tmp_path / "o"),
               "--ledger", str(tmp_path / "l.jsonl"), "--as-of", NOW])
    assert rc == 2 and "Sign-off refused" in capsys.readouterr().err
    assert not os.path.exists(tmp_path / "o")


def test_cli_judge_reports_not_checked_and_stale(capsys):
    assert main(["judge", "--court-id", "fict-alder-ridge", "--judge-id", "fict-unlisted", "--as-of", "2027-01-12"]) == 0
    out = capsys.readouterr().out
    assert "NOT CHECKED" in out and "does not mean no order exists" in out
    assert main(["judge", "--court-id", "fict-port-selwyn", "--judge-id", "fict-marrowby", "--as-of", "2027-01-12"]) == 0
    assert "RECHECK BEFORE RELYING" in capsys.readouterr().out
    assert main(["judge", "--court-id", "fict-port-selwyn", "--judge-id", "fict-marrowby", "--as-of", "2027-01-12",
                 "--staleness-days", "100"]) == 0
    assert "Status: CURRENT" in capsys.readouterr().out


def test_cli_bad_input_returns_1(tmp_path, capsys):
    assert main(["check", str(tmp_path / "missing.json")]) == 1
    assert "Error" in capsys.readouterr().err


def test_module_entry_point_runs():
    p = subprocess.run([sys.executable, "-m", "filingkit", "judge", "--list"], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0 and "JO-001" in p.stdout
