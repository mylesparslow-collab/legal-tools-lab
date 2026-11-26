"""Deterministic RFP parser.

Input is the plain text of a request for proposals. Output is a plain dict
(JSON-serialisable). Requirements are whatever the RFP text says; nothing here
knows any procurement rule. Every extracted item keeps the line it came from.
Items the parser is unsure about get confidence "check" and a reason.

How it reads a document:

1. Page headers and a table of contents are set aside. Addenda are split off,
   wherever they sit in the file.
2. The body is cut into sections by headings (numbered, lettered, "PART ONE"
   over a title line, "ATTACHMENT B" over a title line, numbered paragraphs
   with a run-in title, short question headings). Each heading is classified
   by its words.
3. Each kind of section is read for its own items: schedule rows or dates in
   sentences, labelled or unnumbered requirements, forms, weights in a table or
   in running prose, qualifications, insurance, submission mechanics.
4. Where a kind of item was not found in its own section, the whole body is
   searched for it and anything found is marked "check".
5. Addenda are applied in number order. Values as issued are kept.
"""
import re

from .util import (COUNT, NUMWORD, TIME_24_RE, TIME_RE, count_value, find_dates, find_time, norm_ws,
                   sentences, word_to_int)

# ---------------------------------------------------------------- sections

SECTION_KINDS = [
    ("minquals", r"minimum (qualif|requirement)|who (may|can|should|is eligible to) (propose|apply|respond|submit)|"
                 r"eligib|required qualifications|qualifications required"),
    ("content", r"proposal must contain|what (must|should|does|do|will) .{0,40}(contain|include|cover|address)|"
                r"questionnaire"),
    ("forms", r"\bforms\b|certifications|attachments\b|paperwork|required documents|documents to be (returned|signed)"),
    ("evaluation", r"evaluat|selection|scoring|scored|how .{0,40}will (choose|select|decide|pick)|"
                   r"how we will choose|criteria|judged"),
    ("insurance", r"insurance"),
    ("schedule", r"schedule|timeline|timetable|key dates|important dates|calendar|deadlines|"
                 r"when (are|is|must|do|will)"),
    ("content", r"proposal (content|requirements|sections)|required proposal|what to (submit|send|include)|"
                r"contents? of (the )?proposal|response (content|requirements)|"
                r"information (required|to be (provided|submitted))|checklist|^contents?$"),
    ("submission", r"submission|submittal|how to (submit|send)|how (do|should|must) .{0,30}(submit|send|deliver)|"
                   r"delivery|\bformat\b|instructions|sending in"),
    ("scope", r"scope|services requested|services required"),
    ("parties", r"officials|board of (directors|trustees)|city council|contacts"),
    ("intro", r"introduction|background|overview|purpose|general information"),
]

_NUMWORDS_CAPS = (r"ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|"
                  r"SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY")
ADDENDUM_HEAD_RE = re.compile(r"^\s*ADDENDUM\s+(?:NO\.?\s*|NUMBER\s*|#\s*)?(\d+)\b(.*)$")
TOP_NUM_RE = re.compile(r"^\s*(\d{1,2})(?:\.0)?\.?\s+([A-Z][A-Z0-9 ,&/\-']+)$")
TOP_WORD_RE = re.compile(r"^\s*(SECTION|PART|ARTICLE|Section|Part|Article)\s+([IVXLC]+|[A-Z]|\d+)\s*[-–:.]\s*"
                         r"([A-Z][^.;]{2,70})$")
HEAD_ALONE_RE = re.compile(r"^\s*(SECTION|PART|ARTICLE|EXHIBIT|ATTACHMENT|APPENDIX|SCHEDULE|ANNEX)\s+"
                           r"(" + _NUMWORDS_CAPS + r"|[IVXLC]+|[A-Z]|\d+)\s*$")
CAPS_WORD_HEAD_RE = re.compile(r"^\s*(EXHIBIT|ATTACHMENT|APPENDIX|SCHEDULE|ANNEX)\s+([IVXLC]+|[A-Z]|\d+)\s*[-–:.]\s*"
                               r"([A-Z][A-Z0-9 ,&/\-']{2,70})$")
LETTER_HEAD_RE = re.compile(r"^\s*([A-Z])\.\s+([A-Z][A-Z0-9 ,&/\-']{3,})$")
CAPS_RE = re.compile(r"^[A-Z][A-Z ,&/\-']{3,}$")
SUB_RE = re.compile(r"^\s*([A-Z]\.\d+|\d+\.\d+)\s+([A-Z][^.:;?]{2,60})$")
RUNIN_RE = re.compile(r"^(\d{1,2})\.\s+([A-Z][^.?!:;]{1,60})\.\s+(\S.*)$")
NUM_TITLE_RE = re.compile(r"^\s*(\d{1,2})\.?\s+([A-Z][A-Za-z ,&/\-']{2,60})$")
SEQ_TITLE_RE = re.compile(r"^\s*([A-Z]|\d{1,2})\.?\s+([A-Z][A-Za-z ,&/\-']{2,60})$")
PAGE_HEADER_RE = re.compile(r"^\s*(?:\S.{0,70}\s{2,})?(?:Page\s+\d+(?:\s+of\s+\d+)?|-\s*\d+\s*-)\s*$", re.I)
TOC_HEAD_RE = re.compile(r"^\s*(?:TABLE OF )?CONTENTS\s*$", re.I)
TOC_LINE_RE = re.compile(r"(?:\.{3,}|\s{3,})\s*\d{1,3}\s*$")

_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}

LABEL_RE = re.compile(
    r"^(?P<label>"
    r"[A-Z]\.\d+(?:\.\d+)*\.?"
    r"|\d+(?:\.\d+)+\.?"
    r"|#\s?\d+[.):]?"
    r"|[A-Z]{1,2}-?\d{1,2}[.):]"
    r"|[A-Z]{1,2}-?\d{1,2}(?=\s{2,})"
    r"|Tab\s+\d+\s*[-–:]"
    r"|Item\s+\d+[.:]"
    r"|\((?:[a-z0-9]{1,3}|[ivxl]{1,6})\)"
    r"|[A-Za-z]\."
    r"|\d{1,2}[.)]"
    r")\s+(?P<rest>\S.*)$")
TICK_RE = re.compile(r"^(?:\[[ xX_]?\]|[\u2610\u25a1])\s*(?:(?P<label>[A-Z]{1,2}-?\d{1,2}|#\s?\d+|\d{1,2})[.):]?\s+)?(?P<rest>\S.*)$")
BULLET_RE = re.compile(r"^[-*•]\s+(?P<rest>\S.*)$")


def classify_heading(title):
    low = title.lower()
    for kind, pat in SECTION_KINDS:
        if re.search(pat, low):
            return kind
    return None


def _clean_lines(all_lines):
    """Blank out page headers and the table of contents. Line numbers are kept."""
    out, in_toc = [], False
    for n, raw in all_lines:
        if PAGE_HEADER_RE.match(raw) and raw.strip():
            out.append((n, ""))
            in_toc = False
            continue
        if TOC_HEAD_RE.match(raw):
            in_toc = True
            out.append((n, ""))
            continue
        if in_toc:
            if not raw.strip() or TOC_LINE_RE.search(raw):
                out.append((n, ""))
                continue
            in_toc = False
        out.append((n, raw))
    return out


def _level1(lines, idx):
    """A heading on this line that starts a top-level section: (label, title, rest) or None."""
    n, raw = lines[idx]
    s = raw.strip()
    if not s:
        return None
    prev_blank = idx == 0 or not lines[idx - 1][1].strip()
    next_blank = idx + 1 >= len(lines) or not lines[idx + 1][1].strip()
    m = TOP_NUM_RE.match(raw)
    if m:
        return (m.group(1), m.group(2).strip(), None)
    m = TOP_WORD_RE.match(raw)
    if m:
        return ("%s %s" % (m.group(1), m.group(2)), m.group(3).strip(), None)
    m = CAPS_WORD_HEAD_RE.match(raw)
    if m:
        return ("%s %s" % (m.group(1), m.group(2)), m.group(3).strip(), None)
    m = HEAD_ALONE_RE.match(raw)
    if m and prev_blank:
        return ("%s %s" % (m.group(1), m.group(2)), "", None)
    m = LETTER_HEAD_RE.match(raw)
    if m and prev_blank:
        return (m.group(1), m.group(2).strip(), None)
    if CAPS_RE.match(s) and len(s.split()) <= 8 and prev_blank:
        return ("", s, "caps")
    if prev_blank and not re.search(r"\d", s) and len(s.split()) <= 12:
        q = re.sub(r"^Q\s*[.:)]\s*", "", s)
        if q.endswith("?") and classify_heading(q):
            return ("", q, None)
        if next_blank and not s.endswith((".", ",", ";", ":")) and s[0].isupper() and len(s.split()) <= 8 \
                and all(w[0].isupper() or w.lower() in ("of", "and", "the", "to", "for", "in", "a", "this", "be",
                                                        "with", "we", "will", "is", "are")
                        for w in s.split()) and classify_heading(s):
            return ("", s, None)
    m = NUM_TITLE_RE.match(raw)
    if m and prev_blank and next_blank and len(m.group(2).split()) <= 8 and classify_heading(m.group(2)):
        return (m.group(1), m.group(2).strip(), None)
    return None


def _question_line(lines, idx):
    s = lines[idx][1].strip()
    prev_blank = idx == 0 or not lines[idx - 1][1].strip()
    if not (prev_blank and s.endswith("?") and len(s.split()) <= 12 and not re.search(r"\d", s)):
        return None
    if LABEL_RE.match(s) or BULLET_RE.match(s) or TICK_RE.match(s):
        return None
    return re.sub(r"^Q\s*[.:)]\s*", "", s)


def _child_label(lines, idx, label):
    """True when the next labelled line is numbered under this label ("4.2" then "4.2.1")."""
    for _, raw in lines[idx + 1:idx + 6]:
        m = LABEL_RE.match(raw.strip())
        if m:
            return m.group("label").startswith(label + ".")
    return False


def _segment(lines):
    """lines: list of (lineno, text). Returns sections with their own lines."""
    sections = [{"kind": "preamble", "title": "", "label": "", "line": 1, "lines": [], "level": 0}]
    qa_style = sum(1 for i in range(len(lines))
                   if _question_line(lines, i) and classify_heading(_question_line(lines, i))) >= 3
    runin_next = 1        # next expected number of a run-in numbered heading, or None once switched off
    last_head_idx = None
    for idx, (n, raw) in enumerate(lines):
        s = raw.strip()
        if last_head_idx == idx - 1 and not sections[-1]["lines"] and CAPS_RE.match(s) and len(s.split()) <= 10:
            # second line of a two-line heading ("PART ONE" over its title)
            sec = sections[-1]
            sec["title"] = (sec["title"] + " " + s).strip() if sec["title"] else s
            sec["kind"] = classify_heading(sec["title"]) or "other"
            last_head_idx = idx
            continue
        head = _level1(lines, idx)
        if head and head[2] == "caps" and not (classify_heading(s) or len(sections) > 1):
            head = None
        if not head and qa_style and _question_line(lines, idx):
            head = ("", _question_line(lines, idx), None)
        if not head:
            m = SEQ_TITLE_RE.match(raw)
            prev_lab = next((x["label"] for x in reversed(sections) if x["level"] == 1), "")
            if m and (idx == 0 or not lines[idx - 1][1].strip()) and \
                    (idx + 1 >= len(lines) or not lines[idx + 1][1].strip()) and len(m.group(2).split()) <= 8 and (
                    (m.group(1).isdigit() and prev_lab.isdigit() and int(m.group(1)) == int(prev_lab) + 1) or
                    (len(m.group(1)) == 1 and len(prev_lab) == 1 and m.group(1).isalpha() and prev_lab.isalpha()
                     and ord(m.group(1)) == ord(prev_lab) + 1)):
                head = (m.group(1), m.group(2).strip(), None)
        if head:
            kind = classify_heading(head[1]) or "other"
            sections.append({"kind": kind, "title": head[1], "label": head[0], "line": n,
                             "lines": [], "level": 1})
            last_head_idx = idx
            if runin_next is not None and runin_next > 1:
                runin_next = None
            continue
        m = RUNIN_RE.match(raw)
        if m and runin_next is not None and int(m.group(1)) == runin_next and len(m.group(2).split()) <= 8 \
                and (runin_next > 1 or len(sections) == 1):
            title = m.group(2).strip()
            sections.append({"kind": classify_heading(title) or "other", "title": title, "label": m.group(1),
                             "line": n, "lines": [(n, m.group(3))], "level": 1, "runin": True})
            runin_next += 1
            continue
        m = SUB_RE.match(raw)
        if m and len(m.group(2).split()) <= 6:
            kind = classify_heading(m.group(2))
            if not kind and _child_label(lines, idx, m.group(1)) and classify_question(m.group(2), "") == "other":
                kind = "other"        # a sub-heading over its own numbered items, e.g. "4.1 General"
            if kind:
                sections.append({"kind": kind, "title": m.group(2).strip(), "label": m.group(1),
                                 "line": n, "lines": [], "level": 2})
                continue
        sections[-1]["lines"].append((n, raw))
    return sections


def _label_style(label_raw):
    """(style, value) for labels that run in a sequence; value None when it cannot be told."""
    s = label_raw.strip()
    m = re.fullmatch(r"\(([a-z0-9]+)\)", s)
    if m:
        inner = m.group(1)
        if inner.isdigit():
            return "paren_num", [int(inner)]
        vals = []
        if len(inner) == 1:
            vals.append(ord(inner) - 96)
        if re.fullmatch(r"[ivxl]+", inner):
            vals.append(_roman(inner))
        return "paren_alpha", vals
    m = re.fullmatch(r"(\d{1,2})[.)]", s)
    if m:
        return "num", [int(m.group(1))]
    m = re.fullmatch(r"([a-z])\.", s)
    if m:
        return "lower", [ord(m.group(1)) - 96]
    m = re.fullmatch(r"([A-Z])\.", s)
    if m:
        return "upper", [ord(m.group(1)) - 64]
    return "other", None


def _roman(s):
    total, prev = 0, 0
    for ch in reversed(s.lower()):
        v = _ROMAN.get(ch, 0)
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _blocks(lines):
    """Group section lines into blocks: a labelled item, a bullet, or a paragraph."""
    out, cur = [], None
    last_vals = {}

    def close():
        nonlocal cur
        if cur:
            cur["text"] = norm_ws(" ".join(t for _, t in cur["parts"]))
            out.append(cur)
        cur = None

    for n, raw in lines:
        s = raw.strip()
        if not s or re.fullmatch(r"[=\-_*]{5,}", s):
            close()
            continue
        indent = len(raw) - len(raw.lstrip())
        m = LABEL_RE.match(s)
        t = TICK_RE.match(s)
        b = BULLET_RE.match(s)
        if t and t.group("label"):
            close()
            cur = {"label": norm_ws(t.group("label")).replace("# ", "#"), "bullet": False, "line": n,
                   "raw": [(n, raw)], "parts": [(n, t.group("rest"))], "style": "other", "indent": indent,
                   "textcol": indent + len(s) - len(t.group("rest"))}
            continue
        if t:
            close()
            cur = {"label": None, "bullet": True, "line": n, "raw": [(n, raw)], "parts": [(n, t.group("rest"))],
                   "style": None, "indent": indent, "textcol": indent + len(s) - len(t.group("rest"))}
            continue
        if m:
            style, vals = _label_style(m.group("label"))
            if vals is not None and cur is not None:
                seq_ok = any(v == 1 or v == last_vals.get(style, -9) + 1 for v in vals)
                if not seq_ok and (indent == cur.get("textcol") or cur["label"] is None):
                    m = None      # a wrapped line that only looks like a label, e.g. "(12) or more years"
            if m and vals is not None:
                nxt = [v for v in vals if v == last_vals.get(style, -9) + 1] or vals
                last_vals[style] = nxt[0]
        if m:
            close()
            label = norm_ws(m.group("label").rstrip(".)-–: "))
            if label.startswith("("):
                label = label.strip("()")
            label = label.replace("# ", "#")
            cur = {"label": label, "bullet": False, "line": n, "raw": [(n, raw)],
                   "parts": [(n, m.group("rest"))], "style": style, "indent": indent,
                   "textcol": indent + len(s) - len(m.group("rest"))}
        elif b:
            close()
            cur = {"label": None, "bullet": True, "line": n, "raw": [(n, raw)],
                   "parts": [(n, b.group("rest"))], "style": None, "indent": indent,
                   "textcol": indent + len(s) - len(b.group("rest"))}
        elif cur is None:
            cur = {"label": None, "bullet": False, "line": n, "raw": [(n, raw)], "parts": [(n, s)],
                   "style": None, "indent": indent, "textcol": indent}
        else:
            cur["raw"].append((n, raw))
            cur["parts"].append((n, s))
    close()
    for i, b in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else None
        child = bool(b["label"] is not None and nxt is not None and nxt["label"] is not None and (
            (nxt["style"] != b["style"] and nxt["indent"] > b["indent"])
            or nxt["label"].startswith(b["label"] + ".")))
        b["intro"] = child and bool(
            b["text"].endswith(":") or re.search(r"\b(following|these|below|as follows)\b", b["text"], re.I))
    return out


KV_RE = re.compile(r"^\s*(?P<k>[A-Za-z][^:.]{1,40}?)\s*(?:\.{2,}\s*:?|:)\s+(?P<v>\S.*)$")


def _kv(raw):
    """("label", "value") for a data-sheet row such as "Page limit ....: 20 pages", else None."""
    m = KV_RE.match(raw)
    return (m.group("k").strip(), m.group("v").strip()) if m else None


def _src(n, text):
    return {"line": n, "text": norm_ws(text)}


# ---------------------------------------------------------------- deadlines

DEADLINE_KINDS = [
    ("submission_due", r"^(?!.*question)(?=.*\b(proposals?|submittals?|statements? of qualifications?|"
                       r"responses? to (this|the) (rfp|request|notice|solicitation))\b.{0,50}"
                       r"\b(due|deadline|received|closing|closes)\b)"),
    ("answers_issued", r"respons|answers|addend"),
    ("questions_due", r"question|clarification|inquir"),
    ("conference", r"conference|site visit|walk-?through|pre-?proposal (meeting|briefing)|briefing"),
    ("interview", r"interview|oral presentation|presentation"),
    ("submission_due", r"proposals?\s+(are\s+)?(now\s+)?due|proposal (submission )?deadline|submission deadline|"
                       r"submittal|due date|proposals? (must|shall|should|will) be (received|submitted|delivered|"
                       r"uploaded)|closing (date|time)|deadline (for|to) (submit|submission|receipt)|"
                       r"(submission|receipt) of proposals|proposal due"),
    ("award", r"award|council|board\b.{0,40}(action|approval|consideration|meeting)|approval|recommendation|decision"),
    ("issued", r"issued|release|published|advertis"),
    ("start", r"start|commence|effective|begin"),
]
DEADLINE_LABELS = {
    "issued": "RFP issued", "conference": "Pre-proposal conference", "questions_due": "Questions due",
    "answers_issued": "Answers issued", "submission_due": "Submission due", "interview": "Interviews",
    "award": "Award or board action", "start": "Start of services", "unknown": "Date (kind not recognised)",
}
_WEEKDAY_TAIL = (r"\b(?:on\s+)?(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)[a-z]*\.?,?(?:\s+the)?\s*$")


def classify_deadline(label):
    low = label.lower()
    for kind, pat in DEADLINE_KINDS:
        if re.search(pat, low):
            return kind
    return "unknown"


def _time_and_end(text):
    """(time, index just after it) for the first clock time in text, or (None, 0)."""
    t = find_time(text)
    if not t:
        return None, 0
    ends = [m.end() for m in (TIME_RE.search(text), TIME_24_RE.search(text)) if m]
    return t, min(ends) if ends else 0


def _mk_deadline(kind, label, date, n, raw, time, reasons):
    return {"kind": kind, "label": label or DEADLINE_LABELS.get(kind, ""), "date": date["date"],
            "end_date": date["end"], "time": time, "source": _src(n, raw),
            "confidence": "check" if reasons else "ok", "check_reason": "; ".join(reasons),
            "changed_by": None, "original_date": None, "original_time": None}


def _deadline_from_line(n, raw):
    """A schedule row: one label and one date on a line, in either order."""
    dates = find_dates(raw)
    if not dates:
        return None
    first = dates[0]
    label = re.sub(_WEEKDAY_TAIL, "", raw[:first["start"]].strip(), flags=re.I)
    label = re.sub(r"[\s.:…\-(]+$", "", label).strip()
    label = re.sub(r"\s*\bweek of$", "", label, flags=re.I).strip(" .:-")
    label = re.sub(r"^[\s.:…\-]+", "", label)
    if not re.search(r"[A-Za-z]{3}", label):
        after = raw[first["stop"]:]
        t, end = _time_and_end(after)
        label = re.sub(r"^[\s,.:;…\-–]+|[\s,.:;…\-–]+$", "", TIME_RE.sub("", after) if t else after)
        label = re.sub(r"[\s,]+$", "", re.sub(r"\s{2,}", " ", label))
    kind = classify_deadline(label or raw)
    reasons = []
    if kind == "unknown":
        reasons.append("kind of date not recognised")
    if not first["valid"]:
        reasons.append("date is not a valid calendar date")
    if re.search(r"week of|on or about|approximately", raw, re.I):
        reasons.append("date is approximate in the RFP")
    if len(dates) > 1:
        reasons.append("more than one date on the line")
    return _mk_deadline(kind, label, first, n, raw, find_time(raw[first["stop"]:]) or find_time(raw), reasons)


def _deadlines_from_prose(n, text):
    """Dates stated inside sentences. One sentence can hold more than one deadline."""
    out = []
    for sent in sentences(text):
        dates = find_dates(sent)
        prev_stop, last = 0, None
        for i, d in enumerate(dates):
            clause = sent[prev_stop:d["start"]]
            nxt = dates[i + 1]["start"] if i + 1 < len(dates) else len(sent)
            after = sent[d["stop"]:nxt]
            bare = re.sub(_WEEKDAY_TAIL, "", clause.strip(), flags=re.I).strip(" ,")
            if last is not None and re.fullmatch(r"(?:and|through|thru|to|until|or|[-–])(?:\s+on)?", bare, re.I):
                if last["end_date"] is None:
                    last["end_date"] = d["date"]
                prev_stop = d["stop"]
                continue
            kind = classify_deadline(clause)
            if kind == "unknown" and i == 0:
                kind = classify_deadline(after)
            if kind in ("unknown", "start"):
                prev_stop, last = d["stop"], None
                continue
            t, end = _time_and_end(after[:32])
            if t:
                prev_stop = d["stop"] + end
            else:
                t = find_time(clause[-48:])
                prev_stop = d["stop"]
            reasons = ["date stated in a sentence, not a schedule row"]
            if not d["valid"]:
                reasons.append("date is not a valid calendar date")
            last = _mk_deadline(kind, "", d, n, sent, t, reasons)
            out.append(last)
    return out


def _schedule_deadlines(lines):
    out = []
    for n, text, raw in _paragraphs(lines):
        dated = [(ln, t) for ln, t in raw if find_dates(t)]
        wrapped = any(t.strip()[:1].islower() for _, t in raw[1:])   # a line that carries on a sentence
        prose = wrapped and len(sentences(re.sub(r"\.{3,}", " ", text))) >= 2
        if dated and len(dated) * 10 >= len(raw) * 6 and not prose:
            for ln, t in raw:
                d = _deadline_from_line(ln, t)
                if d:
                    out.append(d)
        else:
            out.extend(_deadlines_from_prose(n, text))
    return out


# ---------------------------------------------------------------- mechanics

PAGE_LIMIT_RE = re.compile(
    r"(?:not (?:to )?exceed|limited to|no more than|maximum of|limit of|longer than|page (?:limit|maximum)"
    r"(?: is| of)?[\s.:…]*)\s*(" + COUNT + r")\s+pages", re.I)
EXCL_RE = re.compile(r"(?:excluding|not counting|exclusive of)\s+(.+?)(?:,\s*(?:must|shall)\b|\.?$)", re.I)
EXCL_SENT_RE = re.compile(
    r"(?:do|does|are|is) not count(?:ed)?\b|not counted|outside the (?:page )?limit|"
    r"excluded from the (?:page )?(?:limit|count)|not (?:included|counted) in the page", re.I)
COPIES_RE = re.compile(
    r"\b(" + COUNT + r")\s+((?:[a-z-]+\s+){0,2})(originals?|cop(?:y|ies)|USB drives?|flash drives?|PDF)\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
FONT_RE = re.compile(
    r"(?:font|type(?:face)?)\b[^.;]{0,40}?\b(\d{1,2})[- ]?(?:points?|pt)\b|"
    r"\b(\d{1,2})[- ]?(?:point|pt)\.?(?: or larger)? (?:font|type(?:face)?)\b|\b(\d{1,2})-point\b|"
    r"\b(\d{1,2}) point\b", re.I)
MARGIN_RE = re.compile(
    r"(one|1|\d(?:\.\d+)?)[- ]inch margins|margins?[^.;]{0,30}?\b(\d(?:\.\d+)?|one)[- ]?inch", re.I)
NOT_ACCEPTED_RE = re.compile(
    r"will not be (accepted|considered|opened|read|reviewed)|will not (consider|accept|open|review)\b|"
    r"do not (send|email|fax|mail|submit|deliver)", re.I)
AMOUNT_RE = re.compile(r"(?:\$\s?|USD\s?)[\d,]*\d(?:\.\d+)?(?:\s+million)?")


def _amounts(text):
    return [re.sub(r"^(?:\$\s?|USD\s?)", "$", a) for a in AMOUNT_RE.findall(text)]


def _mechanics_from_sentence(sent, n):
    """Return a list of mechanics items found in one sentence."""
    out = []

    def add(kind, value, **extra):
        item = {"kind": kind, "value": value, "source": _src(n, sent), "confidence": "ok",
                "check_reason": ""}
        item.update(extra)
        out.append(item)

    m = PAGE_LIMIT_RE.search(sent)
    if m:
        val, consistent = count_value(m.group(1))
        item_extra = {}
        if not consistent:
            item_extra = {"confidence": "check", "check_reason": "word and number disagree"}
        add("page_limit", val, **item_extra)
        e = EXCL_RE.search(sent)
        if e:
            add("page_exclusions", e.group(1).strip(" ."))
    elif EXCL_SENT_RE.search(sent):
        add("page_exclusions", sent, confidence="check",
            check_reason="exclusion stated away from the page limit; read the sentence")
    if NOT_ACCEPTED_RE.search(sent):
        add("not_accepted", sent)
    else:
        copies = []
        for c in COPIES_RE.finditer(sent):
            copies.append(c.group(0))
        if copies:
            add("copies", "; ".join(norm_ws(c) for c in copies))
        if re.search(r"\bPDF\b", sent):
            add("format", "separate PDF files" if re.search(r"separate", sent, re.I) else "PDF")
        pk = re.search(r"sealed (envelope|package|box|container|packet)", sent, re.I)
        if pk:
            add("packaging", "sealed " + pk.group(1).lower())
        email = EMAIL_RE.search(sent)
        if email and re.search(r"\b(submit|email|send|deliver)", sent, re.I):
            add("delivery", "email to " + email.group(0).rstrip("."))
        elif re.search(r"\bportal\b", sent, re.I):
            add("delivery", "online portal")
        elif re.search(r"\b(deliver|delivery|delivered|mail)\b.*\bto\b", sent, re.I):
            add("delivery", "physical delivery")
    m = FONT_RE.search(sent)
    if m:
        add("font", int(next(g for g in m.groups() if g)))
    m = MARGIN_RE.search(sent)
    if m:
        v = (m.group(1) or m.group(2)).lower()
        add("margins", 1.0 if v == "one" else float(v))
    return out


# ---------------------------------------------------------------- requirements

_DISCLOSURE_TITLE = r"litigation|discipline|disciplinary|malpractice|sanction|exceptions?\b"
_DISCLOSURE_TEXT = (r"discipline|disciplinary|malpractice|sanction|exceptions?\b|"
                    r"(litigation|claims?|lawsuits?|judgments?) (against|involving) (the|your) firm|"
                    r"been (sued|the subject of)|litigation history|pending litigation")
QTYPE_RULES = [
    ("cover_letter", r"cover letter|letter of (transmittal|interest|introduction)|transmittal|introductory letter"),
    ("conflicts", r"conflicts?\b|relationship with|adverse to"),
    ("rates", r"\bfees?\b|\brates?\b|compensation|cost proposal|pricing|retainer"),
    ("references", r"references?\b"),
    ("transition", r"transition|continuity|take over|taking over|hand-?over"),
    ("disclosure", None),
    ("diversity_local", r"\blocal\b|diversity|small business|disadvantaged"),
    ("team", r"\bteam\b|personnel|staffing|who would be|resumes|proposed attorneys|key (staff|attorneys)|"
             r"organi[sz]ation(al)? chart|^the people$|attorneys who will"),
    ("experience", r"experience|engagements|has (litigated|arbitrated|handled|tried|represented|advised|served)|"
                   r"representative (matters|clients|cases)|^comparable\b|comparable (work|matters|engagements)"),
    ("approach", r"approach|work plan|methodolog|method of service|service (delivery|plan)|"
                 r"how (do|does|will|would) (you|the firm|your firm)|how (you|the firm|your firm) (will|would)"),
    ("firm_overview", r"firm (overview|profile|qualifications|description|background|information|history)|"
                      r"about (your|the) firm|describe (the|your) firm|^the firm$|history, ownership"),
]
QTYPE_LABELS = {
    "cover_letter": "Cover letter", "firm_overview": "Firm overview", "approach": "Approach",
    "team": "Team", "experience": "Experience", "references": "References", "conflicts": "Conflicts",
    "rates": "Rates and fees", "diversity_local": "Diversity and local presence",
    "transition": "Transition plan", "disclosure": "Disclosures and exceptions", "other": "Other",
}
PERSON_QTYPES = {"cover_letter", "conflicts", "rates", "disclosure"}
TITLE_RE = re.compile(r"^([A-Z][A-Za-z ,/&\-']{2,60}?)[.:]\s+(?=\S)")
DIRECTIVE_RE = re.compile(
    r"\b(?:must|shall)\b.{0,90}?\b(?:include|provide|list|identify|describe|state|submit|attach|contain|be signed|"
    r"confirm|disclose|explain|address|tell|answer)\b|\?$|"
    r"^(?:[^.]{0,70},\s+)?(?:please\s+)?(?:provide|describe|state|list|identify|explain|include|attach|submit|"
    r"disclose|give|tell us)\b", re.I)


def _match_rules(chunk, title_pass):
    low = chunk.lower().strip()
    for qtype, pat in QTYPE_RULES:
        if pat is None:
            pat = _DISCLOSURE_TITLE if title_pass else _DISCLOSURE_TEXT
        if re.search(pat, low):
            return qtype
    return None


def classify_question(title, text):
    """Question type from the item's title if it has one, then its first clause, then all of it."""
    if title:
        q = _match_rules(title, True)
        if q:
            return q
    if text:
        first = re.split(r"(?<=[.?:;])\s", text, maxsplit=1)[0]
        for chunk in ((first, text) if first != text else (text,)):
            q = _match_rules(chunk, False)
            if q:
                return q
    return "other"


def _requirement(block, extra_reason=""):
    text = block["text"]
    title = ""
    m = TITLE_RE.match(text)
    if m and len(m.group(1).split()) <= 7:
        title = m.group(1).strip()
    qtype = classify_question(title, text)
    optional = bool(re.search(r"\boptional\b|\bmay,? at (its|their) option\b|\bif (it|the firm) wishes\b.{0,20}$",
                              text, re.I)) and not re.search(r"\b(must|shall)\b", text, re.I)
    reasons = []
    if qtype == "other":
        reasons.append("question type not recognised")
    if block["label"] is None:
        reasons.append("unnumbered item in the proposal content section")
    if extra_reason:
        reasons.append(extra_reason)
    refs = None
    m = re.search(r"\b(" + COUNT + r")\s+(?:\(\d+\)\s+)?references", text, re.I)
    if m and qtype == "references":
        refs = count_value(m.group(1))[0]
    return {"id": "R-%s" % (block["label"] or "L%d" % block["line"]), "label": block["label"] or "",
            "title": title or QTYPE_LABELS[qtype], "text": text, "qtype": qtype,
            "mandatory": not optional, "references_required": refs,
            "source": _src(block["line"], block["raw"][0][1]),
            "confidence": "check" if reasons else "ok", "check_reason": "; ".join(reasons)}


# ---------------------------------------------------------------- forms

FORM_REF = r"(?:Form|Attachment|Exhibit|Appendix|Document)\s+[A-Z0-9]{1,3}\b"
FORM_LINE_RE = re.compile(r"^(?P<ref>" + FORM_REF + r")\s*[-–:,]\s*(?P<name>.+)$")
FORM_ROW_RE = re.compile(r"^(?P<ref>" + FORM_REF + r")(?:\s*[-–:,.]\s*|\s{2,})(?P<name>\S.+)$")
FORM_INLINE_RE = re.compile(r"(?P<ref>" + FORM_REF + r")\s*[-–:,]\s*(?P<name>[A-Z][A-Za-z'’-]*(?: (?:[A-Z][A-Za-z'’-]*|of|and|for|the)){0,7})")
FORMLIKE_RE = re.compile(r"certif|acknowledg|attachment|\bform\b|affidavit|declaration|proof of|evidence of|"
                         r"disclosure", re.I)
FORM_PROSE_RE = re.compile(r"\b(?:must|shall)\s+(?:also\s+)?(?:enclose|include|submit|attach|return|provide)\s+(.+)$",
                           re.I)


def _form(text, n, raw, confidence="ok", reason="", section_signed=False):
    text = norm_ws(text)
    ref, name = "", text
    m = FORM_LINE_RE.match(text)
    if m:
        ref, name = m.group("ref"), m.group("name")
    else:
        m = re.search(r"\((" + FORM_REF + r")\)", text)
        if m:
            ref = m.group(1)
            name = (text[:m.start()] + text[m.end():]).strip()
    flags = name.lower()
    name = re.sub(r"\s*\((signed|notarized|notarised)\)\s*$", "", name, flags=re.I).strip(" .")
    return {"ref": ref, "name": name, "text": text,
            "signature": section_signed or bool(re.search(r"\bsign", flags)),
            "notarized": bool(re.search(r"notari", flags)),
            "mandatory": True, "source": _src(n, raw), "confidence": confidence, "check_reason": reason}


def _forms_from_prose(sent):
    """Names of documents a sentence says must be enclosed: 'must also enclose X and Y'."""
    m = FORM_PROSE_RE.search(sent)
    if not m or re.search(r"\b(following|below)\b", sent, re.I):
        return []
    names = []
    for piece in re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1)):
        piece = re.sub(r"^(?:an?|the|its|their)\s+", "", piece.strip(" ."), flags=re.I)
        piece = re.sub(r"^(?:completed|signed|executed|current)\s+", "", piece, flags=re.I)
        piece = re.sub(r"\s+(?:as (?:described|required|set out|stated)|described|required by|in the form)\b.*$", "",
                       piece, flags=re.I)
        if 2 <= len(piece.split()) <= 9 and FORMLIKE_RE.search(piece):
            names.append(piece)
    return names


# ---------------------------------------------------------------- evaluation

_W = r"(?P<w>\d{1,3}(?!\.\d)|0?\.\d{1,2}|1\.0{1,2})"
EVAL_RE = re.compile(r"^(?P<name>.*?[A-Za-z)])[\s.\-–:(…]*?" + _W +
                     r"\s*(?P<unit>%|percent|points?|pts\.?)?\)?\s*$")
EVAL_WEIGHT_FIRST_RE = re.compile(
    r"^(?:weight\s*:?\s*)?(?P<w>\d{1,3})\s*(?P<unit>%|percent|points?|pts\.?)\s*[-–:]\s*(?P<name>.+)$", re.I)
EVAL_PROSE_W_RE = re.compile(
    r"(?:(?P<word>" + NUMWORD + r")\s+per ?cent\s*\(\s*(?P<pd>\d{1,3})\s*%?\s*\)|"
    r"(?P<num>\d{1,3})\s*(?P<unit>%|per ?cent|points?|pts\.?)(?!\w))(?:\s+out of\s+\d+(?:\s+points)?)?", re.I)


def _crit(name, w, n, raw, conf="ok", reason=""):
    name = re.sub(r"\s*\((?:[A-Z]?[\d.]+|[A-Z]\(?[ivx]+\)?|[ivx]+)\)\s*$", "", name).strip(" .-–:(…")
    return {"name": name, "weight": w, "source": _src(n, raw), "confidence": conf, "check_reason": reason}


def _evaluation_prose(sec):
    """Criteria and weights written into a sentence: 'experience, forty percent (40%); fees, 15 points'."""
    for n, text, _ in _paragraphs(sec["lines"]):
        for sent in sentences(text):
            ms = list(EVAL_PROSE_W_RE.finditer(sent))
            if len(ms) < 2:
                continue
            crits, unit, prev = [], None, 0
            for m in ms:
                name = sent[prev:m.start()]
                prev = m.end()
                if ":" in name:
                    name = name.rsplit(":", 1)[1]
                name = re.sub(r"^[\s;,.]+(?:and\s+)?", "", name)
                name = re.sub(r"(?:,|\s+counts? for|\s+(?:is|are|will be) worth|\s+worth|\s+will count for|"
                              r"\s+up to|\s+receives?|\s*[-–:(])\s*$", "", name.strip()).strip(" ,")
                w = int(m.group("pd") or m.group("num"))
                u = (m.group("unit") or "percent").lower()
                unit = "percent" if m.group("pd") or u.startswith(("%", "per")) else "points"
                if name and len(name.split()) <= 14:
                    crits.append(_crit(name, w, n, sent, "check", "weight read from a sentence, not a table"))
            if len(crits) >= 2:
                return crits, unit
    return [], None


def _evaluation(sections):
    criteria, total_stated, unit = [], None, None
    for sec in sections:
        if sec["kind"] != "evaluation":
            continue
        found_here = []
        group, groups = [], []
        for n, raw in sec["lines"] + [(0, "")]:
            if raw.strip():
                group.append((n, raw))
            elif group:
                groups.append(group)
                group = []
        for group in groups:
            parsed = []
            for n, raw in group:
                s = re.sub(r"^(?:[-*•]|\(?[a-z0-9]{1,2}[.)])\s+", "", raw.strip())
                wf = EVAL_WEIGHT_FIRST_RE.match(s)
                if wf:
                    s = "%s %s%s" % (wf.group("name"), wf.group("w"), wf.group("unit") or "")
                m = EVAL_RE.match(s)
                parsed.append((n, raw, s, m))
            if not any(m for _, _, _, m in parsed):
                continue
            for n, raw, s, m in parsed:
                if m:
                    name = m.group("name").strip(" .-–:(…")
                    w = float(m.group("w")) if "." in m.group("w") else int(m.group("w"))
                    if m.group("unit"):
                        unit = "percent" if m.group("unit").lower() in ("%", "percent") else "points"
                    if name.lower() in ("total", "total points", "maximum total", "total weight"):
                        total_stated = w
                        continue
                    found_here.append(_crit(name, w, n, raw))
                elif re.search(r"\b(criterion|criteria|weight|points|maximum|score)\b", s, re.I):
                    continue  # column header
                elif not s.endswith((":", ".")) and len(s.split()) <= 10:
                    found_here.append(_crit(s, None, n, raw, "check", "criterion listed without a weight"))
        if len([c for c in found_here if c["weight"] is not None]) < 2:
            prose, punit = _evaluation_prose(sec)
            if prose:
                found_here, unit = prose, punit
        criteria.extend(found_here)
    weights = [c["weight"] for c in criteria if c["weight"] is not None]
    if weights and all(isinstance(w, float) or w in (0, 1) for w in weights) and abs(sum(weights) - 1) < 0.011:
        for c in criteria:
            if c["weight"] is not None:
                c["printed_as"] = c["weight"]
                c["weight"] = int(round(c["weight"] * 100))
        unit = "percent"
        if total_stated is not None:
            total_stated = int(round(total_stated * 100))
    else:
        for c in criteria:
            if isinstance(c["weight"], float):
                c["weight"] = int(round(c["weight"]))
    out = {"criteria": criteria, "total_stated": total_stated, "unit": unit}
    _evaluation_totals(out)
    return out


def _evaluation_totals(ev):
    criteria = ev["criteria"]
    total = sum(c["weight"] for c in criteria if c["weight"] is not None)
    reasons = []
    if criteria and ev["total_stated"] is not None and ev["total_stated"] != total:
        reasons.append("weights add to %d but the RFP states a total of %d" % (total, ev["total_stated"]))
    if criteria and ev["unit"] == "percent" and total != 100:
        reasons.append("percent weights add to %d, not 100" % total)
    if any(c["weight"] is None for c in criteria):
        reasons.append("at least one criterion has no weight")
    for i, c in enumerate(criteria, 1):
        c["id"] = "EV%d" % i
    ev.update({"total": total, "unit": ev["unit"] or ("points" if criteria else None),
               "confidence": "check" if reasons else "ok", "check_reason": "; ".join(reasons)})


# ---------------------------------------------------------------- minimum qualifications

_ATLEAST = r"(?:at least|a minimum of|minimum of|no fewer than|not less than|no less than)"
ORDINAL_RE = re.compile(r"^(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Finally|Lastly)"
                        r"[,:]\s+", re.I)


def classify_min_qual(text):
    """Return (check_kind, value). Only kinds that bio or firm data can check are named."""
    m = re.search(r"\b(?:" + _ATLEAST + r"\s+)?(" + COUNT + r")\s+(?:or more\s+)?years\b", text, re.I)
    if m and re.search(r"admitted|admission|licensed|member (?:in good standing )?of the\b.{0,30}\bbar\b", text, re.I):
        return "years_admitted", count_value(m.group(1))[0]
    m = re.search(r"\boffice\s+(?:located\s+)?(?:within|in)\s+(.+?)(?:\s+or\b|[.;,]|$)", text, re.I)
    if m:
        place = m.group(1).strip()
        if re.match(r"(?:the|its|a|an)\b", place, re.I) or re.search(r"\bor\b", text):
            return "not_checkable", None
        return "office_location", place
    m = re.search(_ATLEAST + r"\s+(" + COUNT + r")\s+attorneys\b", text, re.I) or \
        re.search(r"\b(" + COUNT + r")\s+or more\s+attorneys\b", text, re.I)
    if m:
        return "attorney_count", count_value(m.group(1))[0]
    return "not_checkable", None


def _min_qual(label, text, n, raw, conf="ok", reason=""):
    ck, val = classify_min_qual(text)
    return {"label": label or "", "text": text, "check_kind": ck, "value": val,
            "source": _src(n, raw), "confidence": conf, "check_reason": reason}


# ---------------------------------------------------------------- parties

_ROLE_HEAD = (r"(?:Mayor|Managers?|President|Directors?|Trustees?|Superintendent|Chancellor|Counsel|Attorney|"
              r"Officer|Clerk|Chair(?:person|man|woman)?|Commissioners?|Supervisors?|Secretary|Treasurer|"
              r"Engineer|Administrator|Council ?[Mm]embers?|Board [Mm]embers?|Controller|Auditor|Coordinator)")
ROLE_RE = re.compile(r"((?:[A-Z][a-z]+ ){0,3}" + _ROLE_HEAD + r"\b(?: of (?:the )?[A-Z][a-z]+(?: [A-Z][a-z]+){0,2})?)")
PARTY_TRIGGER_RE = re.compile(_ROLE_HEAD + r"\b|Board of [A-Z][a-z]+|Board members|City Council:")
BOARDISH_RE = re.compile(r"Board of [A-Z][a-z]+|Board members|City Council:|governing board|officers of the Board", re.I)
_BOARD_HEADS = {"mayor", "trustee", "chair", "chairperson", "chairman", "chairwoman", "commissioner",
                "supervisor", "councilmember", "council member", "board member"}
NAME_TOKEN_RE = re.compile(r"(?:O['’])?[A-Z][a-z]+(?:[A-Z][a-z]+)?(?:[-'’][A-Z][a-z]+)*")
NAME_STOP = set("""The A An Board Directors Director President Vice General Manager District City Council
Mayor Water Authority State County Human Resources Assistant Superintendent Executive Chief Officer
Counsel Contracting Clerk Deputy Trustees Trustee Capital Programs Secretary Councilmember Member
Members Road Street Avenue Suite Drive Way Boulevard Lane Proposals Proposers Proposal Section
Attorney Planning Commission Special Request Division Unified School Transit Dr Mr Ms Mrs Chair
Commissioner Commissioners Supervisor Supervisors Do Email Paper Subject Direct Late Use Submit
January February March April May June July August September October November December Monday
Tuesday Wednesday Thursday Friday Saturday Sunday Exhibit Attachment Form Appendix Addendum
Letter Transmittal Agreement Department Office Services Legal Finance Public Works Committee
Its Their Each All Either Firms Questions Answers Treasurer Chancellor Engineer Administrator
Controller Auditor Coordinator College University Court Part Paragraph Item Document""".split())
_ORG_HEAD = (r"(?:Association|Union|Federation|Coalition|Alliance|League|Society|Guild|Constructors|Company|"
             r"Corporation|Partners|Properties|Systems|Group|Builders|Contractors|Holdings|Enterprises|"
             r"Industries|Associates)")
_ORG_SUFFIX = r"(?:Inc\.?|LLC|L\.L\.C\.|LP|LLP|Corp\.?|Co\.|Ltd\.?)"
_CAPWORD = r"[A-Z][A-Za-z&'’-]+"
ORG_RE = re.compile(
    r"((?:" + _CAPWORD + r"\s+){1,5}" + _ORG_HEAD + r"\b(?:\s+of\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})?"
    r"(?:,?\s+" + _ORG_SUFFIX + r")?"
    r"|(?:" + _CAPWORD + r"\s+){1,5}" + _CAPWORD + r",?\s+" + _ORG_SUFFIX + r")")
EMPLOYEE_ORG_RE = re.compile(r"\bUnion\b|\b(?:Employees?|Faculty|Teachers|Officers|Workers|Firefighters|Police|"
                             r"Staff)\b.*\bAssociation\b", re.I)
ADVERSE_RE = re.compile(r"dispute|\bclaims?\s+(?:by|against|from|of)\b|\bclaim\b|adverse|litigation (?:with|against)|"
                        r"lawsuit|petition|\bsued\b|negotiat|employee organi[sz]ations|challeng|\bv\.", re.I)
ADVERSE_PARA_RE = re.compile(r"\bas adverse\b|\badverse to\b|adverse part(?:y|ies)|opposing part(?:y|ies)", re.I)
AGENCY_DEF_RE = re.compile(
    r"((?:[A-Z][a-z]+|of)(?: (?:[A-Z][a-z]+|of|and))*)\s+\((?:the\s+)?[\"“]"
    r"((?:[A-Z][a-z]+ )?(?:City|District|Authority|Town|County|Agency|Commission|Board|Corporation|Library|"
    r"College|University))[\"”]\)")
AGENCY_LINE_RE = re.compile(
    r"^(?:(?:City|Town|County) of [A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*|"
    r"[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)* (?:District|Authority|Agency|Commission))$", re.I)


def agency_type_of(name):
    low = name.lower()
    if re.search(r"school|unified|college", low):
        return "school_district"
    if re.search(r"transit|transportation", low):
        return "transit"
    if re.search(r"\b(city|town)\b", low):
        return "city"
    if "county" in low:
        return "county"
    if "district" in low or "authority" in low or "agency" in low:
        return "special_district"
    return "other"


def agency_short_of(name):
    for word in ("City", "Town", "County"):
        if re.match(word + r" of\b", name):
            return word
    m = re.search(r"(District|Authority|Agency|Commission|County|City|Town)\s*$", name)
    return m.group(1) if m else "Agency"


def _title_case(s):
    words = s.lower().split()
    return " ".join(w if w in ("of", "and", "the") and i else w.capitalize() for i, w in enumerate(words))


def _paragraphs(lines):
    """Blank-line separated paragraphs as (first_line_no, joined_text, raw_lines)."""
    out, cur = [], []
    for n, raw in list(lines) + [(0, "")]:
        if raw.strip():
            cur.append((n, raw))
        elif cur:
            out.append((cur[0][0], norm_ws(" ".join(t for _, t in cur)), cur))
            cur = []
    return out


def _mask(text, spans):
    chars = list(text)
    for a, b in spans:
        for i in range(a, b):
            if chars[i] != " ":
                chars[i] = "x"
    return "".join(chars)


def _people_in(text, stop):
    """Capitalised 2-3 word runs that are not role or organisation words."""
    people = []
    toks = list(re.finditer(r"[A-Za-z][A-Za-z'’-]*|[^\sA-Za-z]+", text))
    run = []

    def flush():
        if 2 <= len(run) <= 3:
            people.append((run[0].start(), run[-1].end(), text[run[0].start():run[-1].end()]))
        run.clear()

    for t in toks:
        w = t.group(0)
        if NAME_TOKEN_RE.fullmatch(w) and w not in stop:
            if run and text[run[-1].end():t.start()] != " ":
                flush()
            run.append(t)
        else:
            flush()
    flush()
    return people


_HONORIFIC = r"(?:(?:Dr|Mr|Ms|Mrs|Mx)\.\s+)?"
_ROLE_GAP_RE = re.compile(r"(?:\s*:?\s*|,\s+|\s+is\s+|,\s[A-Z][A-Za-z ]{2,40},\s+is\s+)" + _HONORIFIC)


def _clean_role(role):
    return re.sub(r"^(?:The|Its|Their|Our|And|A|An)\s+", "", role).strip()


def _role_for(text, start, stop_idx):
    """Role stated next to a name: '(Role)' after it, 'Role Name' or 'Role is Name' before it, or 'Name, Role'."""
    after = text[stop_idx:stop_idx + 70]
    m = re.match(r"\s*\(\s*" + ROLE_RE.pattern, after)
    if m:
        return _clean_role(m.group(1))
    before = text[max(0, start - 110):start]
    m = None
    for m in ROLE_RE.finditer(before):
        pass
    if m and _ROLE_GAP_RE.fullmatch(before[m.end():]):
        return _clean_role(m.group(1))
    return ""


def _role_after(text, stop_idx):
    m = re.match(r"\s*,\s*" + ROLE_RE.pattern, text[stop_idx:stop_idx + 70])
    return _clean_role(m.group(1)) if m else ""


def _party_category(role, boardish):
    words = re.sub(r" of .*$", "", role).split()
    has_tail = " of " in role
    low = [w.lower() for w in words]
    if not low:
        return "board" if boardish else "staff"
    head = re.sub(r"s$", "", low[-1])
    two = " ".join(low[-2:])
    mods = [w for w in low[:-1] if w not in ("vice", "board", "the")]
    if re.sub(r"s$", "", two) in _BOARD_HEADS:
        return "board"
    if head in _BOARD_HEADS:
        return "board"
    if head in ("president", "director") and not mods and not has_tail:
        return "board"
    if head in ("clerk", "treasurer", "secretary") and not mods and not has_tail and boardish:
        return "board"
    return "staff"


def _parties(all_lines, meta):
    agency = meta["agency"]
    parties = []
    if agency:
        parties.append({"name": agency, "category": "agency", "role": "Issuing agency",
                        "source": meta["agency_source"], "confidence": meta["agency_confidence"],
                        "check_reason": "" if meta["agency_confidence"] == "ok" else
                        "agency name taken from the title block; confirm"})
    stop = set(NAME_STOP) | set(re.findall(r"[A-Za-z]+", agency))
    seen = {}
    for n, text, raw in _paragraphs(all_lines):
        org_spans = []
        orgs = []
        for m in ORG_RE.finditer(text):
            full = m.group(1)
            lead = re.match(r"(?:(?:The|A|An|Its|And|Or|By|For|With|Of|To|From|Either|Both)\s+)+", full)
            off = lead.end() if lead else 0
            name = re.sub(r"\s+", " ", full[off:].strip())
            if len(name.split()) < 2:
                continue
            org_spans.append((m.start(1) + off, m.end(1)))
            orgs.append((m.start(1) + off, m.end(1), name))
        if PARTY_TRIGGER_RE.search(text):
            boardish = bool(BOARDISH_RE.search(text))
            masked = _mask(text, org_spans)
            last = None          # (stop index, role) of the person just accepted
            for start, stop_idx, name in _people_in(masked, stop):
                role = ""
                for _, rl in raw:  # the line that holds the name first, so a roster line keeps its own role
                    k = rl.find(name)
                    if k >= 0:
                        role = _role_for(rl, k, k + len(name))
                        break
                role = role or _role_for(text, start, stop_idx)
                for known in seen:
                    if role.startswith(known + " "):
                        role = role[len(known) + 1:]
                listed = False
                if not role and last is not None and re.fullmatch(r"(?:\s*\([^)]*\))?(?:,\s+(?:and\s+)?|\s+and\s+)",
                                                                   text[last[0]:start]):
                    role, listed = last[1], True
                if not role:
                    role = _role_after(text, stop_idx)
                if not role and not (boardish and re.search(r":\s*$", text[max(0, start - 3):start])):
                    last = None
                    continue
                last = (stop_idx, role)
                if name in seen:
                    continue
                cat = _party_category(role, boardish)
                item = {"name": name, "category": cat, "role": role or "Named in the RFP",
                        "source": _src(n, text[:240]),
                        "confidence": "check" if listed or not role else "ok",
                        "check_reason": "role taken from the name before it in a list" if listed
                        else ("" if role else "role not stated next to the name")}
                seen[name] = item
                parties.append(item)
        para_adverse = bool(ADVERSE_PARA_RE.search(text))
        sents = sentences(text)
        for _, _, name in orgs:
            if name in seen or name.rstrip(".") in seen or (agency and name.startswith(agency)):
                continue
            sent = next((s for s in sents if name in s), text)
            if EMPLOYEE_ORG_RE.search(name):
                adverse, why = True, "Employee organisation named in the RFP"
            elif ADVERSE_RE.search(sent) or para_adverse:
                adverse, why = True, "Adverse or counter-party mentioned in the RFP"
            else:
                adverse, why = False, "Organisation mentioned in the RFP"
            item = {"name": name, "category": "adverse" if adverse else "other_organisation", "role": why,
                    "source": _src(n, sent[:240]),
                    "confidence": "ok" if adverse else "check",
                    "check_reason": "" if adverse else "relationship to the agency is not stated"}
            seen[name] = item
            parties.append(item)
    return parties


# ---------------------------------------------------------------- meta

SUBJECTS = {
    "water": r"\bwater\b|groundwater", "rates and charges": r"rates and charges|rate setting",
    "land use": r"land use|planning|zoning", "open meetings": r"open meeting|closed session",
    "public records": r"public records", "public contracting": r"public works|bidding|procurement",
    "personnel": r"personnel|employment", "collective bargaining": r"bargaining|negotiations|impasse|factfinding",
    "construction": r"construction|design-build|change order", "claims": r"\bclaims?\b|dispute",
    "real property": r"right-of-way|real property|easement", "transit": r"\btransit\b|\brail\b",
    "code enforcement": r"code enforcement", "schools": r"school|students",
    "governance": r"governance",
}


def _meta(lines, sections):
    text = "\n".join(t for _, t in lines)
    joined = norm_ws(text)
    agency, short, src, conf = "", "", None, "ok"
    for n, ptext, raw in _paragraphs(lines):
        m = AGENCY_DEF_RE.search(ptext)
        if m:
            agency = re.sub(r"^The\s+", "", m.group(1)).strip()
            short = m.group(2)
            src = _src(n, raw[0][1])
            break
    if not agency:
        conf = "check"
        for n, t in lines[:15]:
            if AGENCY_LINE_RE.match(t.strip()):
                agency = _title_case(t.strip())
                short = agency_short_of(agency)
                src = _src(n, t)
                break
    title, number = "", ""
    head = lines[:14]
    for i, (n, t) in enumerate(head):
        m = re.search(r"request for proposals\b\s*:?\s*(.*)$", t, re.I)
        if m:
            rest = m.group(1).strip()
            if rest and not re.match(r"(No\.?|#|Number)\b", rest, re.I):
                title = rest
            else:
                for _, t2 in head[i + 1:]:
                    if t2.strip():
                        title = t2.strip()
                        break
            break
    if title.isupper():
        title = _title_case(title)
    m = re.search(r"(?i:RFP|Solicitation|Proposals|Reference)\s*(?i:No\.?|Number)?\s*:?\s*#?\s*"
                  r"([A-Z0-9]+(?:[-/][A-Z0-9]+)+)", text)
    if m:
        number = m.group(1)
    low_title = title.lower()
    if re.search(r"labor|negotiat", low_title):
        practice = "labor"
    elif re.search(r"capital|construction|project", low_title):
        practice = "capital_projects"
    elif re.search(r"city attorney|general counsel", low_title):
        practice = "general_counsel"
    else:
        practice = "other"
    low = joined.lower()
    subjects = [name for name, pat in SUBJECTS.items() if re.search(pat, low)]
    return {"agency": agency, "agency_short": short or (agency_short_of(agency) if agency else ""),
            "agency_type": agency_type_of(agency) if agency else "other", "agency_source": src,
            "agency_confidence": conf if agency else "check", "title": title, "rfp_number": number,
            "practice": practice, "subjects": subjects}


# ---------------------------------------------------------------- addenda

CHANGE_VERB_RE = re.compile(r"changed|rescheduled|extended|revised|moved|postponed|is now|are now|now due|"
                            r"will (?:now )?be held|instead of|new (?:date|deadline)", re.I)
_ITEM_REF = (r"(?:(?:Paragraph|Section|Item|Question|Requirement|Subsection|Part|No\.)\s+)?"
             r"(?P<label>#?[A-Z]?(?:-?\d+)(?:\.\d+)*[a-z]?|[A-Z]\.\d+(?:\.\d+)*|[A-Z]?\([ivxl]+\)|[A-Z]-\d+)")
DELETE_RE = re.compile(
    _ITEM_REF + r"\s*(?:\([^)]*\)\s*)?,?\s*(?:is|are|has been)\s+(?:hereby\s+)?"
    r"(?:deleted|removed|withdrawn|struck|stricken|eliminated|no longer required)", re.I)
DELETE_IMPERATIVE_RE = re.compile(r"\b(?:delete|remove|strike|omit)\s+" + _ITEM_REF, re.I)
REMOVE_VERB_RE = re.compile(r"\b(?:deleted|removed|withdrawn|struck|stricken|eliminated|no longer (?:required|needed))\b",
                            re.I)
READ_RE = re.compile(
    _ITEM_REF + r"\s*(?:\([^)]*\)\s*)?(?:is|has been)\s+(?:hereby\s+)?(?:corrected|revised|amended|changed|replaced)"
    r"\s+to\s+read(?:\s+as follows)?\s*:?\s*(?P<new>.+)$", re.I)
_OLD_AFTER_RE = re.compile(r"instead of|rather than|in place of|\(was|previously|formerly|originally|not\s*$", re.I)


def _norm_label(s):
    return re.sub(r"[\s.:)]+$", "", str(s).strip().lower()).lstrip("(")


def _find_by_label(items, label):
    want = _norm_label(label)
    for it in items:
        if it.get("label") and _norm_label(it["label"]) == want:
            return it
    return None


def _change(entry, ctype, kind, old, new, src, conf="ok", reason="", **extra):
    c = {"type": ctype, "kind": kind, "from": old, "to": new, "source": src,
         "confidence": conf, "check_reason": reason}
    c.update(extra)
    entry["changes"].append(c)
    return c


_FROM_TO_RE = re.compile(r"^[\s,]*(?:(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?|noon)[\s,]*)?(?:to|until|[-–])\s+"
                         r"(?:[A-Za-z]{3,9}\.?,?\s+)?(?:the\s+)?$", re.I)


def _one_date_change(kind, new, old, new_time, sent, number, src, result, entry):
    same = [d for d in result["deadlines"] if d["kind"] == kind]
    target = None
    if old:
        target = next((d for d in same if d["date"] == old["date"]), None)
    target = target or (same[0] if same else None)
    reason = ""
    if target is None:
        reason = "addendum changes a date that was not matched to a schedule line"
    elif old and target["date"] != old["date"]:
        reason = "addendum says the old date was %s but the schedule had %s" % (old["date"], target["date"])
    if target is not None:
        _change(entry, "deadline", kind, target["date"], new["date"], src, "check" if reason else "ok", reason,
                from_time=target["time"], to_time=new_time or target["time"])
        if target.get("original_date") is None:
            target["original_date"], target["original_time"] = target["date"], target["time"]
        target.update({"date": new["date"], "end_date": new["end"], "time": new_time or target["time"],
                       "changed_by": "Addendum %s" % number, "change_source": src})
        if reason:
            target["confidence"], target["check_reason"] = "check", reason
    else:
        d = _mk_deadline(kind, "", new, src["line"], sent, new_time, [reason])
        d["changed_by"] = "Addendum %s" % number
        result["deadlines"].append(d)
        _change(entry, "deadline", kind, None, new["date"], src, "check", reason, from_time=None, to_time=new_time)


def _apply_date_change(sent, context, labelled, number, src, result, entry):
    """Date changes in one addendum sentence. A sentence may move more than one date."""
    dates = find_dates(sent)
    if not dates or re.search(r"\b(unchanged|remains?|no change)\b", sent, re.I) and not CHANGE_VERB_RE.search(sent):
        return False
    if not labelled and not CHANGE_VERB_RE.search(sent):
        return False
    done, i, prev_stop = False, 0, 0
    while i < len(dates):
        clause = sent[prev_stop:dates[i]["start"]]
        new, old, used = dates[i], None, 1
        if i + 1 < len(dates):
            between = sent[dates[i]["stop"]:dates[i + 1]["start"]]
            if _OLD_AFTER_RE.search(between):
                old, used = dates[i + 1], 2
            elif _FROM_TO_RE.match(between) and (re.search(r"\bfrom\b", clause, re.I) or i == 0):
                new, old, used = dates[i + 1], dates[i], 2
        kind = classify_deadline(clause)
        if kind in ("unknown", "start", "issued") and i == 0:
            k2 = classify_deadline(sent)
            kind = k2 if k2 != "unknown" else classify_deadline(context)
        last = dates[i + used - 1]
        nxt = dates[i + used]["start"] if i + used < len(dates) else len(sent)
        if kind not in ("unknown", "start", "issued"):
            new_time, _ = _time_and_end(sent[new["stop"]:nxt if new is last else dates[i + 1]["start"]][:40])
            if not new_time and old is None:
                new_time = find_time(clause[-48:])
            _one_date_change(kind, new, old, new_time, sent, number, src, result, entry)
            done = True
        prev_stop = last["stop"]
        i += used
    return done


def _apply_criteria_change(sent, number, src, result, entry):
    crit = result["evaluation"]["criteria"]
    low = sent.lower()
    hit = False
    for c in list(crit):
        name = c["name"].lower()
        k = low.find(name)
        if k < 0 or len(name) < 3:
            continue
        before = low[max(0, low.rfind(" and ", 0, k), low.rfind(";", 0, k), 0):k]
        end = len(low)
        for sep in (" and ", ";"):
            j = low.find(sep, k + len(name))
            if j >= 0:
                end = min(end, j)
        clause = before + low[k:end]
        m = re.search(r"(?:now|to|is|worth|becomes?)\D{0,18}?(\d{1,3})\s*(?:points?|pts\.?|%|per ?cent)", low[k:end])
        if m and not REMOVE_VERB_RE.search(clause):
            new = int(m.group(1))
            if new != c["weight"]:
                _change(entry, "weight_changed", "weight_changed", c["weight"], new, src, criterion=c["name"])
                c.setdefault("original_weight", c["weight"])
                c.update({"weight": new, "changed_by": "Addendum %s" % number})
                hit = True
        elif REMOVE_VERB_RE.search(clause):
            crit.remove(c)
            result["evaluation"].setdefault("removed", []).append(dict(c, removed_by="Addendum %s" % number))
            _change(entry, "criterion_removed", "criterion_removed", c["name"], None, src)
            hit = True
    if hit:
        _evaluation_totals(result["evaluation"])
    return hit


def _apply_addendum_item(text, labelled, number, src, result, entry):
    handled = False
    m = READ_RE.search(text)
    if m:
        new_text = m.group("new").strip()
        ins = _find_by_label(result["insurance"], m.group("label"))
        req = _find_by_label(result["requirements"], m.group("label"))
        mq = _find_by_label(result["min_quals"], m.group("label"))
        if ins is not None:
            old_amounts = list(ins["amounts"])
            ins.update({"original_text": ins["text"], "text": new_text, "amounts": _amounts(new_text),
                        "changed_by": "Addendum %s" % number, "change_source": src})
            _change(entry, "insurance_changed", "insurance_changed", ", ".join(old_amounts) or None,
                    ", ".join(ins["amounts"]) or None, src)
            return True
        if req is not None:
            block = {"label": req["label"], "text": new_text, "line": src["line"], "raw": [(src["line"], new_text)]}
            new_req = _requirement(block)
            new_req.update({"original_text": req["text"], "changed_by": "Addendum %s" % number})
            req.update(new_req)
            _change(entry, "requirement_revised", "requirement_revised", m.group("label"), m.group("label"), src)
            return True
        if mq is not None:
            ck, val = classify_min_qual(new_text)
            mq.update({"original_text": mq["text"], "text": new_text, "check_kind": ck, "value": val,
                       "changed_by": "Addendum %s" % number})
            _change(entry, "min_qual_revised", "min_qual_revised", m.group("label"), m.group("label"), src)
            return True
    context = ""
    for sent in sentences(text):
        done = False
        for m in list(DELETE_RE.finditer(sent)) + list(DELETE_IMPERATIVE_RE.finditer(sent)):
            label = m.group("label")
            req = _find_by_label(result["requirements"], label)
            if req is not None:
                result["requirements"].remove(req)
                result["deleted_requirements"].append(dict(req, deleted_by="Addendum %s" % number))
                _change(entry, "requirement_deleted", "requirement_deleted", req["label"], None, src)
                done = True
                continue
            mq = _find_by_label(result["min_quals"], label)
            if mq is not None and re.search(r"qualif|eligib", text, re.I):
                result["min_quals"].remove(mq)
                _change(entry, "min_qual_deleted", "min_qual_deleted", mq["label"], None, src)
                done = True
        if not done and REMOVE_VERB_RE.search(sent):
            low = sent.lower()
            for f in list(result["forms"]):
                ref_hit = f["ref"] and re.search(r"\b" + re.escape(f["ref"]) + r"\b", sent)
                name_hit = len(f["name"]) > 6 and f["name"].lower() in low
                if (ref_hit or name_hit) and not re.search(r"\badded\b", sent, re.I):
                    result["forms"].remove(f)
                    result.setdefault("removed_forms", []).append(dict(f, removed_by="Addendum %s" % number))
                    _change(entry, "form_removed", "form_removed", f["name"], None, src)
                    done = True
        if not done and re.search(r"point|weight|percent|%|criteri|scor", text, re.I):
            done = _apply_criteria_change(sent, number, src, result, entry)
        if not done:
            done = _apply_date_change(sent, context, labelled, number, src, result, entry)
        if not done and _amounts(sent) and re.search(r"increas|reduc|chang|correct|revis|\bnow\b|rais|lower", sent, re.I):
            for ins in result["insurance"]:
                cov = re.split(r"\s+insurance\b|:|\s+of\b|\s+with\b|\(", ins["text"].lower())[0].strip()
                cov = re.sub(r"^(?:and\s+|the\s+|lawyers'\s+)", "", cov)
                if 2 <= len(cov.split()) <= 5 and cov in sent.lower():
                    old_amounts = list(ins["amounts"])
                    ins.setdefault("original_text", ins["text"])
                    ins.update({"amounts": [_amounts(sent)[-1]], "changed_by": "Addendum %s" % number,
                                "change_source": src,
                                "text": "%s (amount changed by Addendum %s to %s)" % (
                                    ins["original_text"], number, _amounts(sent)[-1])})
                    _change(entry, "insurance_changed", "insurance_changed", ", ".join(old_amounts) or None,
                            ins["amounts"][0], src)
                    done = True
                    break
        if not done and re.search(r"\bpages?\b", sent, re.I) and re.search(r"page limit|not (to )?exceed|limited to|"
                                                                          r"no more than|maximum|longer than", sent, re.I):
            counts = re.findall(r"(" + COUNT + r")\s+pages", sent, re.I)
            if counts:
                val = count_value(counts[-1])[0]
                old_item = next((x for x in result["mechanics"] if x["kind"] == "page_limit"), None)
                _change(entry, "page_limit", "page_limit", old_item["value"] if old_item else None, val, src)
                if old_item:
                    old_item.setdefault("original_value", old_item["value"])
                    old_item.update({"value": val, "changed_by": "Addendum %s" % number, "change_source": src})
                else:
                    result["mechanics"].append({"kind": "page_limit", "value": val, "source": src,
                                                "confidence": "ok", "check_reason": "",
                                                "changed_by": "Addendum %s" % number})
                done = True
        if not done and re.search(r"\badded\b|\bnew required\b|\badditional (?:form|document)\b", sent, re.I):
            m = re.search(r"(" + FORM_REF + r")\s*[-–:,]\s*(.+?)\s*,?\s+(?:is|are)\s+(?:hereby\s+)?added", sent) or \
                re.search(r"(?:added|required)\b[^:]*:\s*(" + FORM_REF + r")\s*[-–:,]\s*(.+?)\.?$", sent)
            if m:
                form = _form("%s: %s" % (m.group(1), m.group(2)), src["line"], sent)
                form["added_by"] = "Addendum %s" % number
                result["forms"].append(form)
                _change(entry, "form_added", "form_added", None, form["name"], src)
                done = True
        handled = handled or done
        context = sent
    return handled


def _apply_addenda(addenda_raw, result):
    addenda = []
    for number, head_line, head_rest, lines in sorted(addenda_raw, key=lambda a: int(a[0])):
        issued = find_dates(head_rest) or find_dates(" ".join(t for _, t in lines[:3]))
        entry = {"number": number, "issued": issued[0]["date"] if issued else None,
                 "source": _src(head_line, "ADDENDUM %s%s" % (number, head_rest)), "changes": [], "notes": []}
        blocks = _blocks(lines)
        any_label = any(b["label"] is not None for b in blocks)
        for i, b in enumerate(blocks):
            labelled = b["label"] is not None
            text = b["text"]
            if not labelled and (any_label or i == 0 and not CHANGE_VERB_RE.search(text)):
                continue  # issue line or free text between items
            src = _src(b["line"], text)
            handled = _apply_addendum_item(text, labelled, number, src, result, entry)
            if not handled and labelled:
                entry["notes"].append({"id": "ADD%s-%s" % (number, b["label"].replace("Item ", "")),
                                       "text": text, "source": src, "confidence": "check",
                                       "check_reason": "addendum item not applied automatically; read it"})
        addenda.append(entry)
    return addenda


MAIN_START_RE = re.compile(r"^\s*(?:REQUEST FOR (?:PROPOSALS?|QUALIFICATIONS)|(?:THE )?(?:RFP|REQUEST)\b.{0,30}"
                           r"AS (?:ORIGINALLY )?ISSUED|ORIGINAL (?:RFP|REQUEST)|NOTICE INVITING)", re.I)


def _split_addenda(lines):
    """Separate addenda from the body. Addenda may follow the RFP or be placed in front of it."""
    heads = [i for i, (_, ln) in enumerate(lines) if ADDENDUM_HEAD_RE.match(ln)]
    if not heads:
        return lines, []
    first_body_head = next((i for i in range(len(lines)) if i not in heads and _level1(lines, i)
                            and (classify_heading(_level1(lines, i)[1]) or _level1(lines, i)[0])), None)
    in_front = first_body_head is None or heads[0] < first_body_head
    body, addenda_raw = list(lines[:heads[0]]), []
    for j, i in enumerate(heads):
        m = ADDENDUM_HEAD_RE.match(lines[i][1])
        end = heads[j + 1] if j + 1 < len(heads) else len(lines)
        if j + 1 == len(heads) and in_front:
            for k in range(i + 1, len(lines)):
                h = _level1(lines, k)
                if MAIN_START_RE.match(lines[k][1]) or (h and (h[0] or classify_heading(h[1]))):
                    end = k
                    break
        addenda_raw.append((m.group(1), lines[i][0], m.group(2), lines[i + 1:end]))
        if j + 1 == len(heads):
            body += lines[end:]
    return body, addenda_raw


# ---------------------------------------------------------------- main

_CONTENT_SKIP_RE = re.compile(r"\b(following|below|consists? of)\b|:$", re.I)
_REQ_START_RE = re.compile(r"^(?:describe|provide|state|list|identify|explain|include|attach|submit|disclose|give|"
                           r"how|what|who|which|when|where|why|has|have|is|are|does|do|will|would|if|whether|"
                           r"a |an |the firm'?s?|summari[sz]e|confirm|name|indicate|discuss|detail|outline)\b", re.I)


def parse_rfp(text):
    raw_lines = [(i + 1, ln.expandtabs(4)) for i, ln in enumerate(text.splitlines())]
    all_lines = _clean_lines(raw_lines)
    body, addenda_raw = _split_addenda(all_lines)

    sections = _segment(body)
    meta = _meta(body, sections)
    result = {"meta": meta, "deadlines": [], "mechanics": [], "requirements": [], "forms": [],
              "min_quals": [], "insurance": [], "scope_items": [], "parties": [], "deleted_requirements": [],
              "sections": [{"kind": s["kind"], "title": s["title"], "label": s["label"], "line": s["line"]}
                           for s in sections if s["kind"] != "preamble"]}
    section_labels = {s["label"].lower() for s in sections if s["label"]}

    mech_seen = set()

    def add_mech(sent, n, only=None, conf=None, reason=""):
        for item in _mechanics_from_sentence(sent, n):
            if only and item["kind"] not in only:
                continue
            key = (item["kind"], str(item["value"]))
            if item["kind"] in ("page_limit", "font", "margins") and \
                    any(k == item["kind"] for k, _ in mech_seen):
                continue
            if key not in mech_seen:
                mech_seen.add(key)
                if conf:
                    item["confidence"], item["check_reason"] = conf, reason
                result["mechanics"].append(item)

    form_refs = set()

    def add_form(form):
        key = form["ref"] or form["name"].lower()
        if key in form_refs:
            return
        form_refs.add(key)
        result["forms"].append(form)
        if re.search(r"insurance", form["text"], re.I) and re.search(r"\$[\d,]+", form["text"]):
            result["insurance"].append({
                "label": "", "text": form["text"], "amounts": _amounts(form["text"]),
                "source": form["source"], "confidence": "check",
                "check_reason": "insurance amount stated in a list of submittals, not an insurance section"})

    def add_insurance(label, text, n, raw, conf="ok", reason=""):
        result["insurance"].append({"label": label or "", "text": text, "amounts": _amounts(text),
                                    "source": _src(n, raw), "confidence": conf, "check_reason": reason})

    def _covered(piece):
        return bool(re.search(r"insurance|liability|coverage|compensation", piece, re.I)) and bool(
            _amounts(piece) or re.search(r"required by law|statutory|law requires|as required by", piece, re.I))

    def insurance_prose(b, conf="ok", reason=""):
        n = 0
        rows = [(ln, _kv(t)) for ln, t in b["raw"]]
        if len(rows) >= 2 and all(kv for _, kv in rows):
            for ln, kv in rows:
                if _covered("%s: %s" % kv):
                    add_insurance("", "%s: %s" % kv, ln, "%s: %s" % kv, conf, reason)
                    n += 1
            return n
        for s in sentences(b["text"]):
            for p in re.split(r";\s*(?:and\s+)?", s):
                p = p.strip()
                if ":" in p and re.search(r"insurance|liability|compensation", p.split(":", 1)[1], re.I) \
                        and not re.search(r"insurance|liability|compensation", p.split(":", 1)[0][-40:], re.I):
                    p = p.split(":", 1)[1].strip()
                if not p or p.endswith(":"):
                    continue
                if not re.search(r"insurance|liability|coverage|compensation", p, re.I):
                    continue
                halves = re.split(r",?\s+and\s+(?=(?:[a-z'’-]+\s+){1,4}(?:insurance|liability|coverage)\b)", p)
                if len(halves) > 1 and all(_covered(h) for h in halves):
                    for h in halves:
                        add_insurance("", h.strip(), b["line"], b["raw"][0][1], conf, reason)
                        n += 1
                    continue
                if not (_amounts(p) or re.search(r"required by law|statutory|law requires|as required by", p, re.I)
                        or (re.search(r"\b(must|shall)\b", p) and re.search(r"statement|certificate|evidence|proof",
                                                                            p, re.I))):
                    continue
                add_insurance("", p, b["line"], b["raw"][0][1], conf, reason)
                n += 1
        return n

    for sec in sections:
        kind, blocks = sec["kind"], _blocks(sec["lines"])
        if kind == "schedule":
            result["deadlines"].extend(_schedule_deadlines(sec["lines"]))
        elif kind == "minquals":
            items = [b for b in blocks if (b["label"] is not None or b["bullet"]) and not b["intro"]]
            for b in items:
                result["min_quals"].append(_min_qual(b["label"], b["text"], b["line"], b["raw"][0][1]))
            if not items:
                for b in blocks:
                    sents = sentences(b["text"])
                    ordinal = [s for s in sents if ORDINAL_RE.match(s)]
                    for s in ordinal:
                        result["min_quals"].append(_min_qual(
                            "", ORDINAL_RE.sub("", s), b["line"], b["raw"][0][1], "check",
                            "qualification stated in a sentence, not a list"))
                    if not ordinal:
                        for s0 in sents:
                            parts = re.split(r",\s+and\s+(?=(?:the|its|each|every)\b)", s0)
                            if not all(re.search(COUNT, p, re.I) for p in parts):
                                parts = [s0]
                            if not re.search(r"\b(must|shall|only if|required to)\b", s0) or re.search(
                                    r"\b(following|below)\b|will not be (evaluated|considered|scored)", s0, re.I):
                                continue
                            for s in parts:
                                result["min_quals"].append(_min_qual(
                                    "", s, b["line"], b["raw"][0][1], "check",
                                    "qualification stated in a sentence, not a list"))
        elif kind == "content":
            first_lab = next((i for i, b in enumerate(blocks) if b["label"] is not None or b["bullet"]), None)
            for i, b in enumerate(blocks):
                if b["label"] is not None:
                    if not b["intro"]:
                        result["requirements"].append(_requirement(b))
                elif b["bullet"]:
                    if FORMLIKE_RE.search(b["text"]) and len(b["text"].split()) <= 14 \
                            and not _REQ_START_RE.match(b["text"]):
                        add_form(_form(b["text"], b["line"], b["raw"][0][1], "check",
                                       "listed as a bullet in the proposal content section, not a forms section"))
                    else:
                        result["requirements"].append(_requirement(b))
                else:
                    sents = sentences(b["text"])
                    has_mech = any(m["kind"] != "not_accepted" for s in sents
                                   for m in _mechanics_from_sentence(s, b["line"]))
                    after_list = first_lab is None or i > first_lab
                    if after_list and not has_mech and DIRECTIVE_RE.search(b["text"]) \
                            and not _CONTENT_SKIP_RE.search(b["text"]):
                        result["requirements"].append(_requirement(b))
                    else:
                        for sent in sents:
                            add_mech(sent, b["line"])
            for b in blocks:  # page-limit exclusions stated inside a question
                if b["label"] is not None:
                    for sent in sentences(b["text"]):
                        if re.search(r"not counted toward the page limit", sent, re.I):
                            add_mech(sent, b["line"])
        elif kind == "forms":
            signed = any(re.search(r"\bsign(ed)?\b", b["text"], re.I) for b in blocks
                         if b["label"] is None and not b["bullet"])
            for b in blocks:
                if b["label"] is not None or b["bullet"]:
                    t = b["text"]
                    modal = bool(re.search(r"\b(may|must|shall|will)\b", t))
                    if b["intro"] or t.endswith(":") or (modal and (
                            re.search(r"\b(following|below)\b", t, re.I)
                            or (len(t.split()) > 8 and not FORMLIKE_RE.search(t)))):
                        continue
                    add_form(_form(t, b["line"], b["raw"][0][1], section_signed=signed))
                else:
                    rows = 0
                    for n, raw in b["raw"]:
                        m = FORM_ROW_RE.match(raw.strip())
                        if m:
                            add_form(_form("%s: %s" % (m.group("ref"), m.group("name")), n, raw,
                                           section_signed=signed))
                            rows += 1
                    if not rows:
                        for m in FORM_INLINE_RE.finditer(b["text"]):
                            add_form(_form("%s: %s" % (m.group("ref"), m.group("name")), b["line"], b["raw"][0][1],
                                           "check", "named in a sentence in the forms section, not in a list",
                                           section_signed=signed))
                            rows += 1
                    if not rows:
                        for sent in sentences(b["text"]):
                            for name in _forms_from_prose(sent):
                                add_form(_form(name, b["line"], b["raw"][0][1], "check",
                                               "named in a sentence in the forms section, not in the list"))
        elif kind == "insurance":
            for b in blocks:
                if b["intro"]:
                    continue
                if b["label"] is not None or b["bullet"]:
                    p = b["text"]
                    if not p or p.endswith(":"):
                        continue
                    if not re.search(r"insurance|liability|coverage|compensation|statement|certificate", p, re.I):
                        continue
                    if len(re.findall(r";", p)) >= 2 and len(_amounts(p)) >= 2:
                        insurance_prose(b)
                    else:
                        add_insurance(b["label"], p, b["line"], b["raw"][0][1])
                else:
                    insurance_prose(b)
        elif kind == "submission":
            for b in blocks:
                for sent in sentences(b["text"]):
                    add_mech(sent, b["line"])
        elif kind == "scope":
            for b in blocks:
                if b["label"] is not None or b["bullet"]:
                    result["scope_items"].append({"label": b["label"] or "", "text": b["text"],
                                                  "source": _src(b["line"], b["raw"][0][1])})

    result["evaluation"] = _evaluation(sections)
    _fallbacks(sections, body, result, add_mech, add_form, insurance_prose)

    # forms mentioned by reference outside the forms list
    for sec in sections:
        if sec["kind"] in ("forms", "preamble"):
            continue
        for n, text, _ in _paragraphs(sec["lines"]):
            for sent in sentences(text):
                for m in re.finditer(FORM_REF, sent):
                    ref = m.group(0)
                    if ref in form_refs or re.search(r"\b(sample|draft)\b", sent, re.I) \
                            or ref.lower() in section_labels:
                        continue
                    if not re.search(r"\b(complete|sign|submit|return|enclose|attach|execute|fill|use)", sent, re.I):
                        continue
                    if re.search(r"\b(selected|successful|chosen|awarded) (firm|proposer|respondent|bidder)|"
                                 r"\b(upon|after) award\b", sent, re.I):
                        continue      # a duty of the firm that wins, not something to send with the proposal
                    form = {"ref": ref, "name": "%s (named in section %s)" % (ref, sec["label"] or sec["title"]),
                            "text": sent, "signature": False, "notarized": False, "mandatory": False,
                            "source": _src(n, sent), "confidence": "check",
                            "check_reason": "referred to in the text but not in the forms list; "
                                            "check whether it must be submitted"}
                    add_form(form)

    result["parties"] = _parties(body, meta)
    result["addenda"] = _apply_addenda(addenda_raw, result)

    # one line per kind of date and day
    seen_dl, kept = set(), []
    for d in result["deadlines"]:
        key = (d["kind"], d["date"])
        if d["kind"] != "unknown" and key in seen_dl:
            continue
        seen_dl.add(key)
        kept.append(d)
    result["deadlines"] = kept

    for i, d in enumerate(result["deadlines"], 1):
        d["id"] = "D%d" % i
    for i, f in enumerate(result["forms"], 1):
        f["id"] = "F%d" % i
    for i, q in enumerate(result["min_quals"], 1):
        q["id"] = "MQ-%s" % (q["label"] or i)
    for i, x in enumerate(result["insurance"], 1):
        x["id"] = "INS%d" % i
    for i, x in enumerate(result["mechanics"], 1):
        x["id"] = "SUB%d" % i

    # things a person must look at
    checks = []
    if not any(d["kind"] == "submission_due" for d in result["deadlines"]):
        checks.append({"category": "deadline", "id": "", "reason": "no submission deadline found"})
    if not result["requirements"]:
        checks.append({"category": "requirement", "id": "", "reason": "no numbered proposal requirements found"})
    if meta["agency_confidence"] != "ok":
        checks.append({"category": "agency", "id": "", "reason": "agency name not confirmed from a defined term"})
    for cat, items in (("deadline", result["deadlines"]), ("requirement", result["requirements"]),
                       ("form", result["forms"]), ("submission", result["mechanics"]),
                       ("insurance", result["insurance"]), ("evaluation", result["evaluation"]["criteria"]),
                       ("party", result["parties"])):
        for it in items:
            if it.get("confidence") == "check":
                checks.append({"category": cat, "id": it.get("id", it.get("name", "")),
                               "reason": it["check_reason"],
                               "text": it.get("text") or it.get("name") or it.get("label") or ""})
    if result["evaluation"]["confidence"] == "check":
        checks.append({"category": "evaluation", "id": "", "reason": result["evaluation"]["check_reason"]})
    for a in result["addenda"]:
        for note in a["notes"]:
            checks.append({"category": "addendum", "id": note["id"], "reason": note["check_reason"],
                           "text": note["text"]})
    result["checks"] = checks
    return result


_FALLBACK_KINDS = ("submission_due", "questions_due", "answers_issued", "interview", "conference", "award")
_ISSUED_LINE_RE = re.compile(r"^\s*(?:DATE|Date|Dated|Issued|Date [Ii]ssued|Issue [Dd]ate|Date of [Ii]ssue|Released|"
                             r"Release [Dd]ate)\b\s*[.:…]*\s*\S")


def _fallbacks(sections, body, result, add_mech, add_form, insurance_prose):
    """Search the whole body for kinds of item that their own section did not yield."""
    why = "found outside the section where it was expected; confirm"
    have = {d["kind"] for d in result["deadlines"]}
    if not all(k in have for k in ("submission_due", "questions_due")) or len(have) < 3:
        for sec in sections:
            if sec["kind"] in ("schedule", "scope"):
                continue
            for n, text, raw in _paragraphs(sec["lines"]):
                found = []
                for ln, t in raw:
                    if find_dates(t) and re.search(r"\.{3,}|:\s|\s{3,}", t.strip()):
                        d = _deadline_from_line(ln, t)
                        if d:
                            found.append(d)
                if not found and sec["kind"] != "preamble":
                    found = _deadlines_from_prose(n, text)
                for d in found:
                    if d["kind"] in _FALLBACK_KINDS and d["kind"] not in have:
                        if d["kind"] == "award" and not re.search(r"award|recommendation", d["source"]["text"], re.I):
                            continue
                        d["confidence"], d["check_reason"] = "check", why
                        result["deadlines"].append(d)
                        have.add(d["kind"])
    if "issued" not in have:
        for n, t in body[:25]:
            if _ISSUED_LINE_RE.match(t) and find_dates(t):
                d = _deadline_from_line(n, t)
                d.update({"kind": "issued", "label": "RFP issued", "confidence": "check",
                          "check_reason": "date taken from the heading of the document"})
                result["deadlines"].append(d)
                break
    if any(d["check_reason"] in (why, "date taken from the heading of the document") for d in result["deadlines"]):
        result["deadlines"].sort(key=lambda d: (d["date"] or "9999"))

    mech_have = {m["kind"] for m in result["mechanics"]}
    wanted = {"page_limit", "font", "margins", "copies", "format", "packaging", "delivery", "not_accepted",
              "page_exclusions"} - mech_have
    for sec in sections:      # data-sheet rows: "Page limit ....: 20 pages"
        if sec["kind"] in ("submission", "evaluation", "insurance", "scope"):
            continue
        for n, raw in sec["lines"]:
            kv = _kv(raw)
            if kv and re.search(r"page|font|type|margin|cop(y|ies)|deliver|format|accept|submit|packag", kv[0], re.I):
                sent = "%s: %s" % kv
                if re.match(r"deliver|submit", kv[0], re.I) and not re.search(r"\bdeliver", kv[1], re.I):
                    sent = "%s: deliver %s" % kv
                add_mech(sent, n, only=wanted, conf="check", reason=why)
    mech_have = {m["kind"] for m in result["mechanics"]}
    wanted -= mech_have
    if "page_limit" in wanted or not any(s["kind"] == "submission" for s in sections):
        for sec in sections:
            if sec["kind"] in ("submission", "scope", "preamble", "evaluation", "insurance"):
                continue
            for b in _blocks(sec["lines"]):
                if b["label"] is not None and sec["kind"] == "content":
                    continue
                for sent in sentences(b["text"]):
                    if not re.search(r"proposal|response|submittal|answers|statement of qualifications", sent, re.I) \
                            and not re.search(r"font|type|margin", sent, re.I):
                        continue
                    add_mech(sent, b["line"], only=wanted, conf="check", reason=why)

    if not result["requirements"]:
        best = []
        for sec in sections:
            if sec["kind"] in ("scope", "minquals", "forms", "insurance", "evaluation", "schedule", "submission",
                               "preamble"):
                continue
            run = []
            for b in _blocks(sec["lines"]):
                if (b["label"] is not None or b["bullet"]) and not b["intro"] and (
                        _REQ_START_RE.match(b["text"]) or b["text"].rstrip().endswith("?")
                        or TITLE_RE.match(b["text"])):
                    run.append(b)
            if len(run) > len(best):
                best = run
        if len(best) >= 4:
            for b in best:
                result["requirements"].append(_requirement(b, why))

    if not result["evaluation"]["criteria"]:
        for sec in sections:
            if sec["kind"] in ("evaluation", "preamble", "scope"):
                continue
            ev = _evaluation([dict(sec, kind="evaluation")])
            ws = [c["weight"] for c in ev["criteria"] if c["weight"] is not None]
            if len(ws) >= 3 and sum(ws) == 100:
                for c in ev["criteria"]:
                    c["confidence"], c["check_reason"] = "check", why
                result["evaluation"] = ev
                break

    if not result["insurance"]:
        for sec in sections:
            if sec["kind"] in ("preamble", "scope", "evaluation", "schedule"):
                continue
            for b in _blocks(sec["lines"]):
                if re.search(r"insurance|liability", b["text"], re.I) and _amounts(b["text"]):
                    insurance_prose(b, "check", why)

    if not result["forms"]:
        for sec in sections:
            if sec["kind"] in ("preamble",):
                continue
            for n, raw in sec["lines"]:
                m = FORM_ROW_RE.match(re.sub(r"^(?:\[[ xX_]?\]|[-*•\u2610\u25a1]|\(?[a-z0-9]{1,3}[.)])\s+", "", raw.strip()))
                if m and len(m.group("name").split()) <= 10 and not re.search(r"\b(is|are|was|will|shall|must)\b",
                                                                              m.group("name")):
                    add_form(_form("%s: %s" % (m.group("ref"), m.group("name")), n, raw, "check", why))


def submission_deadline(rfp):
    """The submission deadline in force, or None."""
    for d in rfp["deadlines"]:
        if d["kind"] == "submission_due" and d["date"]:
            return d
    return None


def page_limit(rfp):
    for m in rfp["mechanics"]:
        if m["kind"] == "page_limit":
            return m
    return None
