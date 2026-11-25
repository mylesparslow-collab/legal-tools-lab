"""Judge and court standing orders on AI: schema check and lookup.

The data file is maintained by hand. The lookup never says "no order exists".
If the file has no entry for a judge, the answer is "not checked". If an entry is
older than the staleness window, the answer is "recheck before relying".
"""
from __future__ import annotations

import os
from datetime import date

from . import DATA_DIR
from .util import load_json, parse_date

DEFAULT_PATH = os.path.join(DATA_DIR, "judge_orders.sample.json")
REQUIREMENT_TYPES = ("certification", "disclosure", "prohibition", "none_known")
APPLIES_WHEN = ("always", "genai_used")
REQUIRED_FIELDS = ("entry_id", "court_id", "court", "judge_id", "judge", "order_title", "effective_date",
                   "requirement_type", "required_text", "source_url", "last_checked", "checked_by")
DEFAULT_STALENESS_DAYS = 30

NOT_CHECKED = "not_checked"
STALE = "stale"
CURRENT = "current"


class JudgeDataError(ValueError):
    pass


def validate_entries(data: dict) -> list:
    """Return a list of problems with the data file. Empty list means it is well formed."""
    problems = []
    entries = data.get("entries")
    if not isinstance(entries, list):
        return ["file has no 'entries' list"]
    seen = set()
    for i, e in enumerate(entries):
        tag = f"entries[{i}]" + (f" ({e.get('entry_id')})" if isinstance(e, dict) and e.get("entry_id") else "")
        if not isinstance(e, dict):
            problems.append(f"{tag}: not an object")
            continue
        for f in REQUIRED_FIELDS:
            if f not in e:
                problems.append(f"{tag}: missing field {f}")
        if e.get("entry_id") in seen:
            problems.append(f"{tag}: duplicate entry_id")
        seen.add(e.get("entry_id"))
        if e.get("requirement_type") not in REQUIREMENT_TYPES:
            problems.append(f"{tag}: requirement_type must be one of {', '.join(REQUIREMENT_TYPES)}")
        if e.get("applies_when", "always") not in APPLIES_WHEN:
            problems.append(f"{tag}: applies_when must be one of {', '.join(APPLIES_WHEN)}")
        for f in ("court_id", "court", "order_title", "source_url", "checked_by"):
            if f in e and not (isinstance(e[f], str) and e[f].strip()):
                problems.append(f"{tag}: {f} must be a non-empty string")
        if bool(e.get("judge_id")) != bool(e.get("judge")):
            problems.append(f"{tag}: judge_id and judge must both be set, or both null for a court-wide entry")
        try:
            parse_date(e.get("last_checked"))
        except (ValueError, TypeError):
            problems.append(f"{tag}: last_checked must be an ISO date")
        if e.get("effective_date") is not None:
            try:
                parse_date(e["effective_date"])
            except (ValueError, TypeError):
                problems.append(f"{tag}: effective_date must be an ISO date or null")
        if e.get("requirement_type") in ("certification", "disclosure", "prohibition") and not e.get("required_text"):
            problems.append(f"{tag}: required_text is needed for requirement_type {e.get('requirement_type')}")
    return problems


def load_orders(path: str = DEFAULT_PATH) -> dict:
    data = load_json(path)
    problems = validate_entries(data)
    if problems:
        raise JudgeDataError("judge orders file is not valid: " + "; ".join(problems))
    return data


def _entry_view(e: dict, as_of: date, staleness_days: int) -> dict:
    age = (as_of - parse_date(e["last_checked"])).days
    out = dict(e)
    out.setdefault("applies_when", "always")
    out["age_days"] = age
    out["stale"] = age > staleness_days or age < 0
    return out


def lookup(data: dict, court_id: str, judge_id: str | None, as_of: date,
           staleness_days: int = DEFAULT_STALENESS_DAYS) -> dict:
    """Find entries for a judge plus court-wide entries for the judge's court.

    status is one of:
      not_checked  no entry for this judge (or, with no judge given, none for the court)
      stale        at least one entry is older than the staleness window
      current      every entry found was checked within the window
    """
    if staleness_days < 0:
        raise ValueError("staleness_days must not be negative")
    entries = data.get("entries", [])
    judge_entries = [_entry_view(e, as_of, staleness_days) for e in entries
                     if judge_id and e["court_id"] == court_id and e["judge_id"] == judge_id]
    court_entries = [_entry_view(e, as_of, staleness_days) for e in entries
                     if e["court_id"] == court_id and e["judge_id"] is None]
    found = judge_entries + court_entries
    primary = judge_entries if judge_id else court_entries
    who = f"judge '{judge_id}' in court '{court_id}'" if judge_id else f"court '{court_id}'"
    if not primary:
        status = NOT_CHECKED
        message = (f"Not checked: the orders file has no entry for {who}. "
                   "This does not mean no order exists. Check the court's website and add an entry.")
        if court_entries and judge_id:
            message += f" {len(court_entries)} court-wide entr{'y' if len(court_entries) == 1 else 'ies'} found and shown."
    elif any(e["stale"] for e in found):
        status = STALE
        old = [e for e in found if e["stale"]]
        message = ("Recheck before relying: " +
                   "; ".join(f"{e['entry_id']} was last checked {e['last_checked']} ({e['age_days']} days before {as_of.isoformat()})"
                             for e in old) + f". Staleness window is {staleness_days} days.")
    else:
        status = CURRENT
        newest = min(e["age_days"] for e in found)
        message = (f"{len(found)} entr{'y' if len(found) == 1 else 'ies'} found for {who}, checked within "
                   f"{staleness_days} days (most recent {newest} days before {as_of.isoformat()}).")
        if all(e["requirement_type"] == "none_known" for e in found):
            message += (" No requirement was known when last checked. That is a record of a search, "
                        "not a statement that no order exists.")
    return {"court_id": court_id, "judge_id": judge_id, "as_of": as_of.isoformat(),
            "staleness_days": staleness_days, "status": status, "message": message,
            "fictional_sample_data": bool(data.get("fictional")), "entries": found}
