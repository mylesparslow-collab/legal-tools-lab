import copy
import csv
import html
import json
import os
import re

from baseline import cli, outputs
from baseline.report import render_report
from baseline.summary import build_summary, pct

ID = re.compile(r"SYN-\d{4}|syn\d{4}@|Sample-\d{4}", re.I)


def read(root, name):
    with open(os.path.join(root, "output", name), encoding="utf-8") as f:
        return f.read()


def committed(root):
    return json.loads(read(root, "baseline.json"))


def sentence(summary, ident):
    return [s["text"] for s in summary if s["id"] == ident][0]


def test_committed_outputs_are_what_the_code_produces_now(root, baseline, tmp_path):
    written = outputs.write_outputs(baseline, str(tmp_path))
    assert len(written) >= 10
    for path in written:
        with open(path, encoding="utf-8") as f:
            assert f.read() == read(root, os.path.basename(path)), os.path.basename(path)


def test_every_summary_sentence_is_in_the_html_and_built_from_baseline_json(root):
    b = committed(root)
    page = read(root, "baseline_report.html")
    summary = build_summary(b)
    assert len(summary) >= 10
    for s in summary:
        assert html.escape(s["text"]) in page, s["id"]
    assert page.count("data-summary=") == len(summary)
    assert render_report(b) == page          # the report needs nothing but baseline.json


def test_summary_numbers_match_baseline_json(root):
    b = committed(root)
    s = build_summary(b)
    h = b["headline"]
    c = h["weekly_active_last_4_weeks"]
    assert "%s of lawyers" % pct(c["n"] / c["d"]) in sentence(s, "weekly_active")
    assert "(%d of %d lawyer-weeks)" % (c["n"], c["d"]) in sentence(s, "weekly_active")
    c = h["weekly_active_latest"]
    assert "%d of %d lawyers were active (%s)" % (c["n"], c["d"], pct(c["n"] / c["d"])) in sentence(s, "latest_week")
    assert b["meta"]["latest_week"] in sentence(s, "latest_week")
    c = h["regular_use"]
    assert sentence(s, "regular_use").startswith("%d of %d lawyers (%s)" % (c["n"], c["d"], pct(c["n"] / c["d"])))
    low = min(b["weekly_trend"], key=lambda w: w["rate"])
    assert sentence(s, "lowest_week") == "The lowest week was %s at %s (%d of %d)." % (
        low["week"], pct(low["n"] / low["d"]), low["n"], low["d"])
    for t in b["targets"]["targets"]:
        assert "month %d target of %s, %s" % (t["due_month"], pct(t["threshold"]), t["status"]) in sentence(s, "targets")
    for g in b["targets"]["gates"]:
        assert g["practice"] + " " + g["status"] in sentence(s, "gates")
        if g["rate"] is not None:
            assert "%s (%d of %d lawyer-weeks)" % (pct(g["n"] / g["d"]), g["n"], g["d"]) in sentence(s, "gates")
    for t in b["tools"]:
        u = t["cells"]["unused_licences"]
        assert "%d of %d %s licences (%s)" % (u["n"], u["d"], t["tool"], pct(u["n"] / u["d"])) in sentence(s, "unused_licences")
    o = b["survey"]["overall"]
    gap = sentence(s, "survey_gap")
    assert "(%d responses)" % b["survey"]["responses"] in gap
    assert "%s of responding lawyers (%d of %d)" % (pct(o["claimed"]["n"] / o["claimed"]["d"]), o["claimed"]["n"], o["claimed"]["d"]) in gap
    assert "%s of all lawyers (%d of %d)" % (pct(o["logged"]["n"] / o["logged"]["d"]), o["logged"]["n"], o["logged"]["d"]) in gap
    t = b["data_quality"]["ingestion"]["totals"]
    assert sentence(s, "data_quality").startswith("%d of %d export rows were dropped and %d were repaired" % (
        t["rows_dropped"], t["rows_read"], t["rows_repaired"]))


def test_every_number_in_the_summary_can_be_found_in_baseline_json(root):
    """No number may be typed into a sentence by hand: each must be a value, or a rounded rate, in the file."""
    b = committed(root)
    values, rates = set(), set()

    def collect(node):
        if isinstance(node, dict):
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)
        elif isinstance(node, bool):
            pass
        elif isinstance(node, (int, float)):
            values.add(str(int(node)) if float(node).is_integer() else ("%.1f" % node).rstrip("0").rstrip("."))
            if 0 <= node <= 1:
                rates.add(int(node * 100 + 0.5))
        elif isinstance(node, str):
            values.update(re.findall(r"\d+", node))

    collect(b)
    for s in build_summary(b):
        text = s["text"]
        for p in re.findall(r"(\d+)%", text):
            assert int(p) in rates, (s["id"], p)
        for n in re.findall(r"\d+(?:\.\d+)?", re.sub(r"\d+%", "", text)):
            assert n in values, (s["id"], n)


def test_summary_follows_the_data_when_the_data_changes(root):
    b = committed(root)
    before = build_summary(b)
    c = copy.deepcopy(b)
    c["headline"]["weekly_active_last_4_weeks"].update(n=700, rate=700 / c["headline"]["weekly_active_last_4_weeks"]["d"])
    c["targets"]["targets"][0]["status"] = "pass"
    after = build_summary(c)
    assert sentence(after, "weekly_active") != sentence(before, "weekly_active")
    assert "(700 of" in sentence(after, "weekly_active")
    assert "month 6 target of 50%, pass" in sentence(after, "targets")
    assert html.escape(sentence(after, "weekly_active")) in render_report(c)


def test_report_is_self_contained_and_has_no_script(root):
    page = read(root, "baseline_report.html")
    assert "<script" not in page and "<link" not in page and "<img" not in page and "@import" not in page
    urls = set(re.findall(r"https?://[^\s\"'<>]+", page))
    assert urls <= {"http://www.w3.org/2000/svg"}


def test_report_works_in_dark_mode_and_on_a_phone(root):
    page = read(root, "baseline_report.html")
    assert "prefers-color-scheme: dark" in page and "color-scheme: light dark" in page
    assert 'name="viewport"' in page and "overflow-x: auto" in page
    assert not re.search(r'fill="#|stroke="#', page)          # chart colours come from CSS variables


def test_charts_are_accessible_svg_with_a_table_each(root):
    page = read(root, "baseline_report.html")
    svgs = re.findall(r"<svg.*?</svg>", page, re.S)
    assert len(svgs) == 5
    for svg in svgs:
        assert 'role="img"' in svg and "aria-labelledby" in svg
        assert re.search(r"<title id=[^>]+>[^<]+</title><desc id=[^>]+>[^<]+</desc>", svg)
    assert page.count("<figure>") == page.count("Show the numbers") == 5
    for ident in ("c-trend", "c-practice", "c-role", "c-gap", "c-block"):
        assert 'id="%s-t"' % ident in page


def test_percentages_carry_their_numerator_and_denominator(root):
    page = read(root, "baseline_report.html")
    tables = "".join(re.findall(r"<table>.*?</table>", page, re.S))
    cells = re.findall(r"<td>(.*?)</td>", tables, re.S)
    with_pct = [c for c in cells if re.search(r"\d+%", c) and "nd" in c]
    assert len(with_pct) > 100
    for c in with_pct:
        assert re.search(r'title="\d+ of \d+', c) and re.search(r'class="nd">\d+ of \d+', c)
    bars = re.findall(r"<path class=\"s[12]\"[^>]*><title>([^<]+)</title>", page)
    assert bars and all(re.search(r"\d+% \(\d+ of \d+", t) for t in bars)
    b = committed(root)
    c = b["breakdowns"]["practice"]["rows"][2]["cells"]["weekly_active_last_4_weeks"]
    assert 'title="%d of %d person-weeks">%s</span>' % (c["n"], c["d"], pct(c["rate"])) in page


def test_report_has_data_quality_panel_definitions_and_synthetic_label(root):
    page = read(root, "baseline_report.html")
    assert 'id="h-dq"' in page and 'id="h-def"' in page
    assert "Synthetic demo data" in page and "not legal advice" in page
    assert "User not on the roster" in page and "count as zero, not as missing" in page


def test_no_individual_level_data_in_any_committed_output(root):
    out = os.path.join(root, "output")
    names = os.listdir(out)
    assert "baseline_individual_activity.csv" not in names
    for name in names:
        assert not ID.search(read(root, name)), name
    assert committed(root)["meta"]["individual_level_output"] is False


def test_suppressed_rows_in_csv_have_no_numbers(root):
    with open(os.path.join(root, "output", "baseline_by_practice.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    hidden = [r for r in rows if r["suppressed"]]
    assert hidden and all(r["numerator"] == r["denominator"] == r["rate"] == r["people"] == "" for r in hidden)
    assert {r["practice"] for r in hidden} >= {"Competition"}
    shown = [r for r in rows if not r["suppressed"]]
    assert all(int(r["people"]) >= 5 for r in shown)


def test_cli_report_keeps_individual_output_off_unless_asked(root, tmp_path, capsys):
    off, on = tmp_path / "off", tmp_path / "on"
    assert cli.main(["report", "--out-dir", str(off)]) == 0
    assert cli.main(["report", "--out-dir", str(on), "--include-individuals"]) == 0
    assert not (off / "baseline_individual_activity.csv").exists()
    assert (on / "baseline_individual_activity.csv").exists()
    assert "identifies individuals" in capsys.readouterr().out
    assert (off / "baseline_report.html").read_text(encoding="utf-8") == read(root, "baseline_report.html")


def test_cli_ingest_writes_quality_but_not_person_level_rows_by_default(tmp_path, capsys):
    assert cli.main(["ingest", "--out-dir", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data_quality.json"]
    assert not ID.search((tmp_path / "data_quality.json").read_text(encoding="utf-8"))
    events = tmp_path / "events.csv"
    assert cli.main(["ingest", "--out-dir", str(tmp_path), "--write-events", str(events)]) == 0
    with open(events, newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == ["person_id", "date", "tool", "feature", "interactions"]


def test_cli_compare_and_bad_mapping(root, tmp_path, capsys):
    out = os.path.join(root, "output")
    assert cli.main(["compare", os.path.join(out, "checkpoint.json"), os.path.join(out, "baseline.json"),
                     "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "compare.md").read_text(encoding="utf-8") == read(root, "compare.md")
    swapped = "sample_data/assistant_a_events.csv=mappings/assistant_b_daily.json"
    assert cli.main(["ingest", "--out-dir", str(tmp_path), "--source", swapped]) == 2
    assert "not in the file" in capsys.readouterr().err


def test_readme_says_what_this_is_near_the_top(root):
    with open(os.path.join(root, "README.md"), encoding="utf-8") as f:
        top = f.read()[:900].lower()
    assert "personal portfolio" in top and "synthetic" in top and "not legal advice" in top


def test_report_states_the_per_tool_population_and_still_shows_unlicensed_rows(root):
    page = read(root, "baseline_report.html")
    assert "Per-tool and any-tool figures" in page
    assert "counts only people who hold that tool's licence" in page
    assert "Use by someone without a licence for the tool" in page
    with open(os.path.join(root, "METRICS.md"), encoding="utf-8") as f:
        md = f.read()
    assert "only people who hold that tool's licence are\ncounted" in md
