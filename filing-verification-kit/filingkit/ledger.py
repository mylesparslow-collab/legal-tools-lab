"""Append-only, hash-chained JSONL ledger.

Each line is one JSON object with seq, ts, prev_hash and hash. hash is the SHA-256
of the entry without its hash field; prev_hash is the hash of the line before it.
Changing, removing or reordering a past line breaks the chain.

The entry layout and hash scheme match the existing citation checker's ledger, so
verify_ledger() can also check a ledger written by that tool.

Tamper-evident, not tamper-proof: someone who can rewrite the whole file can rebuild
the chain. Removing lines from the end leaves a valid shorter chain; pass
expect_head (kept somewhere else) to catch that.
"""
from __future__ import annotations

import json
import os

from .util import canonical_hash, now_iso

GENESIS = "0" * 64
RESERVED = ("seq", "ts", "prev_hash", "hash")


class Ledger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not os.path.exists(path):
            open(path, "a", encoding="utf-8").close()

    def entries(self) -> list:
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def head(self) -> str:
        e = self.entries()
        return e[-1]["hash"] if e else GENESIS

    def append(self, entry: dict, now: str | None = None) -> dict:
        for k in RESERVED:
            if k in entry:
                raise ValueError(f"entry may not set reserved field {k}")
        check = verify_ledger(self.path)
        if not check["ok"]:
            raise LedgerBroken("ledger chain is broken; refusing to append. Run verify-ledger.")
        body = {"seq": check["entries"] + 1, "ts": now_iso(now), **entry, "prev_hash": check["head"]}
        body["hash"] = canonical_hash(body)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(body, ensure_ascii=False) + "\n")
        return body

    def find(self, **match) -> list:
        return [e for e in self.entries() if all(e.get(k) == v for k, v in match.items())]


class LedgerBroken(RuntimeError):
    pass


def verify_ledger(path: str, expect_head: str | None = None) -> dict:
    """Check every line of a ledger file.

    Returns {ok, entries, head, problems}. Each problem has line, seq and problem.
    """
    problems = []
    prev = GENESIS
    count = 0
    if not os.path.exists(path):
        return {"ok": False, "entries": 0, "head": GENESIS,
                "problems": [{"line": 0, "seq": None, "problem": "ledger file not found"}]}
    with open(path, encoding="utf-8") as f:
        lines = [(i, line) for i, line in enumerate(f, start=1) if line.strip()]
    for lineno, line in lines:
        count += 1
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            problems.append({"line": lineno, "seq": None, "problem": "line is not valid JSON"})
            prev = None
            continue
        if not isinstance(e, dict) or any(k not in e for k in RESERVED):
            problems.append({"line": lineno, "seq": None, "problem": "entry is missing seq, ts, prev_hash or hash"})
            prev = None
            continue
        seq = e["seq"]
        if seq != count:
            problems.append({"line": lineno, "seq": seq,
                             "problem": f"sequence number is {seq}, expected {count} (entry removed, added or reordered)"})
        if prev is not None and e["prev_hash"] != prev:
            problems.append({"line": lineno, "seq": seq,
                             "problem": "prev_hash does not match the entry before it"})
        if canonical_hash({k: v for k, v in e.items() if k != "hash"}) != e["hash"]:
            problems.append({"line": lineno, "seq": seq, "problem": "entry content does not match its hash (edited)"})
        prev = e["hash"]
    head = prev if (prev is not None and count) else GENESIS
    if expect_head and head != expect_head:
        problems.append({"line": lines[-1][0] if lines else 0, "seq": count or None,
                         "problem": "head hash differs from the expected head (entries removed from or added to the end)"})
    return {"ok": not problems, "entries": count, "head": head, "problems": problems}
