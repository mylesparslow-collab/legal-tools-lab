"""Tests for the eval harness."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from harness import report  # noqa: E402
from harness.config import TimeModel, load_time_model  # noqa: E402
from harness.corpus import list_doc_ids, load_document, validate_document  # noqa: E402
from harness.score import cites, score_document, score_run  # noqa: E402
from harness.textnorm import find_quote, normalise  # noqa: E402
from harness.__main__ import main  # noqa: E402
from authorities import load_register, unverified  # noqa: E402

DOC = """# Test Lease

_Fictional document for software testing._

1.1 Deposit. Landlord shall return the Security Deposit within ninety (90) days after the Expiration Date, less any amounts applied.

1.2 Jury. Landlord and Tenant each waive trial by jury in any action arising out of this Lease or the Premises.

1.3 Accessibility. Tenant shall comply with the Americans with Disabilities Act at its sole cost and expense.

1.4 Notices. All notices must be in writing and delivered to the addresses stated in the Basic Lease Information.
"""
KEY = {
    "doc_id": "t-01", "doc_type": "commercial_lease", "title": "Test Lease",
    "fictional_notice": "All parties and facts are invented.", "baseline_review_minutes": 100,
    "defects": [
        {"id": "t-01-D1", "severity": "high", "kind": "clause", "title": "Deposit", "authority": "Civ. Code § 1950.7(c)",
         "authority_keys": ["1950.7"], "why": "90 days exceeds 30.",
         "quotes": ["Landlord shall return the Security Deposit within ninety (90) days after the Expiration Date"]},
        {"id": "t-01-D2", "severity": "high", "kind": "clause", "title": "Jury", "authority": "Code Civ. Proc. § 631(a), (f)",
         "authority_keys": ["631"], "why": "Predispute waiver.",
         "quotes": ["Landlord and Tenant each waive trial by jury in any action arising out of this Lease"]},
        {"id": "t-01-D3", "severity": "medium", "kind": "omission", "title": "CASp", "authority": "Civ. Code § 1938(a)",
         "authority_keys": ["1938"], "why": "No CASp statement.", "quotes": []},
    ],
}


@pytest.fixture()
def doc(tmp_path):
    (tmp_path / "t-01.md").write_text(DOC, encoding="utf-8")
    key = dict(KEY)
    (tmp_path / "t-01.key.json").write_text(json.dumps(key), encoding="utf-8")
    return load_document("t-01", tmp_path)


M = TimeModel()


# ---------- text normalisation and quote grounding ----------

def test_quote_grounding_tolerates_only_whitespace_quotes_dashes_and_bracketed_ellipsis():
    src = normalise("The “Tenant” shall pay   Rent\non the first day — without offset — of each month.")
    assert find_quote(src, 'The "Tenant" shall pay Rent on the first day')
    assert find_quote(src, "shall pay Rent [...] of each month.")
    assert find_quote(src, "on the first day - without offset")
    assert find_quote(src, "the tenant shall pay rent") is None          # case changed
    assert find_quote(src, "Tenant shall pay the Rent") is None          # word added
    assert find_quote(src, "of each month [...] shall pay Rent") is None  # out of order
    assert find_quote(src, "[...]") is None


def test_cites_matches_whole_section_numbers_only():
    assert cites("Civ. Code § 1950.7(c)", "1950.7")
    assert cites("Bus. & Prof. Code §§ 16600, 16600.5", "16600")
    assert not cites("Bus. & Prof. Code § 16600.5", "16600")
    assert not cites("Lab. Code § 1201", "201")
    assert not cites("Lab. Code § 201.3", "201")
    assert cites("Labor Code section 201(a)", "201")
    assert not cites("", "201")


# ---------- scoring ----------

def test_perfect_run(doc):
    run = {"tool_minutes": 5, "findings": [
        {"issue": "x", "authority": "Civ. Code § 1950.7", "quote": "return the Security Deposit within ninety (90) days after the Expiration Date"},
        {"issue": "x", "authority": "CCP 631", "quote": "each waive trial by jury in any action arising out of this Lease"},
        {"issue": "No CASp statement", "authority": "Civil Code section 1938", "quote": "Tenant shall comply with the Americans with Disabilities Act"},
    ]}
    s = score_document(doc, run, M)
    assert s.recall == 1.0 and s.high_recall == 1.0 and s.grounding == 1.0 and s.extra_findings == 0
    # 100 unaided; with tool: 5 setup + 5 run + 3 x 4 verify + 25 read-through + 0 residual = 47
    assert s.time_with_tool == pytest.approx(47.0) and s.net_minutes_saved == pytest.approx(53.0)
    assert [f.match_basis for f in s.findings] == ["quote", "quote", "citation"]


def test_empty_run_costs_time(doc):
    s = score_document(doc, {"tool_minutes": 2, "findings": []}, M)
    assert s.recall == 0 and s.high_recall == 0
    # 5 + 2 + 0 + 25 + 75 = 107, so the tool cost 7 minutes
    assert s.net_minutes_saved == pytest.approx(-7.0)


def test_paraphrased_quote_is_unverified_and_does_not_earn_recall(doc):
    run = {"findings": [{"issue": "x", "authority": "Civ. Code § 1950.7",
                         "quote": "Landlord will give back the deposit within 90 days of expiration"}]}
    s = score_document(doc, run, M)
    assert s.grounding == 0 and s.found == [] and s.findings[0].display_quote.startswith("[UNVERIFIED QUOTE]")
    # verification 4 + 6 penalty
    assert s.verification_minutes == pytest.approx(10.0)


def test_right_citation_wrong_clause_does_not_match_a_clause_defect(doc):
    run = {"findings": [{"issue": "x", "authority": "Civ. Code § 1950.7",
                         "quote": "All notices must be in writing and delivered to the addresses stated"}]}
    s = score_document(doc, run, M)
    assert s.found == [] and s.extra_findings == 1 and s.grounding == 1.0


def test_severity_weighting_of_missed_defects(doc):
    run = {"findings": [
        {"authority": "", "quote": "return the Security Deposit within ninety (90) days after the Expiration Date"},
        {"authority": "", "quote": "each waive trial by jury in any action arising out of this Lease"}]}
    s = score_document(doc, run, M)
    assert s.missed == ["t-01-D3"] and s.high_recall == 1.0
    # missed share = 1 of (2+2+1) = 0.2; residual = 25 + 75*0.2 = 40
    assert s.residual_minutes == pytest.approx(40.0)


def test_reviewer_adjudication_overrides_matching(doc):
    run = {"findings": [
        {"authority": "", "quote": "", "issue": "deposit timing", "adjudicated_defect": "t-01-D1"},
        {"authority": "Civ. Code § 1938", "quote": "", "adjudicated_defect": "none"}]}
    s = score_document(doc, run, M)
    assert s.found == ["t-01-D1"] and s.findings[1].matched_defect is None
    with pytest.raises(ValueError):
        score_document(doc, {"findings": [{"adjudicated_defect": "nope"}]}, M)


def test_measured_verification_time_replaces_the_estimate(doc):
    s = score_document(doc, {"attorney_verification_minutes": 30, "findings": [{"quote": "", "authority": ""}]}, M)
    assert s.verification_minutes == 30 and s.verification_measured


def test_two_findings_on_one_defect_count_once(doc):
    q = "return the Security Deposit within ninety (90) days after the Expiration Date"
    s = score_document(doc, {"findings": [{"quote": q, "authority": ""}, {"quote": q, "authority": ""}]}, M)
    assert s.found == ["t-01-D1"] and len(s.findings) == 2


def test_run_level_errors(doc):
    with pytest.raises(ValueError):
        score_run({"documents": [{"doc_id": "missing"}]}, {"t-01": doc}, M)
    with pytest.raises(ValueError):
        score_run({"documents": [{"doc_id": "t-01"}, {"doc_id": "t-01"}]}, {"t-01": doc}, M)


def test_time_model_file(tmp_path):
    p = tmp_path / "m.json"
    p.write_text('{"verify_minutes_per_finding": 10}')
    assert load_time_model(p).verify_minutes_per_finding == 10
    p.write_text('{"nope": 1}')
    with pytest.raises(ValueError):
        load_time_model(p)


def test_validator_catches_bad_keys(tmp_path):
    (tmp_path / "t-01.md").write_text(DOC, encoding="utf-8")
    bad = json.loads(json.dumps(KEY))
    bad["defects"][0]["quotes"] = ["Landlord shall return the Security Deposit within thirty (30) days after"]
    (tmp_path / "t-01.key.json").write_text(json.dumps(bad), encoding="utf-8")
    problems = validate_document("t-01", tmp_path)
    assert any("not found verbatim" in p for p in problems)
    assert any("expected 6 to 10" in p for p in problems)


# ---------- the shipped corpus ----------

DOC_IDS = list_doc_ids()


def test_corpus_has_three_documents_of_each_type():
    types = {}
    for d in DOC_IDS:
        types.setdefault(load_document(d).doc_type, []).append(d)
    assert {t: len(v) for t, v in types.items()} == {
        "commercial_lease": 3, "snf_rcfe_apa": 3, "public_works_contract": 3, "executive_employment": 3}


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_corpus_document_is_valid(doc_id):
    assert validate_document(doc_id) == []
    d = load_document(doc_id)
    assert d.word_count >= 5000
    assert all(x.spans for x in d.defects if x.kind == "clause")


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_corpus_keys_cite_only_verified_sections(doc_id):
    register = load_register()
    d = load_document(doc_id)
    assert [u for x in d.defects for u in unverified(x.authority, register)] == []
    for x in d.defects:
        assert all(cites(x.authority, k) for k in x.authority_keys), x.id


@pytest.mark.parametrize("doc_id", DOC_IDS)
def test_corpus_has_no_real_firm_names(doc_id):
    text = load_document(doc_id).text.lower()
    for word in ("hanson bridgett", "kaiser", "sutter health", "bart ", "caltrain"):
        assert word not in text


def test_sample_runs_score_and_report(tmp_path):
    docs = {d: load_document(d) for d in DOC_IDS}
    runs = {}
    for name in ("sample_tool_a", "sample_tool_b"):
        run = json.loads((HERE / "sample_runs" / f"{name}.json").read_text(encoding="utf-8"))
        runs[name] = score_run(run, docs, M)
    a, b = runs["sample_tool_a"], runs["sample_tool_b"]
    assert len(a.docs) == 12 and a.grounding == 1.0 and a.high_recall > b.high_recall
    assert b.grounding < 1.0 and a.net_minutes_saved > b.net_minutes_saved
    md = report.to_markdown(b)
    assert "[UNVERIFIED QUOTE]" in md and "not a measurement" in md
    assert report.to_csv(a).count("\n") == 13
    assert json.loads(report.dumps(a))["documents_scored"] == 12
    assert "Sample Tool A" in report.compare_markdown([a, b])


def test_cli_score_writes_files(tmp_path, capsys):
    assert main(["score", str(HERE / "sample_runs" / "sample_tool_a.json"), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "sample_tool_a.scorecard.md").exists()
    assert main(["prompt", DOC_IDS[0]]) == 0
    out = capsys.readouterr().out
    assert "Return only JSON" in out and "<document id=" in out
