"""Hash-chained query log.

One JSON object per line. Each entry carries the hash of the previous entry
and its own hash over (previous hash + its content), so an edited, removed
or reordered line breaks the chain from that point on.

Limits, stated plainly: the chain does not detect removal of the newest
entries or replacement of the whole file unless the latest hash is also
recorded somewhere else. The log holds query text and result ids and is
itself sensitive; it should be readable only by whoever the firm designates.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import threading
from collections import OrderedDict
from pathlib import Path

GENESIS = "0" * 64
_lock = threading.Lock()


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _entry_hash(prev_hash: str, body: dict) -> str:
    return hashlib.sha256((prev_hash + _canonical(body)).encode("utf-8")).hexdigest()


def read_entries(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


class AuditLog:
    def __init__(self, path, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: _dt.datetime.now(_dt.timezone.utc))

    def _tail(self):
        last_hash, seq = GENESIS, 0
        if self.path.exists():
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        entry = json.loads(line)
                        last_hash, seq = entry["hash"], entry["seq"]
        return last_hash, seq

    def append(self, action: str, user: str, query: str, filters: dict, result_ids: list,
               access: str = "ok", relaxed: bool = False) -> dict:
        """Write one entry and return it. Raises if the log cannot be written."""
        with _lock:
            prev_hash, seq = self._tail()
            body = {
                "seq": seq + 1, "time": self.clock().isoformat(), "user": user,
                "action": action, "query": query, "filters": filters or {},
                "access": access, "relaxed": bool(relaxed),
                "result_count": len(result_ids), "result_ids": list(result_ids),
                "prev_hash": prev_hash,
            }
            entry = dict(body, hash=_entry_hash(prev_hash, body))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(_canonical(entry) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return entry


def verify(path) -> dict:
    """Check the chain. Returns {"ok", "entries", "first_bad_seq", "reason"}."""
    prev, count = GENESIS, 0
    path = Path(path)
    if not path.exists():
        return {"ok": True, "entries": 0, "first_bad_seq": None, "reason": "no log file"}
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                body = {k: v for k, v in entry.items() if k != "hash"}
                seq = entry["seq"]
                stored = entry["hash"]
            except (ValueError, KeyError, AttributeError, TypeError):
                return {"ok": False, "entries": count, "first_bad_seq": None,
                        "reason": f"line {line_no} is not a valid entry"}
            if seq != count + 1:
                return {"ok": False, "entries": count, "first_bad_seq": seq,
                        "reason": f"line {line_no}: expected seq {count + 1}, found {seq}"}
            if body.get("prev_hash") != prev:
                return {"ok": False, "entries": count, "first_bad_seq": seq,
                        "reason": f"line {line_no}: does not follow the previous entry"}
            if _entry_hash(prev, body) != stored:
                return {"ok": False, "entries": count, "first_bad_seq": seq,
                        "reason": f"line {line_no}: content does not match its hash"}
            prev, count = stored, count + 1
    return {"ok": True, "entries": count, "first_bad_seq": None, "reason": "",
            "head_hash": prev}


def zero_result_report(entries) -> list:
    """Queries that found nothing, or only partial matches, most frequent first.

    This is a to-do list for the knowledge lawyer: things people looked for
    and did not find. ``kind`` is "nothing" when no result was returned and
    "partial matches only" when no document had every term and the search
    fell back to documents matching some of them.

    A query can come up empty because the firm has no such document or
    because that user may not open the ones it has; the log cannot tell
    which, and this report does not try to."""
    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    for e in entries:
        if e.get("access") != "ok" or e.get("action") not in ("search", "who"):
            continue
        if e.get("result_count", 0) == 0:
            kind = "nothing"
        elif e.get("relaxed"):
            kind = "partial matches only"
        else:
            continue
        text = " ".join(str(e.get("query", "")).lower().split())
        key = (e["action"], text, _canonical(e.get("filters", {})), kind)
        g = groups.setdefault(key, {"action": e["action"], "query": text, "kind": kind,
                                    "filters": e.get("filters", {}), "times": 0,
                                    "users": set(), "first_seen": e["time"], "last_seen": e["time"]})
        g["times"] += 1
        g["users"].add(e["user"])
        g["last_seen"] = max(g["last_seen"], e["time"])
        g["first_seen"] = min(g["first_seen"], e["time"])
    rows = []
    for g in groups.values():
        rows.append({"action": g["action"], "query": g["query"], "kind": g["kind"],
                     "filters": g["filters"], "times": g["times"],
                     "distinct_users": len(g["users"]),
                     "first_seen": g["first_seen"], "last_seen": g["last_seen"]})
    rows.sort(key=lambda r: (-r["times"], -r["distinct_users"], r["query"], r["kind"]))
    return rows


def format_zero_result_report(rows) -> str:
    lines = ["Queries that found nothing or only partial matches (most frequent first)",
             "A to-do list for the knowledge lawyer. A miss can mean the firm has no such "
             "document or that the user may not open it; the log does not say which.", ""]
    for r in rows:
        filters = f" filters {r['filters']}" if r["filters"] else ""
        lines.append(f"{r['times']}x by {r['distinct_users']} user(s)  {r['action']:<6} "
                     f"{r['kind']:<20} {r['query']!r}{filters}  last {r['last_seen']}")
    if not rows:
        lines.append("None.")
    return "\n".join(lines) + "\n"
