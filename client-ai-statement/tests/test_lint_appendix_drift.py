"""Banned words, the internal evidence appendix, the drift check and the command line."""
import json
import re
from pathlib import Path

import pytest
from conftest import AS_OF, LATER, ROOT, SAMPLES, printed, tool

from statement import drift, lint, render
from statement.build import BuildError, build_statement
from statement.cli import main
from statement.model import load_banned, load_claims, load_options, registry_schema, validate_schema


def sample_statements(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
    return [build_statement(clean, inputs, AS_OF), build_statement(gaps, inputs_gaps, AS_OF),
            build_statement(clean, inputs, AS_OF, client_consent),
            build_statement(clean, inputs, AS_OF, client_restricted)]


# ---------- banned words ----------

def test_no_hype_or_vague_words_in_any_generated_text(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
    for stmt in sample_statements(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
        for text in (render.statement_md(stmt), render.proposal_md(stmt)):
            assert lint.find_terms(text, "hype") == []
            assert lint.find_terms(text, "vague") == []
        assert lint.lint_statement(stmt) == []


def test_absolute_words_only_in_universal_supported_sentences(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
    seen = 0
    for stmt in sample_statements(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
        for s in printed(stmt).values():
            if lint.find_terms(s["text"], "absolute"):
                seen += 1
                assert s["universal"] is True and s["evidence"]["status"] == "SUPPORTED", s["text"]
    assert seen > 10  # the check is exercised, not vacuous


def test_library_texts_have_no_hype_and_absolutes_need_universal_rules():
    from statement.evidence import is_universal
    for c in load_claims()["claims"]:
        for v in c.get("variants", []):
            for text in (v["text"], v.get("short", "")):
                assert not lint.find_terms(text, "hype") and not lint.find_terms(text, "vague"), text
                if lint.find_terms(text, "absolute"):
                    assert is_universal(v["rule"]), f"{c['id']}/{v['id']} uses an absolute word without a universal rule"
    for topic in load_options()["topics"].values():
        for o in topic["options"]:
            for text in (o["text"] or "", o.get("short", "")):
                assert not lint.find_terms(text, "hype") and not lint.find_terms(text, "vague"), text
                if lint.find_terms(text, "absolute"):
                    assert "rule" in o and is_universal(o["rule"]), o["id"]


@pytest.mark.parametrize("word", ["cutting-edge", "leverage", "revolutionary", "robust"])
def test_hype_list_contains_the_named_words(word):
    assert word in load_banned()["hype"]
    assert lint.lint_sentence(f"Our {word} tools help clients.")


@pytest.mark.parametrize("phrase", ["We never share data.", "We always check.", "We guarantee accuracy.",
                                    "Our tools are fully secure."])
def test_absolute_words_rejected_without_universal_support(phrase):
    assert lint.lint_sentence(phrase, universal_supported=False)
    assert lint.lint_sentence(phrase, universal_supported=True) == []


def test_build_refuses_a_library_sentence_with_a_banned_word(clean, inputs):
    claims = load_claims()
    c = next(c for c in claims["claims"] if c["id"] == "rollout")
    c["variants"][0]["text"] = "{rollout_phrase} Our robust tools are always reviewed."
    with pytest.raises(BuildError, match="banned-words check failed") as ex:
        build_statement(clean, inputs, AS_OF, claims=claims)
    assert "robust" in str(ex.value) and "always" in str(ex.value)


def test_generated_text_is_plain_ascii_no_emoji(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
    for stmt in sample_statements(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
        for text in (render.statement_md(stmt), render.proposal_md(stmt), render.appendix_md(stmt)):
            assert text.isascii()


# ---------- evidence appendix ----------

def test_appendix_is_marked_internal(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    assert "INTERNAL. NOT FOR CLIENTS." in render.appendix_html(stmt)
    assert "INTERNAL. Not for clients." in render.appendix_md(stmt)
    assert "INTERNAL" not in render.statement_html(stmt)


def test_appendix_lists_every_printed_sentence(gaps, inputs_gaps):
    stmt = build_statement(gaps, inputs_gaps, AS_OF)
    model = render.appendix_model(stmt)
    texts = [s["text"] for sec in stmt["sections"] for s in sec["sentences"]]
    assert [p["text"] for p in model["printed"]] == texts
    md = render.appendix_md(stmt)
    assert all(t in md for t in texts)


def test_appendix_shows_registry_values_behind_a_claim(clean, inputs):
    md = render.appendix_md(build_statement(clean, inputs, AS_OF))
    assert "transcript-summary: data_boundary.used_for_training = 'no'" in md
    assert "DRAFT option B1." in md and "Needs General Counsel approval." in md


def test_appendix_explains_downgrades_and_omissions(gaps, inputs_gaps):
    stmt = build_statement(gaps, inputs_gaps, AS_OF)
    for out in (render.appendix_md(stmt), render.appendix_html(stmt)):
        assert "intake-assistant: data_boundary.used_for_training must be" in out
        assert "cannot tell (recorded as" in out
        assert "brief-drafting: sb574_log.mechanism must not start with" in out
        assert "439 days before the as-of date 2026-11-25" in out
    model = render.appendix_model(stmt)
    assert len(model["downgraded"]) == 8 and len(model["omitted"]) == 3


def test_appendix_carries_hash_and_category_check(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    md = render.appendix_md(stmt)
    assert stmt["content_hash"] in md
    assert "| translation | pilot | Translation |" in md


# ---------- drift check ----------

def test_no_drift_against_the_registry_it_was_built_from(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    report = drift.check_statement(stmt, clean, AS_OF)
    assert report["drift"] is False
    assert all(r["status"] in (drift.STILL_TRUE, drift.NOT_CHECKED) for r in report["rows"])


def test_later_registry_breaks_exactly_two_claims(clean, later, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    report = drift.check_statement(stmt, later, LATER)
    broken = {r["claim_id"]: r for r in report["rows"] if r["status"] in drift.DRIFT_STATUSES}
    assert set(broken) == {"no_training", "review_cycle"}
    assert broken["no_training"]["status"] == drift.NO_LONGER
    assert "transcript-summary: data_boundary.used_for_training" in broken["no_training"]["detail"][0]
    assert "translation: last_review" in broken["review_cycle"]["detail"][0]
    assert "232 days" in broken["review_cycle"]["detail"][0]


def test_time_alone_causes_drift(clean, inputs):
    from datetime import date
    stmt = build_statement(clean, inputs, AS_OF)
    report = drift.check_statement(stmt, clean, date(2027, 6, 1))
    assert report["drift"] and any("identical" in i for i in report["info"])
    assert {"review_cycle", "client_terms_check"} <= {r["claim_id"] for r in report["rows"] if r["status"] == drift.NO_LONGER}


def test_new_tool_that_trains_on_inputs_is_caught(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    new = json.loads(json.dumps(tool(clean, "translation")))
    new.update(id="new-notes-tool", name="New Notes Tool (fictional)")
    new["data_boundary"]["used_for_training"] = "yes"
    clean["tools"].append(new)
    report = drift.check_statement(stmt, clean, AS_OF)
    rows = {r["claim_id"]: r for r in report["rows"]}
    assert rows["no_training"]["status"] == drift.NO_LONGER
    assert rows["tools_in_use"]["status"] in (drift.NO_LONGER, drift.FIGURES_CHANGED)
    assert any("new-notes-tool" in i for i in report["info"])


def test_changed_count_is_reported_as_figures_changed(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    tool(clean, "translation")["status"] = "production"
    rows = {r["claim_id"]: r for r in drift.check_statement(stmt, clean, AS_OF)["rows"]}
    assert rows["rollout"]["status"] == drift.FIGURES_CHANGED
    assert rows["rollout"]["text_now"] == "Three are in firmwide use and one is in a limited pilot."


def test_unknown_value_is_cannot_tell_now(clean, inputs):
    stmt = build_statement(clean, inputs, AS_OF)
    tool(clean, "contract-review")["data_boundary"]["used_for_training"] = "unknown"
    rows = {r["claim_id"]: r for r in drift.check_statement(stmt, clean, AS_OF)["rows"]}
    assert rows["no_training"]["status"] == drift.CANNOT_TELL_NOW


def test_drift_check_uses_the_rule_stored_at_issue_time(clean, later, inputs):
    stmt = json.loads(json.dumps(build_statement(clean, inputs, AS_OF)))  # round trip as the file would be
    assert drift.check_statement(stmt, later, LATER)["drift_count"] == 2


# ---------- command line ----------

def _build(tmp_path, registry="registry.clean.json", extra=()):
    return main(["build", "--registry", str(SAMPLES / registry), "--inputs", str(SAMPLES / "statement_inputs.json"),
                 "--as-of", "2026-11-25", "--out", str(tmp_path), *extra])


def test_cli_build_writes_all_files(tmp_path, capsys):
    assert _build(tmp_path) == 0
    assert {p.name for p in tmp_path.iterdir()} == {"statement.html", "statement.md", "statement.json", "proposal.md",
                                                    "appendix.html", "appendix.md"}
    assert "DRAFT firm statement" in capsys.readouterr().out


def test_cli_check_exit_codes(tmp_path, capsys):
    _build(tmp_path)
    stmt = str(tmp_path / "statement.json")
    assert main(["check", "--statement", stmt, "--registry", str(SAMPLES / "registry.clean.json"),
                 "--as-of", "2026-11-25"]) == 0
    report = tmp_path / "drift.md"
    assert main(["check", "--statement", stmt, "--registry", str(SAMPLES / "registry.later.json"),
                 "--as-of", "2027-05-20", "--out", str(report)]) == 1
    assert "2 printed sentence(s) are no longer backed" in report.read_text()
    capsys.readouterr()


def test_cli_bad_input_exits_2_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    code = main(["build", "--registry", str(SAMPLES / "registry.gaps.json"),
                 "--inputs", str(SAMPLES / "statement_inputs.json"), "--as-of", "25 Nov 2026", "--out", str(out)])
    assert code == 2 and not out.exists()
    assert "not a date" in capsys.readouterr().err


def test_cli_appendix_rerenders_from_statement_json(tmp_path, capsys):
    _build(tmp_path)
    first = (tmp_path / "appendix.md").read_text()
    again = tmp_path / "again"
    assert main(["appendix", "--statement", str(tmp_path / "statement.json"), "--out", str(again)]) == 0
    assert (again / "appendix.md").read_text() == first
    capsys.readouterr()


def test_build_is_deterministic(tmp_path, capsys):
    a, b = tmp_path / "a", tmp_path / "b"
    _build(a), _build(b)
    for name in ("statement.html", "statement.json", "appendix.md", "proposal.md"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    capsys.readouterr()


# ---------- sample data and repository hygiene ----------

@pytest.mark.parametrize("name", ["registry.clean.json", "registry.gaps.json", "registry.later.json"])
def test_sample_registries_match_the_registry_schema(name):
    reg = json.loads((SAMPLES / name).read_text())
    assert validate_schema(reg, registry_schema()) == []
    assert reg["organization"] == "Example Firm LLP (fictional)"
    assert all("(fictional)" in t["name"] for t in reg["tools"])


def test_vendored_schema_is_identical_to_the_kit_schema():
    kit = ROOT.parent / "governance-eval-kit" / "registry" / "registry.schema.json"
    if not kit.exists():
        pytest.skip("governance-eval-kit is not next to this folder")
    assert kit.read_bytes() == (ROOT / "data" / "registry.schema.json").read_bytes()


def test_committed_sample_outputs_match_a_fresh_build(clean, inputs):
    committed = ROOT / "output" / "statement.json"
    if not committed.exists():
        pytest.skip("run python3 run_demo.py first")
    fresh = json.loads(json.dumps(build_statement(clean, inputs, AS_OF)))
    assert json.loads(committed.read_text()) == fresh


def test_statement_text_cites_no_legal_authority(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
    pattern = re.compile(r"§|\bRule \d|\bCode\b|\bAct\b|\bOpinion\b|\bstatute|\brequired by law|\bethic|\bthe law\b", re.I)
    for stmt in sample_statements(clean, gaps, inputs, inputs_gaps, client_consent, client_restricted):
        assert not pattern.search(render.statement_md(stmt) + render.proposal_md(stmt))
    library = json.dumps(load_claims()) + json.dumps(load_options())
    assert not re.search(r"§|\bRule \d|\bOpinion\b|\bstatute|\brequired by law|\bethic", library, re.I)
