import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from baseline import pipeline  # noqa: E402


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def config():
    return pipeline.load_json(os.path.join(ROOT, "data", "config.json"))


@pytest.fixture(scope="session")
def built(config):
    """Baseline and analysis built fresh from the committed sample data."""
    return pipeline.build_baseline(dict(config), ROOT, with_analysis=True)


@pytest.fixture(scope="session")
def baseline(built):
    return built[0]


@pytest.fixture(scope="session")
def analysis(built):
    return built[1]


@pytest.fixture(scope="session")
def checkpoint(config):
    return pipeline.build_baseline(dict(config), ROOT, period_end="2026-10-18")


@pytest.fixture(scope="session")
def key():
    with open(os.path.join(ROOT, "sample_data", "answer_key.json"), encoding="utf-8") as f:
        return json.load(f)
