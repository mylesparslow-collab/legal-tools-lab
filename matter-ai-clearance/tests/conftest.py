import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clearance import clauses, engine, lanes  # noqa: E402
from clearance.store import Store, load_policy  # noqa: E402

AS_OF = "2026-11-25"


@pytest.fixture(scope="session")
def patterns():
    return clauses.load_patterns()


@pytest.fixture(scope="session")
def store():
    return Store()


@pytest.fixture()
def policy():
    return load_policy()


@pytest.fixture()
def features():
    return lanes.load_lanes()[0]


@pytest.fixture()
def clear(store, patterns, policy, features):
    """clear(matter_or_id, features=None, policy=None, as_of=AS_OF) -> clearance record"""
    def run(matter, features_=None, policy_=None, as_of=AS_OF):
        if isinstance(matter, str):
            matter = store.matter(matter)
        return engine.clear_matter(matter, store, features_ or features, policy_ or policy, patterns, as_of)
    return run


def by_id(record):
    return {d["feature_id"]: d for d in record["decisions"]}
