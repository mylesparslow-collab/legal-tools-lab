"""Record-anchored verifier.

Checks every record cite in a draft (brief, coverage letter, response memo) against the source
pages: does the page exist, is each quotation on it word for word, is each timestamp, dollar amount
and measurement on it, and has the quoted policy language been replaced by an endorsement.

No model is involved. A quote either matches the page text or it does not.

Record cites look like (CHART-0003:14-16): a Bates prefix, a four-digit page, optional line range.
"""
from __future__ import annotations
import difflib, json, re
from dataclasses import dataclass
from pathlib import Path

CITE_RE = re.compile(r"\(([A-Z]{2,8})-(\d{4})(?::(\d+)(?:-(\d+))?)?\)")
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{12,}?)[”\"]")
VALUE_PATTERNS = [
    ("datetime", re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}(?:,? (?:at )?\d{1,2}:\d{2})?\b")),
    ("time", re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")),
    ("money", re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")),
    ("measure", re.compile(r"\b\d+(?:\.\d+)?\s?(?:mg/kg|mg/dL|mg|mL|mcg|µg/day|µg|ppm|ppb|units|kg|g|%)(?![A-Za-z/])")),
]


def norm(s: str) -> str:
    s = (s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
          .replace("–", "-").replace("—", "-").replace(" ", " "))
    return re.sub(r"\s+", " ", s).strip()


def norm_value(s: str) -> str:
    return re.sub(r"[\s,]", "", s).replace("at", "").lower()


@dataclass
class Page:
    doc: str
    number: int
    lines: list

    @property
    def bates(self) -> str:
        return f"{self.doc}-{self.number:04d}"

    def text(self, lo: int | None = None, hi: int | None = None) -> str:
        ls = self.lines if lo is None else self.lines[lo - 1:(hi or lo)]
        return norm(" ".join(ls))

    def locate(self, needle_regex: re.Pattern) -> tuple[int, int] | None:
        """Line range (1-based) of the first match of a compiled pattern over the page text."""
        offsets, parts, pos = [], [], 0
        for ln in self.lines:
            t = norm(ln)
            offsets.append(pos); parts.append(t); pos += len(t) + (1 if t else 0)
        joined = " ".join(p for p in parts if p)
        # rebuild offsets against the joined string (empty lines contribute nothing)
        offs, pos = [], 0
        for p in parts:
            offs.append(pos)
            if p:
                pos += len(p) + 1
        m = needle_regex.search(joined)
        if not m:
            return None
        start = max(i for i, o in enumerate(offs) if o <= m.start()) + 1
        end = max(i for i, o in enumerate(offs) if o < m.end()) + 1
        return start, end


class Record:
    """A set of source documents split into pages and lines. Pages are separated by form feeds."""

    def __init__(self, index_path: str | Path):
        index_path = Path(index_path)
        self.index = json.loads(index_path.read_text(encoding="utf-8"))
        self.pages: dict[str, Page] = {}
        self.docs: dict[str, dict] = {}
        for d in self.index["documents"]:
            raw = (index_path.parent / d["file"]).read_text(encoding="utf-8")
            self.docs[d["prefix"]] = d
            for i, chunk in enumerate(raw.split("\f"), start=1):
                p = Page(d["prefix"], i, chunk.strip("\n").split("\n"))
                self.pages[p.bates] = p
        self.superseded = self._scan_endorsements()

    # -- endorsements that replace or delete lettered exclusions in the base form
    def _scan_endorsements(self) -> list[dict]:
        out = []
        pat = re.compile(r"Exclusion ([a-z])\.[^.]*?\b(?:is|are) (replaced|deleted)", re.I)
        for p in self.pages.values():
            txt = p.text()
            if "THIS ENDORSEMENT CHANGES THE POLICY" not in txt.upper():
                continue
            for m in pat.finditer(txt):
                loc = p.locate(re.compile(re.escape(m.group(0))))
                out.append({"doc": p.doc, "label": m.group(1).lower(), "action": m.group(2).lower(),
                            "endorsement_page": p.bates, "endorsement_line": loc[0] if loc else None})
        return out

    def paragraph_label(self, page: Page, line: int) -> str | None:
        """Lettered paragraph ('f.') that a line on a base policy page falls under."""
        if "THIS ENDORSEMENT CHANGES THE POLICY" in page.text().upper():
            return None
        label = None
        for ln in page.lines[:line]:
            m = re.match(r"\s*([a-z])\.\s+\S", ln)
            if m:
                label = m.group(1)
        return label

    def find_everywhere(self, rx: re.Pattern) -> list[tuple[Page, tuple[int, int]]]:
        hits = []
        for p in self.pages.values():
            loc = p.locate(rx)
            if loc:
                hits.append((p, loc))
        return hits


def quote_regex(q: str) -> re.Pattern:
    """Exact match after normalization. An ellipsis may skip text; [brackets] may replace 1-6 words."""
    q = norm(q).rstrip(".,;")       # terminal punctuation moved inside the quote marks is conventional
    parts = re.split(r"(\.\s?\.\s?\.|…|\[[^\]]*\])", q)
    rx = ""
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"\.\s?\.\s?\.|…", part):
            rx += r".{0,400}?"
        elif part.startswith("["):
            rx += r"(?:\S+ ?){0,6}?"
        else:
            rx += re.escape(part.strip()).replace(r"\ ", " ")
            rx += " ?"
    return re.compile(rx.strip(" ?"))


def closest_passage(record: Record, quote: str, prefer_doc: str | None = None) -> dict | None:
    qn = norm(quote)
    best = None
    qw = qn.split()
    for p in record.pages.values():
        words = p.text().split()
        if not words:
            continue
        n = len(qw)
        for i in range(0, max(1, len(words) - n + 1), max(1, n // 4)):
            cand = " ".join(words[i:i + n + 2])
            score = difflib.SequenceMatcher(None, qn.lower(), cand.lower()).ratio()
            if prefer_doc and p.doc == prefer_doc:
                score += 0.02
            if best is None or score > best["score"]:
                best = {"score": score, "page": p.bates, "text": cand}
    if not best or best["score"] < 0.55:
        return None
    a, b = qn.split(), best["text"].split()
    sm = difflib.SequenceMatcher(None, [w.lower().strip('.,;"') for w in a], [w.lower().strip('.,;"') for w in b])
    diffs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace":
            diffs.append({"draft": " ".join(a[i1:i2]), "record": " ".join(b[j1:j2])})
        elif op == "delete":
            diffs.append({"draft": " ".join(a[i1:i2]), "record": ""})
        elif op == "insert" and 0 < i1 < len(a):
            diffs.append({"draft": "", "record": " ".join(b[j1:j2])})
    best["diff"] = diffs
    best["score"] = round(best["score"], 3)
    return best


def _check_quote(record: Record, quote: str, doc: str, page: Page | None, lo, hi) -> dict:
    rx = quote_regex(quote)
    item = {"type": "quote", "text": quote}
    if page is not None:
        loc = page.locate(rx)
        if loc:
            item["found"] = {"page": page.bates, "lines": list(loc)}
            if lo is None or (loc[0] >= lo and loc[1] <= (hi or lo)):
                item.update(status="PASS", message="Quote is on the cited page" + ("" if lo is None else " and lines") + ", word for word.")
            else:
                item.update(status="WARN", code="WRONG_LINE", message=f"Quote is on the cited page but at lines {loc[0]}-{loc[1]}, not {lo}" + (f"-{hi}" if hi else "") + ".")
            lab = record.paragraph_label(page, loc[0])
            for s in record.superseded:
                if s["doc"] == page.doc and s["label"] == lab:
                    item.update(status="WARN" if item["status"] == "PASS" else item["status"], code="SUPERSEDED",
                                message=f"The quoted language is in Exclusion {lab}., which an endorsement says is {s['action']} ({s['endorsement_page']}:{s['endorsement_line']}). Quote the endorsement instead, or explain.",
                                superseded_by={"page": s["endorsement_page"], "line": s["endorsement_line"]})
            return item
    hits = record.find_everywhere(rx)
    if hits:
        same = [h for h in hits if h[0].doc == doc] or hits
        p, loc = same[0]
        item.update(status="WARN", code="WRONG_PAGE", found={"page": p.bates, "lines": list(loc)},
                    message=f"Quote is not on the cited page. The same words are at {p.bates}:{loc[0]}-{loc[1]}.")
        return item
    near = closest_passage(record, quote, doc)
    item.update(status="FAIL", code="QUOTE_NOT_IN_RECORD", closest=near,
                message="These words are not in the record." + (f" Closest passage is on {near['page']}." if near else " Nothing similar found."))
    return item


def _check_value(record: Record, kind: str, value: str, page: Page, lo=None, hi=None) -> dict:
    nv = norm_value(value)
    item = {"type": kind, "text": value}
    rx = re.compile(re.escape(norm(value)).replace(r"\ ", r",? ?(?:at )?"))
    same_kind = lambda text: sorted({m.group(0) for k, rxp in VALUE_PATTERNS if k == kind for m in rxp.finditer(text)})
    if nv in norm_value(page.text()):
        loc = page.locate(rx)
        item["found"] = {"page": page.bates, "lines": list(loc) if loc else None}
        if lo is None or nv in norm_value(page.text(lo, hi)):
            item.update(status="PASS", message="Value is on the cited page" + ("" if lo is None else " and lines") + ".")
        else:
            there = same_kind(page.text(lo, hi))
            item.update(status="WARN", code="VALUE_OTHER_LINE", on_lines_instead=there,
                        message=f"{value} is on the cited page" + (f" at line {loc[0]}" if loc else "") + f", not at the cited line {lo}" + (f"-{hi}" if hi else "") + "." +
                                (f" The cited line has: {', '.join(there)}." if there else ""))
        return item
    on_page = same_kind(page.text())
    elsewhere = [p.bates for p in record.pages.values() if nv in norm_value(p.text())]
    item.update(status="FAIL", code="VALUE_NOT_ON_PAGE", on_page_instead=on_page[:8], found_elsewhere=elsewhere[:5],
                message=f"{value} is not on the cited page." + (f" The page has: {', '.join(on_page[:8])}." if on_page else "") +
                        (f" The value does appear on {', '.join(elsewhere[:5])}." if elsewhere else ""))
    return item


def verify_draft(draft_text: str, record: Record, name: str = "draft") -> dict:
    """Return one result per record cite, plus quotes that carry no cite."""
    results, n = [], 0
    for para_no, para in enumerate([p for p in re.split(r"\n\s*\n", draft_text) if p.strip()], start=1):
        if para.lstrip().startswith("#"):
            continue
        prev_end, cites = 0, list(CITE_RE.finditer(para))
        for m in cites:
            n += 1
            span = para[prev_end:m.start()]
            sent = span      # everything since the previous cite in this paragraph rests on this cite
            prev_end = m.end()
            doc, pg = m.group(1), int(m.group(2))
            lo = int(m.group(3)) if m.group(3) else None
            hi = int(m.group(4)) if m.group(4) else None
            cite_str = m.group(0)[1:-1]
            res = {"id": f"{name}#{n}", "paragraph": para_no, "cite": cite_str, "assertion": norm(sent), "items": []}
            page = record.pages.get(f"{doc}-{pg:04d}")
            if doc not in record.docs:
                res.update(status="FAIL", items=[{"type": "cite", "status": "FAIL", "code": "UNKNOWN_DOCUMENT", "text": cite_str,
                                                  "message": f"No document with prefix {doc} is in the record."}])
                results.append(res); continue
            if page is None:
                last = max(p.number for p in record.pages.values() if p.doc == doc)
                res["items"].append({"type": "cite", "status": "FAIL", "code": "PAGE_NOT_IN_RECORD", "text": cite_str,
                                     "message": f"{doc} has {last} pages. There is no page {pg}."})
            elif lo and (hi or lo) > len(page.lines):
                res["items"].append({"type": "cite", "status": "FAIL", "code": "LINE_NOT_ON_PAGE", "text": cite_str,
                                     "message": f"{page.bates} has {len(page.lines)} lines."})
            quotes = [q.group(1) for q in QUOTE_RE.finditer(sent)]
            for q in quotes:
                res["items"].append(_check_quote(record, q, doc, page, lo, hi))
            if page is not None:
                bare = QUOTE_RE.sub(" ", sent)
                seen = set()
                for kind, rxp in VALUE_PATTERNS:
                    for vm in rxp.finditer(bare):
                        v = vm.group(0)
                        if any(v in s for s in seen):
                            continue
                        seen.add(v)
                        res["items"].append(_check_value(record, kind, v, page, lo, hi))
            if not res["items"]:
                res["items"].append({"type": "cite", "status": "MANUAL", "code": "NOTHING_TO_MATCH", "text": cite_str,
                                     "message": "The cite carries no quotation, time, amount or measurement to match. Read the page."})
            st = [i["status"] for i in res["items"]]
            res["status"] = "FAIL" if "FAIL" in st else "WARN" if "WARN" in st else "MANUAL" if "MANUAL" in st else "PASS"
            results.append(res)
        tail = para[prev_end:]
        for q in QUOTE_RE.finditer(tail):
            if len(q.group(1).split()) < 4:
                continue
            n += 1
            results.append({"id": f"{name}#{n}", "paragraph": para_no, "cite": None, "assertion": norm(q.group(0)), "status": "FAIL",
                            "items": [{"type": "quote", "status": "FAIL", "code": "QUOTE_WITHOUT_CITE", "text": q.group(1),
                                       "message": "Quotation with no record cite after it."}]})
    counts = {k: sum(1 for r in results if r["status"] == k) for k in ("PASS", "WARN", "FAIL", "MANUAL")}
    return {"draft": name, "counts": counts, "results": results}


def verify_claims(case: dict, record: Record) -> dict:
    """Set anchor_status on each extracted claim of a triage case.

    A claim is VERIFIED only if its quote is at the cited page and line, word for word, and the
    quote contains the value. This is the gate between any extraction step and the calculations.
    """
    for key, c in case.get("claims", {}).items():
        a = c.get("anchor")
        if not a:
            c["anchor_status"] = "MISSING"; c["anchor_message"] = "No anchor given."; continue
        m = CITE_RE.fullmatch("(" + a["cite"] + ")")
        page = record.pages.get(f"{m.group(1)}-{int(m.group(2)):04d}") if m else None
        if not page:
            c["anchor_status"] = "FAILED"; c["anchor_message"] = f"Page {a['cite']} is not in the record."; continue
        lo = int(m.group(3)) if m.group(3) else None
        hi = int(m.group(4)) if m.group(4) else None
        q = _check_quote(record, a["quote"], m.group(1), page, lo, hi)
        vt = c.get("value_text", str(c["value"]))
        if q["status"] != "PASS":
            c["anchor_status"] = "FAILED"; c["anchor_message"] = q["message"]
        elif norm_value(vt) not in norm_value(a["quote"]):
            c["anchor_status"] = "FAILED"; c["anchor_message"] = f"The anchored quote does not contain the value {vt}."
        else:
            c["anchor_status"] = "VERIFIED"; c["anchor_message"] = f"Found at {a['cite']}."
    return case
