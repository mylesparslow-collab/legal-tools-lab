#!/usr/bin/env python3
"""Build app/data.js for the catch-the-error drill from the governance eval kit.

Reads, and never writes to, ../governance-eval-kit:
  eval_harness/corpus/*.md          the 12 synthetic documents
  eval_harness/corpus/*.key.json    the answer keys (90 planted defects)
  eval_harness/corpus/DEFECT_CATALOG.md   the rule behind each defect, as read
  verified_authorities.json         the sections that were read, with dates

Usage:
  python3 build.py            write app/data.js
  python3 build.py --check    exit 1 if app/data.js is out of date

The build stops with an error if a defect's quoted text is not found exactly
once in its document, if a quote crosses a paragraph, or if anything else about
the source is not what this script expects. There is no fuzzy matching.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_KIT = HERE.parent / "governance-eval-kit"
OUT = HERE / "app" / "data.js"

SCHEMA = "catch-the-error-drill/data/1"

# Marking rule constants. app/scoring.js reads these from the data file so the
# build, the app and the tests cannot drift apart.
MIN_MARK_CHARS = 20      # same as MIN_QUOTE_CHARS in the kit's harness/score.py
MAX_MARK_CHARS = 600     # the kit's prompt asks tools for 20 to 400; see README
OVERLAP_CAP = 30         # same as the kit: need = min(30, max(1, span // 2))

# Reading budgets. These are planning assumptions, not measurements.
READING_WPM = 150
EXCERPT_WORDS = {"short": 1300, "long": 2500}
SPOT_SECONDS = 300
VERIFY_MINUTES = 3
VERIFY_PLANTED = 5
VERIFY_OTHER = 5

DEFECT_TYPES = [
    # id, kind, severity, label. Labels use the catalog's own two fields.
    ("clause_high", "clause", "high", "Clause conflicts with a rule: high severity"),
    ("clause_medium", "clause", "medium", "Clause conflicts with a rule: medium severity"),
    ("omission", "omission", None, "A required clause is missing"),
]


class BuildError(Exception):
    """Raised when the source does not meet an assumption the drill depends on."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_kit_modules(kit: Path):
    """Import the kit's own normaliser and citation resolver so matching stays identical."""
    for p in (str(kit / "eval_harness"), str(kit)):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from harness import textnorm  # type: ignore
        import authorities  # type: ignore
    except ImportError as exc:  # pragma: no cover - only when the kit is missing
        raise BuildError(f"cannot import the eval kit from {kit}: {exc}") from exc
    return textnorm, authorities


# ---------------------------------------------------------------- markdown

def _inline(segment: str, raw_start: int, where: str):
    """Strip inline markdown from one segment.

    Returns (text, rawmap, bold_runs, italic) where rawmap[i] is the index in
    the raw document of display character i. Only the markup the corpus uses is
    understood: **bold**, and a whole segment wrapped in _underscores_.
    """
    lead = len(segment) - len(segment.lstrip())
    core = segment.strip()
    start = raw_start + lead
    italic = False
    if len(core) > 2 and core[0] == "_" and core[-1] == "_" and core[1] != "_" and core[-2] != "_":
        italic = True
        core = core[1:-1]
        start += 1
    out: list[str] = []
    rawmap: list[int] = []
    bold: list[list[int]] = []
    open_at: int | None = None
    i = 0
    while i < len(core):
        if core.startswith("**", i):
            if open_at is None:
                open_at = len(out)
            else:
                if len(out) > open_at:
                    bold.append([open_at, len(out)])
                open_at = None
            i += 2
            continue
        out.append(core[i])
        rawmap.append(start + i)
        i += 1
    if open_at is not None:
        raise BuildError(f"{where}: unbalanced ** in {segment[:60]!r}")
    text = "".join(out)
    if "*" in text or "`" in text:
        raise BuildError(f"{where}: markup this build does not understand in {segment[:60]!r}")
    return text, rawmap, bold, italic


def parse_markdown(raw: str, doc_id: str):
    """Turn a corpus document into display blocks.

    Returns (blocks, rawmaps). Each block is a dict:
      t   'h1' | 'h2' | 'h3' | 'p' | 'hr' | 'td' | 'th'
      s   start offset of the block in the display text
      x   plain text of the block
      b   bold runs as [start, end) offsets inside x (omitted if none)
      i   1 if the whole block is italic
      c   1 if the block directly follows the previous line (no blank line)
      sec section index (a section starts at each '## ' heading; 0 is the preamble)
      r   table row number, for 'td' and 'th'
    The display text of the document is the blocks' text joined by newlines.
    """
    blocks: list[dict] = []
    rawmaps: list[list[int]] = []
    pos = 0          # raw offset of the current line
    offset = 0       # display offset of the next block
    sec = 0
    prev_blank = True
    table_row = None  # row counter while inside a table

    def add(t: str, text: str, rawmap: list[int], bold, italic, **extra):
        nonlocal offset
        b = {"t": t, "s": offset, "x": text, "sec": sec}
        if bold:
            b["b"] = bold
        if italic:
            b["i"] = 1
        b.update(extra)
        blocks.append(b)
        rawmaps.append(rawmap)
        offset += len(text) + 1

    for n, line in enumerate(raw.split("\n"), 1):
        where = f"{doc_id} line {n}"
        body = line.rstrip()
        if not body.strip():
            prev_blank = True
            table_row = None
            pos += len(line) + 1
            continue
        if body.startswith("|"):
            cells = body.strip().strip("|").split("|")
            if all(re.fullmatch(r"\s*:?-{3,}:?\s*", c) for c in cells):
                pos += len(line) + 1
                continue
            header = table_row is None
            table_row = 0 if header else table_row + 1
            cursor = pos + body.index("|") + 1
            for c in cells:
                text, rawmap, bold, italic = _inline(c, cursor, where)
                add("th" if header else "td", text, rawmap, bold, italic, r=table_row)
                cursor += len(c) + 1
            prev_blank = False
            pos += len(line) + 1
            continue
        table_row = None
        m = re.match(r"(#{1,3}) +", body)
        if m:
            level = len(m.group(1))
            if level == 2:
                sec += 1
            text, rawmap, bold, italic = _inline(body[m.end():], pos + m.end(), where)
            add(f"h{level}", text, rawmap, None, italic)
        elif re.fullmatch(r"-{3,}", body.strip()):
            add("hr", "", [], None, False)
        elif body.startswith("#") or body.startswith(">") or body.startswith("    "):
            raise BuildError(f"{where}: markdown this build does not understand: {body[:60]!r}")
        else:
            text, rawmap, bold, italic = _inline(body, pos, where)
            extra = {} if prev_blank else {"c": 1}
            add("p", text, rawmap, bold, italic, **extra)
        prev_blank = False
        pos += len(line) + 1
    return blocks, rawmaps


def display_text(blocks: list[dict]) -> str:
    return "\n".join(b["x"] for b in blocks)


# ---------------------------------------------------------------- catalog

def parse_catalog(md: str) -> dict[str, dict]:
    """Read DEFECT_CATALOG.md into {code: {rule, key, example, area}}."""
    out: dict[str, dict] = {}
    area = None
    for line in md.split("\n"):
        if line.startswith("## "):
            area = line[3:].strip()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.fullmatch(r"[A-Z]\d+", cells[0]):
            continue
        if cells[0] in out:
            raise BuildError(f"catalog lists {cells[0]} twice")
        out[cells[0]] = {"rule": cells[1], "key": cells[2], "example": cells[3], "area": area}
    if not out:
        raise BuildError("no rules found in DEFECT_CATALOG.md")
    return out


# ---------------------------------------------------------------- defects

def locate_quote(quote: str, raw: str, blocks, rawmaps, textnorm, where: str) -> list[int]:
    """Return [start, end) of a quote in display offsets, or raise BuildError.

    The quote is matched the way the kit matches it (whitespace, curly quotes
    and dashes normalised, nothing else) and must occur exactly once.
    """
    if re.search(r"\[\s*(?:\.\.\.|…)\s*\]", quote):
        raise BuildError(f"{where}: quotes with a bracketed ellipsis are not supported by the drill")
    qn = textnorm.normalise(quote)
    if not qn:
        raise BuildError(f"{where}: empty quote")
    norm, idx = textnorm.normalise_with_map(raw)
    count = 0
    pos = norm.find(qn)
    first = pos
    while pos >= 0:
        count += 1
        pos = norm.find(qn, pos + 1)
    if count != 1:
        raise BuildError(f"{where}: quote found {count} times in the document, need exactly 1: {quote[:70]!r}")
    raw_start = idx[first]
    raw_end = idx[first + len(qn) - 1] + 1
    hit = None
    for bi, rm in enumerate(rawmaps):
        if not rm or rm[-1] < raw_start or rm[0] >= raw_end:
            continue
        if hit is not None:
            raise BuildError(f"{where}: quote crosses a paragraph or table cell: {quote[:70]!r}")
        hit = bi
    if hit is None:
        raise BuildError(f"{where}: quote not found in any display block: {quote[:70]!r}")
    rm = rawmaps[hit]
    local = [k for k, r in enumerate(rm) if raw_start <= r < raw_end]
    s, e = local[0], local[-1] + 1
    shown = blocks[hit]["x"][s:e]
    if textnorm.normalise(shown) != qn:
        raise BuildError(f"{where}: quote does not match the displayed text exactly: {quote[:70]!r}")
    return [blocks[hit]["s"] + s, blocks[hit]["s"] + e]


def defect_type(kind: str, severity: str) -> str:
    for tid, k, sev, _ in DEFECT_TYPES:
        if k == kind and (sev is None or sev == severity):
            return tid
    raise BuildError(f"no defect type for kind={kind!r} severity={severity!r}")


def build_document(doc_id: str, corpus: Path, catalog, register, textnorm, authorities):
    md_bytes = (corpus / f"{doc_id}.md").read_bytes()
    key_bytes = (corpus / f"{doc_id}.key.json").read_bytes()
    raw = md_bytes.decode("utf-8")
    if "\r" in raw:
        raise BuildError(f"{doc_id}: carriage returns in the source document")
    key = json.loads(key_bytes.decode("utf-8"))
    if key.get("doc_id") != doc_id:
        raise BuildError(f"{doc_id}: key doc_id is {key.get('doc_id')!r}")
    blocks, rawmaps = parse_markdown(raw, doc_id)
    text = display_text(blocks)
    if "fictional" not in text[:600].lower():
        raise BuildError(f"{doc_id}: document does not say it is fictional in its first lines")

    defects, unscored, excluded = [], [], []
    taken: list[tuple[int, int, str]] = []
    areas = set()
    for d in key["defects"]:
        did = d["id"]
        code = d.get("catalog_code")
        if code not in catalog:
            raise BuildError(f"{did}: catalog_code {code!r} is not in DEFECT_CATALOG.md")
        areas.add(catalog[code]["area"])
        try:
            sections = authorities.base_sections(d["authority"])
        except ValueError as exc:
            excluded.append({"id": did, "reason": f"authority not recognised: {exc}"})
            continue
        missing = [s for s in sections if s not in register]
        if missing:
            excluded.append({"id": did, "reason": "authority not in verified_authorities.json: " + ", ".join(missing)})
            continue
        if not all(any(k in s for s in sections) for k in d["authority_keys"][:1]):
            raise BuildError(f"{did}: authority_keys do not match the authority")
        entry = {
            "id": did,
            "code": code,
            "type": defect_type(d["kind"], d["severity"]),
            "kind": d["kind"],
            "severity": d["severity"],
            "title": d["title"],
            "authority": d["authority"],
            "why": d["why"],
            "read": [{"section": s, "date": register[s]["read"], "source": register[s]["source"],
                      **({"note": register[s]["note"]} if register[s].get("note") else {})}
                     for s in sections],
            "spans": [],
        }
        for q in d.get("quotes", []):
            span = locate_quote(q, raw, blocks, rawmaps, textnorm, did)
            for s, e, other in taken:
                if span[0] < e and s < span[1]:
                    raise BuildError(f"{did}: quote overlaps a quote of {other}")
            taken.append((span[0], span[1], did))
            entry["spans"].append(span)
        if d["kind"] == "clause" and not entry["spans"]:
            raise BuildError(f"{did}: a clause defect has no quote")
        entry["spans"].sort()
        (defects if entry["spans"] else unscored).append(entry)

    if len(areas) != 1:
        raise BuildError(f"{doc_id}: defects come from more than one catalog section: {sorted(areas)}")
    doc = {
        "id": doc_id,
        "type": key["doc_type"],
        "area": areas.pop(),
        "title": key["title"],
        "words": len(re.findall(r"\S+", text)),
        "sha256": sha256(md_bytes),
        "key_sha256": sha256(key_bytes),
        "blocks": blocks,
        "defects": defects,
        "unscored": unscored,
    }
    doc["sections"] = section_table(doc)
    doc["excerpts"] = {name: pick_excerpt(doc, words) for name, words in EXCERPT_WORDS.items()}
    doc["verify"] = verify_items(doc)
    return doc, excluded


# ---------------------------------------------------------------- excerpts

def section_table(doc: dict) -> list[dict]:
    """One row per section: heading, display range, word count, defect ids."""
    rows: list[dict] = []
    for b in doc["blocks"]:
        if not rows or b["sec"] != rows[-1]["sec"]:
            rows.append({"sec": b["sec"], "title": b["x"] if b["t"] == "h2" else "Opening",
                         "s": b["s"], "e": b["s"], "words": 0, "defects": []})
        r = rows[-1]
        r["e"] = b["s"] + len(b["x"])
        r["words"] += len(b["x"].split())
    for d in doc["defects"]:
        for s, _e in d["spans"]:
            for r in rows:
                if r["s"] <= s <= r["e"] and d["id"] not in r["defects"]:
                    r["defects"].append(d["id"])
    return rows


def pick_excerpt(doc: dict, budget: int) -> dict:
    """Choose the run of consecutive sections, within the word budget, that holds the most planted defects.

    Ties go to the run closest to the budget, then to the earliest. A defect
    counts only if every one of its spans is inside the run. The opening
    section (title and fictional notice) is always shown as well, so it is
    not part of the run.
    """
    rows = doc["sections"][1:]
    best = None
    for i in range(len(rows)):
        words = 0
        for j in range(i, len(rows)):
            words += rows[j]["words"]
            if words > budget and j > i:
                break
            secs = {r["sec"] for r in rows[i:j + 1]}
            inside = [d["id"] for d in doc["defects"]
                      if all(any(r["s"] <= s <= r["e"] for r in rows[i:j + 1]) for s, _ in d["spans"])]
            cand = (len(inside), -abs(budget - words), -i)
            if best is None or cand > best[0]:
                best = (cand, {"from": rows[i]["sec"], "to": rows[j]["sec"], "words": words, "defects": inside})
            if words > budget:
                break
            del secs
    if best is None or not best[1]["defects"]:
        raise BuildError(f"{doc['id']}: no excerpt of about {budget} words contains a planted defect")
    return best[1]


# ---------------------------------------------------------------- verify lists

_SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z(\"“])")


def sentences(block: dict):
    """Yield (start, end) local offsets of rough sentences in a block."""
    text = block["x"]
    start = 0
    for m in _SENT.finditer(text):
        yield start, m.start()
        start = m.end()
    yield start, len(text)


def verify_items(doc: dict) -> list[dict]:
    """Statements for the "Which would you verify?" list.

    Planted statements are the first quote of clause defects. The others are
    sentences taken from paragraphs that hold no planted defect and that state
    a number, so that both kinds read alike. Which ones are taken is decided by
    a hash of the text, so the list is stable while the source is unchanged.
    Nothing here says an unplanted statement is correct; the key covers planted
    defects only.
    """
    def order(s: str) -> str:
        return sha256((doc["id"] + "|" + s).encode("utf-8"))

    text = display_text(doc["blocks"])
    planted = [d for d in doc["defects"] if d["kind"] == "clause"]
    planted = sorted(planted, key=lambda d: order(d["id"]))[:VERIFY_PLANTED]
    # A planted statement is shown as the whole sentence (or sentences) around the
    # defect's first quote, so that it does not stand out as a fragment.
    items = []
    for d in planted:
        qs, qe = d["spans"][0]
        blk = max((b for b in doc["blocks"] if b["s"] <= qs), key=lambda b: b["s"])
        sents = [(blk["s"] + ls, blk["s"] + le) for ls, le in sentences(blk)]
        s = max(a for a, _ in sents if a <= qs)
        e = min(z for _, z in sents if z >= qe)
        items.append({"s": s, "e": e, "defect": d["id"]})

    spans = [sp for d in doc["defects"] for sp in d["spans"]]
    lengths = sorted(i["e"] - i["s"] for i in items)
    lo = 90
    hi = max(lengths[-1] + 20, 300)
    cands = []
    for b in doc["blocks"]:
        if b["t"] != "p" or b["sec"] == 0 or b.get("i"):
            continue
        bs, be = b["s"], b["s"] + len(b["x"])
        if any(s < be and bs < e for s, e in spans):
            continue
        for ls, le in sentences(b):
            sent = b["x"][ls:le]
            if not (lo <= len(sent) <= hi):
                continue
            if not sent[0].isupper() or not sent.endswith(".") or "____" in sent:
                continue
            if not re.search(r"\(\d+%?\)|\d+ percent|\$\d", sent):
                continue
            cands.append((order(sent), bs + ls, bs + le))
    cands.sort()
    used_blocks = set()
    for _h, s, e in cands:
        blk = max(b["s"] for b in doc["blocks"] if b["s"] <= s)
        if blk in used_blocks:
            continue
        used_blocks.add(blk)
        items.append({"s": s, "e": e, "defect": None})
        if len(items) == len(planted) + VERIFY_OTHER:
            break
    if len(items) < len(planted) + VERIFY_OTHER:
        raise BuildError(f"{doc['id']}: not enough unplanted statements for the verify list")
    items.sort(key=lambda i: i["s"])
    for n, it in enumerate(items, 1):
        it["id"] = f"{doc['id']}-V{n}"
        assert text[it["s"]:it["e"]].strip() == text[it["s"]:it["e"]]
    return items


# ---------------------------------------------------------------- drill sets

def build_sets(docs: list[dict]) -> list[dict]:
    """Session sets: practice area x length (10, 20, 30 minutes) x rotation (A, B, C)."""
    by_area: dict[str, list[dict]] = {}
    for d in docs:
        by_area.setdefault(d["area"], []).append(d)
    areas = list(by_area)
    for a, ds in by_area.items():
        if len(ds) != 3:
            raise BuildError(f"expected 3 documents for {a!r}, found {len(ds)}")

    def exercises(spot, verify, review, length):
        ex = [
            {"mode": "spot", "doc": spot["id"], "seconds": SPOT_SECONDS, "minutes": SPOT_SECONDS // 60},
            {"mode": "verify", "doc": verify["id"], "minutes": VERIFY_MINUTES},
        ]
        if length >= 20:
            name = "short" if length == 20 else "long"
            ex.append({"mode": "review", "doc": review["id"], "excerpt": name,
                       "minutes": round(review["excerpts"][name]["words"] / READING_WPM)})
        return ex

    sets = []
    for ai, area in enumerate(areas + ["Mixed"]):
        for length in (10, 20, 30):
            for v in range(3):
                if area == "Mixed":
                    picks = [by_area[areas[(v + k) % len(areas)]][k] for k in range(3)]
                else:
                    ds = by_area[area]
                    picks = [ds[(v + k) % 3] for k in range(3)]
                sets.append({
                    "id": f"{'mixed' if area == 'Mixed' else picks[0]['type']}-{length}-{'ABC'[v]}",
                    "area": area, "length": length, "rotation": "ABC"[v],
                    "exercises": exercises(picks[0], picks[1], picks[2], length),
                })
    return sets


# ---------------------------------------------------------------- main

def build(kit: Path = DEFAULT_KIT) -> dict:
    textnorm, authorities = load_kit_modules(kit)
    corpus = kit / "eval_harness" / "corpus"
    catalog_bytes = (corpus / "DEFECT_CATALOG.md").read_bytes()
    register_bytes = (kit / "verified_authorities.json").read_bytes()
    catalog = parse_catalog(catalog_bytes.decode("utf-8"))
    register = json.loads(register_bytes.decode("utf-8"))["sections"]
    doc_ids = sorted(p.name[: -len(".key.json")] for p in corpus.glob("*.key.json"))
    if not doc_ids:
        raise BuildError(f"no answer keys found in {corpus}")
    docs, excluded = [], []
    for doc_id in doc_ids:
        doc, ex = build_document(doc_id, corpus, catalog, register, textnorm, authorities)
        docs.append(doc)
        excluded.extend(ex)
    used = sorted({d["code"] for doc in docs for d in doc["defects"] + doc["unscored"]},
                  key=lambda c: (c[0], int(c[1:])))
    data = {
        "schema": SCHEMA,
        "source": {
            "kit": "governance-eval-kit",
            "catalog_sha256": sha256(catalog_bytes),
            "authorities_sha256": sha256(register_bytes),
            "documents": {d["id"]: d["sha256"] for d in docs},
            "keys": {d["id"]: d["key_sha256"] for d in docs},
        },
        "rule": {"minMarkChars": MIN_MARK_CHARS, "maxMarkChars": MAX_MARK_CHARS, "overlapCap": OVERLAP_CAP},
        "assumptions": {"readingWordsPerMinute": READING_WPM, "spotSeconds": SPOT_SECONDS},
        "types": [{"id": t, "label": label} for t, _k, _s, label in DEFECT_TYPES],
        "catalog": {c: {"rule": catalog[c]["rule"], "area": catalog[c]["area"]} for c in used},
        "counts": {
            "in_keys": sum(len(d["defects"]) + len(d["unscored"]) for d in docs) + len(excluded),
            "scored": sum(len(d["defects"]) for d in docs),
            "unscored": sum(len(d["unscored"]) for d in docs),
            "excluded": len(excluded),
        },
        "excluded": excluded,
        "docs": docs,
        "sets": build_sets(docs),
    }
    # One hash over everything above, so a saved result can say which build it came from.
    data["build"] = sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8"))[:16]
    return data


def render(data: dict) -> str:
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    body = body.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("</", "<\\/")
    return (
        "// Generated by build.py from ../governance-eval-kit. Do not edit by hand.\n"
        "// Fictional documents with planted errors. Not legal advice.\n"
        "(function (root) {\n"
        "  var data = " + body + ";\n"
        "  if (typeof module === 'object' && module.exports) { module.exports = data; }\n"
        "  else { root.DRILL_DATA = data; }\n"
        "})(typeof self !== 'undefined' ? self : this);\n"
    )


def main(argv: list[str]) -> int:
    try:
        data = build()
    except BuildError as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    text = render(data)
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("app/data.js is out of date. Run: python3 build.py", file=sys.stderr)
            return 1
        print("app/data.js is up to date")
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    c = data["counts"]
    print(f"wrote {OUT.relative_to(HERE)}: {len(data['docs'])} documents, {c['scored']} scored defects, "
          f"{c['unscored']} shown but not scored, {c['excluded']} excluded, {len(data['sets'])} sets, "
          f"build {data['build']}")
    for e in data["excluded"]:
        print(f"  excluded {e['id']}: {e['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
