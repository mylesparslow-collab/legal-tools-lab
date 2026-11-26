"""Reports, CLI, sample data and the committed demo outputs."""
import csv
import io
import json
import re
from html.parser import HTMLParser

import pytest

from clearance import DATA, cli, reports

ROOT = DATA.parent
AS_OF = "2026-11-25"
VOID = {"meta", "br", "link", "img", "hr", "input"}


class Balance(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.errors.append(tag)


def balanced(html):
    b = Balance()
    b.feed(html)
    return not b.errors and not b.stack


def test_sample_data_meets_the_brief(store):
    assert len(store.clients) >= 8 and len(store.matter_ids()) >= 10
    matters = [store.matter(i) for i in store.matter_ids()]
    assert any(m["data_flags"]["phi"] == "yes" for m in matters)
    assert any(m["data_flags"]["phi"] == "unknown" for m in matters)
    assert any(m["protective_order"]["present"] == "yes" for m in matters)
    assert any(m["additional_terms"] and m["additional_terms"][0]["role"] == "insurer" for m in matters)
    assert all("(fictional)" in c["name"] for c in store.clients.values())
    for d in store.all_document_entries():
        assert "(fictional)" in store.document_text(d["id"])


def test_memo_html_is_self_contained_and_escaped(clear, store):
    m = store.matter("M-1001")
    m["name"] = "Quenby <script>alert(1)</script> & co"
    html = reports.memo_html(clear(m))
    assert balanced(html)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert "Not legal advice" in html and "Not reviewed by an attorney" in html
    assert not re.search(r"(src|href)\s*=", html) and "http" not in html
    assert "no PHI in any tool except" in html
    assert "characters " in html and "quenby-ocg-2026" in html


def test_tracker_covers_every_party_and_shows_conflicts(store, patterns):
    rows = reports.tracker_rows(store, patterns)
    assert len(rows) == len(store.clients) + len(store.other_parties)
    table = list(csv.DictReader(io.StringIO(reports.tracker_csv(rows, patterns))))
    row = {r["party_id"]: r for r in table}
    assert row["marrowfinch"]["status"] == "needs_analyst_review"
    assert "ai_prohibited vs ai_permitted" in row["marrowfinch"]["conflicts"]
    assert row["marrowfinch"]["ai_prohibited"] == "marrowfinch-ocg-2024"
    assert row["drennick"]["silent"] == "all documents" and row["drennick"]["ai_prohibited"] == ""
    assert row["orrinthe"]["ai_prohibited"] == "orrinthe-el-2026; orrinthe-ocg-2026"
    assert row["pallister"]["status"] == "not_on_file"
    assert row["sablemere"]["ambiguous_spans"] == "2"
    assert row["tessaly"]["dismissed_by_analyst"] == "2"
    assert row["quillfether"]["pending_documents"] == "quillfether-ocg-v2-2026"
    assert balanced(reports.tracker_html(rows, patterns))


def test_change_report_shows_which_decisions_flip(store, patterns, policy, features):
    rep = reports.diff_terms("quillfether", "quillfether-ocg-v1-2025", "quillfether-ocg-v2-2026",
                             store, features, policy, patterns, AS_OF)
    assert {c["class"] for c in rep["classes_added"]} == {"consent_required", "data_residency_retention"}
    assert "ai_permitted" in {c["class"] for c in rep["classes_removed"]}
    assert rep["decisions_flipped"] == 7
    m = rep["matters"][0]
    assert m["matter_id"] == "M-1011" and "consent required" in m["banner_after"]
    flip = next(f for f in m["changes"] if f["feature_id"] == "suite-b.doc-summary")
    assert (flip["before"], flip["after"]) == ("ALLOWED_WITH_CONDITIONS", "NOT_ALLOWED")
    assert "POL-CT-03" in flip["rules_added"]
    assert rep["classes_added"][0]["spans"][0]["quote"]
    assert balanced(reports.diff_html(rep))


def test_change_report_with_the_same_document_changes_nothing(store, patterns, policy, features):
    rep = reports.diff_terms("quillfether", "quillfether-ocg-v1-2025", "quillfether-ocg-v1-2025",
                             store, features, policy, patterns, AS_OF)
    assert rep["decisions_flipped"] == 0 and not rep["classes_added"] and not rep["classes_removed"]
    assert rep["matters"][0]["changes"] == []


def test_change_report_does_not_alter_the_stored_matter(store, patterns, policy, features):
    before = store.matter("M-1011")
    reports.diff_terms("quillfether", "quillfether-ocg-v1-2025", "quillfether-ocg-v2-2026",
                       store, features, policy, patterns, AS_OF)
    assert store.matter("M-1011") == before


def test_cli_scan_terms_prints_hits_guards_and_measured_accuracy(capsys):
    assert cli.main(["scan-terms", "--client", "tessaly", "--evaluate"]) == 0
    out = capsys.readouterr().out
    assert "[consent_required]" in out and "negation guard G-NEG-01" in out
    assert re.search(r"overall: precision 0\.\d+, recall 0\.\d+", out)
    assert "misses:" in out


def test_cli_scan_terms_on_a_file(tmp_path, capsys):
    p = tmp_path / "letter.txt"
    p.write_text("Use of AI\n\nThe Firm shall not use generative AI on our matters.\n")
    assert cli.main(["scan-terms", str(p), "--json"]) == 0
    res = json.loads(capsys.readouterr().out)
    assert res[0]["document_id"] == "letter" and res[0]["hits"][0]["class"] == "ai_prohibited"


def test_cli_clear_writes_memo_files(tmp_path, capsys):
    assert cli.main(["clear", "--matter", "M-1008", "--as-of", AS_OF, "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "no protective-order material in any tool" in out
    rec = json.loads((tmp_path / "M-1008.json").read_text())
    assert rec["matter"]["id"] == "M-1008" and (tmp_path / "M-1008.html").exists()


def test_cli_clear_accepts_a_registry_file_as_lanes(capsys):
    assert cli.main(["clear", "--matter", "M-1003", "--as-of", AS_OF, "--json",
                     "--lanes", str(DATA / "registry_sample.json")]) == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["lanes_import_report"]["tools_read"] == 3
    assert {d["feature_id"] for d in rec["decisions"]} == {"intake-summarizer", "contract-compare", "idea-board"}


def test_cli_tracker_and_diff(tmp_path, capsys):
    assert cli.main(["tracker", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "client_terms_tracker.csv").read_text().startswith("party_id,")
    assert cli.main(["diff", "--client", "quillfether", "--replace", "quillfether-ocg-v1-2025",
                     "--with", "quillfether-ocg-v2-2026", "--as-of", AS_OF]) == 0
    assert "feature decisions flipped: 7" in capsys.readouterr().out


def test_cli_reports_errors_without_a_traceback(capsys):
    assert cli.main(["clear", "--matter", "M-9999"]) == 2
    assert "error:" in capsys.readouterr().err


def test_committed_outputs_match_a_fresh_run(clear, store):
    for mid in store.matter_ids():
        committed = json.loads((ROOT / "output" / "memos" / (mid + ".json")).read_text())
        assert committed == json.loads(json.dumps(clear(mid))), mid
        assert (ROOT / "output" / "memos" / (mid + ".html")).exists()
    for name in ("client_terms_tracker.csv", "client_terms_tracker.html", "change_report_quillfether.json",
                 "change_report_quillfether.html", "classifier_evaluation.txt", "clause_hits.json",
                 "registry_import_report.json", "matter_summary.txt"):
        assert (ROOT / "output" / name).stat().st_size > 0


def test_index_page_shows_four_matters_and_needs_no_network():
    html = (ROOT / "index.html").read_text()
    assert html.count('role="tabpanel"') == 4
    # M-1002 (PHI status unknown) is on the page so the hold outcome is visible.
    assert "M-1002" in html and "PHI status unknown" in html
    assert balanced(html)
    assert "http://" not in html and "https://" not in html and "<link" not in html
    assert "Not legal advice" in html


def test_runtime_code_uses_only_the_standard_library_and_no_network():
    allowed = {"argparse", "copy", "csv", "io", "json", "re", "sys", "datetime", "html", "pathlib", "shutil"}
    for path in list((ROOT / "clearance").glob("*.py")) + [ROOT / "run_demo.py"]:
        for line in path.read_text().splitlines():
            m = re.match(r"\s*(?:from|import)\s+([a-zA-Z_]+)", line)
            if m and not line.strip().startswith("from ."):
                assert m.group(1) in allowed | {"clearance"}, (path.name, line)


def test_open_questions_cover_every_code_used_in_policy(policy):
    text = (ROOT / "OPEN_QUESTIONS.md").read_text()
    codes = {r["open_question"] for r in policy["rules"] if r.get("open_question")}
    assert len(codes) >= 20
    for c in codes:
        assert ("### " + c) in text, c
