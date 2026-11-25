"""Tool lanes and the registry import."""
import copy
import json
from pathlib import Path

import pytest

from clearance import DATA, lanes

from conftest import by_id

KIT_EXAMPLE = DATA.parent.parent / "governance-eval-kit" / "registry" / "registry.example.json"


def test_lanes_file_loads_and_has_required_fields(features):
    assert len(features) >= 10
    assert len({f["tool_id"] for f in features}) >= 5
    for f in features:
        assert set(lanes.REQUIRED) <= set(f)


def test_lanes_reject_unknown_data_class_and_bad_tristate(features):
    bad = copy.deepcopy(features)
    bad[0]["data_allowed"].append("secret_sauce")
    with pytest.raises(ValueError):
        lanes.validate_features(bad)
    bad = copy.deepcopy(features)
    bad[0]["baa_covers_feature"] = "yes"
    with pytest.raises(ValueError):
        lanes.validate_features(bad)


def test_registry_import_maps_fields_and_reports_the_rest():
    feats, report = lanes.load_lanes(DATA / "registry_sample.json")
    f = {x["id"]: x for x in feats}
    assert f["intake-summarizer"]["data_allowed"] == ["public", "firm_internal", "client_confidential", "phi"]
    assert f["intake-summarizer"]["used_for_training"] == "no"
    assert f["intake-summarizer"]["runs_in"] == "Firm productivity-suite tenant"
    for k in lanes.DEFAULTED:
        assert f["intake-summarizer"][k] == "unknown"
    assert {"ocg_check", "golden_set", "sb574_log"} <= set(report["unmapped_tool_fields"])
    assert "registry_owner" in report["unmapped_top_level_fields"]
    assert {"tool": "contract-compare", "field": "data_boundary.data_allowed", "value": "personal_data",
            "effect": "dropped; no matching data class in the lanes"} in report["unmapped_values"]


def test_registry_tool_listing_health_information_is_still_not_cleared_for_phi(clear, store):
    feats, _ = lanes.load_lanes(DATA / "registry_sample.json")
    matter = store.matter("M-1013")
    rec = clear(matter, features_=feats)
    d = by_id(rec)["intake-summarizer"]
    assert "phi" in next(f for f in feats if f["id"] == "intake-summarizer")["data_allowed"]
    assert d["by_data_class"]["phi"]["decision"] == "NOT_ALLOWED"
    assert "POL-PHI-02" in d["by_data_class"]["phi"]["rule_ids"]
    assert "no PHI in any tool" in rec["banner"] and "except" not in rec["banner"].split("no PHI")[1].split(";")[0]


def test_registry_file_missing_required_key_is_rejected():
    raw = json.loads((DATA / "registry_sample.json").read_text())
    del raw["registry_owner"]
    with pytest.raises(ValueError):
        lanes.from_registry(raw)


@pytest.mark.skipif(not KIT_EXAMPLE.exists(), reason="governance-eval-kit example not present")
def test_existing_kit_example_registry_imports():
    feats, report = lanes.load_lanes(KIT_EXAMPLE)
    assert report["tools_read"] == len(feats) >= 3
    assert all(f["baa_covers_feature"] == "unknown" for f in feats)
    assert "technical_owner" in report["unmapped_tool_fields"]
