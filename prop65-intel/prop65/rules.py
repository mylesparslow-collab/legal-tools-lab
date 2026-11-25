"""Loads the rules-as-data files. Code reads legal numbers from here, never from literals."""
from __future__ import annotations
import csv, json, re
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "rules"


@lru_cache(maxsize=None)
def load_rules() -> dict:
    data = json.loads((RULES_DIR / "prop65_rules.json").read_text(encoding="utf-8"))
    return {r["id"]: r for r in data["rules"]}


def rule(rule_id: str) -> dict:
    return load_rules()[rule_id]


def cite(rule_id: str) -> dict:
    r = rule(rule_id)
    return {"rule_id": rule_id, "citation": r["citation"], "status": r["status"]}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


@lru_cache(maxsize=None)
def load_levels() -> list[dict]:
    rows = []
    with open(RULES_DIR / "safe_harbor_levels.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            r["date_listed"] = date.fromisoformat(r["date_listed"])
            r["level_ug_day"] = float(r["level_ug_day"]) if r["level_ug_day"] else None
            names = [r["chemical"]] + [a for a in r["aliases"].split("|") if a]
            r["_keys"] = {_norm(n) for n in names}
            rows.append(r)
    return rows


def find_chemical(name: str) -> list[dict]:
    """All list rows (one per endpoint and route) matching a chemical name or alias."""
    key = _norm(name)
    return [r for r in load_levels() if key in r["_keys"]]


@lru_cache(maxsize=None)
def load_product_classes() -> list[dict]:
    return json.loads((RULES_DIR / "product_classes.json").read_text(encoding="utf-8"))["classes"]
