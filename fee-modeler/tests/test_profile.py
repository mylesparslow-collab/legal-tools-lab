import copy
import os
import shutil

from feemodel import profile
from feemodel.cli import main
from feemodel.loader import load_mapping
from test_loader import MAPPING, write_tiny


def status(report, name):
    return [c for c in report["checks"] if c["name"] == name][0]


def test_clean_synthetic_exports_are_ready(ws, root):
    for shape in ("export_a", "export_b"):
        r = profile.profile_export(os.path.join(root, "data", shape), os.path.join(root, "data", "mappings", shape + ".json"),
                                   ws.code_map, ws.rate_card, ws.cost_rates)
        assert r["ready"], shape
        assert r["summary"]["matters"] == 640 and r["summary"]["closed_matters"] == 600


def test_profile_reports_unmapped_task_codes_and_coverage(ws, root):
    r = profile.profile_export(os.path.join(root, "data", "export_a"), os.path.join(root, "data", "mappings", "export_a.json"),
                               ws.code_map, ws.rate_card, ws.cost_rates)
    cov = status(r, "task code coverage")
    assert list(cov["unmapped_codes"]) == ["ZZ99"]
    assert 80 <= cov["coded_hours_pct"] < 100
    assert status(r, "task codes not in the phase map")["status"] == "warn"


def test_profile_flags_thin_matter_type(ws, root):
    r = profile.profile_export(os.path.join(root, "data", "export_a"), os.path.join(root, "data", "mappings", "export_a.json"))
    thin = [t["matter_type"] for t in r["matter_types"] if not t["enough_to_model"]]
    assert thin == ["election_law_advisory"]


def test_missing_table_makes_export_not_ready(tmp_path, root):
    dst = tmp_path / "x"
    shutil.copytree(os.path.join(root, "data", "export_b"), dst)
    os.remove(dst / "AR_SUMMARY.csv")
    r = profile.profile_export(str(dst), os.path.join(root, "data", "mappings", "export_b.json"))
    assert not r["ready"]
    assert status(r, "table invoices")["status"] == "fail"
    assert "Fix the failed checks" in r["next_step"]


def test_missing_required_column_named_in_report(tmp_path):
    mapping = copy.deepcopy(MAPPING)
    del mapping["tables"]["matters"]["columns"]["open_date"]
    r = profile.profile_export(write_tiny(tmp_path), mapping)
    assert not r["ready"]
    assert "open_date" in status(r, "table matters")["detail"]


def test_missing_optional_fields_come_with_consequences(tmp_path):
    r = profile.profile_export(write_tiny(tmp_path), MAPPING)
    names = {c["name"]: c for c in r["checks"]}
    assert "Write-downs cannot be shown" in names["optional field time_entries.hours_billed"]["detail"]
    assert "date windows" in names["optional field time_entries.task_code"]["detail"]
    assert names["table timekeepers"]["status"] == "ok"       # levels come from the entries


def test_levels_missing_from_rate_card_fail(tmp_path):
    r = profile.profile_export(write_tiny(tmp_path), MAPPING, rate_card={"partner": 1})
    assert status(r, "levels covered by rate card")["status"] == "fail"
    assert not r["ready"]


def test_profile_finds_planted_late_time_and_unpaid_balances(ws, root):
    r = profile.profile_export(os.path.join(root, "data", "export_a"), os.path.join(root, "data", "mappings", "export_a.json"))
    assert "6 after close (on 6 matters)" in status(r, "time dated outside the matter's open-to-close dates")["detail"]
    assert status(r, "closed matters with an unpaid balance")["detail"].startswith("3 closed matters")


def test_profile_cli_exit_codes(tmp_path, root, capsys):
    assert main(["profile", os.path.join(root, "data", "export_b"), "--mapping",
                 os.path.join(root, "data", "mappings", "export_b.json")]) == 0
    assert "ready to back-test" in capsys.readouterr().out
    # Without a mapping it lists files and the canonical fields, and does not claim readiness.
    assert main(["profile", os.path.join(root, "data", "export_b")]) == 2
    out = capsys.readouterr().out
    assert "WIP_DETAIL.csv" in out and "hours_worked" in out
    # Shape B files against the shape A mapping: not ready.
    assert main(["profile", os.path.join(root, "data", "export_b"), "--mapping",
                 os.path.join(root, "data", "mappings", "export_a.json")]) == 2
    assert load_mapping(os.path.join(root, "data", "mappings", "export_a.json"))["tables"]
