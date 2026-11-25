"""Guideline intake helper.

Reads a plain-text guideline document and proposes candidate rules using fixed
text patterns. Every candidate carries the quoted sentence, its section and
page, status "proposed" and confidence "proposed, needs confirmation".

Nothing proposed here is enforced. A person reviews each candidate, corrects
the parameters, and sets status to "confirmed" (with confirmed_by and
confirmed_on) in the JSON. The engine skips every rule that is not confirmed.

Document conventions the helper understands:
- a page marker on its own line: [Page 3]
- a heading on its own line that starts with a number ("2.1 Rates"), or with
  Article, Section, Schedule or Part
- sentences end with a full stop, question mark or exclamation mark
"""

import re

from . import guidelines as G

_PAGE = re.compile(r"^\[Page\s+(\d+)\]$", re.I)
_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+\S|(?:Article|Section|Schedule|Part)\s+\S)", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(\[])")
_NUM = r"(\d+(?:\.\d+)?)"
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def split_sentences(paragraph):
    text = " ".join(paragraph.split())
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def iter_sentences(text):
    """Yield (sentence, source_ref) for every sentence in the document."""
    page = 1
    heading = ""
    paragraph_no = 0
    buffer = []

    def flush():
        nonlocal paragraph_no
        if not buffer:
            return []
        paragraph = " ".join(buffer)
        buffer.clear()
        if not re.search(r"[.!?][\"')\]]?$", paragraph.strip()):
            return []  # a title or other line that is not a sentence
        paragraph_no += 1
        if heading:
            ref = "%s, page %d" % (heading, page)
        else:
            ref = "page %d, paragraph %d" % (page, paragraph_no)
        return [(s, ref) for s in split_sentences(paragraph)]

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            for item in flush():
                yield item
            continue
        match = _PAGE.match(line)
        if match:
            for item in flush():
                yield item
            page = int(match.group(1))
            paragraph_no = 0
            continue
        if _HEADING.match(line) and len(line) < 90 and not line.endswith((".", "?", "!")):
            for item in flush():
                yield item
            heading = line
            continue
        buffer.append(line)
    for item in flush():
        yield item


def locate(text, quote):
    """Return the source_ref for a sentence quoted exactly from the document, or None."""
    for sentence, ref in iter_sentences(text):
        if sentence == quote:
            return ref
    return None


def _int(text):
    text = text.lower()
    if text in _WORD_NUMBERS:
        return _WORD_NUMBERS[text]
    return int(text)


def _quoted(sentence):
    return [q.strip().lower() for q in re.findall(r'"([^"]+)"', sentence) if q.strip()]


def _negative(low):
    return bool(re.search(r"not pay|not billable|not be billed|not be compensated|does not pay|do not pay|not be paid|included in the hourly rates", low))


def _ai(low):
    return bool(re.search(r"artificial intelligence|\bai\b|ai-assisted", low))


# Each pattern function takes (sentence, lowercase sentence) and returns params or None.


def p_block_billing(s, low):
    if not re.search(r"block[- ]bill|lump several tasks|lump multiple tasks|combines two or more tasks|each task must be entered separately", low):
        return None
    m = re.search(r"(?:more than|exceeding|over) %s hours?" % _NUM, low)
    return {"max_tasks": 1, "min_hours": m.group(1) if m else 0}


def p_minimum_increment(s, low):
    m = re.search(r"increments of %s|%s hour increments" % (_NUM, _NUM), low)
    if m:
        return {"increment": m.group(1) or m.group(2)}
    if re.search(r"one-tenth of an hour|tenths of an hour|a tenth of an hour", low):
        return {"increment": "0.1"}
    return None


def p_rounding_pattern(s, low):
    if re.search(r"round(?:ed|ing)? up", low):
        return {"block": "0.5", "min_entries": 5, "threshold_percent": 80}
    return None


def p_daily_hour_cap(s, low):
    m = re.search(r"more than %s hours" % _NUM, low)
    if m and re.search(r"\bday\b", low) and re.search(r"one timekeeper|one person|single timekeeper", low):
        return {"max_hours": m.group(1)}
    return None


def p_staffing_matter_limit(s, low):
    m = re.search(r"no more than (\d+|one|two|three|four|five) timekeepers", low)
    return {"max_timekeepers": _int(m.group(1))} if m else None


def p_staffing_event_limit(s, low):
    events = [e for e in ("deposition", "hearing", "mediation") if e in low]
    m = re.search(r"(?:only|no more than) (\d+|one|two|three) (?:of your )?(?:attorneys?|lawyers?)", low)
    if events and m:
        return {"max_attendees": _int(m.group(1)), "events": events}
    return None


def p_unapproved_timekeeper(s, low):
    if re.search(r"only timekeepers approved|personnel not listed|timekeepers? (?:who (?:has|have) )?not (?:been )?approved", low):
        return {}
    return None


def p_rate_above_card(s, low):
    names = re.search(r"rate schedule|rate card|rates listed|rates in your engagement", low)
    limit = re.search(r"above|exceed|higher|only at", low)
    if names and limit and "rate increase" not in low:
        return {}
    return None


def p_rate_increase_notice(s, low):
    if "rate increase" not in low:
        return None
    m = re.search(r"(\d+) days", low)
    return {"notice_days": int(m.group(1)) if m else 0}


def p_non_billable_task(s, low):
    if not _negative(low) or _ai(low):
        return None
    found = {}
    tests = [
        ("clerical", r"clerical|secretarial|administrative"),
        ("training", r"\btraining\b"),
        ("conflicts", r"conflicts? checks?"),
        ("invoice_prep", r"preparation of invoices|invoice preparation|preparing, reviewing or correcting invoices"),
    ]
    for name, pattern in tests:
        if re.search(pattern, low):
            found[name] = list(G.DEFAULT_CATEGORY_PHRASES[name])
    return {"categories": found} if found else None


def p_internal_conference_limit(s, low):
    if not re.search(r"intra-office conference|internal conference|office conference", low):
        return None
    m = re.search(r"%s hours?" % _NUM, low)
    return {"max_hours_per_entry": m.group(1) if m else 0}


def p_research_approval(s, low):
    m = re.search(r"%s hours" % _NUM, low)
    if "research" in low and "approval" in low and m:
        return {"max_hours": m.group(1)}
    return None


def p_travel_time(s, low):
    if "travel time" not in low:
        return None
    m = re.search(r"(\d+)\s?(?:%|percent)", low)
    needs = bool(re.search(r"unless .*approved|prior approval|approved .* in advance", low))
    return {"billable_percent": int(m.group(1)) if m else 100, "requires_approval": needs}


def p_expense_overhead(s, low):
    if "overhead" in low and re.search(r"not reimbursable|not chargeable|do not reimburse|not be reimbursed", low):
        return {"codes": list(G.DEFAULT_OVERHEAD_CODES), "phrases": list(G.DEFAULT_OVERHEAD_PHRASES)}
    return None


def p_expense_receipt_threshold(s, low):
    m = re.search(r"\$%s" % _NUM, low)
    if "receipt" in low and m:
        return {"threshold": m.group(1), "inclusive": not bool(re.search(r"\bover \$", low))}
    return None


def p_expense_per_diem(s, low):
    caps = {}
    m = re.search(r"meals?[^$]*\$%s" % _NUM, low)
    if m:
        caps["meal"] = m.group(1)
    m = re.search(r"lodging[^$]*\$%s" % _NUM, low)
    if m:
        caps["lodging"] = m.group(1)
    return {"caps": caps} if caps else None


def p_expense_markup(s, low):
    return {} if re.search(r"mark-?up", low) else None


def p_vague_description(s, low):
    if not re.search(r"vague|too generic|not enough|non-descriptive", low):
        return None
    quoted = _quoted(s)
    always = [q for q in quoted if q.startswith("attention to") or q.startswith("work on") and len(q.split()) > 3]
    bare = [q for q in quoted if q not in always]
    return {
        "always_phrases": sorted(set(always + G.DEFAULT_ALWAYS_VAGUE)),
        "bare_phrases": sorted(set(bare + G.DEFAULT_BARE_VAGUE)),
        "min_words": 3,
    }


def p_required_codes(s, low):
    task = "task code" in low
    activity = "activity code" in low
    if not (task or activity):
        return None
    return {"require_task": task, "require_activity": activity, "require_expense": "expense code" in low}


def p_late_time(s, low):
    m = re.search(r"more than (\d+) days (?:old|after)|within (\d+) days of the work", low)
    if m:
        return {"max_age_days": int(m.group(1) or m.group(2))}
    return None


def p_budget_cap(s, low):
    return {} if re.search(r"not[- ]to[- ]exceed", low) else None


def p_phase_cap(s, low):
    return {} if "phase" in low and "budget" in low and "exceed" in low else None


def p_duplicate_entries(s, low):
    return {} if re.search(r"duplicate|charged twice|appears twice|pay twice", low) else None


def p_ai_disclosure_required(s, low):
    if _ai(low) and re.search(r"must be marked|must be disclosed|must disclose|must be identified", low):
        quoted = re.findall(r'"([^"]+)"', s)
        return {"disclosure_marker": quoted[0] if quoted else "[AI-assisted]", "ai_terms": list(G.DEFAULT_AI_TERMS)}
    return None


def p_ai_nonpayable_task(s, low):
    if _ai(low) and re.search(r"will not pay|not pay for", low):
        return {
            "disclosure_marker": "[AI-assisted]",
            "ai_terms": list(G.DEFAULT_AI_TERMS),
            "task_phrases": ["summarize", "summary of", "summaries of", "first-pass document review"],
        }
    return None


PATTERNS = [
    ("block_billing", p_block_billing),
    ("minimum_increment", p_minimum_increment),
    ("rounding_pattern", p_rounding_pattern),
    ("daily_hour_cap", p_daily_hour_cap),
    ("staffing_matter_limit", p_staffing_matter_limit),
    ("staffing_event_limit", p_staffing_event_limit),
    ("unapproved_timekeeper", p_unapproved_timekeeper),
    ("rate_above_card", p_rate_above_card),
    ("rate_increase_notice", p_rate_increase_notice),
    ("non_billable_task", p_non_billable_task),
    ("internal_conference_limit", p_internal_conference_limit),
    ("research_approval", p_research_approval),
    ("travel_time", p_travel_time),
    ("expense_overhead", p_expense_overhead),
    ("expense_receipt_threshold", p_expense_receipt_threshold),
    ("expense_per_diem", p_expense_per_diem),
    ("expense_markup", p_expense_markup),
    ("vague_description", p_vague_description),
    ("required_codes", p_required_codes),
    ("late_time", p_late_time),
    ("budget_cap", p_budget_cap),
    ("phase_cap", p_phase_cap),
    ("duplicate_entries", p_duplicate_entries),
    ("ai_disclosure_required", p_ai_disclosure_required),
    ("ai_nonpayable_task", p_ai_nonpayable_task),
]


def propose_rules(text, client_id="client", client_name="", document=""):
    """Return a guideline dict in which every rule is proposed, none confirmed."""
    rules = []
    counter = {}
    prefix = re.sub(r"[^A-Z0-9]", "", client_id.upper())[:6] or "CLIENT"
    for sentence, ref in iter_sentences(text):
        low = sentence.lower()
        for rule_type, pattern in PATTERNS:
            params = pattern(sentence, low)
            if params is None:
                continue
            counter[rule_type] = counter.get(rule_type, 0) + 1
            rules.append(
                {
                    "rule_id": "%s-P-%s-%02d" % (prefix, rule_type.upper().replace("_", "-"), counter[rule_type]),
                    "type": rule_type,
                    "status": "proposed",
                    "severity": G.RULE_TYPES[rule_type]["severity"],
                    "params": params,
                    "source_quote": sentence,
                    "source_ref": ref,
                    "confidence": G.PROPOSED_CONFIDENCE,
                    "notes": "Proposed by pattern match. Check the parameters against the sentence before confirming.",
                }
            )
    return {
        "client_id": client_id,
        "client_name": client_name or client_id,
        "document": document,
        "rules": rules,
    }


def compare_with_guideline(proposed, guideline):
    """Compare intake candidates with the rules on file, by (type, quoted sentence).

    Used in the demo to report honestly what the patterns catch and miss.
    """
    candidates = {(r["type"], r["source_quote"]) for r in proposed["rules"]}
    on_file = {(r.type, r.source_quote): r.rule_id for r in guideline.rules}
    matched = sorted(on_file[k] for k in on_file if k in candidates)
    missed = sorted(on_file[k] for k in on_file if k not in candidates)
    extra = sorted("%s: %s" % k for k in candidates if k not in on_file)
    return {
        "client_id": guideline.client_id,
        "client_name": guideline.client_name,
        "rules_on_file": len(on_file),
        "proposed": len(proposed["rules"]),
        "matched": len(matched),
        "missed": missed,
        "extra": len(extra),
        "extra_candidates": extra,
    }
