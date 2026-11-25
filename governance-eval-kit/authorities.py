"""Shared helper: resolve a citation string to entries in verified_authorities.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

REGISTER_PATH = Path(__file__).resolve().parent / "verified_authorities.json"
_CODES = ["Gov. Code", "Pub. Contract Code", "Lab. Code", "Civ. Code", "Code Civ. Proc.",
          "Bus. & Prof. Code", "Health & Saf. Code", "Rev. & Tax. Code", "42 C.F.R."]
_NUM = r"\d+[a-z]?(?:\.\d+)*"


def load_register() -> dict:
    return json.loads(REGISTER_PATH.read_text(encoding="utf-8"))["sections"]


def base_sections(citation: str) -> list[str]:
    """'Gov. Code § 54954.2(a)(1)' -> ['Gov. Code § 54954.2'].

    Handles several sections after one code name ('Lab. Code § 201(a) and § 202(a)',
    'Code Civ. Proc. §§ 437c(a)(2), 12c') and ranges ('§§ 22185-22185.11'), which
    resolve to both endpoints. Raises ValueError if no code name is recognised.
    """
    out: list[str] = []
    pieces = re.split("(" + "|".join(re.escape(c) for c in _CODES) + ")", citation)
    if len(pieces) < 3:
        raise ValueError(f"no recognised code name in {citation!r}")
    for code, rest in zip(pieces[1::2], pieces[2::2]):
        nums = re.findall(rf"(?:§+\s*|,\s*|-|\bto\s+|\band\s+(?:§\s*)?)({_NUM})", rest)
        if not nums:
            raise ValueError(f"no section number after {code!r} in {citation!r}")
        out.extend(f"{code} § {n}" for n in nums)
    return out


def unverified(citation: str, register: dict | None = None) -> list[str]:
    register = register if register is not None else load_register()
    return [s for s in base_sections(citation) if s not in register]
