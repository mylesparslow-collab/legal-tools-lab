"""Score one tool run against the corpus.

Three measures per document:

  issue recall     share of planted defects the tool found
  quote grounding  share of the tool's quotes that appear word for word in the document
  net time saved   unaided review time minus time with the tool, where time with the
                   tool includes checking every finding and covering what it missed

A finding matches a defect when:
  * a reviewer has set "adjudicated_defect" on the finding (that always wins), or
  * the defect is a clause and the finding's quote is verbatim and overlaps the
    defect's quoted text, or
  * the defect is an omission and the finding cites the defect's section number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .config import TimeModel
from .corpus import Defect, Document
from .textnorm import find_quote, normalise

MIN_QUOTE_CHARS = 20
UNVERIFIED = "[UNVERIFIED QUOTE]"


def cites(authority_text: str, key: str) -> bool:
    """True if a citation string names section `key` (not a longer or decimal number)."""
    return re.search(rf"(?<![\d.]){re.escape(key)}(?!\.?\d)", authority_text or "") is not None


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


@dataclass
class FindingResult:
    index: int
    issue: str
    authority: str
    quote: str
    grounded: bool
    matched_defect: str | None
    match_basis: str | None  # "adjudicated", "quote", "citation"
    authority_correct: bool | None

    @property
    def display_quote(self) -> str:
        if not self.quote:
            return "(no quote given)"
        return self.quote if self.grounded else f"{UNVERIFIED} {self.quote}"


@dataclass
class DocScore:
    doc_id: str
    doc_type: str
    defects_total: int
    defects_high: int
    found: list[str]
    missed: list[str]
    found_high: int
    findings: list[FindingResult]
    baseline_minutes: float
    tool_minutes: float
    verification_minutes: float
    verification_measured: bool
    residual_minutes: float
    time_with_tool: float
    net_minutes_saved: float
    notes: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return len(self.found) / self.defects_total if self.defects_total else 0.0

    @property
    def high_recall(self) -> float:
        return self.found_high / self.defects_high if self.defects_high else 1.0

    @property
    def quotes_grounded(self) -> int:
        return sum(1 for f in self.findings if f.grounded)

    @property
    def grounding(self) -> float:
        return self.quotes_grounded / len(self.findings) if self.findings else 1.0

    @property
    def extra_findings(self) -> int:
        return sum(1 for f in self.findings if f.matched_defect is None)


def _match(doc: Document, finding: dict, spans: list[tuple[int, int]] | None) -> tuple[Defect | None, str | None]:
    adjudicated = finding.get("adjudicated_defect")
    if adjudicated is not None:
        if adjudicated in ("", "none"):
            return None, "adjudicated"
        for d in doc.defects:
            if d.id == adjudicated:
                return d, "adjudicated"
        raise ValueError(f"{doc.doc_id}: adjudicated_defect '{adjudicated}' is not in the answer key")
    best: tuple[int, Defect] | None = None
    if spans:
        for d in doc.defects:
            for ds in d.spans:
                need = min(30, max(1, (ds[1] - ds[0]) // 2))
                ov = max(_overlap(s, ds) for s in spans)
                if ov >= need and (best is None or ov > best[0]):
                    best = (ov, d)
    if best:
        return best[1], "quote"
    authority = finding.get("authority", "")
    for d in doc.defects:
        if d.kind == "omission" and any(cites(authority, k) for k in d.authority_keys):
            return d, "citation"
    return None, None


def score_document(doc: Document, run_doc: dict, model: TimeModel) -> DocScore:
    results: list[FindingResult] = []
    found: dict[str, Defect] = {}
    for i, f in enumerate(run_doc.get("findings", []), 1):
        quote = (f.get("quote") or "").strip()
        spans = find_quote(doc.text_norm, quote) if len(normalise(quote)) >= MIN_QUOTE_CHARS else None
        defect, basis = _match(doc, f, spans)
        if defect:
            found.setdefault(defect.id, defect)
        results.append(FindingResult(
            index=i, issue=f.get("issue", ""), authority=f.get("authority", ""), quote=quote,
            grounded=spans is not None, matched_defect=defect.id if defect else None, match_basis=basis,
            authority_correct=(any(cites(f.get("authority", ""), k) for k in defect.authority_keys)
                               if defect else None),
        ))
    missed = [d for d in doc.defects if d.id not in found]
    weight = lambda d: model.high_weight if d.severity == "high" else model.medium_weight  # noqa: E731
    total_w = sum(weight(d) for d in doc.defects) or 1.0
    missed_share = sum(weight(d) for d in missed) / total_w

    baseline = float(doc.baseline_review_minutes)
    tool_minutes = float(run_doc.get("tool_minutes", 0.0))
    measured = run_doc.get("attorney_verification_minutes")
    n_unverified = sum(1 for r in results if not r.grounded)
    if measured is not None:
        verification = float(measured)
    else:
        verification = (len(results) * model.verify_minutes_per_finding
                        + n_unverified * model.unverified_quote_penalty_minutes)
    # Review still needed: a fixed read-through, plus the share of the remaining
    # review that corresponds to the defects the tool missed.
    residual = baseline * model.spot_check_fraction + baseline * (1 - model.spot_check_fraction) * missed_share
    with_tool = model.setup_minutes + tool_minutes + verification + residual
    notes = []
    if n_unverified:
        notes.append(f"{n_unverified} quote(s) not found word for word in the document.")
    return DocScore(
        doc_id=doc.doc_id, doc_type=doc.doc_type, defects_total=len(doc.defects),
        defects_high=sum(1 for d in doc.defects if d.severity == "high"),
        found=sorted(found), missed=[d.id for d in missed],
        found_high=sum(1 for d in found.values() if d.severity == "high"),
        findings=results, baseline_minutes=baseline, tool_minutes=tool_minutes,
        verification_minutes=verification, verification_measured=measured is not None,
        residual_minutes=residual, time_with_tool=with_tool, net_minutes_saved=baseline - with_tool,
        notes=notes,
    )


@dataclass
class RunScore:
    tool: str
    docs: list[DocScore]
    model: TimeModel
    skipped: list[str] = field(default_factory=list)

    def _sum(self, attr: str) -> float:
        return sum(getattr(d, attr) for d in self.docs)

    @property
    def recall(self) -> float:
        total = self._sum("defects_total")
        return sum(len(d.found) for d in self.docs) / total if total else 0.0

    @property
    def high_recall(self) -> float:
        total = self._sum("defects_high")
        return self._sum("found_high") / total if total else 1.0

    @property
    def grounding(self) -> float:
        n = sum(len(d.findings) for d in self.docs)
        return self._sum("quotes_grounded") / n if n else 1.0

    @property
    def net_minutes_saved(self) -> float:
        return self._sum("net_minutes_saved")

    @property
    def baseline_minutes(self) -> float:
        return self._sum("baseline_minutes")

    @property
    def passes(self) -> bool:
        return self.high_recall >= self.model.pass_high_recall and self.grounding >= self.model.pass_grounding

    def by_type(self) -> dict[str, "RunScore"]:
        out: dict[str, RunScore] = {}
        for d in self.docs:
            out.setdefault(d.doc_type, RunScore(self.tool, [], self.model)).docs.append(d)
        return out


def score_run(run: dict, documents: dict[str, Document], model: TimeModel) -> RunScore:
    docs, seen = [], set()
    for rd in run.get("documents", []):
        doc_id = rd["doc_id"]
        if doc_id in seen:
            raise ValueError(f"run lists {doc_id} twice")
        seen.add(doc_id)
        if doc_id not in documents:
            raise ValueError(f"run refers to unknown document '{doc_id}'")
        docs.append(score_document(documents[doc_id], rd, model))
    return RunScore(run.get("tool", "unnamed tool"), docs, model, skipped=sorted(set(documents) - seen))
