import csv
import io
import json
import os
import re

import pytest

from billcheck import report
from billcheck.cli import main
from billcheck.model import fmt_money
from conftest import DATA, ROOT, mk_guideline, mk_invoice, mk_line, mk_rule
from billcheck.engine import check_invoice

EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["'](?:https?:)?//|@import|url\(\s*["']?https?:""", re.I)


def test_html_report_is_self_contained_sortable_and_printable(by_invoice):
    html = report.html_report(by_invoice["INV-Q-1001"])
    assert not EXTERNAL.search(html)
    assert "<script>" in html and "data-sortable" in html
    assert 'data-col="3">by timekeeper' in html and 'data-col="0">by severity' in html
    assert "@media print" in html
    assert "Personal portfolio demo. Fictional data. Not legal or billing advice." in html


def test_html_report_shows_quote_reference_and_waiver(by_invoice):
    html = report.html_report(by_invoice["INV-Q-1001"])
    assert "Time must be recorded in increments of 0.1 hour." in html
    assert "3.1 Time increments, page 2" in html
    assert "Waived by the client" in html and "W-001" in html and "sev-waived" in html
    assert "Not checked:" in html


def test_html_escapes_narrative_text():
    inv = mk_invoice([mk_line(1, hours="0.25", narrative='Review <script>alert("x")</script> & exhibits')])
    result = check_invoice(inv, mk_guideline(mk_rule("minimum_increment", {"increment": "0.1"})))
    html = report.html_report(result)
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; exhibits" in html


def test_summary_paragraph_is_built_from_the_numbers(by_invoice):
    result = by_invoice["INV-Q-1001"]
    text = report.summary_paragraph(result)
    counts = result.severity_counts()
    assert "\n" not in text
    assert "totals %s across %d lines" % (fmt_money(result.invoice.line_total), len(result.invoice.lines)) in text
    assert "found %d open findings" % len(result.open_findings) in text
    assert "%d will likely be rejected, %d likely reduced and %d for review" % (counts["reject"], counts["reduce"], counts["review"]) in text
    assert fmt_money(result.total_at_risk) in text
    assert "1 finding is covered by a client waiver" in text


def test_summary_for_clean_invoice_and_for_unconfirmed_rule(by_invoice):
    assert "found no open findings" in report.summary_paragraph(by_invoice["INV-O-3002"])
    assert "1 proposed rule was not enforced because it is not confirmed" in report.summary_paragraph(by_invoice["INV-P-5001"])


def test_timekeeper_notes_cover_each_person_with_open_findings(by_invoice):
    result = by_invoice["INV-Q-1001"]
    notes = report.timekeeper_notes(result)
    assert set(notes) == {f.timekeeper_id for f in result.open_findings if f.timekeeper_id}
    note = notes["TK03"]
    assert note.startswith("To: Rowan Achterberg (TK03)")
    assert 'Your entry: "Review documents"' in note
    assert "Client rule (QMI-VAGUE-01" in note
    assert "TK01" not in note and "Odalys" not in note  # one person's note does not show another's entries
    own_lines = {f.line_no for f in result.open_findings if f.timekeeper_id == "TK03" and f.line_no is not None}
    expected = sum(result.entry_at_risk[n] for n in own_lines)
    assert "Amount at risk on your entries: %s." % fmt_money(expected) in note


def test_waived_finding_is_left_out_of_timekeeper_note(by_invoice):
    note = report.timekeeper_notes(by_invoice["INV-Q-1001"])["TK02"]
    assert "2026-10-20" in note
    waived = by_invoice["INV-Q-1001"].waived_findings[0]
    assert "Line %d," % waived.line_no not in note


def test_findings_csv_has_one_row_per_finding(by_invoice):
    result = by_invoice["INV-L-4001"]
    rows = list(csv.DictReader(io.StringIO(report.findings_csv(result))))
    assert len(rows) == len(result.findings)
    assert {r["severity"] for r in rows} <= {"will likely be rejected", "likely reduced", "review"}
    assert all(r["source_quote"] and r["rule_id"] for r in rows)


def test_result_json_round_trips(by_invoice):
    result = by_invoice["INV-B-2001"]
    data = json.loads(report.result_json(result))
    assert data["invoice"]["invoice_id"] == "INV-B-2001"
    assert data["totals"]["open_findings"] == len(result.open_findings)
    assert data["summary"] == report.summary_paragraph(result)
    assert len(data["findings"]) == len(result.findings)
    assert data["notice"].startswith("Personal portfolio demo")


def test_comparison_lists_every_rule_type_for_every_client(guides):
    from billcheck.guidelines import RULE_TYPES

    clients, rows = report.comparison(list(guides.values()))
    assert len(clients) == 5 and len(rows) == len(RULE_TYPES)
    cells = {rule_type: c for rule_type, _, c in rows}
    assert cells["ai_disclosure_required"]["luminqa"].startswith("yes")
    assert cells["ai_disclosure_required"]["quillfeather"] == ""
    assert cells["budget_cap"]["brackenmoor"] == "yes"
    assert cells["late_time"]["pellwick"].startswith("proposed, not enforced")
    assert cells["daily_hour_cap"]["ostervane"] == "yes (12 h a day)"
    table = list(csv.reader(io.StringIO(report.comparison_csv(list(guides.values())))))
    assert len(table) == len(RULE_TYPES) + 1 and len(table[0]) == 7


def test_index_page_is_static_and_links_to_local_reports():
    with open(os.path.join(ROOT, "index.html"), "r", encoding="utf-8") as handle:
        html = handle.read()
    assert not EXTERNAL.search(html)
    links = re.findall(r'href="([^"]+)"', html)
    assert len(links) == 7
    for link in links:
        assert os.path.isfile(os.path.join(ROOT, link)), link
    assert "64 planted violations" in html and "Guidelines comparison" in html


def test_cli_intake_writes_proposed_rules(tmp_path, capsys):
    out = tmp_path / "proposed.json"
    code = main(["intake", os.path.join(DATA, "guideline_docs", "luminqa.txt"), "--client-id", "luminqa", "-o", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["rules"]) == 9 and {r["status"] for r in data["rules"]} == {"proposed"}
    assert "needs confirmation" in capsys.readouterr().err


def test_cli_check_writes_all_outputs(tmp_path, capsys):
    code = main([
        "check", os.path.join(DATA, "invoices", "INV-O-3001.csv"),
        "--guidelines", os.path.join(DATA, "guidelines", "ostervane.json"),
        "--matters", os.path.join(DATA, "matters.json"),
        "--waivers", os.path.join(DATA, "waivers.json"),
        "--out-dir", str(tmp_path),
    ])
    assert code == 0
    names = sorted(os.listdir(tmp_path))
    assert names == ["INV-O-3001.csv", "INV-O-3001.html", "INV-O-3001.json", "INV-O-3001.summary.txt", "INV-O-3001.timekeeper_notes.txt"]
    assert "Draft invoice INV-O-3001" in capsys.readouterr().out


def test_cli_check_prints_findings_without_out_dir(capsys):
    code = main([
        "check", os.path.join(DATA, "invoices", "INV-P-5001.ledes.txt"),
        "--guidelines", os.path.join(DATA, "guidelines", "pellwick.json"),
        "--matters", os.path.join(DATA, "matters.json"),
    ])
    out = capsys.readouterr().out
    assert code == 0 and "PBS-DUP-01" in out and "[will likely be rejected]" in out


def test_cli_compare_formats(tmp_path, capsys):
    assert main(["compare", os.path.join(DATA, "guidelines")]) == 0
    text = capsys.readouterr().out
    assert "Block billing prohibited" in text and "quillfeather" in text
    out = tmp_path / "compare.html"
    assert main(["compare", os.path.join(DATA, "guidelines"), "--format", "html", "-o", str(out)]) == 0
    assert "<table" in out.read_text(encoding="utf-8")


def test_cli_reports_errors_with_exit_code_2(tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("LEDES1998B[]\nnot the header[]\n", encoding="utf-8")
    code = main(["check", str(bad), "--guidelines", os.path.join(DATA, "guidelines", "pellwick.json")])
    assert code == 2 and "error:" in capsys.readouterr().err
    code = main(["check", os.path.join(DATA, "invoices", "INV-P-5001.ledes.txt"), "--guidelines", os.path.join(DATA, "guidelines", "luminqa.json")])
    assert code == 2


def test_cli_requires_a_command():
    with pytest.raises(SystemExit):
        main([])
