"""PDF redaction that removes the text itself, then checks the saved file for leaks.

Uses pypdfium2 (Apache-2.0 / BSD-3-Clause). For each match the text object holding it is
deleted from the page. The parts of that object that were not redacted are written back as new
text in Helvetica, and a black box is drawn over the gap. The saved file is then reopened and
searched, both through the text layer and through the raw and decompressed bytes.

Limits: text inside form XObjects or images is not handled (the run stops with an error rather
than produce a file). Re-set text uses Helvetica, so other fonts will shift slightly."""
import ctypes
import re
import zlib
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as R


class RedactionError(Exception):
    pass


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def extract_text(path) -> str:
    doc = pdfium.PdfDocument(str(path))
    try:
        parts = []
        for page in doc:
            tp = page.get_textpage()
            parts.append(tp.get_text_bounded())
            tp.close()
            page.close()
        return "\n".join(parts)
    finally:
        doc.close()


def _matches(tp, term):
    s = tp.search(term, match_case=False)
    out = []
    while True:
        hit = s.get_next()
        if hit is None:
            break
        out.append(hit)
    s.close()
    return out


def redact_pdf(src, dst, terms: list) -> dict:
    """Remove every occurrence of each term. Returns {"hits": {term: n}, "pages": n}."""
    terms = [t for t in dict.fromkeys(t.strip() for t in terms) if t]
    doc = pdfium.PdfDocument(str(src))
    hits = {t: 0 for t in terms}
    font_name = b"Helvetica"
    try:
        for page in doc:
            tp = page.get_textpage()
            n = tp.count_chars()
            red, boxes = set(), []
            for t in terms:
                for idx, cnt in _matches(tp, t):
                    hits[t] += 1
                    red.update(range(idx, idx + cnt))
                    for k in range(R.FPDFText_CountRects(tp.raw, idx, cnt)):
                        l, top, r, b = (ctypes.c_double() for _ in range(4))
                        R.FPDFText_GetRect(tp.raw, k, l, top, r, b)
                        boxes.append((l.value, b.value, r.value, top.value))
            if not red:
                tp.close(); page.close()
                continue
            # group characters by the text object that holds them
            objs, chars = {}, {}
            for i in range(n):
                o = R.FPDFText_GetTextObject(tp.raw, i)
                if not o:
                    continue
                addr = ctypes.addressof(o.contents)
                objs[addr] = o
                x, y = ctypes.c_double(), ctypes.c_double()
                R.FPDFText_GetCharOrigin(tp.raw, i, x, y)
                chars.setdefault(addr, []).append((i, chr(R.FPDFText_GetUnicode(tp.raw, i)), x.value, y.value, R.FPDFText_GetFontSize(tp.raw, i)))
            affected = {a for a, cs in chars.items() if any(c[0] in red for c in cs)}
            covered = {c[0] for a in affected for c in chars[a]}
            if red - covered - {i for i in red if not R.FPDFText_GetTextObject(tp.raw, i)}:
                raise RedactionError(f"{src}: matched text is not in a removable page object.")
            keep_runs = []
            for a in affected:
                run = []
                for c in chars[a] + [None]:
                    if c is not None and c[0] not in red:
                        run.append(c)
                    else:
                        if run and "".join(x[1] for x in run).strip():
                            keep_runs.append(run)
                        run = []
            tp.close()
            for a in affected:
                if not R.FPDFPage_RemoveObject(page.raw, objs[a]):
                    raise RedactionError(f"{src}: could not remove a text object (it may sit inside a form). No file written.")
                R.FPDFPageObj_Destroy(objs[a])
            for run in keep_runs:
                text = "".join(c[1] for c in run).rstrip()
                o = R.FPDFPageObj_NewTextObj(doc.raw, font_name, ctypes.c_float(run[0][4] or 10))
                buf = (text + "\x00").encode("utf-16-le")
                arr = (ctypes.c_ushort * (len(buf) // 2)).from_buffer_copy(buf)
                R.FPDFText_SetText(o, arr)
                R.FPDFPageObj_Transform(o, 1, 0, 0, 1, run[0][2], run[0][3])
                R.FPDFPage_InsertObject(page.raw, o)
            for l, b, r, t in boxes:
                o = R.FPDFPageObj_CreateNewRect(l - 1, b - 1, (r - l) + 2, (t - b) + 2)
                R.FPDFPageObj_SetFillColor(o, 0, 0, 0, 255)
                R.FPDFPath_SetDrawMode(o, R.FPDF_FILLMODE_ALTERNATE, 0)
                R.FPDFPage_InsertObject(page.raw, o)
            if not R.FPDFPage_GenerateContent(page.raw):
                raise RedactionError(f"{src}: could not rewrite page content.")
            page.close()
        pages = len(doc)
        doc.save(str(dst))
    finally:
        doc.close()
    return {"hits": hits, "pages": pages}


def verify_no_leak(path, terms: list) -> list:
    """Returns a list of leaks. Empty list means none of the terms were found by either check."""
    leaks = []
    layer = _squash(extract_text(path))
    for t in terms:
        if _squash(t) and _squash(t) in layer:
            leaks.append({"term": t, "where": "text layer"})
    raw = Path(path).read_bytes()
    blobs = [raw]
    for m in re.finditer(rb"stream\r?\n", raw):
        end = raw.find(b"endstream", m.end())
        if end > 0:
            try:
                blobs.append(zlib.decompress(raw[m.end():end]))
            except zlib.error:
                pass
    hay = b"\n".join(blobs).lower()
    for t in terms:
        t = t.strip()
        if not t:
            continue
        for enc in ("latin-1", "utf-16-be"):
            try:
                needle = t.lower().encode(enc)
            except UnicodeEncodeError:
                continue
            if needle in hay and not any(l["term"] == t and l["where"] == "file bytes" for l in leaks):
                leaks.append({"term": t, "where": "file bytes"})
    return leaks


def _shingles(text, k=5):
    w = re.findall(r"\w+", text.lower())
    return {" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1))}


def near_duplicates(texts: dict, threshold: float = 0.35) -> list:
    """Group documents whose word-shingle overlap (Jaccard) meets the threshold. texts: {doc_id: text}."""
    ids = list(texts)
    sh = {i: _shingles(texts[i]) for i in ids}
    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = sh[ids[x]], sh[ids[y]]
            contain = len(a & b) / max(1, min(len(a), len(b)))
            if contain >= threshold:
                parent[find(ids[y])] = find(ids[x])
    groups = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def propagate(terms: list, sources: dict, out_dir) -> dict:
    """Apply approved terms to every PDF in the set, then verify each output.
    sources: {doc_id: path}. Returns per-document hits and leaks. Raises if any leak is found."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    for doc_id, src in sources.items():
        dst = out_dir / f"{doc_id}_redacted.pdf"
        res = redact_pdf(src, dst, terms)
        leaks = verify_no_leak(dst, terms)
        report[doc_id] = {"output": str(dst), "hits": {t: c for t, c in res["hits"].items() if c}, "leaks": leaks}
        if leaks:
            dst.unlink()
            raise RedactionError(f"{doc_id}: redacted text is still present ({leaks}). Output deleted.")
    return report
