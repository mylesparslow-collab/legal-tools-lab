"""Deterministic RFP parser.

Input is the plain text of a request for proposals. Output is a plain dict
(JSON-serialisable). Requirements are whatever the RFP text says; nothing here
knows any procurement rule. Every extracted item keeps the line it came from.
Items the parser is unsure about get confidence "check" and a reason; they are
never dropped silently.
"""
import re

from .util import (COUNT, count_value, find_dates, find_time, norm_ws, sentences)

# ---------------------------------------------------------------- sections

SECTION_KINDS = [
    ("minquals", r"minimum (qualif|requirement)|who may propose|eligib"),
    ("content", r"proposal must contain"),
    ("forms", r"\bforms\b|certifications|attachments\b"),
    ("evaluation", r"evaluat|selection|scoring|how we will choose|criteria|judged"),
    ("insurance", r"insurance"),
    ("schedule", r"schedule|timeline|key dates|important dates|calendar"),
    ("content", r"proposal (content|requirements|sections)|required proposal|what to submit|"
                r"contents of (the )?proposal"),
    ("submission", r"submission|submittal|how to submit|delivery|\bformat\b|instructions|sending in"),
    ("scope", r"scope|services requested|services required"),
    ("parties", r"officials|board of (directors|trustees)|city council|contacts"),
    ("intro", r"introduction|background|overview|purpose|general information"),
]

ADDENDUM_HEAD_RE = re.compile(r"^\s*ADDENDUM\s+(?:NO\.?\s*|NUMBER\s*|#\s*)?(\d+)\b(.*)$")
TOP_NUM_RE = re.compile(r"^\s*(\d{1,2})\.\s+([A-Z][A-Z0-9 ,&/\-']+)$")
TOP_WORD_RE = re.compile(r"^\s*(SECTION|PART|ARTICLE|Section|Part|Article)\s+([IVXLC]+|[A-Z]|\d+)\s*[-–:.]\s*"
                         r"([A-Z][^.;]{2,70})$")
CAPS_RE = re.compile(r"^[A-Z][A-Z ,&/\-']{3,}$")
SUB_RE = re.compile(r"^\s*([A-Z]\.\d+|\d+\.\d+)\s+([A-Z][^.:;?]{2,60})$")

LABEL_RE = re.compile(
    r"^(?P<label>"
    r"[A-Z]\.\d+(?:\.\d+)*"
    r"|\d+(?:\.\d+)+"
    r"|Q\d+\)"
    r"|Tab\s+\d+\s*[-–:]"
    r"|Item\s+\d+\."
    r"|\([a-z0-9]{1,3}\)"
    r"|[A-Z]\."
    r"|\d{1,2}[.)]"
    r")\s+(?P<rest>\S.*)$")
BULLET_RE = re.compile(r"^[-*•]\s+(?P<rest>\S.*)$")


def classify_heading(title):
    low = title.lower()
    for kind, pat in SECTION_KINDS:
        if re.search(pat, low):
            return kind
    return None


def _segment(lines):
    """lines: list of (lineno, text). Returns sections with their own lines."""
    sections = [{"kind": "preamble", "title": "", "label": "", "line": 1, "lines": [], "level": 0}]
    parent_kind = "preamble"
    for idx, (n, raw) in enumerate(lines):
        s = raw.strip()
        prev_blank = idx == 0 or not lines[idx - 1][1].strip()
        head = None
        m = TOP_NUM_RE.match(raw)
        if m:
            head = (m.group(1), m.group(2).strip(), 1)
        if not head:
            m = TOP_WORD_RE.match(raw)
            if m:
                head = ("%s %s" % (m.group(1), m.group(2)), m.group(3).strip(), 1)
        if not head and s and CAPS_RE.match(s) and len(s.split()) <= 8 and prev_blank:
            kind = classify_heading(s)
            if kind or len(sections) > 1:
                head = ("", s, 1)
        if head and head[2] == 1:
            kind = classify_heading(head[1]) or "other"
            parent_kind = kind
            sections.append({"kind": kind, "title": head[1], "label": head[0], "line": n,
                             "lines": [], "level": 1})
            continue
        m = SUB_RE.match(raw)
        if m and len(m.group(2).split()) <= 6:
            kind = classify_heading(m.group(2))
            if kind:
                sections.append({"kind": kind, "title": m.group(2).strip(), "label": m.group(1),
                                 "line": n, "lines": [], "level": 2})
                continue
        sections[-1]["lines"].append((n, raw))
    return sections


def _blocks(lines):
    """Group section lines into blocks: a labelled item, a bullet, or a paragraph."""
    out, cur = [], None

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
        m = LABEL_RE.match(s)
        b = BULLET_RE.match(s)
        if m:
            close()
            label = norm_ws(m.group("label").rstrip(".)-–: "))
            if label.startswith("("):
                label = label.strip("()")
            cur = {"label": label, "bullet": False, "line": n, "raw": [(n, raw)],
                   "parts": [(n, m.group("rest"))]}
        elif b:
            close()
            cur = {"label": None, "bullet": True, "line": n, "raw": [(n, raw)],
                   "parts": [(n, b.group("rest"))]}
        elif cur is None:
            cur = {"label": None, "bullet": False, "line": n, "raw": [(n, raw)], "parts": [(n, s)]}
        else:
            cur["raw"].append((n, raw))
            cur["parts"].append((n, s))
    close()
    return out


def _src(n, text):
    return {"line": n, "text": norm_ws(text)}


# ---------------------------------------------------------------- deadlines

DEADLINE_KINDS = [
    ("answers_issued", r"respons|answers|addend"),
    ("questions_due", r"question|clarification|inquir"),
    ("conference", r"conference|site visit|walk-?through"),
    ("interview", r"interview|oral presentation|presentation"),
    ("submission_due", r"proposals?\s+(are\s+)?due|proposal (submission )?deadline|submission deadline|"
                       r"submittal|due date|proposals must be received"),
    ("award", r"award|council|board (action|approval|consideration)|approval"),
    ("issued", r"issued|release"),
    ("start", r"start|commence|effective"),
]
DEADLINE_LABELS = {
    "issued": "RFP issued", "conference": "Pre-proposal conference", "questions_due": "Questions due",
    "answers_issued": "Answers issued", "submission_due": "Submission due", "interview": "Interviews",
    "award": "Award or board action", "start": "Start of services", "unknown": "Date (kind not recognised)",
}


def classify_deadline(label):
    low = label.lower()
    for kind, pat in DEADLINE_KINDS:
        if re.search(pat, low):
            return kind
    return "unknown"


def _deadline_from_line(n, raw):
    dates = find_dates(raw)
    if not dates:
        return None
    first = dates[0]
    label = raw[:first["start"]]
    label = re.sub(r"\b(Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)[a-z]*\.?,?\s*$", "", label.strip())
    label = re.sub(r"[\s.:…\-]+$", "", label).strip()
    label = re.sub(r"\s*\bweek of$", "", label, flags=re.I).strip(" .:-")
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
    return {"kind": kind, "label": label or DEADLINE_LABELS.get(kind, ""), "date": first["date"],
            "end_date": first["end"], "time": find_time(raw[first["stop"]:]) or find_time(raw),
            "source": _src(n, raw), "confidence": "check" if reasons else "ok",
            "check_reason": "; ".join(reasons), "changed_by": None, "original_date": None,
            "original_time": None}


# ---------------------------------------------------------------- mechanics

PAGE_LIMIT_RE = re.compile(
    r"(?:not (?:to )?exceed|limited to|no more than|maximum of|limit of|longer than)\s+(" + COUNT + r")\s+pages", re.I)
EXCL_RE = re.compile(r"(?:excluding|not counting|exclusive of)\s+(.+?)(?:,\s*(?:must|shall)\b|\.?$)", re.I)
COPIES_RE = re.compile(
    r"\b(" + COUNT + r")\s+((?:unbound|bound|electronic|paper|hard|printed)\s+)?"
    r"(originals?|cop(?:y|ies)|USB drives?|PDF)\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


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
    elif re.search(r"not counted toward the page limit", sent, re.I):
        add("page_exclusions", sent, confidence="check",
            check_reason="exclusion stated away from the page limit; read the sentence")
    if re.search(r"will not be (accepted|considered)", sent, re.I):
        add("not_accepted", sent)
    else:
        copies = [(m.group(0)) for m in COPIES_RE.finditer(sent)]
        if copies:
            add("copies", "; ".join(norm_ws(c) for c in copies))
        if re.search(r"\bPDF\b", sent):
            add("format", "separate PDF files" if re.search(r"separate", sent, re.I) else "PDF")
        if re.search(r"sealed envelope", sent, re.I):
            add("packaging", "sealed envelope")
        email = EMAIL_RE.search(sent)
        if email and re.search(r"\b(submit|email|send|deliver)", sent, re.I):
            add("delivery", "email to " + email.group(0).rstrip("."))
        elif re.search(r"\bportal\b", sent, re.I):
            add("delivery", "online portal")
        elif re.search(r"\b(deliver|mail)\b.*\bto\b", sent, re.I):
            add("delivery", "physical delivery")
    m = re.search(r"(\d{1,2})[- ]?point\b", sent, re.I)
    if m:
        add("font", int(m.group(1)))
    m = re.search(r"(one|1|\d(?:\.\d+)?)[- ]inch margins|margins of (?:at least )?(\d(?:\.\d+)?|one)[- ]inch",
                  sent, re.I)
    if m:
        v = (m.group(1) or m.group(2)).lower()
        add("margins", 1.0 if v == "one" else float(v))
    return out


# ---------------------------------------------------------------- requirements

QTYPE_RULES = [
    ("cover_letter", r"cover letter|letter of transmittal|transmittal"),
    ("conflicts", r"conflicts?\b|relationship with"),
    ("rates", r"\bfees?\b|\brates?\b|compensation|cost proposal|pricing|retainer"),
    ("references", r"references?\b"),
    ("transition", r"transition|continuity"),
    ("disclosure", r"litigation|discipline|disciplinary|malpractice|exceptions?\b"),
    ("diversity_local", r"\blocal\b|diversity|small business|disadvantaged"),
    ("team", r"\bteam\b|personnel|staffing|who would be|resumes"),
    ("experience", r"experience|engagements"),
    ("approach", r"approach|work plan|methodolog|how (do|will|would) (you|the firm)"),
    ("firm_overview", r"firm (overview|profile|qualifications)|about your firm|describe the firm|firm history"),
]
QTYPE_LABELS = {
    "cover_letter": "Cover letter", "firm_overview": "Firm overview", "approach": "Approach",
    "team": "Team", "experience": "Experience", "references": "References", "conflicts": "Conflicts",
    "rates": "Rates and fees", "diversity_local": "Diversity and local presence",
    "transition": "Transition plan", "disclosure": "Disclosures and exceptions", "other": "Other",
}
PERSON_QTYPES = {"cover_letter", "conflicts", "rates", "disclosure"}
TITLE_RE = re.compile(r"^([A-Z][A-Za-z ,/&\-']{2,60}?)[.:]\s+(?=\S)")


def classify_question(title, text):
    for chunk in (title, text):
        if not chunk:
            continue
        low = chunk.lower()
        for qtype, pat in QTYPE_RULES:
            if re.search(pat, low):
                return qtype
    return "other"


def _requirement(block):
    text = block["text"]
    title = ""
    m = TITLE_RE.match(text)
    if m and len(m.group(1).split()) <= 7:
        title = m.group(1).strip()
    qtype = classify_question(title, text)
    optional = bool(re.search(r"\boptional\b", text, re.I))
    reasons = []
    if qtype == "other":
        reasons.append("question type not recognised")
    if block["label"] is None:
        reasons.append("unnumbered item in the proposal content section")
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

FORM_REF = r"(?:Form|Attachment|Exhibit|Appendix)\s+[A-Z0-9]{1,3}\b"
FORM_LINE_RE = re.compile(r"^(?P<ref>" + FORM_REF + r")\s*[-–:]\s*(?P<name>.+)$")
FORMLIKE_RE = re.compile(r"certif|acknowledg|attachment|\bform\b|affidavit|declaration|proof of|disclosure", re.I)


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


# ---------------------------------------------------------------- evaluation

EVAL_RE = re.compile(r"^(?P<name>.*?[A-Za-z)])[\s.\-–:(]*?(?P<w>\d{1,3})\s*(?P<unit>%|percent|points?|pts\.?)?\)?\s*$")


EVAL_WEIGHT_FIRST_RE = re.compile(
    r"^(?:weight\s*:?\s*)?(?P<w>\d{1,3})\s*(?P<unit>%|percent|points?|pts\.?)\s*[-–:]\s*(?P<name>.+)$", re.I)


def _evaluation(sections):
    criteria, total_stated, unit = [], None, None
    for sec in sections:
        if sec["kind"] != "evaluation":
            continue
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
                    name = m.group("name").strip(" .-–:(")
                    w = int(m.group("w"))
                    if m.group("unit"):
                        unit = "percent" if m.group("unit").lower() in ("%", "percent") else "points"
                    if name.lower() in ("total", "total points", "maximum total"):
                        total_stated = w
                        continue
                    criteria.append({"name": name, "weight": w, "source": _src(n, raw),
                                     "confidence": "ok", "check_reason": ""})
                elif re.search(r"\b(criterion|criteria|weight|points|maximum|score)\b", s, re.I):
                    continue  # column header
                elif not s.endswith((":", ".")) and len(s.split()) <= 10:
                    criteria.append({"name": s, "weight": None, "source": _src(n, raw),
                                     "confidence": "check",
                                     "check_reason": "criterion listed without a weight"})
    total = sum(c["weight"] for c in criteria if c["weight"] is not None)
    reasons = []
    if criteria and total_stated is not None and total_stated != total:
        reasons.append("weights add to %d but the RFP states a total of %d" % (total, total_stated))
    if criteria and unit == "percent" and total != 100:
        reasons.append("percent weights add to %d, not 100" % total)
    if any(c["weight"] is None for c in criteria):
        reasons.append("at least one criterion has no weight")
    for i, c in enumerate(criteria, 1):
        c["id"] = "EV%d" % i
    return {"criteria": criteria, "total": total, "total_stated": total_stated,
            "unit": unit or ("points" if criteria else None),
            "confidence": "check" if reasons else "ok", "check_reason": "; ".join(reasons)}


# ---------------------------------------------------------------- minimum qualifications

_ATLEAST = r"(?:at least|a minimum of|minimum of|no fewer than|not less than|no less than)"


def classify_min_qual(text):
    """Return (check_kind, value). Only kinds that bio or firm data can check are named."""
    m = re.search(r"\b(?:" + _ATLEAST + r"\s+)?(" + COUNT + r")\s+years\b", text, re.I)
    if m and re.search(r"admitted|admission|licensed", text, re.I):
        return "years_admitted", count_value(m.group(1))[0]
    m = re.search(r"\boffice\s+(?:located\s+)?(?:within|in)\s+(.+?)(?:\s+or\b|[.;,]|$)", text, re.I)
    if m:
        place = m.group(1).strip()
        if re.match(r"(?:the|its|a|an)\b", place, re.I) or re.search(r"\bor\b", text):
            return "not_checkable", None
        return "office_location", place
    m = re.search(_ATLEAST + r"\s+(" + COUNT + r")\s+attorneys\b", text, re.I)
    if m:
        return "attorney_count", count_value(m.group(1))[0]
    return "not_checkable", None


# ---------------------------------------------------------------- parties

ROLE_RE = re.compile(
    r"(Vice Mayor|Mayor|Council ?[Mm]embers?|City Manager|Deputy City Clerk|City Clerk|General Manager|"
    r"Vice President|President|Directors?|Trustees?|Assistant Superintendent|Superintendent|"
    r"Executive Director|General Counsel|Chief [A-Z][a-z]+(?: [A-Z][a-z]+)* Officer|Contracting Officer|"
    r"District Secretary|Clerk|Chair|Vice Chair|Commissioners?|Supervisors?)")
PARTY_TRIGGER_RE = re.compile(ROLE_RE.pattern + r"|Board of (?:Directors|Trustees)|Board members|City Council:")
BOARD_ROLES = {"mayor", "vice mayor", "councilmember", "council member", "president", "vice president",
               "director", "trustee", "chair", "vice chair", "commissioner", "supervisor"}
NAME_TOKEN_RE = re.compile(r"(?:O['’])?[A-Z][a-z]+(?:[A-Z][a-z]+)?(?:[-'’][A-Z][a-z]+)*")
NAME_STOP = set("""The A An Board Directors Director President Vice General Manager District City Council
Mayor Water Authority State County Human Resources Assistant Superintendent Executive Chief Officer
Counsel Contracting Clerk Deputy Trustees Trustee Capital Programs Secretary Councilmember Member
Members Road Street Avenue Suite Drive Way Boulevard Lane Proposals Proposers Proposal Section
Attorney Planning Commission Special Request Division Unified School Transit Dr Mr Ms Mrs Chair
Commissioner Commissioners Supervisor Supervisors Do Email Paper Subject Direct Late Use Submit
January February March April May June July August September October November December Monday
Tuesday Wednesday Thursday Friday Saturday Sunday Exhibit Attachment Form Appendix Addendum
Letter Transmittal Agreement Department Office Services Legal Finance Public Works Committee""".split())
ORG_RE = re.compile(
    r"((?:[A-Z][A-Za-z&'’-]+\s+){1,5}"
    r"(?:(?:Association|Union|Federation|Constructors|Company|Corporation|Partners|Properties|Systems|"
    r"Group|Builders|Contractors|Holdings)(?:,?\s+(?:Inc\.?|LLC|LP|LLP|Corp\.?|Co\.))?"
    r"|(?:,\s*)?(?:Inc\.?|LLC|LP|LLP|Corp\.)))")
ADVERSE_RE = re.compile(r"dispute|claim|adverse|litigation|lawsuit|negotiat|employee organizations|\bv\.", re.I)
AGENCY_DEF_RE = re.compile(
    r"((?:[A-Z][a-z]+|of)(?: (?:[A-Z][a-z]+|of|and))*)\s+\((?:the\s+)?[\"“]"
    r"(City|District|Authority|Town|County|Agency|Commission)[\"”]\)")
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
    for n, raw in lines + [(0, "")]:
        if raw.strip():
            cur.append((n, raw))
        elif cur:
            out.append((cur[0][0], norm_ws(" ".join(t for _, t in cur)), cur))
            cur = []
    return out


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


def _role_for(text, start, stop_idx):
    """Role stated next to a name: '(Role)' after it, 'Role Name' before it, or 'Name, Role'."""
    after = text[stop_idx:stop_idx + 60]
    m = re.match(r"\s*\(\s*(" + ROLE_RE.pattern + r")", after)
    if m:
        return m.group(1)
    before = text[max(0, start - 60):start]
    m = None
    for m in ROLE_RE.finditer(before):
        pass
    if m and re.fullmatch(r"(?:\s*:?\s*|\s+is\s+)", before[m.end():]):
        return m.group(1)
    m = re.match(r"\s*,\s*(" + ROLE_RE.pattern + r")", after)
    if m:
        return m.group(1)
    return ""


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
        if PARTY_TRIGGER_RE.search(text):
            boardish = bool(re.search(r"Board of (?:Directors|Trustees)|Board members|City Council:", text))
            for start, stop_idx, name in _people_in(text, stop):
                if name in seen:
                    continue
                role = ""
                for _, rl in raw:  # look on the line that holds the name first
                    k = rl.find(name)
                    if k >= 0:
                        role = _role_for(rl, k, k + len(name))
                        break
                if not role:
                    role = _role_for(text, start, stop_idx)
                base = re.sub(r"s$", "", role.lower())
                if base in BOARD_ROLES or (boardish and base in ("", "clerk")):
                    cat = "board"
                else:
                    cat = "staff"
                item = {"name": name, "category": cat, "role": role or "Named in the RFP",
                        "source": _src(n, text[:240]),
                        "confidence": "ok" if role or boardish else "check",
                        "check_reason": "" if role or boardish else "role not stated next to the name"}
                seen[name] = item
                parties.append(item)
        for sent in sentences(text):
            for m in ORG_RE.finditer(sent):
                name = re.sub(r"^The\s+", "", m.group(1).strip())
                name = re.sub(r"\s+", " ", name)
                if name in seen or name.rstrip(".") in seen or (agency and name.startswith(agency)):
                    continue
                adverse = bool(ADVERSE_RE.search(sent))
                item = {"name": name, "category": "adverse" if adverse else "other_organisation",
                        "role": "Adverse or counter-party mentioned in the RFP" if adverse
                        else "Organisation mentioned in the RFP",
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
    m = re.search(r"(?i:RFP|Solicitation|Proposals)\s*(?i:No\.?|Number)?\s*:?\s*#?\s*([A-Z0-9]+(?:-[A-Z0-9]+)+)", text)
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

CHANGE_VERB_RE = re.compile(r"changed|rescheduled|extended|revised|moved|postponed|is now", re.I)


def _apply_addenda(addenda_raw, result):
    addenda = []
    for number, head_line, head_rest, lines in addenda_raw:
        issued = find_dates(head_rest) or find_dates(" ".join(t for _, t in lines[:3]))
        entry = {"number": number, "issued": issued[0]["date"] if issued else None,
                 "source": _src(head_line, "ADDENDUM %s%s" % (number, head_rest)), "changes": [], "notes": []}
        blocks = _blocks(lines)
        for b in blocks:
            if b["label"] is None:
                continue  # issue line or free text between items
            text = b["text"]
            src = _src(b["line"], text)
            dates = find_dates(text)
            handled = False
            if dates and CHANGE_VERB_RE.search(text):
                kind = classify_deadline(text)
                new = dates[-1]
                old = dates[0] if len(dates) > 1 else None
                new_time = find_time(text[new["stop"]:])
                target = None
                same = [d for d in result["deadlines"] if d["kind"] == kind]
                if old:
                    target = next((d for d in same if d["date"] == old["date"]), None)
                target = target or (same[0] if same else None)
                reason = ""
                if kind == "unknown" or target is None:
                    reason = "addendum changes a date that was not matched to a schedule line"
                elif old and target["date"] != old["date"]:
                    reason = "addendum says the old date was %s but the schedule had %s" % (
                        old["date"], target["date"])
                if target is not None and kind != "unknown":
                    change = {"type": "deadline", "kind": kind, "from": target["date"],
                              "from_time": target["time"], "to": new["date"],
                              "to_time": new_time or target["time"], "source": src,
                              "confidence": "check" if reason else "ok", "check_reason": reason}
                    target.update({"original_date": target["date"], "original_time": target["time"],
                                   "date": new["date"], "end_date": new["end"],
                                   "time": new_time or target["time"],
                                   "changed_by": "Addendum %s" % number, "change_source": src})
                    if reason:
                        target["confidence"], target["check_reason"] = "check", reason
                    entry["changes"].append(change)
                else:
                    d = _deadline_from_line(b["line"], text)
                    d.update({"kind": kind, "date": new["date"], "changed_by": "Addendum %s" % number,
                              "confidence": "check", "check_reason": reason})
                    result["deadlines"].append(d)
                    entry["changes"].append({"type": "deadline", "kind": kind, "from": None, "from_time": None,
                                             "to": new["date"], "to_time": new_time, "source": src,
                                             "confidence": "check", "check_reason": reason})
                handled = True
            m = PAGE_LIMIT_RE.search(text)
            if m and not handled:
                val = count_value(m.group(1))[0]
                old_item = next((x for x in result["mechanics"] if x["kind"] == "page_limit"), None)
                entry["changes"].append({"type": "page_limit", "kind": "page_limit",
                                         "from": old_item["value"] if old_item else None, "to": val,
                                         "source": src, "confidence": "ok", "check_reason": ""})
                if old_item:
                    old_item.update({"original_value": old_item["value"], "value": val,
                                     "changed_by": "Addendum %s" % number, "change_source": src})
                else:
                    result["mechanics"].append({"kind": "page_limit", "value": val, "source": src,
                                                "confidence": "ok", "check_reason": "",
                                                "changed_by": "Addendum %s" % number})
                handled = True
            m = re.search(r"(" + FORM_REF + r")\s*[-–:]\s*(.+?)\s+(?:is|are)\s+(?:hereby\s+)?added", text)
            if m and not handled:
                form = _form("%s: %s" % (m.group(1), m.group(2)), b["line"], text)
                form["added_by"] = "Addendum %s" % number
                result["forms"].append(form)
                entry["changes"].append({"type": "form_added", "kind": "form_added", "from": None,
                                         "to": form["name"], "source": src, "confidence": "ok",
                                         "check_reason": ""})
                handled = True
            if not handled:
                entry["notes"].append({"id": "ADD%s-%s" % (number, b["label"].replace("Item ", "")),
                                       "text": text, "source": src, "confidence": "check",
                                       "check_reason": "addendum item not applied automatically; read it"})
        addenda.append(entry)
    return addenda


# ---------------------------------------------------------------- main

def parse_rfp(text):
    all_lines = [(i + 1, ln.expandtabs(4)) for i, ln in enumerate(text.splitlines())]
    heads = [i for i, (_, ln) in enumerate(all_lines) if ADDENDUM_HEAD_RE.match(ln)]
    body = all_lines[:heads[0]] if heads else all_lines
    addenda_raw = []
    for j, i in enumerate(heads):
        m = ADDENDUM_HEAD_RE.match(all_lines[i][1])
        end = heads[j + 1] if j + 1 < len(heads) else len(all_lines)
        addenda_raw.append((m.group(1), all_lines[i][0], m.group(2), all_lines[i + 1:end]))

    sections = _segment(body)
    meta = _meta(body, sections)
    result = {"meta": meta, "deadlines": [], "mechanics": [], "requirements": [], "forms": [],
              "min_quals": [], "insurance": [], "scope_items": [], "parties": [],
              "sections": [{"kind": s["kind"], "title": s["title"], "label": s["label"], "line": s["line"]}
                           for s in sections if s["kind"] != "preamble"]}

    mech_seen = set()

    def add_mech(sent, n):
        for item in _mechanics_from_sentence(sent, n):
            key = (item["kind"], str(item["value"]))
            if key not in mech_seen:
                mech_seen.add(key)
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
                "text": form["text"], "amounts": re.findall(r"\$[\d,]+(?:\s+million)?", form["text"]),
                "source": form["source"], "confidence": "check",
                "check_reason": "insurance amount stated in a list of submittals, not an insurance section"})

    for sec in sections:
        kind, blocks = sec["kind"], _blocks(sec["lines"])
        if kind == "schedule":
            for n, raw in sec["lines"]:
                d = _deadline_from_line(n, raw)
                if d:
                    result["deadlines"].append(d)
        elif kind == "minquals":
            for b in blocks:
                if b["label"] is None and not b["bullet"]:
                    continue
                ck, val = classify_min_qual(b["text"])
                result["min_quals"].append({
                    "label": b["label"] or "", "text": b["text"], "check_kind": ck, "value": val,
                    "source": _src(b["line"], b["raw"][0][1]), "confidence": "ok", "check_reason": ""})
        elif kind == "content":
            for b in blocks:
                if b["label"] is not None:
                    result["requirements"].append(_requirement(b))
                elif b["bullet"]:
                    if FORMLIKE_RE.search(b["text"]):
                        add_form(_form(b["text"], b["line"], b["raw"][0][1], "check",
                                       "listed as a bullet in the proposal content section, not a forms section"))
                    else:
                        result["requirements"].append(_requirement(b))
                else:
                    for sent in sentences(b["text"]):
                        add_mech(sent, b["line"])
            for b in blocks:  # page-limit exclusions stated inside a question
                if b["label"] is not None:
                    for sent in sentences(b["text"]):
                        if re.search(r"not counted toward the page limit", sent, re.I):
                            add_mech(sent, b["line"])
        elif kind == "forms":
            signed = any(re.search(r"\bsigned\b", b["text"], re.I) for b in blocks
                         if b["label"] is None and not b["bullet"])
            for b in blocks:
                if b["label"] is not None or b["bullet"]:
                    add_form(_form(b["text"], b["line"], b["raw"][0][1], section_signed=signed))
                else:
                    for n, raw in b["raw"]:
                        if FORM_LINE_RE.match(raw.strip()):
                            add_form(_form(raw.strip(), n, raw, section_signed=signed))
        elif kind == "insurance":
            for b in blocks:
                if b["label"] is not None or b["bullet"]:
                    pieces = [b["text"]]
                else:
                    pieces = [p.strip() for s in sentences(b["text"]) for p in re.split(r";\s*(?:and\s+)?", s)]
                for p in pieces:
                    if not p or p.endswith(":"):
                        continue
                    if not re.search(r"insurance|liability|coverage|compensation|statement|certificate", p, re.I):
                        continue
                    result["insurance"].append({
                        "text": p, "amounts": re.findall(r"\$[\d,]+(?:\s+million)?", p),
                        "source": _src(b["line"], b["raw"][0][1]), "confidence": "ok", "check_reason": ""})
        elif kind == "submission":
            for b in blocks:
                for sent in sentences(b["text"]):
                    add_mech(sent, b["line"])
        elif kind == "scope":
            for b in blocks:
                if b["label"] is not None or b["bullet"]:
                    result["scope_items"].append({"label": b["label"] or "", "text": b["text"],
                                                  "source": _src(b["line"], b["raw"][0][1])})

    # forms mentioned by reference outside the forms list
    for sec in sections:
        if sec["kind"] in ("forms", "preamble"):
            continue
        for n, text, _ in _paragraphs(sec["lines"]):
            for sent in sentences(text):
                for m in re.finditer(FORM_REF, sent):
                    ref = m.group(0)
                    if ref in form_refs or re.search(r"\b(sample|draft)\b", sent, re.I):
                        continue
                    form = {"ref": ref, "name": "%s (named in section %s)" % (ref, sec["label"] or sec["title"]),
                            "text": sent, "signature": False, "notarized": False, "mandatory": False,
                            "source": _src(n, sent), "confidence": "check",
                            "check_reason": "referred to in the text but not in the forms list; "
                                            "check whether it must be submitted"}
                    add_form(form)

    result["evaluation"] = _evaluation(sections)
    result["parties"] = _parties(body, meta)
    result["addenda"] = _apply_addenda(addenda_raw, result)

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
