"""Tests for the Copilot agent pack."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import build_agents as b  # noqa: E402
from authorities import load_register, unverified  # noqa: E402

CHECKLISTS = {c["id"]: c for c in b.load_checklists()}
EXPECTED = {"brown-act-check", "cpra-intake", "public-works-check", "arbitration-check", "fair-hearing-map"}


def test_the_five_agents_exist():
    assert set(CHECKLISTS) == EXPECTED


@pytest.mark.parametrize("agent_id", sorted(EXPECTED))
def test_every_citation_is_in_the_verified_register(agent_id):
    register = load_register()
    missing = [(it["check"][:40], u) for it in CHECKLISTS[agent_id]["items"]
               for a in it["authority"] for u in unverified(a, register)]
    assert not missing


@pytest.mark.parametrize("agent_id", sorted(EXPECTED))
def test_manifest_limits(agent_id):
    c = CHECKLISTS[agent_id]
    da = b.declarative_agent(c)
    assert da["version"] == "v1.9"
    assert 0 < len(da["name"]) <= 100
    assert 0 < len(da["description"]) <= 1000
    assert 0 < len(da["instructions"]) <= 8000
    assert 1 <= len(da["conversation_starters"]) <= 12
    assert all(s["text"].strip() for s in da["conversation_starters"])
    assert "capabilities" not in da and "actions" not in da  # no web search, no connectors, no plugins
    m = b.app_manifest(c)
    assert len(m["name"]["short"]) <= 30 and len(m["description"]["short"]) <= 80
    assert m["copilotAgents"]["declarativeAgents"][0]["file"] == "declarativeAgent.json"


@pytest.mark.parametrize("agent_id", sorted(EXPECTED))
def test_instructions_carry_the_guardrails(agent_id):
    text = b.render_instructions(CHECKLISTS[agent_id])
    for phrase in ("Never invent", "word for word", "Do not calculate deadlines", "Cite only the authorities",
                   "Not legal advice", "Needs attorney judgment"):
        assert phrase in text
    assert all(it["authority"] for it in CHECKLISTS[agent_id]["items"])


@pytest.mark.parametrize("agent_id", sorted(EXPECTED))
def test_built_files_match_the_checklists(agent_id):
    built = json.loads((b.AGENTS / agent_id / "declarativeAgent.json").read_text(encoding="utf-8"))
    assert built == b.declarative_agent(CHECKLISTS[agent_id]), "run build_agents.py"


def test_corrections_to_the_research_report_are_reflected():
    pw = b.render_instructions(CHECKLISTS["public-works-check"])
    assert "SB 706, Pub. Contract Code §§ 22185 to 22185.11" in pw      # report cited §§ 22170-22174
    assert "SB 991" in pw and "up to 10 projects" in pw
    ba = b.render_instructions(CHECKLISTS["brown-act-check"])
    assert "no separate cybersecurity heading" in ba                     # report implied one exists
    assert "54953.8.3" in ba and "54953.4" in ba
    fh = b.render_instructions(CHECKLISTS["fair-hearing-map"])
    assert "The statute does not set the number of days" in fh           # report said 30 days
    assert "at least 10 days" in fh and "within 60 days" in fh
    arb = b.render_instructions(CHECKLISTS["arbitration-check"])
    assert "483.70(m)" in arb


def test_no_firm_or_client_names():
    blob = json.dumps(list(CHECKLISTS.values())).lower()
    for word in ("hanson", "bridgett", "thornwood"):
        assert word not in blob
