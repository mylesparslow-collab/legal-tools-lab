import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.common import load_params  # noqa: E402


@pytest.fixture
def params():
    return load_params()


@pytest.fixture
def clean():
    return json.loads((ROOT / "sample_data" / "ifoa_ledger_clean.json").read_text())


@pytest.fixture
def seeded():
    return json.loads((ROOT / "sample_data" / "ifoa_ledger.json").read_text())


@pytest.fixture
def campus():
    return json.loads((ROOT / "sample_data" / "seismic_campus.json").read_text())
