"""Banned-words check for generated statement text."""
from __future__ import annotations

import re

from .model import load_banned

_cache: dict = {}


def _patterns() -> dict:
    if not _cache:
        banned = load_banned()
        for kind in ("hype", "vague", "absolute"):
            terms = sorted(banned[kind], key=len, reverse=True)
            _cache[kind] = re.compile(r"(?<![\w-])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w-])", re.I)
    return _cache


def find_terms(text: str, kind: str) -> list[str]:
    """Banned terms of one kind ('hype', 'vague', 'absolute') found in text, lower-cased."""
    return [m.group(1).lower() for m in _patterns()[kind].finditer(text)]


def lint_sentence(text: str, universal_supported: bool = False) -> list[str]:
    """Problems with one sentence. Absolute words pass only when the sentence's
    evidence rule is universal and SUPPORTED."""
    problems = [f"hype word '{t}'" for t in find_terms(text, "hype")]
    problems += [f"vague word '{t}'" for t in find_terms(text, "vague")]
    if not universal_supported:
        problems += [f"absolute word '{t}' without a universal, supported evidence rule"
                     for t in find_terms(text, "absolute")]
    return problems


def lint_statement(stmt: dict) -> list[str]:
    """Problems across a built statement: every sentence, fixed text and the proposal paragraph."""
    out = []
    for fixed in (stmt["title"], stmt["subtitle"], stmt["footer"], stmt["status_line"]):
        out += [f"fixed text: {p}: {fixed!r}" for p in lint_sentence(fixed)]
    for sec in stmt["sections"]:
        out += [f"section label: {p}: {sec['label']!r}" for p in lint_sentence(sec["label"])]
        for s in sec["sentences"]:
            ok = bool(s.get("universal")) and s.get("evidence", {}).get("status") == "SUPPORTED"
            out += [f"{s['claim_id']}: {p}: {s['text']!r}" for p in lint_sentence(s["text"], ok)]
    for s in stmt["proposal"]["sentences"]:
        out += [f"proposal/{s['claim_id']}: {p}: {s['text']!r}" for p in lint_sentence(s["text"], s["universal_supported"])]
    return out
