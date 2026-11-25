import ast
import json
import os
import re
from decimal import Decimal

import pytest

from feemodel import memo, site
from feemodel.cli import main
from feemodel.engine import price_proposal, to_jsonable
from feemodel.loader import load_json

MONEY_PATH_MODULES = ["money.py", "loader.py", "cost.py", "comps.py", "stats.py", "pricing.py", "backtest.py",
                      "engine.py", "profile.py", "schema.py"]


def no_json_floats(path):
    def boom(text):
        raise AssertionError("float %s found in %s" % (text, path))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_float=boom)


@pytest.fixture(scope="module")
def p001(ws, root):
    return price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))


def test_no_float_calls_or_literals_in_money_path_modules(root):
    for name in MONEY_PATH_MODULES:
        with open(os.path.join(root, "feemodel", name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
                raise AssertionError("float() call in %s line %d" % (name, node.lineno))
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                raise AssertionError("float literal in %s line %d" % (name, node.lineno))


def test_result_holds_decimals_and_json_holds_strings(p001, tmp_path):
    def walk(obj, path="result"):
        assert not isinstance(obj, float), "float at %s" % path
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, "%s.%s" % (path, k))
        elif isinstance(obj, (list, tuple, set, frozenset)):
            for i, v in enumerate(obj):
                walk(v, "%s[%d]" % (path, i))
    walk(p001)
    assert isinstance(p001["distribution"]["normalized"]["quantiles"]["p50"], Decimal)
    assert isinstance(p001["scenarios"][0]["expected_margin"], Decimal)
    j = to_jsonable(p001)
    assert isinstance(j["distribution"]["normalized"]["quantiles"]["p50"], str)
    assert re.fullmatch(r"-?\d+\.\d\d", j["scenarios"][0]["expected_margin"])
    with pytest.raises(TypeError):
        to_jsonable({"fee": 1.5})


def test_committed_json_outputs_contain_no_floats(root):
    out = os.path.join(root, "output")
    names = [n for n in os.listdir(out) if n.endswith(".json")]
    assert len(names) >= 8
    for name in names:
        no_json_floats(os.path.join(out, name))


def test_memo_never_shows_a_number_without_its_comps(p001):
    html = memo.render_memo(p001)
    n = p001["selection"]["n"]
    assert html.count("n=%d" % n) >= 6
    for comp in p001["selection"]["comps"]:
        assert comp["matter_id"] in html                 # every comp is listed
    for line in p001["selection"]["rules"]:
        assert line.replace("<", "&lt;") in html         # and so is every selection rule
    assert "Appendix: the %d comps" % n in html


def test_memo_is_self_contained_accessible_and_themed(p001):
    html = memo.render_memo(p001)
    assert "http://" not in html and "https://" not in html and "<script" not in html and "<link" not in html
    assert html.count('role="img"') == 2 and html.count("<title id=") == 2 and html.count("<desc id=") == 2
    assert "prefers-color-scheme:dark" in html and "@media print" in html
    assert '<html lang="en">' in html
    assert "Fixed fee $90,000" in html                    # the proposed fee is marked on the chart
    assert "Not financial, pricing or legal advice" in html
    assert "PLACEHOLDER" in html                          # cost rates are labelled as an input, not a fact


def test_memo_labels_ai_assumptions_as_the_users(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-002.json")))
    html = memo.render_memo(r)
    assert "user assumption" in html and "not predictions" in html
    assert r["ai"]["any_applied"] is True
    assert r["ai"]["total"]["median_value_after"] < r["ai"]["total"]["median_value_before"]
    none = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    assert none["ai"]["any_applied"] is False
    assert "None were entered" in memo.render_memo(none)


def test_displayed_figures_are_rounded_json_keeps_cents(p001):
    html = memo.render_memo(p001)
    assert not re.search(r"\$\d[\d,]*\.\d", html)          # no cents anywhere in the memo
    exact = to_jsonable(p001)["distribution"]["normalized"]["quantiles"]["p50"]
    assert "." in exact


def test_refusal_memo_shows_no_fee_figures(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-004.json")))
    html = memo.render_memo(r)
    assert "No fee figures are shown" in html and "8 required" in html
    assert "P50" not in html and "Pricing scenarios" not in html and "<svg" not in html


def test_price_cli_writes_memo_and_json(tmp_path, root, capsys):
    code = main(["price", "--proposal", os.path.join(root, "data", "proposals", "P-003.json"), "--out", str(tmp_path)])
    assert code == 0
    assert "n=41 comps" in capsys.readouterr().out
    data = no_json_floats(os.path.join(tmp_path, "memo_P-003.json"))
    assert data["status"] == "modeled" and data["selection"]["n"] == 41
    assert os.path.getsize(os.path.join(tmp_path, "memo_P-003.html")) > 5000
    code = main(["price", "--proposal", os.path.join(root, "data", "proposals", "P-004.json"), "--out", str(tmp_path)])
    assert code == 3                                       # refused, and says so through the exit code


def test_comps_cli_prints_rules_and_comp_list(root, capsys):
    assert main(["comps", "--proposal", os.path.join(root, "data", "proposals", "P-002.json")]) == 0
    out = capsys.readouterr().out
    assert "Selection rules:" in out and "Number of units between 2 and 4." in out
    assert "20 selected" in out and out.count("\nM-") == 20
    assert main(["comps", "--proposal", os.path.join(root, "data", "proposals", "P-004.json")]) == 3
    assert "Not modeled" in capsys.readouterr().out


def test_backtest_cli_and_same_answer_from_either_export_shape(tmp_path, root, capsys):
    assert main(["backtest", "--out", str(tmp_path / "a")]) == 0
    out_a = capsys.readouterr().out
    assert "ALL TYPES" in out_a and "nominal 50%" in out_a
    assert main(["backtest", "--out", str(tmp_path / "b"), "--data", os.path.join(root, "data", "export_b"),
                 "--mapping", os.path.join(root, "data", "mappings", "export_b.json")]) == 0
    a = no_json_floats(os.path.join(tmp_path, "a", "backtest.json"))
    b = no_json_floats(os.path.join(tmp_path, "b", "backtest.json"))
    assert a["summary"]["by_type"] == b["summary"]["by_type"]
    html = open(os.path.join(tmp_path, "a", "modelability.html"), encoding="utf-8").read()
    assert "Not modelable" in html and "Modelable with care" in html and "http" not in html


def test_cli_reports_bad_input_plainly(tmp_path, capsys):
    bad = tmp_path / "p.json"
    bad.write_text(json.dumps({"matter_type": "public_records_litigation", "as_of": "2026-01-01",
                               "selection_rules": {"forums": "same"}}))
    assert main(["price", "--proposal", str(bad), "--out", str(tmp_path)]) == 1
    assert "unknown selection rule" in capsys.readouterr().err


def test_index_page_is_static_and_matches_python_figures(ws, bt, root):
    with open(os.path.join(root, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    assert "https://" not in html and "src=" not in html and "<link" not in html and "fetch(" not in html
    assert html.count("http://") == 1 and "http://www.w3.org/2000/svg" in html     # the SVG namespace string only
    assert "Not financial, pricing or legal advice" in html and "synthetic" in html
    data = json.loads(re.search(r'id="explorer-data">(.*?)</script>', html, re.S).group(1))
    assert [p["id"] for p in data] == ["P-001", "P-002", "P-003", "P-003b"]        # the refused one has no explorer
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    fixed = r["scenarios"][0]
    comps = data[0]["comps"]
    fee_cents = 9000000
    assert all(isinstance(c["v"], int) and isinstance(c["c"], int) for c in comps)
    assert sum(1 for c in comps if c["v"] <= fee_cents) == fixed["under_fee"]["count"]
    assert sum(1 for c in comps if c["c"] <= fee_cents) == fixed["no_loss"]["count"]
    _records, summary, table = bt
    assert site.render_index([r], summary, table).count("<h2>") == 5


def test_demo_outputs_exist_and_match_a_fresh_run(ws, root):
    out = os.path.join(root, "output")
    for name in ("backtest.json", "backtest.txt", "modelability.html", "modelability.json", "profile_export_a.txt",
                 "profile_export_b.txt", "memo_P-001.html", "memo_P-001.json", "memo_P-004.html"):
        assert os.path.isfile(os.path.join(out, name)), name
    for pid in ("P-001", "P-002", "P-003", "P-003b", "P-004"):
        fresh = to_jsonable(price_proposal(ws, load_json(os.path.join(root, "data", "proposals", pid + ".json"))))
        assert fresh == no_json_floats(os.path.join(out, "memo_%s.json" % pid)), pid
