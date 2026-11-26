"""Vocabulary bridging: finding documents that use different words for the same thing.

Four sources of alternatives, each weighted below the user's own words:

* thesaurus    config/thesaurus.json, curated equivalents. Static data, the
               same for every user.
* word form    other forms of the same word (assign, assignment, assignee).
* spelling     British and American spellings.
* typo         a near-miss spelling, tried only when the user's word occurs in
               no document they can open.

and one that depends on the documents:

* related      terms that keep turning up in the user's own top results
               (kx/search.py, "feedback"). Used only to list further
               documents after the direct matches.

Permission rule for all of them: an alternative is used, counted, weighted
and shown only on the strength of documents the asking user can open. This
module proposes candidates from static data; kx/search.py keeps a candidate
only if it occurs in the visible set, and every statistic it uses is a
visible-set statistic. A word that occurs only behind a wall is therefore
indistinguishable from a word that occurs nowhere.
"""
from __future__ import annotations

import json
from pathlib import Path

from kx.text import QUERY_FILLER, STOP_WORDS, raw_tokens, root, spelling_variants, stem

DEFAULT_THESAURUS_PATH = Path(__file__).resolve().parent.parent / "config" / "thesaurus.json"
OWN = "your words"

_cache: dict = {}


def make_unit(tokens):
    """A term unit ("t", term) or a phrase unit ("p", ((term, offset), ...)).

    Phrases are matched on their content words at the right distances apart;
    the small words between them (of, to, the) are not checked."""
    content = [(t, i) for i, t in enumerate(tokens) if t not in STOP_WORDS]
    if not content:
        return None
    if len(content) == 1:
        return ("t", content[0][0])
    first = content[0][1]
    return ("p", tuple((t, i - first) for t, i in content))


def unit_terms(unit) -> list:
    return [unit[1]] if unit[0] == "t" else [t for t, _ in unit[1]]


def unit_label(unit) -> str:
    return unit[1] if unit[0] == "t" else " ".join(t for t, _ in unit[1])


class Thesaurus:
    def __init__(self, path=None):
        self.path = Path(path or DEFAULT_THESAURUS_PATH)
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.by_key: dict = {}      # tuple of stems -> list of (alt key, alt text, area)
        self.by_root: dict = {}     # root of a one-word key -> that key
        self.groups = 0
        self.max_len = 1
        self.multi: list = []       # (key, roots of its content words) for keys of 2+ words
        for section in data.get("sections", []):
            area = section.get("area", "")
            for group in section.get("groups", []):
                entries = []
                for text in group:
                    key = tuple(stem(t) for t in raw_tokens(text))
                    if key and make_unit(key) and key not in [e[0] for e in entries]:
                        entries.append((key, text))
                if len(entries) < 2:
                    continue
                self.groups += 1
                for key, _ in entries:
                    self.max_len = max(self.max_len, len(key))
                    bucket = self.by_key.setdefault(key, [])
                    for other, text in entries:
                        if other != key and other not in [b[0] for b in bucket]:
                            bucket.append((other, text, area))
                    if len(key) == 1:
                        self.by_root.setdefault(root(key[0]), key)
                    else:
                        content = tuple(root(t) for t in key if t not in STOP_WORDS)
                        if len(content) >= 2 and (key, content) not in self.multi:
                            self.multi.append((key, content))
        self.multi.sort()

    def lookup(self, key: tuple) -> list:
        """Alternatives for a run of query stems, or [] if the thesaurus has none."""
        hit = self.by_key.get(key)
        if hit is None and len(key) == 1:
            base = self.by_root.get(root(key[0]))
            if base is not None and base != key:
                # The query used another form of a thesaurus word (hacking, hack).
                return [(base, base[0], "word form of a thesaurus term")] + [
                    a for a in self.by_key[base]]
        return list(hit or [])


def load_thesaurus(path=None) -> Thesaurus:
    key = str(path or DEFAULT_THESAURUS_PATH)
    if key not in _cache:
        _cache[key] = Thesaurus(path)
    return _cache[key]


def build_groups(parsed: dict, config: dict, expand: bool, thesaurus=None,
                 max_span: dict | None = None) -> list:
    """Turn a parsed query into concept groups.

    Each group is one thing the user asked for: their own word or words, plus
    alternatives. A document satisfies a group through any one alternative."""
    weights = config["expansion"]["weights"]
    groups = []
    for phrase in parsed["phrases"]:
        unit = make_unit(phrase)
        if unit is None:
            continue
        groups.append({"label": '"' + " ".join(phrase) + '"', "quoted": True, "thesaurus": False,
                       "alts": [{"units": [unit], "source": OWN, "weight": 1.0,
                                 "label": " ".join(phrase), "why": ""}]})
    seq = [(s, raw) for s, raw in parsed["sequence"]]
    thesaurus = thesaurus or (load_thesaurus() if expand else None)
    seen = set()
    i = 0
    while i < len(seq):
        s, raw = seq[i]
        if s in STOP_WORDS or raw in QUERY_FILLER:
            i += 1
            continue
        span, found = 1, []
        if expand and thesaurus is not None:
            longest = min(thesaurus.max_len, len(seq) - i, (max_span or {}).get(i, 99))
            for length in range(longest, 0, -1):
                last = seq[i + length - 1]
                if last[0] in STOP_WORDS:
                    continue
                key = tuple(x[0] for x in seq[i:i + length])
                found = thesaurus.lookup(key)
                if found:
                    span = length
                    break
        own_terms = []
        for x in seq[i:i + span]:
            if x[0] not in STOP_WORDS and x[0] not in own_terms:
                own_terms.append(x[0])
        label = " ".join(x[1] for x in seq[i:i + span])
        pos = i
        i += span
        if tuple(own_terms) in seen:
            continue
        seen.add(tuple(own_terms))
        alts = [{"units": [("t", t) for t in own_terms], "source": OWN, "weight": 1.0,
                 "label": label, "why": ""}]
        for key, text, area in found:
            unit = make_unit(key)
            if unit is None or [unit] == alts[0]["units"]:
                continue
            alts.append({"units": [unit], "source": "thesaurus", "weight": weights["thesaurus"],
                         "label": text, "why": f"thesaurus: {area}"})
        groups.append({"label": label, "quoted": False, "thesaurus": bool(found), "alts": alts,
                       "single": own_terms[0] if len(own_terms) == 1 else None, "pos": pos,
                       "span": span})
    if expand and thesaurus is not None:
        _loose_phrases(groups, thesaurus, weights)
    return groups


LOOSE_WINDOW = 5


def _loose_phrases(groups: list, thesaurus: Thesaurus, weights: dict) -> None:
    """Recognise a thesaurus phrase whose words the user wrote in another order,
    with other words between them, or with a listed equivalent of one word
    ("deferred price ..." for "deferred consideration"). The phrase and its
    equivalents are added, at a lower weight, as alternatives for each of the
    user's words involved. Static data only: nothing here reads the index."""
    weight = weights.get("thesaurus_loose", 0.5)
    singles = []
    for g in groups:
        if g["quoted"] or not g.get("single"):
            continue
        roots = {root(g["single"])}
        for alt in g["alts"][1:]:
            if alt["source"] == "thesaurus" and len(alt["units"]) == 1 and alt["units"][0][0] == "t":
                roots.add(root(alt["units"][0][1]))
        singles.append((g, roots))
    if len(singles) < 2:
        return
    additions = []
    for key, content in thesaurus.multi:
        chosen = []
        for r in content:
            hit = next((g for g, roots in singles if r in roots and all(g is not c for c in chosen)), None)
            if hit is None:
                break
            chosen.append(hit)
        else:
            positions = [g["pos"] for g in chosen]
            if max(positions) - min(positions) > LOOSE_WINDOW:
                continue
            read_as = " ".join(key)
            options = [(key, read_as)] + [(k, text) for k, text, _ in thesaurus.by_key[key]]
            additions.append((chosen, read_as, options))
    for chosen, read_as, options in additions:
        words = " ... ".join(g["label"] for g in sorted(chosen, key=lambda g: g["pos"]))
        for g in chosen:
            have = [a["units"] for a in g["alts"]]
            for key, text in options:
                unit = make_unit(key)
                if unit is None or [unit] in have:
                    continue
                have.append([unit])
                g["alts"].append({"units": [unit], "source": "thesaurus", "weight": weight,
                                  "label": text,
                                  "why": f"thesaurus: read {words!r} as {read_as!r}"})
            g["thesaurus"] = True


def static_variants(term: str) -> set:
    """Spelling variants of a term, proposed without reference to any corpus."""
    return spelling_variants(term)


def match_tokens(group: dict, tokens: list, expand: bool, weights: dict):
    """Best weight with which a group is satisfied by a token list, or 0.

    Used for matter descriptions, which are matched directly. Word forms and
    spellings are compared token to token here, so nothing is looked up in the
    index and nothing outside this matter's own text can affect the answer."""
    token_set = set(tokens)
    best = 0.0
    for alt in group["alts"]:
        if alt["weight"] <= best:
            continue
        ok = True
        for unit in alt["units"]:
            if unit[0] == "t":
                if unit[1] not in token_set:
                    ok = False
                    break
            else:
                first = unit[1][0][0]
                starts = [i for i, t in enumerate(tokens) if t == first]
                if not any(all(0 <= i + off < len(tokens) and tokens[i + off] == t
                               for t, off in unit[1]) for i in starts):
                    ok = False
                    break
        if ok:
            best = alt["weight"]
    single = group.get("single")
    if expand and single and best < weights["spelling"]:
        if static_variants(single) & token_set:
            best = max(best, weights["spelling"])
    if expand and single and best < weights["word_form"] and len(single) >= 4:
        r = root(single)
        if any(root(t) == r for t in token_set if len(t) >= 4):
            best = max(best, weights["word_form"])
    return best
