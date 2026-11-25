"""Tokenising and light stemming shared by indexing and querying.

The same function is used on both sides so a query token always matches the
indexed form. The stemmer is deliberately conservative: it only folds plurals.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")
_POSSESSIVE = re.compile(r"[’']s\b")

# Dropped from loose query terms only. They stay in the index so that
# phrase queries such as "motion to dismiss" keep their positions.
STOP_WORDS = frozenset(
    """a an and are as at be by for from in into is it its of on or our that the
    their this to was we were which with""".split()
)


def stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("sses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def raw_tokens(text: str) -> list[str]:
    """Lower-cased word tokens, unstemmed. Hyphens split words."""
    if not text:
        return []
    text = _POSSESSIVE.sub("", text.lower()).replace("’", "").replace("'", "")
    return _TOKEN.findall(text)


def tokenize(text: str) -> list[str]:
    """Stemmed tokens in document order (stop words kept)."""
    return [stem(t) for t in raw_tokens(text)]


def query_terms(text: str) -> list[str]:
    """Stemmed tokens for a loose (non-phrase) query, stop words removed, de-duplicated."""
    out: list[str] = []
    for t in raw_tokens(text):
        if t in STOP_WORDS:
            continue
        s = stem(t)
        if s not in out:
            out.append(s)
    return out
