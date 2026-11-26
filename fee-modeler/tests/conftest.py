import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feemodel import backtest  # noqa: E402
from feemodel.engine import Workspace, default_paths  # noqa: E402


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def ws():
    """The committed synthetic export, shape A."""
    return Workspace(**default_paths(ROOT))


@pytest.fixture(scope="session")
def ws_b():
    """The same synthetic firm exported in shape B."""
    paths = default_paths(ROOT)
    paths["export_dir"] = os.path.join(ROOT, "data", "export_b")
    paths["mapping_path"] = os.path.join(ROOT, "data", "mappings", "export_b.json")
    return Workspace(**paths)


@pytest.fixture(scope="session")
def bt(ws):
    records = backtest.walk_forward(ws.dataset, ws.book, ws.rate_card)
    summary = backtest.summarize_backtest(records, ws.dataset, ws.book, ws.rate_card)
    table = backtest.modelability(ws.dataset, ws.book, summary)
    return records, summary, table
