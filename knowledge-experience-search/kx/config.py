"""Load ranking configuration from config/ranking.json."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "ranking.json"
DEFAULT_MAPPING_PATH = ROOT / "config" / "mapping.synthetic.json"
DEFAULT_DATA_DIR = ROOT / "data" / "synthetic"
DEFAULT_DB_PATH = ROOT / "var" / "index.sqlite"
DEFAULT_AUDIT_PATH = ROOT / "var" / "audit.jsonl"

_cache: dict = {}


def load_config(path=None) -> dict:
    path = Path(path or DEFAULT_CONFIG_PATH)
    key = str(path)
    if key not in _cache:
        with open(path, encoding="utf-8") as fh:
            _cache[key] = json.load(fh)
    return copy.deepcopy(_cache[key])
