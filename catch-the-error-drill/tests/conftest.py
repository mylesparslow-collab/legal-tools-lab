import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT.parent / "governance-eval-kit"
sys.path.insert(0, str(ROOT))

import build as build_mod  # noqa: E402


@pytest.fixture(scope="session")
def data():
    return build_mod.build()


@pytest.fixture(scope="session")
def docs(data):
    return {d["id"]: d for d in data["docs"]}


def js(*calls):
    """Run functions from app/scoring.js in Node. Each call is (name, *args)."""
    payload = {"calls": [{"fn": c[0], "args": list(c[1:])} for c in calls]}
    out = subprocess.run(["node", str(ROOT / "tests" / "run_scoring.js")], input=json.dumps(payload),
                         capture_output=True, text=True, check=True)
    results = json.loads(out.stdout)
    return results[0] if len(calls) == 1 else results
