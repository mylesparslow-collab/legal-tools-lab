"""Access to data/authorities.json, the one place statutory paraphrases live."""
from __future__ import annotations

import os

from . import DATA_DIR
from .util import load_json

DEFAULT_PATH = os.path.join(DATA_DIR, "authorities.json")
REQUIRED = ("section", "paraphrase", "verified_on")


class AuthorityError(KeyError):
    pass


class Authorities:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        raw = load_json(path)
        self.source = raw.get("source", "")
        self.items = raw["authorities"]
        for key, a in self.items.items():
            missing = [f for f in REQUIRED if not a.get(f)]
            if missing:
                raise AuthorityError(f"authority {key} is missing {', '.join(missing)}")

    def get(self, key: str) -> dict:
        if key not in self.items:
            raise AuthorityError(f"unknown authority key: {key}")
        return self.items[key]

    def section(self, key: str) -> str:
        return self.get(key)["section"]

    def snapshot(self, keys) -> list:
        """Copy of the entries for the given keys, for saving inside a record."""
        out = []
        for key in sorted(set(keys)):
            a = self.get(key)
            out.append({"key": key, "section": a["section"], "paraphrase": a["paraphrase"],
                        "verified_on": a["verified_on"]})
        return out

    def operative_date(self) -> str:
        return self.get("sb574_enactment")["operative_date"]
