"""Tests for the AI Tool Registry."""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import registry as r  # noqa: E402

EXAMPLE = json.loads((HERE / "registry.example.json").read_text(encoding="utf-8"))
BLANK = json.loads((HERE / "registry.blank.json").read_text(encoding="utf-8"))


def test_example_is_valid_and_flags_what_it_should():
    errors, flags = r.check(EXAMPLE)
    assert errors == []
    assert flags["checklist-agents"] == []
    assert flags["deadline-helper"] == []
    f = " ".join(flags["general-drafting-assistant"])
    for expected in ("No business owner", "Training use", "no citation verification log", "Last review was 237 days ago"):
        assert expected in f


def test_blank_template_is_valid_shape():
    assert r.validate(BLANK, r.load_schema()) == []


def test_schema_errors_are_reported_with_paths():
    bad = copy.deepcopy(EXAMPLE)
    bad["tools"][0]["status"] = "live"
    del bad["tools"][1]["sb574_log"]
    bad["tools"][2]["golden_set"]["high_severity_recall"] = 1.4
    bad["tools"][2]["surprise"] = 1
    bad["as_of"] = "25 Nov 2026"
    errors, _ = r.check(bad)
    text = "\n".join(errors)
    assert "$.tools[0].status" in text and "missing 'sb574_log'" in text
    assert "above maximum" in text and "unknown field 'surprise'" in text and "not a date" in text


def test_duplicate_ids_rejected():
    bad = copy.deepcopy(EXAMPLE)
    bad["tools"][1]["id"] = bad["tools"][0]["id"]
    assert any("duplicate" in e for e in r.check(bad)[0])


def _tool(**changes):
    reg = copy.deepcopy(EXAMPLE)
    t = reg["tools"][0]
    for path, value in changes.items():
        obj = t
        keys = path.split("__")
        for k in keys[:-1]:
            obj = obj[k]
        obj[keys[-1]] = value
    return r.tool_flags(t, reg)


def test_individual_flags():
    assert any("180" in f or "days ago" in f for f in _tool(last_review="2026-01-01"))
    assert any("days old" in f for f in _tool(ocg_check__last_checked="2026-06-01"))
    assert any("no outside counsel guideline check" in f for f in _tool(ocg_check__method="none"))
    assert any("without a golden-set score" in f for f in _tool(golden_set={"status": "not_run"}))
    assert any("below the pass mark" in f for f in _tool(golden_set__passes=False))
    assert any("business associate" in f for f in _tool(
        data_boundary__data_allowed=["client_confidential", "health_information"]))
    assert any("court disclosure step" in f for f in _tool(sb574_log__court_filing_use="yes"))
    assert any("No human review" in f for f in _tool(human_review=""))


def test_render_outputs(tmp_path):
    assert r.main(["render", str(HERE / "registry.example.json"), "--out", str(tmp_path)]) == 0
    page = (tmp_path / "registry.html").read_text(encoding="utf-8")
    assert "Larkspur &amp; Vane LLP (fictional)" in page and "<script" not in page
    assert page.count("<tr>") == 1 + len(EXAMPLE["tools"])
    md = (tmp_path / "registry.md").read_text(encoding="utf-8")
    assert md.count("\n| ") == 2 + len(EXAMPLE["tools"])
    assert (tmp_path / "registry.csv").read_text(encoding="utf-8").startswith("Tool,Status,Owner")


def test_check_exit_codes(tmp_path, capsys):
    assert r.main(["check", str(HERE / "registry.example.json")]) == 0
    p = tmp_path / "bad.json"
    p.write_text('{"organization": "x"}')
    assert r.main(["check", str(p)]) == 1
