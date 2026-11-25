"""Write a scorecard as Markdown, CSV and JSON."""
from __future__ import annotations

import csv
import io
import json

from .score import DocScore, RunScore

TYPE_LABEL = {
    "commercial_lease": "Commercial leases",
    "snf_rcfe_apa": "SNF and RCFE asset purchase agreements",
    "public_works_contract": "Public works contracts",
    "executive_employment": "Executive employment agreements",
}


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def _min(x: float) -> str:
    return f"{x:+.0f}" if x else "0"


def to_json(rs: RunScore) -> dict:
    def doc(d: DocScore) -> dict:
        return {
            "doc_id": d.doc_id, "doc_type": d.doc_type, "defects": d.defects_total, "found": d.found,
            "missed": d.missed, "recall": round(d.recall, 4), "high_recall": round(d.high_recall, 4),
            "findings": len(d.findings), "quotes_grounded": d.quotes_grounded,
            "grounding": round(d.grounding, 4), "extra_findings": d.extra_findings,
            "baseline_minutes": d.baseline_minutes, "time_with_tool_minutes": round(d.time_with_tool, 1),
            "verification_minutes": round(d.verification_minutes, 1),
            "verification_measured": d.verification_measured,
            "net_minutes_saved": round(d.net_minutes_saved, 1),
            "unverified_quotes": [f.quote for f in d.findings if f.quote and not f.grounded],
        }
    return {
        "tool": rs.tool, "documents_scored": len(rs.docs), "documents_not_in_run": rs.skipped,
        "recall": round(rs.recall, 4), "high_severity_recall": round(rs.high_recall, 4),
        "quote_grounding": round(rs.grounding, 4),
        "net_minutes_saved": round(rs.net_minutes_saved, 1), "baseline_minutes": rs.baseline_minutes,
        "passes": rs.passes, "time_model": rs.model.to_dict(), "documents": [doc(d) for d in rs.docs],
    }


def to_csv(rs: RunScore) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["tool", "doc_id", "doc_type", "defects", "found", "recall", "high_defects", "high_found",
                "findings", "quotes_grounded", "extra_findings", "baseline_min", "with_tool_min", "net_saved_min"])
    for d in rs.docs:
        w.writerow([rs.tool, d.doc_id, d.doc_type, d.defects_total, len(d.found), f"{d.recall:.3f}",
                    d.defects_high, d.found_high, len(d.findings), d.quotes_grounded, d.extra_findings,
                    f"{d.baseline_minutes:.0f}", f"{d.time_with_tool:.1f}", f"{d.net_minutes_saved:.1f}"])
    return buf.getvalue()


def to_markdown(rs: RunScore) -> str:
    m = rs.model
    L = [f"# Scorecard: {rs.tool}", ""]
    L.append(f"Documents scored: {len(rs.docs)}"
             + (f" ({len(rs.skipped)} corpus documents not in this run)" if rs.skipped else ""))
    L += ["", "| Measure | Result | Pass mark |", "| --- | --- | --- |",
          f"| High-severity issue recall | {_pct(rs.high_recall)} | {_pct(m.pass_high_recall)} |",
          f"| All-issue recall | {_pct(rs.recall)} | |",
          f"| Quote grounding | {_pct(rs.grounding)} | {_pct(m.pass_grounding)} |",
          f"| Net time saved (modeled) | {_min(rs.net_minutes_saved)} min of {rs.baseline_minutes:.0f} min unaided "
          f"({_pct(rs.net_minutes_saved / rs.baseline_minutes) if rs.baseline_minutes else 'n/a'}) | |",
          f"| Result | {'Pass' if rs.passes else 'Does not pass'} | |", ""]
    L += ["## By document type", "", "| Type | Docs | High recall | Recall | Grounding | Net min saved |",
          "| --- | --- | --- | --- | --- | --- |"]
    for t, sub in sorted(rs.by_type().items()):
        L.append(f"| {TYPE_LABEL.get(t, t)} | {len(sub.docs)} | {_pct(sub.high_recall)} | {_pct(sub.recall)} "
                 f"| {_pct(sub.grounding)} | {_min(sub.net_minutes_saved)} |")
    L += ["", "## By document", "",
          "| Document | Found | Missed | Findings | Quotes verified | Extra findings | Net min saved |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for d in rs.docs:
        L.append(f"| {d.doc_id} | {len(d.found)} of {d.defects_total} | {', '.join(d.missed) or 'none'} "
                 f"| {len(d.findings)} | {d.quotes_grounded} of {len(d.findings)} | {d.extra_findings} "
                 f"| {_min(d.net_minutes_saved)} |")
    bad = [(d.doc_id, f) for d in rs.docs for f in d.findings if not f.grounded]
    if bad:
        L += ["", "## Quotes that could not be verified", "",
              "These were presented by the tool as quotes but do not appear word for word in the document.", ""]
        for doc_id, f in bad:
            L.append(f"- {doc_id}, finding {f.index}: {f.display_quote[:300]}")
    L += ["", "## How to read this", "",
          "- Recall counts a planted defect as found when a finding quotes the defective clause word for word, "
          "or, for a missing clause, cites the right section. A reviewer can override any match.",
          "- Extra findings are findings that match no planted defect. They may be false alarms or real "
          "points outside the answer key. Each still costs verification time.",
          "- Net time saved is a model, not a measurement. Time with the tool = setup "
          f"({m.setup_minutes:g} min) + tool run time + verification ({m.verify_minutes_per_finding:g} min per finding, "
          f"plus {m.unverified_quote_penalty_minutes:g} min for each unverified quote, or the measured figure if the run "
          f"supplies one) + a read-through ({_pct(m.spot_check_fraction)} of unaided time) + the remaining "
          "review time in proportion to the severity-weighted share of defects missed.",
          "- The documents are synthetic and the answer keys cover only the planted defects. "
          "A pass here says nothing about real matters.", ""]
    return "\n".join(L)


def compare_markdown(runs: list[RunScore]) -> str:
    L = ["# Comparison", "", "| Tool | Docs | High recall | Recall | Grounding | Net min saved | Result |",
         "| --- | --- | --- | --- | --- | --- | --- |"]
    for rs in runs:
        L.append(f"| {rs.tool} | {len(rs.docs)} | {_pct(rs.high_recall)} | {_pct(rs.recall)} | {_pct(rs.grounding)} "
                 f"| {_min(rs.net_minutes_saved)} | {'Pass' if rs.passes else 'Does not pass'} |")
    L += ["", "Net time saved is modeled; see each scorecard for the assumptions.", ""]
    return "\n".join(L)


def dumps(rs: RunScore) -> str:
    return json.dumps(to_json(rs), indent=2, ensure_ascii=False) + "\n"
