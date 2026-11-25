"""Text normalisation shared by the corpus checker and the quote-grounding check.

A quote counts as verbatim if it matches the source after these changes only:
  * runs of whitespace collapse to one space
  * curly quotes and apostrophes become straight ones
  * en and em dashes become a hyphen
  * a bracketed ellipsis "[...]" (or "[…]") may stand for omitted text
Case, punctuation, numbers and word order must match exactly.
"""
from __future__ import annotations

import re

_TRANS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ",
})
_ELLIPSIS = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]")


def normalise(text: str) -> str:
    """Return text with whitespace, quote marks and dashes normalised."""
    return re.sub(r"\s+", " ", text.translate(_TRANS)).strip()


def normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Normalise and return, for each output character, its index in the input."""
    out: list[str] = []
    idx: list[int] = []
    pending_space = False
    for i, ch in enumerate(text.translate(_TRANS)):
        if ch.isspace():
            pending_space = bool(out)
            continue
        if pending_space:
            out.append(" ")
            idx.append(i - 1)
            pending_space = False
        out.append(ch)
        idx.append(i)
    return "".join(out), idx


def find_quote(source_norm: str, quote: str) -> list[tuple[int, int]] | None:
    """Locate a quote in normalised source text.

    Returns a list of (start, end) spans in the normalised source, one per
    segment between bracketed ellipses, or None if the quote is not verbatim.
    Segments must appear in order.
    """
    segments = [normalise(s) for s in _ELLIPSIS.split(quote)]
    segments = [s for s in segments if s]
    if not segments:
        return None
    spans: list[tuple[int, int]] = []
    cursor = 0
    for seg in segments:
        pos = source_norm.find(seg, cursor)
        if pos < 0:
            return None
        spans.append((pos, pos + len(seg)))
        cursor = pos + len(seg)
    return spans
