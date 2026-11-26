"""Survey responses: loading, validation, tallies, and the survey-versus-log gap.

Responses carry role, practice and office but no person id. The gap is a
comparison of two group rates, never a match of individuals.
"""
import csv
import glob
import json
import os
from collections import Counter

from .metrics import week_label
from .suppress import cell, hidden, suppress_cells, suppress_counts

APPROVED = ("assistant_a", "assistant_b")
MULTI_SEPARATOR = "|"


def load_definition(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_responses(path):
    """Load responses from a CSV file, or from a folder of JSON files saved by survey.html."""
    if os.path.isdir(path):
        rows = []
        for name in sorted(glob.glob(os.path.join(path, "*.json"))):
            with open(name, encoding="utf-8") as f:
                data = json.load(f)
            rows.append(data.get("answers", data))
        return rows
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clean_responses(raw_rows, definition):
    """Validate answers against the survey definition.

    Returns (responses, quality). An answer that is not one of the listed
    options is removed and counted. A response missing a required answer is
    kept for the questions it did answer, and counted.
    """
    quality = {"responses_read": len(raw_rows), "invalid_answers_removed": 0,
               "responses_missing_required": 0, "responses_with_no_valid_answers": 0}
    out = []
    for raw in raw_rows:
        resp, missing = {}, False
        for q in definition["questions"]:
            qid, kind = q["id"], q["type"]
            value = raw.get(qid)
            if kind == "text":
                resp[qid] = (value or "").strip() if isinstance(value, str) else ""
                continue
            options = {str(o["id"]) for o in q["options"]}
            if kind == "multi":
                items = value if isinstance(value, list) else [v for v in str(value or "").split(MULTI_SEPARATOR)]
                items = [str(v).strip() for v in items if str(v).strip()]
                good = [v for v in items if v in options]
                quality["invalid_answers_removed"] += len(items) - len(good)
                resp[qid] = good
                if q.get("required") and not good:
                    missing = True
            else:
                v = "" if value is None else str(value).strip()
                if v and v not in options:
                    quality["invalid_answers_removed"] += 1
                    v = ""
                resp[qid] = v or None
                if q.get("required") and not v:
                    missing = True
        if missing:
            quality["responses_missing_required"] += 1
        if not any(v for k, v in resp.items()):
            quality["responses_with_no_valid_answers"] += 1
            continue
        out.append(resp)
    quality["responses_used"] = len(out)
    return out, quality


def claims_approved_7d(resp):
    return any(t in APPROVED for t in resp.get("used_7d") or [])


def claims_approved_30d(resp):
    return any(t in APPROVED for t in resp.get("used_30d") or [])


def tally(responses, definition, threshold):
    """Counts per option for every choice question, with small counts withheld."""
    out = {}
    for q in definition["questions"]:
        if q["type"] == "text" or q["id"] in ("role", "practice", "office"):
            continue
        counts = Counter()
        answered = 0
        for r in responses:
            v = r.get(q["id"])
            if q["type"] == "multi":
                if v:
                    answered += 1
                    counts.update(v)
            elif v:
                answered += 1
                counts[v] += 1
        ordered = {str(o["id"]): counts.get(str(o["id"]), 0) for o in q["options"]}
        out[q["id"]] = {
            "type": q["type"],
            "answered": answered,
            "labels": {str(o["id"]): o["label"] for o in q["options"]},
            "counts": suppress_counts(ordered, threshold, partition=(q["type"] != "multi")),
        }
    return out


def survey_section(analysis, responses, definition, quality, survey_monday):
    """Everything the report says about the survey, including the gap to the logs."""
    threshold = analysis.threshold
    lawyers = [r for r in responses if analysis.is_lawyer(r.get("role"))]
    week = [survey_monday]

    def gap_row(label, resp, where, population):
        claimed = cell(sum(1 for r in resp if claims_approved_7d(r)), len(resp))
        logged = analysis.weekly_active(week, population, None, where)
        roster = cell(len(resp), logged["d"])
        return {"group": label, "claimed": claimed, "logged": logged, "response": roster}

    def finish(rows):
        sizes = [cell(0, 0, min(r["claimed"]["people"], r["logged"]["people"])) for r in rows]
        marks = suppress_cells(sizes, threshold)
        for r, m in zip(rows, marks):
            if m["suppressed"]:
                r["claimed"] = r["logged"] = r["response"] = hidden(m["suppressed"])
                r["gap_points"] = None
            else:
                r["gap_points"] = _gap(r["claimed"], r["logged"])
        return rows

    practices = sorted({r["practice"] for r in analysis._select(week, "lawyers")})
    by_practice = finish([gap_row(p, [r for r in lawyers if r.get("practice") == p],
                                  lambda rec, p=p: rec["practice"] == p, "lawyers") for p in practices])
    roles = sorted({r["role"] for r in analysis._select(week, "all")})
    by_role = finish([gap_row(ro, [r for r in responses if r.get("role") == ro],
                              lambda rec, ro=ro: rec["role"] == ro, "all") for ro in roles])
    overall = gap_row("All lawyers", lawyers, None, "lawyers")
    overall["gap_points"] = _gap(overall["claimed"], overall["logged"])
    known_practices = {a.practice for p in analysis.roster.people.values() for a in p.assignments}
    quality = dict(quality)
    quality["responses_with_practice_not_on_roster"] = sum(
        1 for r in responses if r.get("practice") and r["practice"] not in known_practices)
    return {
        "survey_week": week_label(survey_monday),
        "responses": len(responses),
        "lawyer_responses": len(lawyers),
        "claimed_30d_lawyers": cell(sum(1 for r in lawyers if claims_approved_30d(r)), len(lawyers)),
        "other_tool_7d": cell(sum(1 for r in responses if "other_tool" in (r.get("used_7d") or [])), len(responses)),
        "free_text_comments": sum(1 for r in responses if r.get("comments")),
        "overall": overall,
        "by_practice": by_practice,
        "by_role": by_role,
        "tallies": tally(responses, definition, threshold),
        "quality": quality,
        "note": "Group comparison only. Respondents are not matched to log records. "
                "Free-text comments are counted, not reproduced.",
    }


def _gap(claimed, logged):
    if claimed["rate"] is None or logged["rate"] is None:
        return None
    return round(100 * (claimed["rate"] - logged["rate"]), 1)
