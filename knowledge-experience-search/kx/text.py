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


# ---------------------------------------------------------------------------
# Query-side helpers for vocabulary bridging (kx/expand.py). None of these
# change what is stored in the index; they only widen what a query looks for.

# Words people put around a request that say nothing about the subject.
# Dropped from loose query terms, like stop words. Never applied inside quotes.
QUERY_FILLER = frozenset(
    """who whom what where when how why has have had having does do did done doing
    anyone anybody someone somebody everyone here there me my i us you your he she
    they them can could would should will shall may might must need needs needed
    want wants wanted looking look find finding show give get got any some about
    regarding concerning involving involved involve related relating relate
    dealt deal dealing handle handled handling worked working experience
    experienced example examples sample samples best good prior previous please
    thing things something anything kind sort type types also just like such
    than then so if but not no yes over under up out off again ever before after
    during while one ones other others another same new old big small lot many
    much more most few less least very really quite rather against between among
    into onto upon toward towards via through across along around""".split()
) - {"out", "off", "not", "no", "new", "one", "before", "after", "up", "under", "over", "type"}

_ROOT_SUFFIXES = sorted(
    """ification ifications ifying ified ifies ify ization isation izations isations izing
    ising ized ised izes ises ize ise ations ation ating ated ates ator ators ate itions
    ition ments ment ingly ings ing ences ence ances ance ancy ency able ible ively ives ive
    ally ities ity ures ure ions ion ous ful ant ent ary als al ly ed ees ee ers er ors
    or es itor itors itive itively""".split(), key=len, reverse=True)
_SHORT_OK = ("ed", "ing")


def _strip_once(word: str) -> str:
    for suffix in _ROOT_SUFFIXES:
        if word.endswith(suffix):
            stem_part = word[: -len(suffix)]
            need = 3 if suffix in _SHORT_OK else (5 if len(suffix) <= 2 else 4)
            # The longest matching ending decides. If what is left is too
            # short, leave the word alone instead of trying a shorter ending.
            return stem_part if len(stem_part) >= need else word
    return word


def root(token: str) -> str:
    """A rough word root, for finding other forms of a word (assign, assignment,
    assignee). Deliberately crude and used only to propose alternatives, which
    are weighted below the user's own word and shown in the explanation."""
    word = stem(token)
    if len(word) < 4 or not word.isalpha():
        return word
    for _ in range(2):
        shorter = _strip_once(word)
        if shorter == word:
            break
        word = shorter
    if len(word) >= 4 and word.endswith("e"):
        word = word[:-1]
    if len(word) >= 4 and word.endswith("i"):
        word = word[:-1] + "y"
    if len(word) >= 5 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    return word


_SPELLING_SWAPS = [("isation", "ization"), ("ise", "ize"), ("ised", "ized"), ("ising", "izing"),
                   ("iser", "izer"), ("yse", "yze"), ("ysed", "yzed"), ("our", "or"),
                   ("oured", "ored"), ("ouring", "oring"), ("ourable", "orable"),
                   ("ence", "ense"), ("tre", "ter"), ("ogue", "og"), ("lled", "led"),
                   ("lling", "ling"), ("ller", "ler"), ("llor", "lor"), ("gement", "gment"),
                   ("amme", "am")]


def spelling_variants(token: str) -> set:
    """British and American spellings of the same word, by ending."""
    out = set()
    if len(token) < 5:
        return out
    for a, b in _SPELLING_SWAPS:
        for x, y in ((a, b), (b, a)):
            if token.endswith(x) and len(token) - len(x) >= 3:
                out.add(token[: -len(x)] + y)
    out.discard(token)
    return out


def edit_distance(a: str, b: str, limit: int) -> int:
    """Edit distance counting a swap of neighbouring letters as one edit.
    Returns limit + 1 as soon as the distance is known to exceed ``limit``."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]
