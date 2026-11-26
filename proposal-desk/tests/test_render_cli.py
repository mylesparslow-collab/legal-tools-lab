import csv
import io
import json
import os
import re

import pytest

from conftest import AS_OF, RFPS
from desk import render
from desk.__main__ import main


@pytest.mark.parametrize("name", RFPS)
def test_markdown_draft_has_one_heading_per_requirement_in_order(name, built):
    md = render.draft_markdown(built[name])
    heads = [ln[3:] for ln in md.splitlines() if ln.startswith("## ")]
    assert heads == ["%s %s" % (s["label"], s["title"]) for s in built[name]["sections"]]
    assert "WORKING DRAFT" in md and "Not legal advice" in md


@pytest.mark.parametrize("name", RFPS)
def test_every_gap_is_marked_visibly_in_markdown_and_html(name, built):
    res = built[name]
    md, html = render.draft_markdown(res), render.draft_html(res)
    people = sum(1 for s in res["sections"] if s["status"] == "person")
    assert md.count("[NEEDS A PERSON:") == people == html.count('class="mark person"')
    for s in res["sections"]:
        if s["status"] == "partial":
            assert "[PARTIAL:" in md
        if s["status"] == "no_content":
            assert "[GAP:" in md and 'class="mark gap"' in html
    for f in res["go_no_go"]["blocking_flags"]:
        assert "[BLOCKING: %s]" % f["message"] in md


def test_blocking_and_gap_marks_cannot_be_hidden_by_the_toggle(built):
    html = render.draft_html(built["labor_negotiator_quillfeather_usd"])
    assert 'class="mark blocking"' in html
    hide_rule = re.search(r"#hide:checked[^{]*\{display:none\}", html).group(0)
    assert ".src" in hide_rule and ".check" in hide_rule
    assert "blocking" not in hide_rule and "gap" not in hide_rule and "person" not in hide_rule


@pytest.mark.parametrize("fn", [render.draft_html, render.matrix_html])
def test_html_is_self_contained(fn, built):
    html = fn(built["general_counsel_redwood_flats"])
    assert html.startswith("<!doctype html>")
    assert not re.search(r"https?://", html)
    assert "<link" not in html and "src=" not in html and "@import" not in html


def test_html_escapes_rfp_text(data):
    from conftest import rfp_text
    from desk.pipeline import build
    text = rfp_text("city_attorney_marlow_ridge").replace("5.5 Approach.", "5.5 Approach <script>alert(1)</script>.")
    html = render.draft_html(build(text, data, AS_OF))
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)" in html


def test_matrix_csv_has_one_row_per_item(built):
    res = built["special_counsel_tannery_creek_transit"]
    rows = list(csv.DictReader(io.StringIO(render.matrix_csv(res))))
    assert len(rows) == len(res["matrix"])
    assert set(rows[0]) >= {"id", "requirement", "status", "owner", "due", "answered_in"}
    assert {r["status"] for r in rows} <= set(res["status_labels"].values())


def test_matrix_html_has_the_disqualifier_panel(built):
    res = built["city_attorney_marlow_ridge"]
    html = render.matrix_html(res)
    assert "Disqualifiers: %d mandatory item(s) not yet satisfied" % len(res["disqualifiers"]) in html


def test_go_no_go_summary_has_the_four_headline_facts(built):
    md = render.go_no_go_markdown(built["general_counsel_redwood_flats"])
    assert "Thu 17 Dec 2026 at 14:00 (changed by Addendum 1; was Thu 10 Dec 2026 at 14:00)" in md
    assert "Met: 2. Not met: 0. Not checkable from bio or firm data: 1." in md
    assert "answered in full: 83%" in md
    assert "## Open disqualifiers:" in md
    assert "The tool does not make the decision" in md


def test_conflicts_csv_lists_the_parties_with_source_lines(built):
    rows = list(csv.DictReader(io.StringIO(render.conflicts_csv(built["special_counsel_tannery_creek_transit"]))))
    names = {r["name"]: r for r in rows}
    assert names["Granite Spur Constructors, Inc."]["category"] == "Adverse or counter-party"
    assert names["Cornelius Abernathy"]["rfp_line"].isdigit()


def test_cli_parse_with_key_and_json(tmp_path, capsys, root):
    rfp = os.path.join(root, "data", "rfps", "general_counsel_redwood_flats.txt")
    key = os.path.join(root, "data", "answer_keys", "general_counsel_redwood_flats.json")
    out = tmp_path / "p.json"
    assert main(["parse", rfp, "--json", str(out), "--key", key]) == 0
    printed = capsys.readouterr().out
    assert "changed by Addendum 1; was 2026-12-10" in printed and "| overall |" in printed
    assert json.loads(out.read_text())["meta"]["agency"] == "Redwood Flats Water District"


def test_cli_match_prints_reasons(capsys, root):
    rfp = os.path.join(root, "data", "rfps", "labor_negotiator_quillfeather_usd.txt")
    assert main(["match", rfp, "--as-of", AS_OF]) == 0
    printed = capsys.readouterr().out
    assert "Lead attorney: Priya Raghunathan" in printed and "Why:" in printed
    assert "Not considered (no longer with the firm): Corwin Halloway" in printed


def test_cli_draft_and_matrix_write_files(tmp_path, root):
    rfp = os.path.join(root, "data", "rfps", "city_attorney_marlow_ridge.txt")
    hol = os.path.join(root, "data", "holidays_sample.json")
    assert main(["draft", rfp, "--out", str(tmp_path), "--as-of", AS_OF, "--holidays", hol]) == 0
    assert main(["matrix", rfp, "--out", str(tmp_path), "--as-of", AS_OF]) == 0
    for f in ("draft.md", "draft.html", "go_no_go.md", "conflicts_parties.csv", "conflicts_parties.md",
              "matrix.html", "matrix.csv"):
        assert (tmp_path / f).stat().st_size > 200
    assert "A holiday file was supplied" in (tmp_path / "go_no_go.md").read_text()


def test_cli_check_data(capsys):
    assert main(["check-data"]) == 0
    assert "rejected records: 0" in capsys.readouterr().out


def test_index_demo_page_is_self_contained_and_shows_the_addendum_change(root):
    html = open(os.path.join(root, "index.html"), encoding="utf-8").read()
    assert not re.search(r"https?://", html) and "<link" not in html and "src=" not in html
    assert "Redwood Flats Water District" in html and "Changed by Addendum 1" in html
    for anchor in ("go", "dates", "disq", "matrixsec", "draft", "match", "conflicts", "parser"):
        assert 'id="%s"' % anchor in html
    assert "Not legal advice" in html and "invented" in html


def test_committed_sample_outputs_match_a_fresh_run(built, root):
    for name in RFPS:
        path = os.path.join(root, "output", name, "draft.md")
        expect = render.draft_markdown(built[name])
        if name == "general_counsel_redwood_flats":
            continue            # the demo applies a status file to this one; checked through the matrix below
        assert open(path, encoding="utf-8").read() == expect
        assert open(os.path.join(root, "output", name, "matrix.csv"), encoding="utf-8").read() == render.matrix_csv(built[name])


def test_text_rules_no_statute_citations_no_emoji(root):
    bad = re.compile(r"§|U\.S\.C\.|C\.F\.R\.|Gov(ernment)?\.? Code|Public Contract Code|[\U0001F300-\U0001FAFF☀-➿]")
    for folder, _, files in os.walk(root):
        if any(part in folder for part in ("__pycache__", ".pytest_cache", os.sep + "tests")):
            continue
        for f in files:
            if f.endswith((".py", ".md", ".txt", ".json", ".html", ".csv")):
                text = open(os.path.join(folder, f), encoding="utf-8").read()
                assert not bad.search(text), os.path.join(folder, f)
