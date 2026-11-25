"""The synthetic invoices carry planted violations. Every one must be found, and clean entries must stay clean."""

import filecmp
import os

from billcheck import scoring
from billcheck.blockbilling import count_tasks
from conftest import DATA, ROOT


def test_sample_set_has_five_clients_and_at_least_six_invoices(results, guides):
    assert len(guides) == 5
    assert len(results) >= 6
    assert {r.invoice.source_format for r in results} == {"ledes1998b", "csv"}


def test_every_planted_violation_is_found(results, answer_key):
    score = scoring.score(results, answer_key)
    assert score["planted_total"] == 64
    assert score["planted_missed"] == []
    assert score["planted_wrong_status"] == []
    assert score["planted_found"] == score["planted_total"]


def test_false_positives_on_clean_entries_are_zero(results, answer_key):
    """Honest count: any finding that is not in the answer key is a false positive. README states this number."""
    score = scoring.score(results, answer_key)
    assert score["clean_lines"] == 120
    assert score["false_positives"] == []
    assert score["clean_lines_flagged"] == []


def test_answer_key_covers_every_rule_type_plus_arithmetic(answer_key):
    from billcheck.guidelines import RULE_TYPES

    planted = {item["rule_type"] for item in answer_key["planted"]}
    assert planted == set(RULE_TYPES) | {"ARITH-LINE", "ARITH-TOTAL"}


def test_planted_items_have_the_expected_severity_mix(results, answer_key):
    statuses = [item["expected_status"] for item in answer_key["planted"]]
    assert statuses.count("waived") == 1
    assert sum(len(r.open_findings) for r in results) == 63


def test_clean_control_invoice_has_no_findings(by_invoice):
    result = by_invoice["INV-O-3002"]
    assert result.findings == []
    assert result.total_at_risk == 0
    assert len(result.rules_run) == 13


def test_hard_case_entries_in_the_sample_are_not_flagged(by_invoice, answer_key):
    cases = answer_key["hard_cases_clean"]
    assert len(cases) >= 6
    for case in cases:
        result = by_invoice[case["invoice_id"]]
        assert not [f for f in result.findings if f.line_no == case["line_no"]], case


def test_two_task_entries_under_a_client_threshold_really_have_two_tasks(answer_key):
    under = [c for c in answer_key["hard_cases_clean"] if "threshold" in c["note"]]
    assert len(under) == 2
    for case in under:
        assert count_tasks(case["narrative"]) == 2


def test_scoring_counts_a_missing_finding_and_an_extra_finding(results, answer_key):
    import copy

    key = copy.deepcopy(answer_key)
    removed = key["planted"].pop(0)
    key["planted"].append(dict(removed, line_no=9999))
    score = scoring.score(results, key)
    assert len(score["planted_missed"]) == 1
    assert score["false_positive_count"] == 1


def _compare_trees(left, right):
    diff = []

    def walk(cmp, prefix=""):
        diff.extend(prefix + n for n in cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files)
        for name, sub in cmp.subdirs.items():
            walk(sub, prefix + name + "/")

    walk(filecmp.dircmp(left, right, ignore=["schema.json", "__pycache__"]))
    return diff


def test_generator_is_deterministic_and_matches_committed_data(tmp_path):
    import generate_data

    generate_data.generate(str(tmp_path / "a"))
    generate_data.generate(str(tmp_path / "b"))
    assert _compare_trees(str(tmp_path / "a"), str(tmp_path / "b")) == []
    assert _compare_trees(str(tmp_path / "a"), DATA) == []


def test_committed_outputs_match_a_fresh_demo_run(tmp_path):
    import run_demo

    out = tmp_path / "output"
    index = tmp_path / "index.html"
    run_demo.main(str(out), str(index), quiet=True)
    assert _compare_trees(str(out), os.path.join(ROOT, "output")) == []
    assert filecmp.cmp(str(index), os.path.join(ROOT, "index.html"), shallow=False)
