import datetime as dt
import os
import sys
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from billcheck import guidelines as G  # noqa: E402
from billcheck import scoring  # noqa: E402
from billcheck.model import Invoice, Line  # noqa: E402

DATA = os.path.join(ROOT, "data")
D = Decimal


def mk_line(no, hours="1.2", rate="300", narrative="Draft responses to second set of interrogatories",
            tk="TK01", date=dt.date(2026, 10, 6), kind="fee", task="L310", act="A103", exp="",
            amount=None, name="Test Person", **extra):
    hours, rate = D(str(hours)), D(str(rate))
    return Line(
        line_no=no, kind=kind, date=date, timekeeper_id=tk if kind == "fee" else "", timekeeper_name=name if kind == "fee" else "",
        classification="AS", units=hours, rate=rate, adjustment=D("0"),
        amount=D(str(amount)) if amount is not None else (hours * rate).quantize(D("0.01")),
        task_code=task if kind == "fee" else "", activity_code=act if kind == "fee" else "",
        expense_code=exp, narrative=narrative, **extra,
    )


def mk_expense(no, amount="100.00", narrative="Deposition transcript", code="E115", units="1", **extra):
    return mk_line(no, hours=units, rate=amount, narrative=narrative, kind="expense", exp=code, **extra)


def mk_invoice(lines, client="testco", matter="M-1", invoice_date=dt.date(2026, 11, 5), total=None):
    line_sum = sum((ln.amount for ln in lines), D("0"))
    return Invoice(
        invoice_id="INV-T-1", client_id=client, matter_id=matter, invoice_date=invoice_date,
        billing_start=dt.date(2026, 10, 1), billing_end=dt.date(2026, 10, 31),
        declared_total=D(str(total)) if total is not None else line_sum, source_format="test", lines=list(lines),
    )


def mk_rule(rule_type, params=None, severity=None, status="confirmed", rule_id=None):
    rule = {
        "rule_id": rule_id or "T-%s" % rule_type.upper(),
        "type": rule_type,
        "status": status,
        "severity": severity or G.RULE_TYPES[rule_type]["severity"],
        "params": params or {},
        "source_quote": "Test sentence for %s." % rule_type,
        "source_ref": "Section 1, page 1",
    }
    if status == "confirmed":
        rule["confirmed_by"] = "tester"
        rule["confirmed_on"] = "2026-09-01"
    return rule


def mk_guideline(*rules, client="testco"):
    return G.from_dict({"client_id": client, "client_name": "Test Co", "document": "none", "rules": list(rules)})


def mk_matter(**timekeepers):
    cards = {}
    for tk, spec in timekeepers.items():
        if not isinstance(spec, dict):
            spec = {"approved_rate": str(spec)}
        spec.setdefault("last_billed_rate", spec["approved_rate"])
        spec.setdefault("rate_notice_date", None)
        cards[tk] = spec
    return {"matter_id": "M-1", "client_id": "testco", "timekeepers": cards, "approvals": {}}


@pytest.fixture(scope="session")
def data_dir():
    return DATA


@pytest.fixture(scope="session")
def results():
    return scoring.check_all(DATA)


@pytest.fixture(scope="session")
def by_invoice(results):
    return {r.invoice.invoice_id: r for r in results}


@pytest.fixture(scope="session")
def answer_key():
    return scoring.load_answer_key(DATA)


@pytest.fixture(scope="session")
def guides():
    return {g.client_id: g for g in G.load_all(os.path.join(DATA, "guidelines"))}
