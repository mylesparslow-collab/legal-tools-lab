import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from desk.loader import load_data          # noqa: E402
from desk.pipeline import build            # noqa: E402
from desk.rfp import parse_rfp             # noqa: E402

AS_OF = "2026-11-25"
RFPS = ["city_attorney_marlow_ridge", "general_counsel_redwood_flats",
        "labor_negotiator_quillfeather_usd", "special_counsel_tannery_creek_transit"]


def rfp_text(name):
    with open(os.path.join(ROOT, "data", "rfps", name + ".txt"), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def data():
    return load_data(os.path.join(ROOT, "data", "library"))


@pytest.fixture(scope="session")
def parsed():
    return {name: parse_rfp(rfp_text(name)) for name in RFPS}


@pytest.fixture(scope="session")
def built(data):
    return {name: build(rfp_text(name), data, AS_OF) for name in RFPS}


@pytest.fixture()
def ctx(data):
    """Fact-guard context for a proposal to the Redwood Flats Water District."""
    from desk import facts as F
    meta = {"agency": "Redwood Flats Water District", "agency_short": "District", "agency_type": "special_district"}
    c = F.make_context(meta, data, "Board of Directors General Manager")
    c.update({"governing_body": "Board of Directors", "chief_exec": "General Manager"})
    return c
