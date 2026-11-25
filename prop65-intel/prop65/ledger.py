"""Hash-chained sign-off log. The tool flags; a person verifies and signs. Editing a past line breaks the chain."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def append(self, action: str, item_id: str, actor: str, status: str = "", note: str = "", when: str | None = None) -> dict:
        es = self.entries()
        e = {"ts": when or datetime.now(timezone.utc).isoformat(timespec="seconds"), "action": action, "item_id": item_id,
             "actor": actor, "status": status, "note": note, "prev": es[-1]["hash"] if es else "0" * 64}
        e["hash"] = _hash(e)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(e) + "\n")
        return e

    def intact(self) -> bool:
        prev = "0" * 64
        for e in self.entries():
            if e["prev"] != prev or e["hash"] != _hash(e):
                return False
            prev = e["hash"]
        return True

    def sign(self, result: dict, actor: str, note: str = "") -> dict:
        """Record a person's verification of one cite. A flagged cite needs a note on how it was resolved."""
        if result["status"] != "PASS" and not note.strip():
            raise ValueError(f"{result['id']} is {result['status']}; a note explaining the resolution is required.")
        return self.append("verified", result["id"], actor, result["status"], note)

    def outstanding(self, report: dict) -> list[str]:
        signed = {e["item_id"] for e in self.entries() if e["action"] == "verified"}
        return [r["id"] for r in report["results"] if r["id"] not in signed]
