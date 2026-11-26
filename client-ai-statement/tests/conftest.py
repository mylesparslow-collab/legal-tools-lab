import copy
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from statement.model import load_claims, load_json  # noqa: E402

SAMPLES = ROOT / "samples"
AS_OF = date(2026, 11, 25)
LATER = date(2027, 5, 20)


def _load(name):
    return load_json(SAMPLES / name)


@pytest.fixture
def clean():
    return _load("registry.clean.json")


@pytest.fixture
def gaps():
    return _load("registry.gaps.json")


@pytest.fixture
def later():
    return _load("registry.later.json")


@pytest.fixture
def inputs():
    return _load("statement_inputs.json")


@pytest.fixture
def inputs_gaps():
    return _load("statement_inputs.gaps.json")


@pytest.fixture
def client_consent():
    return _load("client_terms.consent.json")


@pytest.fixture
def client_restricted():
    return _load("client_terms.restricted.json")


@pytest.fixture
def claims():
    return load_claims()


def tool(reg, tid):
    return next(t for t in reg["tools"] if t["id"] == tid)


def printed(stmt):
    return {s["claim_id"]: s for sec in stmt["sections"] for s in sec["sentences"]}


def all_text(stmt):
    return " ".join(s["text"] for sec in stmt["sections"] for s in sec["sentences"])


def ctx_for(reg, claims, as_of=AS_OF, inputs=None, client=None):
    from statement.build import make_context
    return make_context(reg, inputs or {}, client, as_of, claims["scopes"])


def variant_rule(claims, claim_id, variant_id):
    c = next(c for c in claims["claims"] if c["id"] == claim_id)
    return copy.deepcopy(next(v for v in c["variants"] if v["id"] == variant_id)["rule"])
