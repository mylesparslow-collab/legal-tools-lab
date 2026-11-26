"""Guideline intake helper.

Reads a plain-text guideline document and proposes candidate rules using fixed
text patterns. Every candidate carries the quoted text, where it sits in the
document, status "proposed" and confidence "proposed, needs confirmation".

Nothing proposed here is enforced. A person reviews each candidate, corrects
the parameters, and sets status to "confirmed" (with confirmed_by and
confirmed_on) in the JSON. The engine skips every rule that is not confirmed.

Layouts the helper understands:
- page markers on their own line: [Page 3], Page 3, Sheet 1 of 2, - 3 -
- headings on their own line: "2.1 Rates", "Article II. Invoices", "Part B. ..."
- prose paragraphs, with or without a clause number ("2.04 ...", "(a) ...", "3) ...")
- a numbered item that opens with a short label ("1) Time. Quarter-hour ...")
- table rows: a short label, two or more spaces or a | character, then the
  requirement (and any further columns)

Numbers written as words ("four (4)", "one and one-half", "half the rate",
"six-minute units") are normalised before the patterns run. The quoted text is
always the original wording.

This is pattern matching. It misses rules that are worded in ways the patterns
do not cover, and it can misread a number. A person must read the document.
"""

import re

from . import guidelines as G

_PAGE = re.compile(r"^(?:\[Page\s+(\d+)\]|Page\s+(\d+)(?:\s+of\s+\d+)?|Sheet\s+(\d+)\s+of\s+\d+|-\s*(\d+)\s*-)$", re.I)
_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+\S|(?:Article|Section|Schedule|Part|Exhibit|Appendix)\s+\S|[A-Z]\.\s+[A-Z])", re.I)
_SEPARATOR = re.compile(r"^[\s\-=+|_.:]{4,}$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(\[])")
_CLAUSE = re.compile(r"^(\d+(?:\.\d+)+\.?|\d+[.)]|\(\w{1,4}\)|[A-Za-z][.)]|§+\s*[\d.]+)\s+(?=\S)")
_NUM = r"(\d+(?:\.\d+)?)"

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUMBER_WORD = r"(?:%s|hundred)" % "|".join(list(_UNITS) + list(_TENS))
_NUMBER_WORDS = re.compile(r"\b%s(?:(?:[\s-]+(?:and[\s-]+)?)%s)*\b" % (_NUMBER_WORD, _NUMBER_WORD))
_WORDS_BEFORE_PAREN = re.compile(
    r"\b(?:(?:%s|and|half|one-half|one-tenth|tenth|one-quarter|quarter)[\s-]+)+(?:dollars\s+)?\((\$?\d[\d,]*(?:\.\d+)?)\)" % _NUMBER_WORD
)


def _words_to_number(text):
    total, current = 0, 0
    for token in re.split(r"[\s-]+", text):
        if token in _UNITS:
            current += _UNITS[token]
        elif token in _TENS:
            current += _TENS[token]
        elif token == "hundred":
            current = max(current, 1) * 100
    return str(total + current)


def normalise(text):
    """Lower-case the text and rewrite numbers in words as digits, for matching only."""
    n = text.lower().replace("’", "'")
    n = re.sub(r"\bper cent\b|\bpercent\b", "%", n)
    n = re.sub(r"(?<=\d),(?=\d{3}\b)", "", n)
    n = re.sub(r"\bhrs?\b\.?", lambda m: "hours" if m.group(0).startswith("hrs") else "hour", n)
    n = _WORDS_BEFORE_PAREN.sub(lambda m: m.group(1), n)
    n = re.sub(r"\((\$?\d+(?:\.\d+)?)\)", r" \1 ", n)
    n = re.sub(r"\bone and (?:one-half|a half)\b", "1.5", n)
    n = re.sub(r"\b(?:one-tenth|one tenth|a tenth|tenths?)\b", "0.1", n)
    n = re.sub(r"\b(?:six|6)[- ]minute\b", "0.1 hour", n)
    n = re.sub(r"\bquarter[- ](?:of an )?hours?\b|\bquarter of an hour\b", "0.25 hour", n)
    n = re.sub(r"\bhalf (?:an |of an )?hour\b|\bhalf-hour\b|\bone-half hour\b", "0.5 hour", n)
    n = re.sub(r"\ban hour\b", "1 hour", n)
    n = re.sub(r"\b(?:one-)?half (?:of )?(?:the|their|his|her|its|normal|standard|usual|regular|ordinary|approved|hourly)\b", "50% of the", n)
    n = re.sub(r"\bhalf[- ]rate\b", "50% rate", n)
    n = _NUMBER_WORDS.sub(lambda m: _words_to_number(m.group(0)), n)
    return " ".join(n.split())


def split_sentences(paragraph):
    text = " ".join(paragraph.split())
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def _column_starts(raw):
    """Column start offsets from a ruled line such as "---  -------  ----", or None."""
    line = raw.rstrip()
    if "|" in line or "+" in line:
        return None
    groups = [m.start() for m in re.finditer(r"[-=_]{2,}", line)]
    if len(groups) >= 2 and not re.search(r"[^\s\-=_]", line):
        return groups
    return None


def _slice(raw, starts):
    line = raw.rstrip("\n")
    return [line[a:b].strip() for a, b in zip(starts, starts[1:] + [None])]


def _table_cells(raw, starts=None):
    """Return the cells of a table row, or None if the line is not one."""
    if raw[:1].isspace():
        return None
    line = raw.rstrip()
    if starts:
        cells = _slice(raw, starts)
        if not cells[0]:
            return None
        return cells if len([c for c in cells if c]) >= 2 else None
    if "|" in line:
        cells = [c.strip() for c in line.strip("|").split("|")]
    else:
        cells = [c.strip() for c in re.split(r"\s{2,}|\t+", line)]
    cells = [c for c in cells if c]
    if len(cells) < 2 or len(cells[0]) > 32:
        return None
    return cells


def _row_number(cell):
    return bool(re.fullmatch(r"[#(]?\d+[.)]?|[A-Za-z][.)]|\([A-Za-z]\)", cell))


def iter_units(text):
    """Yield (quote, source_ref, topic, heading, consequence) for every sentence or table row.

    consequence is the text of any further table column ("If not followed"); it is
    empty for prose.
    """
    page = 1
    heading = ""
    paragraph_no = 0
    buffer = []
    row = None  # pending table row: list of cell texts
    starts = None  # column offsets, when the table has a ruled line
    out = []

    def flush_row():
        nonlocal row
        if row is None:
            return
        cells, row = row, None
        if cells and _row_number(cells[0]) and len(cells) > 2:
            cells = cells[1:]
        label, body, rest = cells[0], cells[1] if len(cells) > 1 else "", " ".join(c for c in cells[2:] if c)
        if not body or (label.isupper() and body.isupper()):
            return  # a header row such as ITEM / REQUIREMENT
        where = "%s, page %d" % (label, page) if label else "page %d" % page
        out.append((" ".join(body.split()), where, label, heading, rest))

    def flush():
        nonlocal paragraph_no
        flush_row()
        if not buffer:
            return
        paragraph = " ".join(buffer)
        buffer.clear()
        if not re.search(r"[.!?][\"')\]]?$", paragraph.strip()):
            return  # a title, greeting or other line that is not a sentence
        clause = ""
        m = _CLAUSE.match(paragraph)
        if m:
            clause = m.group(1).rstrip(".)").lstrip("(")
            paragraph = paragraph[m.end():]
        paragraph_no += 1
        sentences = split_sentences(paragraph)
        topic = ""
        if len(sentences) > 1 and len(sentences[0].split()) <= 4 and clause:
            topic = sentences[0].rstrip(".:")
            sentences = sentences[1:]
        if clause and topic:
            ref = "item %s (%s), page %d" % (clause, topic, page)
        elif clause and heading:
            ref = "clause %s, %s, page %d" % (clause, heading, page)
        elif clause:
            ref = "clause %s, page %d" % (clause, page)
        elif heading:
            ref = "%s, page %d" % (heading, page)
        else:
            ref = "page %d, paragraph %d" % (page, paragraph_no)
        for sentence in sentences:
            out.append((sentence, ref, topic, heading, ""))

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        m = _PAGE.match(line)
        if m:
            flush()
            page = int(next(g for g in m.groups() if g))
            paragraph_no = 0
            starts = None
            continue
        ruled = _column_starts(raw)
        if ruled:
            row = None  # the row above a ruled line is the header
            buffer.clear()
            starts = ruled
            continue
        if _SEPARATOR.match(line):
            flush()
            continue
        if starts and raw[:1].isspace():
            if row is not None:
                for i, cell in enumerate(_slice(raw, starts)):
                    if cell and i < len(row):
                        row[i] = (row[i] + " " + cell).strip()
                continue
        cells = _table_cells(raw, starts)
        if cells is not None and not buffer:
            flush_row()
            row = list(cells)
            continue
        if row is not None and raw[:1].isspace():
            row[-1 if len(row) < 3 else 1] += " " + line  # a wrapped table cell
            continue
        if "|" in raw and row is not None:
            parts = [c.strip() for c in raw.strip().strip("|").split("|")]
            if parts and not parts[0]:
                for i, cell in enumerate(parts):
                    if cell and i < len(row):
                        row[i] = (row[i] + " " + cell).strip()
                continue
        if starts and not raw[:1].isspace():
            starts = None  # prose again
        if _HEADING.match(line) and len(line) < 90 and not line.endswith((".", "?", "!", ";", ",")):
            flush()
            heading = line
            continue
        flush_row()
        buffer.append(line)
    flush()
    return out


def iter_sentences(text):
    """Yield (quote, source_ref) for every sentence or table row in the document."""
    for quote, ref, _, _, _ in iter_units(text):
        yield quote, ref


def locate(text, quote):
    """Return the source_ref for text quoted exactly from the document, or None."""
    for sentence, ref in iter_sentences(text):
        if sentence == quote:
            return ref
    return None


def _quoted(sentence):
    return [q.strip() for q in re.findall(r'"([^"]+)"', sentence) if q.strip()]


_NEGATIVE = re.compile(
    r"not billable|non-?billable|not pay|not paid|not be paid|not be billed|not (?:be )?compensa|does not pay|do not pay|won't pay"
    r"|shall (?:not )?appear as a time charge|none of which|absorb|included in the (?:hourly )?rates|no charge|not charge|not (?:be )?reimburs"
)


def _ai(low):
    return bool(re.search(r"artificial intelligence|\bai\b|\bgen-?ai\b|generative|\bai-", low))


class Unit:
    def __init__(self, quote, topic, heading):
        self.quote = quote
        self.low = quote.lower().replace("’", "'")
        self.n = normalise(quote)
        self.topic = topic.lower()
        self.heading = heading.lower()

    def about(self, pattern):
        """The pattern appears in the text or in its label."""
        return bool(re.search(pattern, self.low) or re.search(pattern, self.topic))


# Each pattern takes a Unit and returns params or None.


def p_block_billing(u):
    cue = (
        r"block[- ]?bill|lump|cram|single task|1 task|1 activity|each task|separate(?:ly)? (?:entr|itemi|enter|record|stat|line)"
        r"|(?:combin|aggregat|bundl|group)\w* (?:\w+ ){0,2}(?:tasks|activities)|more than 1 (?:task|activity)"
        r"|(?:multiple|several|distinct|unrelated) (?:tasks|activities)|\d+ or more (?:things|tasks|activities|items)"
    )
    if not re.search(cue, u.n):
        return None
    m = re.search(r"(?:more than|exceeding|exceeds|over|longer than|in excess of|above) %s hours?" % _NUM, u.n)
    k = re.search(r"(\d+) or more (?:things|tasks|activities|items)", u.n)
    return {"max_tasks": int(k.group(1)) - 1 if k and int(k.group(1)) > 1 else 1, "min_hours": m.group(1) if m else 0}


def p_minimum_increment(u):
    if not re.search(r"increments?|\bunits?\b|0\.\d+ of (?:an|1) hour|\bin 0\.\d+ hours?\b", u.n):
        return None
    if not (re.search(r"time|hour|entr", u.n) or re.search(r"time|increment|unit", u.topic)):
        return None
    if re.search(r"conference|meeting|discussion|research|travel", u.n + " " + u.topic):
        return None
    for pattern in (
        r"(?:increments?|units?) of (0?\.\d+)",
        r"(0?\.\d+)[- ]hours? (?:increments?|units?)",
        r"(0?\.\d+) of (?:an|1) hour",
        r"(0?\.\d+)",
    ):
        m = re.search(pattern, u.n)
        if m:
            return {"increment": m.group(1) if m.group(1).startswith("0") else "0" + m.group(1)}
    return None


def p_rounding_pattern(u):
    if not re.search(r"round(?:ed|ing)? up|on the half hour|half hour or|whole hours?|round numbers|even hours|on the hour\b", u.low):
        return None
    pct = re.search(r"(\d+)\s?%", u.n)
    entries = re.search(r"(\d+) entries", u.n)
    block = "0.5" if "half" in u.low else "1.0"
    return {"block": block, "min_entries": int(entries.group(1)) if entries else 5, "threshold_percent": int(pct.group(1)) if pct else 80}


def p_daily_hour_cap(u):
    if re.search(r"does not impose|not impose|no ceiling|no limit|no cap\b|no maximum", u.low):
        return None
    m = re.search(r"(?:more than|over|exceed\w*|above|in excess of|beyond) %s hours?" % _NUM, u.n)
    if m and re.search(r"\bday\b|daily", u.n) and re.search(r"person|timekeeper|individual|attorney|lawyer|anyone|biller", u.n):
        return {"max_hours": m.group(1)}
    return None


def p_staffing_matter_limit(u):
    who = r"(?:timekeepers|billers|people|professionals)"
    m = re.search(
        r"(?:no|not) more than (\d+) %s|(\d+) %s (?:at most|maximum|or fewer)|limit(?:ed)? (?:to|of) (\d+) %s|max(?:imum)? (?:of )?(\d+) %s|up to (\d+) %s"
        % (who, who, who, who, who),
        u.n,
    )
    if not m or re.search(r"deposition|hearing|mediation|arbitration", u.n):
        return None
    return {"max_timekeepers": int(next(g for g in m.groups() if g))}


EVENTS = ("deposition", "hearing", "mediation", "arbitration", "trial")


def p_staffing_event_limit(u):
    events = sorted((e for e in EVENTS if re.search(r"\b%ss?\b" % e, u.low)), key=lambda e: u.low.index(e))
    if not events:
        return None
    who = r"(?:attorneys?|lawyers?|attendees?|timekeepers?)"
    m = re.search(r"(\d+) (?:of (?:your|our|counsel's) |outside )?%s" % who, u.n)
    if not m or not re.search(r"only|no more than|not more than|at most|max|paid|pay for|limit|on our dime", u.n):
        return None
    return {"max_attendees": int(m.group(1)), "events": events}


def p_unapproved_timekeeper(u):
    who = r"(?:people|persons?|personnel|timekeepers?|individuals?|those|staff|lawyers?|attorneys?|anyone)"
    if re.search(r"only (?:\w+ ){0,3}%s\b[^.]*\b(?:approved|cleared|authori[sz]ed|listed|named|identified)" % who, u.low):
        return {}
    if re.search(
        r"%s\b[^.]{0,40}\b(?:not (?:been )?(?:approved|cleared|listed|named|authori[sz]ed)|(?:does|do) not appear|not appearing|unlisted|unapproved)" % who,
        u.low,
    ):
        return {}
    return None


def p_rate_above_card(u):
    if not re.search(r"\brates?\b", u.low):
        return None
    if re.search(r"increase|notice|travel|transit|new rate", u.low) or u.topic.startswith(("travel", "rate change")):
        return None
    names = re.search(r"schedule|card|sheet|exhibit|engagement letter|agreed", u.low)
    limit = re.search(r"ceiling|above|exceed|higher|only at|maximum|\bcap\b", u.low)
    return {} if names and limit else None


def p_rate_increase_notice(u):
    if not u.about(r"rate (?:increase|change)s?|new rate|increases? (?:in|to) (?:\w+ )?rates?|raise \w+ rates"):
        return None
    m = re.search(r"(\d+) days", u.n)
    return {"notice_days": int(m.group(1)) if m else 0}


def p_non_billable_task(u):
    if _ai(u.low) or not (_NEGATIVE.search(u.low) or _NEGATIVE.search(u.topic)):
        return None
    if re.search(r"overhead|travel|transit|research", u.low + " " + u.topic):
        return None
    found = {}
    tests = [
        ("clerical", r"clerical|secretarial|administrative|file-?room|\bfiling\b|photocopying|calendaring|ministerial"),
        ("training", r"\btraining\b|onboarding|orientation|up to speed"),
        ("conflicts", r"conflicts?"),
        ("invoice_prep", r"(?:prepar\w+|fix\w+|correct\w+|review\w+)(?:,| or| and|\s)[^.;]{0,30}(?:bills?|invoices?)\b|preparation of (?:invoices|bills)|billing (?:questions|inquiries|disputes)"),
    ]
    for name, pattern in tests:
        words = re.findall(pattern, u.low)
        if words:
            extra = [w for w in words if w in ("secretarial", "file-room", "fileroom", "filing", "photocopying", "calendaring", "onboarding")]
            if name == "conflicts" and "clearance" in u.low:
                extra.append("conflicts clearance")
            found[name] = list(G.DEFAULT_CATEGORY_PHRASES[name]) + [w for w in dict.fromkeys(extra) if w not in G.DEFAULT_CATEGORY_PHRASES[name]]
    return {"categories": found} if found else None


def p_internal_conference_limit(u):
    cue = (
        r"intra-?office|in-?firm|inter-?office|internal (?:conference|meeting|discussion|call)s?|office conferences?"
        r"|among your (?:own )?team|within the firm|team meetings?"
    )
    if not u.about(cue):
        return None
    m = re.search(r"%s hours?" % _NUM, u.n)
    return {"max_hours_per_entry": m.group(1) if m else 0}


def p_research_approval(u):
    m = re.search(r"%s hours?" % _NUM, u.n)
    if not m or not u.about(r"research") or re.search(r"subscription|database", u.low):
        return None
    if re.search(r"approv|consent|clear it|without asking|permission|authori[sz]|\bok\b", u.low):
        return {"max_hours": m.group(1)}
    return None


def p_travel_time(u):
    cue = r"travel time|transit time|time spent (?:in transit|travell?ing)|travel (?:is|will be)|pay for travel|travell?ing time"
    if not (re.search(cue, u.low) or u.topic.startswith("travel")):
        return None
    if re.search(r"meals?|lodging|subsistence|hotel", u.low):
        return None
    needs = bool(re.search(r"unless|only (?:where|if|when)|prior (?:written )?(?:approval|consent)|approved .* in advance|pre-?approv", u.low))
    m = re.search(r"(\d+)\s?%", u.n)
    if m:
        percent = int(m.group(1))
    elif not needs and re.search(r"not (?:be )?(?:pay|paid|compens|billable|billed)|rather not pay|won't pay|not pay", u.low):
        percent = 0
    else:
        percent = 100
    return {"billable_percent": percent, "requires_approval": needs}


def _listed_items(low):
    m = re.search(r"(?::|such as|including|includes|like)\s+(.+)$", low)
    if not m:
        return []
    items = re.split(r",\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+", m.group(1).rstrip(". "))
    return [i.strip() for i in items if i.strip() and len(i.split()) <= 4]


def p_expense_overhead(u):
    if not u.about(r"overhead"):
        return None
    neg = r"not reimburs|not chargeable|don't pass|do not pass|not be charged|not billable|do not reimburse|not pay|no charge|not be passed"
    if not u.about(neg):
        return None
    phrases = list(G.DEFAULT_OVERHEAD_PHRASES)
    for item in _listed_items(u.low):
        item = re.sub(r"\s+(?:is|are) not .*$", "", item)
        if item and item not in phrases:
            phrases.append(item)
    return {"codes": list(G.DEFAULT_OVERHEAD_CODES), "phrases": phrases}


def p_expense_receipt_threshold(u):
    m = re.search(r"\$%s" % _NUM, u.n)
    if not m or not u.about(r"receipts?\b") or re.search(r"days of receipt|upon receipt", u.low):
        return None
    if re.search(r"or more|at least|or above|or over|and (?:over|above)", u.n):
        inclusive = True
    else:
        inclusive = not bool(re.search(r"\bover\b|exceed|in excess of|more than|above|greater than", u.n))
    return {"threshold": m.group(1), "inclusive": inclusive}


def p_expense_per_diem(u):
    if not re.search(r"meals?|food|subsistence|lodging|hotel", u.low):
        return None
    caps = {}
    for m in re.finditer(r"\$%s" % _NUM, u.n):
        after = u.n[m.end(): m.end() + 45]
        before = u.n[max(0, m.start() - 45): m.start()]
        next_amount = after.find("$")
        if next_amount >= 0:
            after = after[:next_amount]
        if re.search(r"per night|a night|nightly|for lodging|for (?:the )?hotel", after):
            kind = "lodging"
        elif re.search(r"per person|per day|a day|daily|for meals", after):
            kind = "meal"
        else:
            near = re.findall(r"hotels?|lodging|meals?|food|breakfast|lunch|dinner", before)
            kind = None if not near else ("lodging" if near[-1].startswith(("hotel", "lodging")) else "meal")
        if kind and kind not in caps:
            caps[kind] = m.group(1)
    return {"caps": caps} if caps else None


def p_expense_markup(u):
    cue = r"mark-?up|uplift|surcharge|handling fee|at (?:actual )?cost\b|amount actually paid|what you paid|actual cost"
    return {} if re.search(cue, u.low) else None


def p_vague_description(u):
    cue = (
        r"vague|generic|tells? (?:me|us) nothing|say what was done|what you actually did|non-descriptive|not enough"
        r"|insufficient(?:ly)? (?:detail|descri)|lack(?:ing|s)? detail|meaningless|uninformative"
    )
    if not re.search(cue, u.low) or _ai(u.low):
        return None
    quoted = [q.lower() for q in _quoted(u.quote)]
    always = [q for q in quoted if q.startswith("attention to") or re.match(r"work on (?:case|matter|file)$", q)]
    bare = [q for q in quoted if q not in always]
    return {
        "always_phrases": sorted(set(always + G.DEFAULT_ALWAYS_VAGUE)),
        "bare_phrases": sorted(set(bare + G.DEFAULT_BARE_VAGUE)),
        "min_words": 3,
    }


def p_required_codes(u):
    task = bool(re.search(r"task codes?", u.low))
    activity = bool(re.search(r"activity codes?", u.low))
    if not (task or activity):
        return None
    return {"require_task": task, "require_activity": activity, "require_expense": bool(re.search(r"expense codes?", u.low))}


def p_late_time(u):
    if re.search(r"notice|receipt|report|paid within", u.low):
        return None
    m = re.search(
        r"(\d+) days old|older than (\d+) days|more than (\d+) days (?:old|after)|within (\d+) days of the (?:work|service)"
        r"|(\d+) days (?:after|from|following) (?:the )?(?:work|service|date of service|date on which|date the)",
        u.n,
    )
    if m:
        return {"max_age_days": int(next(g for g in m.groups() if g))}
    return None


def p_budget_cap(u):
    if "phase" in u.low or "estimate" in u.low:
        return None
    cue = (
        r"not[- ]to[- ]exceed|maximum compensation|fee cap|budget cap|hard cap"
        r"|(?:total|aggregate)[^.]{0,80}(?:shall|may|will) (?:not|at no time) (?:exceed|surpass)"
    )
    return {} if re.search(cue, u.low) else None


def p_phase_cap(u):
    if "phase" in u.low and re.search(r"exceed|greater than|more than|surpass", u.low) and re.search(r"budget|portion|allot|assigned|amount", u.low):
        return {}
    return None


def p_duplicate_entries(u):
    return {} if re.search(r"duplicat|twice|more than once|repeated entry|same entry|double[- ]bill", u.low) else None


def _marker(u):
    quoted = _quoted(u.quote)
    for q in quoted:
        if re.search(r"ai", q, re.I):
            return q
    return quoted[0] if quoted else "[AI-assisted]"


def p_ai_disclosure_required(u):
    cue = r"must be (?:marked|disclosed|identified|flagged|labell?ed|tagged)|must disclose|put \"|mark(?:ed)? (?:it|them|with|each)|disclos|need to see it|flag (?:it|each|any)"
    if _ai(u.low) and re.search(cue, u.low):
        return {"disclosure_marker": _marker(u), "ai_terms": list(G.DEFAULT_AI_TERMS)}
    return None


def p_ai_nonpayable_task(u):
    if not (_ai(u.low) and re.search(r"will not pay|won't pay|not pay|not be billed|not compensat|no charge", u.low)):
        return None
    phrases = ["summarize", "summary of", "summaries of", "first-pass document review", "first pass document review"]
    if "digest" in u.low:
        phrases.append("digest")
    m = re.search(r"first[- ](\w+) (?:document )?review", u.low)
    if m and m.group(1) != "pass":
        phrases += ["first-%s document review" % m.group(1), "first %s document review" % m.group(1)]
    return {"disclosure_marker": "[AI-assisted]", "ai_terms": list(G.DEFAULT_AI_TERMS), "task_phrases": phrases}


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

PREFERENCE_NOTE = "The wording reads as a preference, not a requirement; a person may decide to leave it unconfirmed."
_REVIEW_CUE = re.compile(r"quer(?:y|ied)|question|ask why|audit|explain|heads-up|written reason")
_REJECT_CUE = re.compile(
    r"returned|disallow|not be paid|not paid|unpaid|reject|struck|get zero|waived|written off|won't pay|will not pay|send it back|sent back|refus"
)
_PREFERENCE_CUE = re.compile(r"\brather\b|\bprefer|preference|ideally|would like|we hope|not settled|haven't settled")


def _severity(rule_type, low):
    """A first guess at severity from the wording. A person should set it."""
    if _REVIEW_CUE.search(low):
        return "review"
    if _REJECT_CUE.search(low) and G.RULE_TYPES[rule_type]["severity"] == "reduce" and rule_type in ("block_billing", "vague_description"):
        return "reject"
    return G.RULE_TYPES[rule_type]["severity"]


def propose_rules(text, client_id="client", client_name="", document=""):
    """Return a guideline dict in which every rule is proposed, none confirmed."""
    rules = []
    counter = {}
    prefix = re.sub(r"[^A-Z0-9]", "", client_id.upper())[:6] or "CLIENT"
    for quote, ref, topic, heading, consequence in iter_units(text):
        unit = Unit(quote, topic, heading)
        for rule_type, pattern in PATTERNS:
            params = pattern(unit)
            if params is None:
                continue
            counter[rule_type] = counter.get(rule_type, 0) + 1
            note = "Proposed by pattern match. Check the parameters against the text before confirming."
            if _PREFERENCE_CUE.search(unit.low):
                note += " " + PREFERENCE_NOTE
            rules.append(
                {
                    "rule_id": "%s-P-%s-%02d" % (prefix, rule_type.upper().replace("_", "-"), counter[rule_type]),
                    "type": rule_type,
                    "status": "proposed",
                    "severity": _severity(rule_type, unit.low + " " + consequence.lower()),
                    "params": params,
                    "source_quote": quote,
                    "source_ref": ref,
                    "confidence": G.PROPOSED_CONFIDENCE,
                    "notes": note,
                }
            )
    # the client's own AI marker, if the document gives one, applies to both AI rules
    markers = [r["params"]["disclosure_marker"] for r in rules if r["type"] == "ai_disclosure_required"]
    if markers:
        for rule in rules:
            if rule["type"] == "ai_nonpayable_task":
                rule["params"]["disclosure_marker"] = markers[0]
    return {
        "client_id": client_id,
        "client_name": client_name or client_id,
        "document": document,
        "rules": rules,
    }


def compare_with_guideline(proposed, guideline):
    """Compare intake candidates with the rules on file, by (type, quoted text).

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
