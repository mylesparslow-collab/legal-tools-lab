"""Guards on the data files, the documents and the committed demo outputs."""
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, read_json
from filingkit import disclosure
from filingkit.authorities import Authorities

ALLOWED_SECTIONS = {"6068.1", "128.7", "180", "1282.1", "6173"}
TEXT_EXT = (".md", ".py", ".json", ".html", ".txt", ".jsonl")
# Files produced by the existing citation checker from its own sample brief. They cite other
# law because that brief does; they are test input, not statements made by this kit.
EXCLUDE = (os.path.join("tests", "fixtures"),)


def kit_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".git")]
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, ROOT)
            if f.endswith(TEXT_EXT) and not rel.startswith(EXCLUDE):
                yield rel, open(p, encoding="utf-8").read()


def test_authorities_file_is_complete_and_dated():
    a = Authorities()
    assert len(a.items) == 9
    for key, e in a.items.items():
        assert e["section"] and e["paraphrase"] and e["verified_on"] == "2026-11-25", key
    assert a.operative_date() == "2027-01-01"


def test_no_statute_section_outside_the_verified_list():
    pat = re.compile(r"§+\s*([0-9]+(?:\.[0-9]+)?)")
    bad = [(rel, m.group(0)) for rel, text in kit_files() for m in pat.finditer(text)
           if m.group(1) not in ALLOWED_SECTIONS]
    assert bad == []


def test_statute_paraphrases_live_only_in_authorities_json():
    a = Authorities()
    for rel, text in kit_files():
        if rel == os.path.join("data", "authorities.json") or rel == "index.html" or rel.startswith("output"):
            continue  # outputs and the demo page copy entries from the data file at run time
        for key, e in a.items.items():
            assert e["paraphrase"] not in text, f"{rel} repeats the paraphrase for {key}"


@pytest.mark.parametrize("doc", ["standard/FILING_STANDARD.md", "standard/DISCLOSURE_OPTIONS.md", "OPEN_QUESTIONS.md", "README.md"])
def test_authority_keys_used_in_documents_exist(doc):
    text = open(os.path.join(ROOT, doc), encoding="utf-8").read()
    keys = set(re.findall(r"\[((?:bpc|ccp|sb574|no_citator)_[A-Za-z0-9_]+)\]", text))
    assert keys <= set(Authorities().items), keys - set(Authorities().items)
    if doc != "README.md":
        assert keys, f"{doc} cites no authority key"


def test_filing_standard_covers_required_parts_and_is_marked_draft():
    text = open(os.path.join(ROOT, "standard", "FILING_STANDARD.md"), encoding="utf-8").read()
    assert "DRAFT" in text.split("\n", 6)[0] + text[:600]
    for part in ("Responsible attorney", "Before filing", "Record", "Failed check", "Exceptions"):
        assert part in text
    assert len(text.split()) < 900  # one page


def test_disclosure_options_are_all_drafts_and_match_the_document():
    raw = read_json(os.path.join(ROOT, "data", "disclosure_options.json"))
    md = open(os.path.join(ROOT, "standard", "DISCLOSURE_OPTIONS.md"), encoding="utf-8").read()
    assert 3 <= len(raw["options"]) <= 4 and "DRAFT" in raw["status"]
    for o in raw["options"]:
        assert "DRAFT" in o["status"] and "attorney approval" in o["status"]
        assert o["text"] in md
    assert md.count("DRAFT") >= len(raw["options"]) + 1
    assert disclosure.has_placeholder(raw["options"][1]["text"])
    assert not disclosure.has_placeholder(disclosure.fill(raw["options"][1]["text"], "a first draft"))


def test_open_questions_cover_the_required_topics():
    text = open(os.path.join(ROOT, "OPEN_QUESTIONS.md"), encoding="utf-8").read()
    for key in ("[ccp_128_7_d1]", "[ccp_128_7_g]", "[ccp_128_7_b2A]", "[bpc_6068_1_a3C]"):
        assert key in text
    assert "personally verified" in text


def test_readme_states_the_limits_near_the_top():
    head = "\n".join(open(os.path.join(ROOT, "README.md"), encoding="utf-8").read().split("\n")[:12]).lower()
    for phrase in ("personal portfolio demo", "fictional", "not legal advice", "not reviewed by an attorney"):
        assert phrase in head


def test_runtime_code_uses_no_network_modules():
    pat = re.compile(r"^\s*(?:import|from)\s+(urllib|http|socket|requests|ssl|ftplib|smtplib)\b", re.M)
    for rel, text in kit_files():
        if rel.endswith(".py") and not rel.startswith("tests"):
            assert not pat.search(text), rel


def test_demo_page_is_self_contained():
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    assert not re.search(r"<link\b|<script[^>]+src=|<img\b|@import|url\(", html)
    assert set(re.findall(r"https?://[^\s\"'<)]+", html)) <= {u for u in re.findall(r"https://courts\.example/[^\s\"'<)]+", html)}
    assert "Not legal advice" in html and "fictional" in html
    for fid in ("F-2027-001", "F-2027-008"):
        assert fid in html
    assert os.path.exists(os.path.join(ROOT, "output", "records", "F-2027-001.record.html"))


def test_sample_filings_cover_the_required_scenarios():
    out = {f[:10]: read_json(os.path.join(ROOT, "output", "checklists", f))
           for f in sorted(os.listdir(os.path.join(ROOT, "output", "checklists"))) if f.endswith(".json")}
    assert len(out) == 8
    assert {k for k, v in out.items() if v["clear_to_file"]} == {"F-2027-001", "F-2027-003", "F-2027-004", "F-2027-006"}
    assert out["F-2027-002"]["blocking_items"] == ["citations_attested"]
    assert out["F-2027-005"]["blocking_items"] == ["ai_disclosure_decision"]
    assert out["F-2027-007"]["blocking_items"] == ["judge_order_checked"]
    assert out["F-2027-004"]["document"]["type"] == "discovery_response"
    assert out["F-2027-006"]["judge_lookup"]["entries"][0]["requirement_type"] == "certification"
    ed = os.path.join(ROOT, "output", "edited_after_signoff")
    assert read_json(os.path.join(ed, "record_check_before_edit.json"))["status"] == "VALID"
    assert read_json(os.path.join(ed, "record_check_after_edit.json"))["status"] == "INVALID"
    assert read_json(os.path.join(ROOT, "output", "ledger", "ledger_check.json"))["ok"] is True
    assert read_json(os.path.join(ROOT, "output", "tamper_demo", "ledger_tampered_check.json"))["ok"] is False


def test_run_demo_reproduces_the_committed_outputs(tmp_path):
    copy = tmp_path / "kit"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "output", "index.html"))
    p = subprocess.run([sys.executable, "run_demo.py"], cwd=copy, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    for base, _, files in os.walk(os.path.join(ROOT, "output")):
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            assert open(os.path.join(ROOT, rel), "rb").read() == open(copy / rel, "rb").read(), rel
    assert open(os.path.join(ROOT, "index.html"), "rb").read() == open(copy / "index.html", "rb").read()
    made = sum(len(fs) for _, _, fs in os.walk(copy / "output"))
    assert made == sum(len(fs) for _, _, fs in os.walk(os.path.join(ROOT, "output")))
