"""Loads the rules data. Every legal number lives in data/*.json with a cite, source and status."""
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def brown_act() -> dict:
    return load("rules_brown_act")


def cpra() -> dict:
    return load("rules_cpra")


def finding(level: str, code: str, message: str, rule: dict | None = None, **extra) -> dict:
    """level is one of: fail, review, info, pass."""
    f = {"level": level, "code": code, "message": message}
    if rule:
        f["cite"] = rule.get("cite")
        f["source_status"] = rule.get("status")
        f["source_url"] = rule.get("source_url")
    f.update(extra)
    return f
