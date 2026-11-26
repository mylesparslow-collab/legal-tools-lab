"""Harvest: file the final answers of a submitted proposal back into the library.

Input is the final response as Markdown with one "## <label> <title>" heading
per RFP requirement (the layout the draft command writes). New answers are
filed as NOT approved, with a review date, and with the outcome given
(pending until the result is known). Sections that still carry a gap, person
or blocking marker are not filed.
"""
import datetime as dt
import json
import os
import re

from . import facts as F
from .library import fill_placeholders
from .pipeline import detect_terms
from .rfp import parse_rfp, submission_deadline
from .schemas import OUTCOMES
from .util import norm_ws, parse_iso, slug

NEVER_HARVEST = {"conflicts": "conflicts statements are written fresh for each proposal",
                 "rates": "pricing is not library content",
                 "cover_letter": "cover letters are not library content",
                 "disclosure": "disclosures are written fresh for each proposal",
                 "other": "question type not recognised; file it by hand if it is worth keeping"}
LIST_QTYPES = {"team", "experience", "references"}
OPEN_MARK_RE = re.compile(r"\[(GAP|NEEDS A PERSON|BLOCKING|PARTIAL)\b")
NOTE_LINE_RE = re.compile(r"^\s*\[(Source|CHECK|NOTE)\b.*\]\s*$")
HARVEST_FILE = "harvested_answers.json"


def parse_final_markdown(text):
    """Split a final response into sections by '## ' headings. Returns [{heading, lines}]."""
    sections, cur = [], None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = {"heading": line[3:].strip(), "lines": []}
            sections.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    return sections


def _match_requirement(heading, requirements):
    for req in sorted(requirements, key=lambda r: -len(r["label"])):
        if req["label"] and re.match(re.escape(req["label"]) + r"(?![\w.])", heading):
            return req
    return None


def _add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    return dt.date(d.year + y, m + 1, min(d.day, 28))


def tag_text(text, meta, body, chief):
    """Replace this agency's names with placeholders so the answer can be reused. Returns (text, counts)."""
    counts = {}

    def sub(pattern, repl, key, flags=0):
        nonlocal text
        text, n = re.subn(pattern, repl, text, flags=flags)
        if n:
            counts[key] = counts.get(key, 0) + n

    if meta["agency"]:
        sub(r"(?:\b[Tt]he\s+)?" + r"\s+".join(re.escape(w) for w in meta["agency"].split()), "{AGENCY}", "{AGENCY}", re.I)
    if meta["agency_short"]:
        sub(r"\b[Tt]he\s+" + re.escape(meta["agency_short"]) + r"\b(?!\s+of\b)", "{AGENCY_SHORT}", "{AGENCY_SHORT}")
    if body and body != "Board":
        sub(r"(?<![A-Za-z])" + re.escape(body) + r"(?![a-z])", "{GOVERNING_BODY}", "{GOVERNING_BODY}")
    if chief:
        sub(r"(?<![A-Za-z])" + re.escape(chief) + r"(?![a-z])", "{CHIEF_EXEC}", "{CHIEF_EXEC}")
    return text, counts


def harvest(final_markdown, rfp_text, data, outcome="pending", submitted=None, proposal_id=None, write=True):
    """File final answers into <data_dir>/harvested_answers.json. Returns a report dict."""
    if outcome not in OUTCOMES:
        raise ValueError("outcome must be one of %s" % ", ".join(OUTCOMES))
    rfp = parse_rfp(rfp_text)
    meta = rfp["meta"]
    body, chief = detect_terms(norm_ws(rfp_text), meta)
    deadline = submission_deadline(rfp)
    submitted = parse_iso(submitted or (deadline["date"] if deadline else None))
    proposal_id = proposal_id or "P-%d-H-%s" % (submitted.year, slug(F.place_of(meta["agency"])))
    review_by = _add_months(submitted, data.workplan.get("review_months_after_harvest", 18))
    others = [n for n in F.known_agencies(data) if n != meta["agency"]]
    probe_ctx = {"agency": "Probe Agency", "agency_short": "Agency", "governing_body": "governing body",
                 "chief_exec": "chief executive", "facts": data.facts}
    filed, skipped = [], []
    for sec in parse_final_markdown(final_markdown):
        req = _match_requirement(sec["heading"], rfp["requirements"])
        if req is None:
            skipped.append({"heading": sec["heading"], "reason": "heading does not match an RFP requirement number"})
            continue
        if req["qtype"] in NEVER_HARVEST:
            skipped.append({"heading": sec["heading"], "reason": NEVER_HARVEST[req["qtype"]]})
            continue
        raw = "\n".join(sec["lines"])
        if OPEN_MARK_RE.search(raw):
            skipped.append({"heading": sec["heading"], "reason": "section still has an open gap, person or blocking marker"})
            continue
        kept, dropped_list = [], 0
        for line in sec["lines"]:
            s = line.strip()
            if not s or s.startswith(">") or NOTE_LINE_RE.match(s):
                continue
            if s.startswith(("- ", "* ")) and req["qtype"] in LIST_QTYPES:
                dropped_list += 1
                continue
            kept.append(s)
        text = norm_ws(" ".join(kept))
        if len(text.split()) < 8:
            skipped.append({"heading": sec["heading"], "reason": "no narrative text to file"})
            continue
        tagged, counts = tag_text(text, meta, body, chief)
        notes = []
        if dropped_list:
            notes.append("%d list line(s) not filed: team, experience and reference lists are rebuilt from records" % dropped_list)
        probe = fill_placeholders(tagged, probe_ctx)
        left = F.find_wrong_agency(probe, "Probe Agency", others + [meta["agency"]],
                                   [o["city"] for o in data.facts.get("offices", [])])
        for f in left:
            notes.append("still names an agency after tagging: %s" % f["match"])
        _, spans = F.find_fact_conflicts(tagged, data.facts)
        if spans:
            notes.append("firm facts are typed in as text; replace them with fact placeholders before approval")
        rec = {"id": "A-H-%s-%s" % (proposal_id, slug(req["label"]) or "x"), "proposal_id": proposal_id,
               "proposal_agency": meta["agency"], "agency_type": meta["agency_type"], "practice": meta["practice"],
               "submitted": submitted.isoformat(), "outcome": outcome, "question_type": req["qtype"],
               "question_text": req["text"], "answer_text": tagged, "approved": False, "approver": "",
               "review_by": review_by.isoformat(), "tags": ["harvested"]}
        filed.append({"record": rec, "placeholders": counts, "notes": notes})
    path = os.path.join(data.data_dir, HARVEST_FILE)
    if write and filed:
        existing = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        new_ids = {x["record"]["id"] for x in filed}
        merged = [r for r in existing if r["id"] not in new_ids] + [x["record"] for x in filed]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=1, ensure_ascii=False)
            f.write("\n")
    return {"proposal_id": proposal_id, "agency": meta["agency"], "outcome": outcome,
            "submitted": submitted.isoformat(), "review_by": review_by.isoformat(), "file": path,
            "filed": filed, "skipped": skipped}


def set_outcome(data_dir, proposal_id, outcome):
    """Record won/lost/pending on harvested answers of one proposal. Returns the number updated."""
    if outcome not in OUTCOMES:
        raise ValueError("outcome must be one of %s" % ", ".join(OUTCOMES))
    path = os.path.join(data_dir, HARVEST_FILE)
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    n = 0
    for r in records:
        if r["proposal_id"] == proposal_id:
            r["outcome"] = outcome
            n += 1
    if n:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=1, ensure_ascii=False)
            f.write("\n")
    return n


def report_markdown(rep):
    out = ["# Harvest report: %s" % rep["agency"], "",
           "Proposal id: %s. Submitted: %s. Outcome: %s. Review by: %s." % (
               rep["proposal_id"], rep["submitted"], rep["outcome"], rep["review_by"]),
           "Filed answers are NOT approved. The practice lead must approve each one before it is reused in full.", "",
           "## Filed: %d" % len(rep["filed"]), ""]
    for x in rep["filed"]:
        r = x["record"]
        ph = ", ".join("%s x%d" % kv for kv in sorted(x["placeholders"].items())) or "none"
        out.append("- %s (%s). Placeholders set: %s." % (r["id"], r["question_type"], ph))
        for n in x["notes"]:
            out.append("  - %s" % n)
    out += ["", "## Not filed: %d" % len(rep["skipped"]), ""]
    for s in rep["skipped"]:
        out.append("- %s: %s" % (s["heading"], s["reason"]))
    return "\n".join(out) + "\n"
