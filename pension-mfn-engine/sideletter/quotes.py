"""Quote verification. Nothing reaches the memo unless its quote is found verbatim in the source."""
import re

_ABBREV = ("L.P.", "U.S.", "Inc.", "No.", "Sec.", "L.L.C.", "Co.", "Corp.")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def verify_quote(quote: str, source: str) -> bool:
    """True only if the quote appears verbatim in the source (whitespace runs collapsed)."""
    q = norm(quote or "")
    return bool(q) and q in norm(source)


def sentences(text: str):
    """Split into sentences without breaking on common abbreviations. Each piece is a verbatim slice."""
    t = norm(text)
    out, start = [], 0
    for m in re.finditer(r"[.;:]\s+(?=[A-Z(“\"\[])", t):
        end = m.start() + 1
        if any(t[:end].endswith(a) for a in _ABBREV):
            continue
        out.append(t[start:end].strip())
        start = m.end()
    if t[start:].strip():
        out.append(t[start:].strip())
    return out


def sentence_containing(text: str, pattern: str):
    rx = re.compile(pattern, re.I)
    return [s for s in sentences(text) if rx.search(s)]
