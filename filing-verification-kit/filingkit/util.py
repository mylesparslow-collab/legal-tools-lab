"""Small shared helpers: JSON loading, timestamps, canonical hashing."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def canonical_hash(obj) -> str:
    """SHA-256 of the object as sorted-key JSON.

    Same scheme as the existing citation checker's ledger, so one verifier reads both.
    """
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def now_iso(now: str | None = None) -> str:
    """Return an ISO timestamp. A caller-supplied value is validated and returned as given."""
    if now:
        parse_ts(now)
        return now
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(value) -> datetime:
    """Parse an ISO date or datetime. Raises ValueError if it is not one."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp is missing")
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_date(value) -> date:
    return parse_ts(value).date()


def is_ts(value) -> bool:
    try:
        parse_ts(value)
        return True
    except (ValueError, TypeError):
        return False


def same_person(a, b) -> bool:
    return bool(a) and bool(b) and " ".join(str(a).split()).casefold() == " ".join(str(b).split()).casefold()
