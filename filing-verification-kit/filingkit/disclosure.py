"""Draft disclosure wordings (data/disclosure_options.json). All drafts, none approved."""
from __future__ import annotations

import os
import re

from . import DATA_DIR
from .util import load_json

DEFAULT_PATH = os.path.join(DATA_DIR, "disclosure_options.json")
PLACEHOLDER = re.compile(r"\[[^\]]*\]")


def load_options(path: str = DEFAULT_PATH) -> dict:
    raw = load_json(path)
    return {o["id"]: o for o in raw["options"]}


def has_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER.search(text or ""))


def fill(option_text: str, description: str) -> str:
    """Replace the '[describe use]' placeholder with the attorney's description."""
    return option_text.replace("[describe use]", description.strip())
