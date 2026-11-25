"""Clause tracker: find and classify AI-related clauses in client terms documents.

Deterministic. Patterns live in data/clause_patterns.json. No model is called.
Each hit keeps the document id, the exact quoted span with character offsets, and the class.
"""
import json
import re
from pathlib import Path

from . import DATA

FLAGS = re.IGNORECASE


class Patterns:
    """Compiled view of the pattern data file."""

    def __init__(self, raw):
        self.raw = raw
        self.version = raw.get("version", "")
        self.class_ids = [c["id"] for c in raw["classes"]]
        self.class_labels = {c["id"]: c["label"] for c in raw["classes"]}
        self.ai_terms = re.compile(raw["ai_terms"], FLAGS)
        self.abbreviations = {a.lower() for a in raw.get("abbreviations", [])}
        self.heading_max_words = raw.get("heading_max_words", 12)
        self.conflict_pairs = [tuple(p) for p in raw.get("conflict_pairs", [])]
        self.review_classes = list(raw.get("review_classes", []))
        self.suppressors = {k: re.compile(v, FLAGS) for k, v in raw.get("suppressors", {}).items()}
        self.guards = [dict(g, rx=re.compile(g["regex"], FLAGS)) for g in raw.get("guards", [])]
        self.patterns = []
        for p in raw["patterns"]:
            if p["class"] not in self.class_ids:
                raise ValueError("pattern %s uses unknown class %s" % (p["id"], p["class"]))
            for name in p.get("suppress_if", []):
                if name not in self.suppressors:
                    raise ValueError("pattern %s uses unknown suppressor %s" % (p["id"], name))
            self.patterns.append(dict(
                p,
                rx=re.compile(p["regex"], FLAGS),
                req=[re.compile(r, FLAGS) for r in p.get("requires", [])],
            ))


def load_patterns(path=None):
    path = Path(path) if path else DATA / "clause_patterns.json"
    return Patterns(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- segmentation

_BOUNDARY = re.compile(r"[.!?][\"')\]]?(?=\s+[\"'(\[]?[A-Z0-9])")
_NUMBERING = re.compile(r"^\(?(?:\d+(?:\.\d+)*|[A-Za-z])[.)]?$")


def _is_heading(line, max_words):
    s = line.strip()
    if not s or s[-1] in ".;:!?,":
        return False
    return len(s.split()) <= max_words


def split_sentences(text, patterns):
    """Return a list of dicts: start, end, paragraph, heading (the heading text in force).

    A paragraph is one line. A heading is a short line with no closing punctuation.
    Headings are context only and are never classified.
    """
    out = []
    heading = ""
    pos = 0
    para_no = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        line_start = pos
        pos += len(line)
        if not body.strip():
            continue
        if _is_heading(body, patterns.heading_max_words):
            heading = body.strip()
            continue
        para_no += 1
        lead = len(body) - len(body.lstrip())
        seg_start = lead
        cuts = []
        for m in _BOUNDARY.finditer(body):
            end = m.end()
            words = body[seg_start:end].split()
            last = words[-1].rstrip(".!?\"')]") if words else ""
            if last.lower() in patterns.abbreviations:
                continue
            if _NUMBERING.match(words[-1] if words else "") and len(words) == 1:
                continue
            cuts.append((seg_start, end))
            rest = body[end:]
            seg_start = end + (len(rest) - len(rest.lstrip()))
        if seg_start < len(body.rstrip()):
            cuts.append((seg_start, len(body.rstrip())))
        for s, e in cuts:
            out.append({
                "start": line_start + s,
                "end": line_start + e,
                "paragraph": para_no,
                "paragraph_span": (line_start, line_start + len(body)),
                "heading": heading,
            })
    return out


# -------------------------------------------------------------- classification

def classify_document(document_id, text, patterns):
    """Classify one document.

    Returns {"document_id", "hits": [...], "guarded": [...], "silent": bool}.
    A hit: document_id, class, start, end, quote, pattern_ids, context.
    A guarded entry records a pattern match that a negation or scope guard stopped.
    """
    hits, guarded = [], []
    for sent in split_sentences(text, patterns):
        s, e = sent["start"], sent["end"]
        quote = text[s:e]
        ps, pe = sent["paragraph_span"]
        if patterns.ai_terms.search(quote):
            context = "sentence"
        elif patterns.ai_terms.search(text[ps:pe]):
            context = "paragraph"
        elif patterns.ai_terms.search(sent["heading"]):
            context = "heading"
        else:
            continue
        active_guards = [g for g in patterns.guards if g["rx"].search(quote)]
        by_class = {}
        fallback = {}
        for p in patterns.patterns:
            if not p["rx"].search(quote):
                continue
            if not all(r.search(quote) for r in p["req"]):
                continue
            cls = p["class"]
            stopping = [g for g in active_guards if "*" in g["applies_to"] or cls in g["applies_to"]]
            if stopping:
                guarded.append({
                    "document_id": document_id, "class": cls, "start": s, "end": e, "quote": quote,
                    "pattern_id": p["id"], "guard_id": stopping[0]["id"], "guard_kind": stopping[0]["kind"],
                })
                continue
            fired = [n for n in p.get("suppress_if", []) if patterns.suppressors[n].search(quote)]
            if fired:
                for n in fired:
                    alt = p.get("on_suppressed_emit", {}).get(n)
                    if alt:
                        fallback.setdefault(alt, []).append(p["id"] + ":" + n)
                continue
            by_class.setdefault(cls, []).append(p["id"])
        if not by_class and fallback and not active_guards:
            # A qualified restriction that no other class explains goes to a person.
            by_class = fallback
        for cls, ids in by_class.items():
            hits.append({
                "document_id": document_id, "class": cls, "start": s, "end": e, "quote": quote,
                "pattern_ids": ids, "context": context,
            })
    return {"document_id": document_id, "hits": hits, "guarded": guarded, "silent": not hits}


def classify_file(path, patterns, document_id=None):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return classify_document(document_id or path.stem, text, patterns)


# ------------------------------------------------------------- party summaries

def summarize_party(party_id, party_name, doc_results, patterns):
    """Roll document results up to one party (a client, an insurer, a co-counsel group).

    Conflicts and ambiguous clauses are surfaced, never resolved here.
    Status: not_on_file, silent, clear, needs_analyst_review.
    """
    classes = {}
    for res in doc_results:
        for h in res["hits"]:
            classes.setdefault(h["class"], []).append(h)
    conflicts = []
    for a, b in patterns.conflict_pairs:
        if a in classes and b in classes:
            conflicts.append({
                "pair": [a, b],
                "documents": sorted({h["document_id"] for h in classes[a] + classes[b]}),
                "spans": classes[a] + classes[b],
            })
    review_hits = [h for c in patterns.review_classes for h in classes.get(c, [])]
    if not doc_results:
        status = "not_on_file"
    elif conflicts or review_hits:
        status = "needs_analyst_review"
    elif not classes:
        status = "silent"
    else:
        status = "clear"
    present = sorted(classes, key=patterns.class_ids.index)
    if status == "silent":
        present = ["silent"]
    return {
        "party_id": party_id,
        "party_name": party_name,
        "status": status,
        "documents": [r["document_id"] for r in doc_results],
        "silent_documents": [r["document_id"] for r in doc_results if r["silent"]],
        "classes": present,
        "hits_by_class": classes,
        "conflicts": conflicts,
        "review_hits": review_hits,
        "guarded": [g for r in doc_results for g in r["guarded"]],
    }


# ------------------------------------------------------------------ evaluation

def _overlaps(a_start, a_end, b_start, b_end):
    inter = min(a_end, b_end) - max(a_start, b_start)
    return inter > 0 and inter >= 0.5 * min(a_end - a_start, b_end - b_start)


def evaluate(answer_key, results_by_doc, split_by_doc=None):
    """Score classifier hits against the hand-labeled key.

    True positive: a hit that overlaps a key span of the same class in the same document.
    False positive: any other hit, including hits on hard negatives and on unlabeled text.
    False negative: a positive key span with no matching hit.
    """
    labels = answer_key["labels"]
    positives = [k for k in labels if k["label"] != "none"]
    negatives = [k for k in labels if k["label"] == "none"]
    hits = [h for r in results_by_doc.values() for h in r["hits"]]
    matched_keys = set()
    tp, fp = [], []
    for h in hits:
        match = None
        for k in positives:
            if (k["document_id"] == h["document_id"] and k["label"] == h["class"]
                    and _overlaps(k["start"], k["end"], h["start"], h["end"])):
                match = k
                break
        if match:
            matched_keys.add(match["id"])
            tp.append(h)
        else:
            on_negative = any(k["document_id"] == h["document_id"]
                              and _overlaps(k["start"], k["end"], h["start"], h["end"]) for k in negatives)
            fp.append(dict(h, on_hard_negative=on_negative))
    fn = [k for k in positives if k["id"] not in matched_keys]

    def prf(tp_n, fp_n, fn_n):
        p = tp_n / (tp_n + fp_n) if tp_n + fp_n else None
        r = tp_n / (tp_n + fn_n) if tp_n + fn_n else None
        return {"tp": tp_n, "fp": fp_n, "fn": fn_n,
                "precision": None if p is None else round(p, 3),
                "recall": None if r is None else round(r, 3)}

    per_class = {}
    for cls in sorted({k["label"] for k in positives} | {h["class"] for h in hits}):
        per_class[cls] = prf(sum(1 for h in tp if h["class"] == cls),
                             sum(1 for h in fp if h["class"] == cls),
                             sum(1 for k in fn if k["label"] == cls))
    per_split = {}
    if split_by_doc:
        for split in sorted(set(split_by_doc.values())):
            docs = {d for d, s in split_by_doc.items() if s == split}
            per_split[split] = dict(
                prf(sum(1 for h in tp if h["document_id"] in docs),
                    sum(1 for h in fp if h["document_id"] in docs),
                    sum(1 for k in fn if k["document_id"] in docs)),
                documents=len(docs))
    neg_hit = [k for k in negatives if any(
        h["document_id"] == k["document_id"] and _overlaps(k["start"], k["end"], h["start"], h["end"])
        for h in hits)]
    return {
        "labeled_spans": len(labels),
        "positive_spans": len(positives),
        "hard_negative_spans": len(negatives),
        "hard_negatives_wrongly_classified": len(neg_hit),
        "overall": prf(len(tp), len(fp), len(fn)),
        "per_class": per_class,
        "per_split": per_split,
        "false_positives": [{"document_id": h["document_id"], "class": h["class"], "quote": h["quote"],
                             "pattern_ids": h["pattern_ids"], "on_hard_negative": h["on_hard_negative"]} for h in fp],
        "false_negatives": [{"key_id": k["id"], "document_id": k["document_id"], "label": k["label"],
                             "quote": k["quote"]} for k in fn],
    }


def format_evaluation(ev):
    lines = []
    o = ev["overall"]
    lines.append("Clause classifier against the hand-labeled answer key")
    lines.append("  labeled spans: %d (%d positive, %d hard negatives)" % (
        ev["labeled_spans"], ev["positive_spans"], ev["hard_negative_spans"]))
    lines.append("  overall: precision %.3f, recall %.3f (tp %d, fp %d, fn %d)" % (
        o["precision"] or 0, o["recall"] or 0, o["tp"], o["fp"], o["fn"]))
    lines.append("  hard negatives wrongly classified: %d of %d" % (
        ev["hard_negatives_wrongly_classified"], ev["hard_negative_spans"]))
    for split, m in ev["per_split"].items():
        lines.append("  split %-8s precision %s, recall %s (tp %d, fp %d, fn %d, %d documents)" % (
            split, m["precision"], m["recall"], m["tp"], m["fp"], m["fn"], m["documents"]))
    lines.append("  per class:")
    for cls, m in ev["per_class"].items():
        lines.append("    %-26s precision %-5s recall %-5s tp %d fp %d fn %d" % (
            cls, m["precision"], m["recall"], m["tp"], m["fp"], m["fn"]))
    if ev["false_positives"]:
        lines.append("  false positives:")
        for f in ev["false_positives"]:
            lines.append("    [%s] %s: %s" % (f["class"], f["document_id"], f["quote"][:110]))
    if ev["false_negatives"]:
        lines.append("  misses:")
        for f in ev["false_negatives"]:
            lines.append("    [%s] %s: %s" % (f["label"], f["document_id"], f["quote"][:110]))
    return "\n".join(lines)
