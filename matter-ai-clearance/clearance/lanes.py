"""Tool lanes: which data classes each tool feature may receive.

Reads data/tool_lanes.json, or a registry file in the governance-eval-kit format.
Anything a registry file does not say is set to unknown, and unknown never clears restricted data.
"""
from pathlib import Path

from . import DATA
from .store import load_json

DATA_CLASSES = ["public", "firm_internal", "client_confidential", "phi", "protective_order_material", "sealed"]
TRI = (True, False, "unknown")
REQUIRED = ["id", "tool_id", "tool_name", "feature", "status", "data_allowed", "baa_covers_feature",
            "used_for_training", "retention_class", "retention_days", "connectors_enabled", "web_access_enabled", "hosting"]

REGISTRY_DATA_MAP = {"public": "public", "firm_internal": "firm_internal", "client_confidential": "client_confidential",
                     "health_information": "phi"}
REGISTRY_TOOL_MAPPED = {"id": "id and tool_id", "name": "tool_name and short_name", "purpose": "feature", "status": "status",
                        "business_owner": "business_owner", "human_review": "human_review", "last_review": "last_review"}
REGISTRY_BOUNDARY_MAPPED = {"runs_in": "runs_in", "model_provider": "model_provider", "data_allowed": "data_allowed",
                            "retention": "retention", "used_for_training": "used_for_training", "agreements": "agreements"}
DEFAULTED = ["baa_covers_feature", "retention_class", "retention_days", "connectors_enabled", "web_access_enabled",
             "hosting", "data_region"]


def validate_features(features):
    seen = set()
    for f in features:
        for k in REQUIRED:
            if k not in f:
                raise ValueError("feature %s is missing %s" % (f.get("id"), k))
        if f["id"] in seen:
            raise ValueError("duplicate feature id %s" % f["id"])
        seen.add(f["id"])
        bad = [c for c in f["data_allowed"] if c not in DATA_CLASSES]
        if bad:
            raise ValueError("feature %s has unknown data class %s" % (f["id"], bad))
        for k in ("baa_covers_feature", "connectors_enabled", "web_access_enabled"):
            if f[k] not in TRI:
                raise ValueError("feature %s: %s must be true, false or unknown" % (f["id"], k))
        if f["used_for_training"] not in ("no", "yes", "unknown"):
            raise ValueError("feature %s: used_for_training must be no, yes or unknown" % f["id"])
    return features


def is_registry(raw):
    return isinstance(raw, dict) and "tools" in raw and "features" not in raw


def from_registry(raw):
    """Map a governance-eval-kit registry to lane features. Returns (features, report)."""
    for k in ("organization", "registry_owner", "as_of", "tools"):
        if k not in raw:
            raise ValueError("registry file is missing %s" % k)
    features = []
    unmapped_fields = set()
    unmapped_values = []
    top_unmapped = sorted(k for k in raw if k not in ("organization", "as_of", "tools"))
    for t in raw["tools"]:
        b = t.get("data_boundary", {})
        allowed = []
        for v in b.get("data_allowed", []):
            if v in REGISTRY_DATA_MAP:
                allowed.append(REGISTRY_DATA_MAP[v])
            elif v != "none":
                unmapped_values.append({"tool": t["id"], "field": "data_boundary.data_allowed", "value": v,
                                        "effect": "dropped; no matching data class in the lanes"})
        for k in t:
            if k not in REGISTRY_TOOL_MAPPED and k != "data_boundary":
                unmapped_fields.add(k)
        for k in b:
            if k not in REGISTRY_BOUNDARY_MAPPED:
                unmapped_fields.add("data_boundary." + k)
        features.append({
            "id": t["id"], "tool_id": t["id"], "tool_name": t["name"], "category": "from registry",
            "feature": t.get("purpose", ""), "short_name": t["name"], "status": t["status"],
            "business_owner": t.get("business_owner", ""), "last_review": t.get("last_review", ""),
            "data_allowed": allowed,
            "baa_covers_feature": "unknown",
            "used_for_training": b.get("used_for_training", "unknown"),
            "retention": b.get("retention", ""), "retention_class": "unknown", "retention_days": "unknown",
            "connectors_enabled": "unknown", "web_access_enabled": "unknown", "hosting": "unknown",
            "data_region": "unknown",
            "runs_in": b.get("runs_in", ""), "model_provider": b.get("model_provider", ""),
            "agreements": b.get("agreements", []), "human_review": t.get("human_review", ""),
            "source": "registry",
        })
    report = {
        "source_format": "governance-eval-kit registry",
        "organization": raw.get("organization"),
        "tools_read": len(features),
        "mapped_tool_fields": REGISTRY_TOOL_MAPPED,
        "mapped_data_boundary_fields": REGISTRY_BOUNDARY_MAPPED,
        "mapped_data_values": REGISTRY_DATA_MAP,
        "set_to_unknown": DEFAULTED,
        "unmapped_top_level_fields": top_unmapped,
        "unmapped_tool_fields": sorted(unmapped_fields),
        "unmapped_values": unmapped_values,
        "notes": [
            "The registry has one entry per tool, so each tool becomes one feature.",
            "The registry has no field for business associate agreement coverage, connectors, web access, hosting or "
            "structured retention. These are set to unknown, so no imported tool is cleared for PHI or "
            "protective-order material until the lanes file is completed by hand.",
            "The registry has no value for protective-order material or sealed material, so neither is ever allowed.",
        ],
    }
    return validate_features(features), report


def load_lanes(path=None):
    """Return (features, import_report). import_report is None for a native lanes file."""
    raw = load_json(Path(path) if path else DATA / "tool_lanes.json")
    if is_registry(raw):
        return from_registry(raw)
    return validate_features(raw["features"]), None
