"""Firm policy settings (data/policy.json). Policy choices, not legal requirements."""
from __future__ import annotations

import os

from . import DATA_DIR
from .util import load_json

DEFAULT_PATH = os.path.join(DATA_DIR, "policy.json")
DISCOVERY_MODES = ("advisory", "same_as_filings")


class PolicyError(ValueError):
    pass


def load_policy(path: str | None = None, overrides: dict | None = None) -> dict:
    base = load_json(DEFAULT_PATH)
    if path and os.path.abspath(path) != os.path.abspath(DEFAULT_PATH):
        base.update(load_json(path))
    if overrides:
        base.update(overrides)
    if base["discovery_mode"] not in DISCOVERY_MODES:
        raise PolicyError(f"discovery_mode must be one of {DISCOVERY_MODES}")
    days = base["judge_entry_staleness_days"]
    if not isinstance(days, int) or isinstance(days, bool) or days < 0:
        raise PolicyError("judge_entry_staleness_days must be a non-negative integer")
    overlap = set(base["filing_document_types"]) & set(base["discovery_document_types"])
    if overlap:
        raise PolicyError(f"document types listed as both filing and discovery: {sorted(overlap)}")
    return base
