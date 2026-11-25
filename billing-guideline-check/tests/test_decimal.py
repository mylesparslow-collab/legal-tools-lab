"""Money and hours are decimal.Decimal everywhere. No binary floats in money paths."""

import ast
import dataclasses
import json
import os
from decimal import Decimal

import pytest

from billcheck import guidelines as G
from billcheck import report
from billcheck.model import DataError, dec, money
from conftest import ROOT


def python_sources():
    files = [os.path.join(ROOT, "generate_data.py"), os.path.join(ROOT, "run_demo.py")]
    package = os.path.join(ROOT, "billcheck")
    files += [os.path.join(package, name) for name in sorted(os.listdir(package)) if name.endswith(".py")]
    return files


@pytest.mark.parametrize("path", python_sources(), ids=lambda p: os.path.basename(p))
def test_source_has_no_float_literals_or_float_calls(path):
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            problems.append("float literal %r on line %d" % (node.value, node.lineno))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
            problems.append("float() call on line %d" % node.lineno)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            # true division of ints would produce a float; Decimal division is allowed only where reviewed
            if not path.endswith(("engine.py", "report.py")):
                problems.append("true division on line %d" % node.lineno)
    assert problems == []


def test_every_numeric_field_of_every_sample_line_is_decimal(results):
    for result in results:
        assert isinstance(result.invoice.declared_total, Decimal)
        for line in result.invoice.lines:
            for name in ("units", "rate", "adjustment", "amount"):
                assert type(getattr(line, name)) is Decimal, (result.invoice.invoice_id, line.line_no, name)
            assert line.cost is None or type(line.cost) is Decimal


def test_no_float_anywhere_in_results(results):
    def walk(value, path):
        assert not isinstance(value, float), path
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            for f in dataclasses.fields(value):
                if f.name not in ("invoice", "guideline", "matter"):
                    walk(getattr(value, f.name), path + "." + f.name)
        elif isinstance(value, dict):
            for k, v in value.items():
                walk(v, "%s[%r]" % (path, k))
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                walk(v, "%s[%d]" % (path, i))

    for result in results:
        walk(result, result.invoice.invoice_id)
        assert type(result.total_at_risk) is Decimal
        for f in result.findings:
            assert type(f.amount_at_risk) is Decimal


def test_dec_refuses_binary_floats():
    with pytest.raises(DataError, match="float"):
        dec(float("0.1"))
    assert dec("0.1") + dec("0.2") == Decimal("0.3")
    assert dec(3) == Decimal(3)


def test_json_loader_reads_decimals_not_floats(data_dir):
    assert type(G.loads('{"x": 0.1}')["x"]) is Decimal
    matters = G.load_matters(os.path.join(data_dir, "matters.json"))

    def walk(value):
        assert not isinstance(value, float)
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(matters)


def test_json_output_writes_money_as_strings_with_two_places(by_invoice):
    data = json.loads(report.result_json(by_invoice["INV-Q-1001"]))
    assert data["totals"]["total_at_risk"] == "4334.40"
    for finding in data["findings"]:
        assert isinstance(finding["amount_at_risk"], str)
        assert len(finding["amount_at_risk"].split(".")[1]) == 2


def test_money_rounds_half_up():
    assert money(Decimal("1.005")) == Decimal("1.01")
    assert money(Decimal("2.675")) == Decimal("2.68")
