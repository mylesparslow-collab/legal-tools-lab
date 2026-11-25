"""Shared helpers: money rounding, findings, legal parameters."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CENT = Decimal("0.01")


def money(x) -> Decimal:
    """Round to cents, half up (matches Excel ROUND)."""
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def D(x) -> Decimal:
    return Decimal(str(x))


def parse_date(s) -> date | None:
    if s in (None, ""):
        return None
    if isinstance(s, date):
        return s
    return date.fromisoformat(s)


@dataclass
class Finding:
    code: str
    severity: str  # error | warn | info
    where: str
    message: str

    def as_dict(self):
        return asdict(self)


def load_params(path: Path | None = None) -> dict:
    raw = json.loads((path or ROOT / "legal_params.json").read_text())
    return {p["id"]: p for p in raw["params"]}


def pval(params: dict, key: str):
    return params[key]["value"]
