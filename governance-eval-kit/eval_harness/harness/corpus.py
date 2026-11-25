"""Load and validate corpus documents and their answer keys."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .textnorm import find_quote, normalise

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
DOC_TYPES = {"commercial_lease", "snf_rcfe_apa", "public_works_contract", "executive_employment"}
SEVERITIES = {"high", "medium"}
KINDS = {"clause", "omission"}


@dataclass
class Defect:
    id: str
    severity: str
    kind: str
    title: str
    authority: str
    authority_keys: list[str]
    why: str
    quotes: list[str]
    spans: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Document:
    doc_id: str
    doc_type: str
    title: str
    text: str
    text_norm: str
    baseline_review_minutes: int
    defects: list[Defect]

    @property
    def word_count(self) -> int:
        return len(re.findall(r"\S+", self.text))


def load_document(doc_id: str, corpus_dir: Path = CORPUS_DIR) -> Document:
    text = (corpus_dir / f"{doc_id}.md").read_text(encoding="utf-8")
    key = json.loads((corpus_dir / f"{doc_id}.key.json").read_text(encoding="utf-8"))
    text_norm = normalise(text)
    defects = []
    for d in key["defects"]:
        defect = Defect(
            id=d["id"], severity=d["severity"], kind=d["kind"], title=d["title"],
            authority=d["authority"], authority_keys=list(d["authority_keys"]),
            why=d["why"], quotes=list(d.get("quotes", [])),
        )
        for q in defect.quotes:
            spans = find_quote(text_norm, q)
            if spans:
                defect.spans.extend(spans)
        defects.append(defect)
    return Document(
        doc_id=key["doc_id"], doc_type=key["doc_type"], title=key["title"], text=text,
        text_norm=text_norm, baseline_review_minutes=int(key["baseline_review_minutes"]),
        defects=defects,
    )


def list_doc_ids(corpus_dir: Path = CORPUS_DIR) -> list[str]:
    return sorted(p.name[: -len(".key.json")] for p in corpus_dir.glob("*.key.json"))


def validate_document(doc_id: str, corpus_dir: Path = CORPUS_DIR) -> list[str]:
    """Return a list of problems with one document and its key (empty if clean)."""
    problems: list[str] = []
    md = corpus_dir / f"{doc_id}.md"
    kj = corpus_dir / f"{doc_id}.key.json"
    if not md.exists():
        return [f"{doc_id}: missing {md.name}"]
    if not kj.exists():
        return [f"{doc_id}: missing {kj.name}"]
    try:
        key = json.loads(kj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{doc_id}: key is not valid JSON ({exc})"]
    text = md.read_text(encoding="utf-8")
    text_norm = normalise(text)
    for fld in ("doc_id", "doc_type", "title", "fictional_notice", "baseline_review_minutes", "defects"):
        if fld not in key:
            problems.append(f"{doc_id}: key missing field '{fld}'")
    if problems:
        return problems
    if key["doc_id"] != doc_id:
        problems.append(f"{doc_id}: key doc_id is '{key['doc_id']}'")
    if key["doc_type"] not in DOC_TYPES:
        problems.append(f"{doc_id}: unknown doc_type '{key['doc_type']}'")
    if "fictional" not in text[:600].lower():
        problems.append(f"{doc_id}: document must say it is fictional in its first lines")
    n = len(key["defects"])
    if not 6 <= n <= 10:
        problems.append(f"{doc_id}: has {n} defects, expected 6 to 10")
    seen: set[str] = set()
    taken: list[tuple[int, int, str]] = []
    for d in key["defects"]:
        did = d.get("id", "?")
        for fld in ("id", "severity", "kind", "title", "authority", "authority_keys", "why", "quotes"):
            if fld not in d:
                problems.append(f"{doc_id}/{did}: missing field '{fld}'")
        if did in seen:
            problems.append(f"{doc_id}/{did}: duplicate defect id")
        seen.add(did)
        if not did.startswith(doc_id + "-D"):
            problems.append(f"{doc_id}/{did}: id should start with '{doc_id}-D'")
        if d.get("severity") not in SEVERITIES:
            problems.append(f"{doc_id}/{did}: severity must be high or medium")
        if d.get("kind") not in KINDS:
            problems.append(f"{doc_id}/{did}: kind must be clause or omission")
        if not d.get("authority_keys"):
            problems.append(f"{doc_id}/{did}: authority_keys is empty")
        quotes = d.get("quotes", [])
        if d.get("kind") == "clause" and not quotes:
            problems.append(f"{doc_id}/{did}: a clause defect needs at least one quote")
        for q in quotes:
            qn = normalise(q)
            if len(qn) < 40:
                problems.append(f"{doc_id}/{did}: quote shorter than 40 characters: {q!r}")
            spans = find_quote(text_norm, q)
            if not spans:
                problems.append(f"{doc_id}/{did}: quote not found verbatim: {q[:70]!r}")
                continue
            if "[" not in q and text_norm.count(qn) != 1:
                problems.append(f"{doc_id}/{did}: quote appears {text_norm.count(qn)} times, must be unique")
            for s, e in spans:
                for ts, te, other in taken:
                    if s < te and ts < e and other != did:
                        problems.append(f"{doc_id}/{did}: quote overlaps a quote of {other}")
                taken.append((s, e, did))
    return problems
