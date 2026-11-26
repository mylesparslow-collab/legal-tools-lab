"""Wider wording for the keyword-based checks.

The client's guideline JSON carries phrase lists. Timekeepers describe the same
work in many other ways, so the engine also uses the patterns here. They were
written from general knowledge and from the misses on held-out batch A; none is
keyed to a client, an invoice or a line.

Three kinds of thing live here:

- concept patterns: wider wording for travel, research, internal conferences,
  attendance at an event, clerical work, training, conflicts checks, invoice
  preparation, meals and lodging, and mentions of AI tools;
- expansions: related wording that is used only when the client's own list
  holds the base phrase (for example toner and binder tabs when the client
  lists "office supplies");
- guards: listed words that have a second, billable meaning ("filing" a motion,
  the insured's "training" files) are not flagged in that second meaning.

All of this is pattern matching. It will miss wording nobody thought of and
will sometimes match wording it should not. Findings say when they come from
the wider wording and not from the client's own list.
"""

import re

I = re.I

# ------------------------------------------------------------------ travel

_TRAVEL_NOUNS = r"(?:records?|polic(?:y|ies)|expenses?|costs?|itinerar(?:y|ies)|vouchers?|receipts?|agent|agency|logs?|arrangements?|ban|documents?|history|restrictions?|reimbursement)"
TRAVEL = re.compile(
    r"\btravel(?:l?ing|led|ed|s)?\b(?!\s+" + _TRAVEL_NOUNS + r"\b)"
    r"|\b(?:drive|drove|driving|driven|fly|flew|flying|flown|ride|rode|riding)\s+(?:to|from|back|between|out to|up to|down to|over to|home)\b"
    r"|\bflights?\s+(?:to|from|time|home|back)\b"
    r"|\bround[- ]?trip\b|\breturn (?:trip|journey|flight|drive)\b|\btrip (?:to|from|back)\b"
    r"|\bwindshield time\b|\bin transit\b|\btransit (?:time|to|from)\b|\ben route\b|\bcommut(?:e|ed|ing)\b"
    r"|\b(?:train|car|cab|taxi) (?:ride )?(?:to|from)\b"
    r"|\bairport\b|\bon the road\b|\bjourney\b|\b(?:drive|driving|flight|road) time\b"
    r"|\breturn(?:ed|ing)? (?:home |to (?:the )?office )?from\b",
    I,
)


def is_travel(narrative):
    return bool(TRAVEL.search(narrative))


# ------------------------------------------------------------------ research

_AUTHORITY = (
    r"(?:case ?law|precedents?|authorit(?:y|ies) (?:on|regarding|for|addressing|re|under)"
    r"|(?:appellate|reported|published|unpublished|recent|circuit|district court|supreme court|court of appeals?|trial court|federal|state) (?:decisions|opinions|cases|authority|authorities|rulings)"
    r"|(?:the |governing |applicable |controlling )law (?:on|of|governing|regarding|applicable to)|legal standards? (?:for|on|governing)"
    r"|statutory (?:and regulatory )?(?:scheme|framework|provisions|text|history)|treatises?|secondary sources|annotations"
    r"|line of cases|legislative history|(?:statutes?|regulations?) and (?:cases|case law|regulations?)"
    r"|(?:decisions|opinions|cases|rulings) (?:on|regarding|addressing|applying|interpreting|construing|involving))"
)
_READING = (
    r"(?:read|reading|review\w*|analy[sz]\w+|survey\w*|dig(?:ging)? into|dug into|look(?:ed|ing)? (?:into|up|at|for)"
    r"|stud(?:y|ied|ying)|brief(?:ed|ing)?|canvass\w*|pull(?:ed|ing)?|find|found|finding|locat\w+|check\w*|collect\w*"
    r"|compil\w+|shepardi[sz]\w+|run(?:ning)? down|ran down|search\w*|examin\w+|gather\w*)"
)
RESEARCH_WORD = re.compile(r"\bresearch(?:ing|ed|es)?\b", I)
RESEARCH_WIDE = re.compile(r"\b" + _READING + r"\b[^.;]*?\b" + _AUTHORITY, I)
_NOT_RESEARCH = re.compile(r"\btable of authorities\b", I)


def research_match(narrative, activity_code=""):
    """Return a short reason if the entry reads as legal research, else ''."""
    if activity_code.upper() == "A102":
        return "activity code A102"
    m = RESEARCH_WORD.search(narrative)
    if m:
        return '"%s"' % m.group(0)
    cleaned = _NOT_RESEARCH.sub(" ", narrative)
    m = RESEARCH_WIDE.search(cleaned)
    if m:
        return 'wider wording: "%s"' % m.group(0)
    return ""


# ------------------------------------------------------------------ internal conferences

_MEETING = (
    r"(?:huddl\w+|confer(?:red|ring|ence|ences)?|meet(?:ing|ings)?|met|strategy session|session|check-?in|touch(?:ed)? base"
    r"|debrief\w*|catch-?up|sync(?:ed)?(?:-up)?|discuss\w*|consult\w*|call|spoke|speak|talk(?:ed)?|brainstorm\w*|stand-?up|roundtable)"
)
MEETING = re.compile(r"\b" + _MEETING + r"\b", I)
INTERNAL_WORD = re.compile(
    r"\b(?:internal|intra-?office|in-?firm|inter-?office|office conference|team (?:meeting|call|session|sync|huddle|check-?in|conference|discussion)"
    r"|(?:case|trial|litigation|deal|firm|our|my) team|colleagues?|with (?:the )?(?:associates?|partners?|paralegals?|co-?workers?))\b",
    I,
)
EXTERNAL_WORD = re.compile(
    r"\b(?:clients?|opposing|adjusters?|examiners?|experts?|witness(?:es)?|court|judge|clerk|mediators?|arbitrators?|counsel for|co-?counsel"
    r"|insurers?|insured|carrier|district|agency|vendors?|officers?|directors?|managers?|inventors?|owners?|plaintiffs?|defendants?|consultants?"
    r"|reporter|general counsel|in-house|board|staff of|representatives?|supervisors?|engineers?|investigators?|brokers?|lenders?|borrowers?)\b",
    I,
)


def surname_pattern(names):
    """Regex matching the surname of any of the given 'First Last' or 'Last, First' names."""
    surnames = set()
    for name in names:
        name = (name or "").strip()
        if not name:
            continue
        surname = name.split(",")[0].strip() if "," in name else name.split()[-1]
        if len(surname) >= 3:
            surnames.add(surname)
    if not surnames:
        return None
    return re.compile(r"(?<![\w-])(?:%s)(?![\w-])" % "|".join(re.escape(s) for s in sorted(surnames, key=len, reverse=True)), I)


def internal_conference_match(narrative, activity_code, listed_phrases_regex, roster_regex, own_name=""):
    """Return a short reason if the entry reads as a conference inside the firm, else ''."""
    m = listed_phrases_regex.search(narrative)
    if m:
        return '"%s"' % m.group(0)
    if activity_code.upper() == "A105":
        return "activity code A105"
    if not MEETING.search(narrative):
        return ""
    m = INTERNAL_WORD.search(narrative)
    if m and not EXTERNAL_WORD.search(narrative):
        return 'wider wording: "%s"' % m.group(0)
    if roster_regex is not None and not EXTERNAL_WORD.search(narrative):
        own = surname_pattern([own_name]) if own_name else None
        for m in roster_regex.finditer(narrative):
            if own is not None and own.fullmatch(m.group(0)):
                continue
            return "a meeting with %s, who is a timekeeper on this matter, and no outside party named" % m.group(0)
    return ""


# ------------------------------------------------------------------ attendance at an event

_ATTEND = (
    r"(?:(?:prepar\w+ for and |travel\w* to and |drove to and )?(?:attend\w*|appear\w*(?: (?:at|for|in))?|defend\w*|second[- ]chair\w*|first[- ]chair\w*"
    r"|s[ia]t(?:ting)? in on|sit in on|observ\w+|monitor\w*|cover(?:ed|ing)?|participat\w+ in|conduct\w*|argu(?:e|ed|ing)(?: at)?"
    r"|t(?:ake|ook|aking)|present at|represent\w+ (?:\w+ ){0,3}at|handl\w+))"
)
_BETWEEN = r"(?:(?!\b(?:to|for|regarding|re|about|before|after|ahead|following|from)\b)[^.;,]){0,60}?"


def attendance_regex(event):
    """Entry starts by saying the timekeeper was at the event (not preparing for it or writing about it)."""
    return re.compile(r"^\W*(?:\([^)]*\)\s*)?" + _ATTEND + r"\b" + _BETWEEN + r"(?<![-\w])" + re.escape(event) + r"s?\b", I)


# ------------------------------------------------------------------ non-billable categories

_FILING_CLERICAL = (
    r"\bfil(?:e|ed|ing)\b[^.;]{0,40}\b(?:correspondence|mail|incoming|loose papers|paperwork"
    r"|(?:in|into|to) (?:the )?(?:\w+ )?(?:files?|binders?|folders?|file room|filing cabinet|records room))\b"
)
CATEGORY_WIDE = {
    "clerical": re.compile(
        r"\bscann(?:ed|ing)\b|\bscan\b[^.;]{0,30}\b(?:documents?|pages|records|exhibits|files|into)\b"
        r"|\bphotocop\w+|\bcop(?:y|ies) sets?\b|\b(?:made|make|making|ran|run|running)\b[^.;,]{0,30}\bcopies\b|\bcopying\b"
        r"|\bpaginat\w+|\bbates[- ]?(?:stamp|label|number)\w*"
        r"|\b(?:numbered|numbering|stamped|stamping) (?:the )?(?:\w+ )?(?:pages|documents|exhibits|production)\b"
        r"|" + _FILING_CLERICAL +
        r"|\bfile[- ]room\b|\bupdat\w+ (?:the )?(?:\w+ )?(?:binders?|file index|pleadings index|filing index)\b"
        r"|\borganiz\w+ (?:the )?(?:\w+ )?(?:files?|binders?|folders?|boxes)\b"
        r"|\bhand[- ]?(?:carried|carrying|deliver\w+)\b|\bcourier run\b|\bdata entry\b|\bcalendar(?:ed|ing)\b|\bsecretarial\b"
        r"|\bstuff\w+ envelopes\b|\btyp(?:ed|ing) up\b|\bcollat\w+"
        r"|\bprint(?:ed|ing) (?:out |and \w+ )?(?:\w+ )?(?:copies|sets|exhibits|binders|documents)\b"
        r"|\b(?:assembl\w+|put together) (?:the )?(?:\w+ ){0,3}(?:binders?|notebooks?)\b|\blabel(?:l?ed|l?ing)? (?:the )?(?:\w+ )?(?:folders|boxes|binders|exhibits|files)\b"
        r"|\b(?:upload\w*|download\w*|sav(?:e|ed|ing)|mov(?:e|ed|ing)) [^.;]{0,40}\b(?:to|into|onto|from) (?:the |our |firm's )?(?:\w+ )?(?:document management|dms|portal|shared drive|network drive|system|platform|workspace|database)\b"
        r"|\brenam\w+ (?:the )?(?:\w+ )?files\b|\b(?:schedul\w+|book(?:ed|ing)?|arrang\w+|reserv\w+) (?:the |a )?(?:court reporter|courier|messenger|conference room|flights?|hotel|travel|videographer)\b",
        I,
    ),
    "training": re.compile(
        r"\bonboarding\b|\borientation\b|\b(?:get(?:ting)?|got|bring(?:ing)?|brought|came|come|coming)\b[^.;]{0,30}\bup to speed\b"
        r"|\bcontinuing legal education\b|\bcle (?:course|seminar|program|credit)\b|\b(?:attend\w*|watch\w*|complet\w+) (?:\w+ )?(?:webinar|tutorial|seminar)\b"
        r"|\blearn(?:ed|ing)? (?:the |how to use )?(?:new )?(?:software|system|platform|portal)\b"
        r"|\bfamiliari[sz]\w+|\blearning curve\b|\bshadow(?:ed|ing)\b|\bmentor(?:ed|ing)\b|\bget(?:ting)? acquainted\b|\bbackground reading\b|\bramp(?:ed|ing)? up\b",
        I,
    ),
    "conflicts": re.compile(
        r"\bconflicts?[- ](?:checks?|search\w*|clearance|screen\w*|report|database|review|run)\b"
        r"|\b(?:ran|run|running|clear(?:ed|ing)?|check(?:ed|ing)?|perform\w+|complet\w+) (?:a |the |new )?conflicts?\b"
        r"|\bnew[- ]matter (?:intake|opening|form)\b|\bopen(?:ed|ing)? (?:a |the )?new (?:file|matter)\b",
        I,
    ),
    "invoice_prep": re.compile(
        r"\b(?:prepar\w+|correct\w+|revis\w+|fix\w+|resubmit\w+|re-?submit\w+|redo\w*|redid|reformat\w+)\b(?: and \w+)?(?: (?:the|our|this|a|an|\w+ly|[A-Z][a-z]+))? (?:\w+ )?(?:invoices?|bills?|pre-?bills?)\b(?! of)"
        r"|\b(?:our|firm's|monthly|quarterly|draft) (?:\w+ )?(?:invoice|bill|pre-?bill)\b(?! of)"
        r"|\bbill reviewer\b|\bpre-?bills?\b|\be-?billing\b|\bbilling (?:inquir\w+|questions?|appeal|dispute|entries|narratives)\b"
        r"|\binvoice (?:backup|appeal|corrections?|rejection|submission|adjustments?|audit)\b"
        r"|\b(?:edit\w+|revis\w+|correct\w+|clean\w+ up|rewrit\w+|rewrote) (?:\w+ )?time (?:entries|records|narratives)\b"
        r"|\b(?:reductions?|deductions?|write-?downs?|audit) (?:of|to|on) (?:the |our )?(?:\w+ )?(?:invoice|bill)\b(?! of)",
        I,
    ),
}

# A listed word with a second, billable meaning is not flagged in that meaning.
_TRAINING_AS_SUBJECT = re.compile(
    r"\btraining\s+(?:files?|records?|materials?|manuals?|programs?|polic(?:y|ies)|logs?|history|requirements|practices|documents?|certificat\w+|videos?|standards?|curriculum|data)\b"
    r"|\b(?:driver|employee|staff|safety|officer|operator|company|corporate|hiring and|plaintiff's|defendant's|insured's|their|its|his|her|model|ai)\s+training\b",
    I,
)


def listed_phrase_allowed(phrase, narrative):
    """False when a listed phrase appears only in its other, billable sense."""
    low = phrase.lower()
    if low in ("filing", "file", "filed"):
        return bool(re.search(_FILING_CLERICAL, narrative, I)) or bool(re.match(r"^\W*filing\W*$", narrative, I))
    if low == "training":
        return not _TRAINING_AS_SUBJECT.search(narrative)
    if low in ("calendaring", "calendar"):
        return not re.search(r"\b(?:court|trial|hearing|motion|docket) calendar\b|\bcalendar (?:call|year|quarter|month|days?)\b|\bcalendaring (?:order|notice|conference|statement)\b", narrative, I)
    return True


# ------------------------------------------------------------------ expenses

OVERHEAD_EXPANSIONS = [
    (("office supplies",), re.compile(
        r"\btoner\b|\bprinter (?:paper|ink|cartridges?)\b|\b(?:copy|printer) paper\b|\bbinder (?:tabs|clips)\b|\btabs\b|\bfile folders\b|\bpens\b"
        r"|\bstaples\b|\benvelopes\b|\blabels\b|\bnotepads?\b|\blegal pads\b|\bstationery\b|\bsupplies\b", I)),
    (("subscription", "online research", "database"), re.compile(
        r"\b(?:legal |online |research )?databases? (?:charges?|fees?|access|usage|costs?)\b|\bonline (?:legal )?research (?:charges?|fees?|costs?|service)\b"
        r"|\bresearch service (?:charges?|fees?)\b|\bsubscriptions?\b", I)),
    (("overtime",), re.compile(
        r"\bafter-?hours\b|\bover-?time\b|\bweekend (?:staff|secretarial|support)\b|\b(?:secretarial|staff|administrative) (?:support|services|overtime|assistance)\b", I)),
    (("postage",), re.compile(r"\bpostage\b|\bstamps\b|\bmailing (?:costs?|charges?)\b", I)),
    (("local telephone", "phones", "telephone"), re.compile(
        r"\btelephone\b|\bphone (?:charges?|calls?|lines?|service)\b|\blong[- ]distance\b|\bconference (?:call|line) (?:charges?|service|fees?)\b", I)),
    (("word processing",), re.compile(r"\bword[- ]processing\b|\bdocument formatting\b", I)),
]


def overhead_wide_match(narrative, listed_phrases):
    listed = [p.lower() for p in listed_phrases]
    for bases, regex in OVERHEAD_EXPANSIONS:
        if any(base in phrase for base in bases for phrase in listed):
            m = regex.search(narrative)
            if m:
                return m.group(0), bases[0]
    return None


MEAL = re.compile(r"\b(?:meals?|breakfast|lunch(?:eon)?|dinner|supper|brunch|catering|per diem)\b", I)
LODGING = re.compile(
    r"\b(?:hotels?|lodging|motels?|inns?|overnight (?:stay|accommodation|room)|accommodations?|room (?:charge|rate|night)s?|\d+ nights?|guest ?house)\b", I
)

# ------------------------------------------------------------------ AI

AI_WIDE = re.compile(
    r"\bchat-?bots?\b|\bgen-?ai\b|\bai[- ](?:generated|drafted|written|produced|prepared|created|assisted|based|powered)\b"
    r"|\bllms?\b|\blanguage model\b|\bgenerative\b|\bmachine[- ](?:generated|drafted|written)\b"
    r"|\bai (?:assistant|tool|model|system|platform|software|output|draft\w*|summar\w*|review)\b"
    r"|\b(?:by|using|with|from|via) (?:an? |the |firm's |our )?ai\b|\bartificial intelligence\b",
    I,
)
AI_TASK_EXPANSIONS = [
    (re.compile(r"summar|digest", I), re.compile(r"\bsummar\w+|\bdigest\w*|\bsynops[ie]s\b|\babstract(?:ed|ing|s)? of\b|\brecap\w*", I)),
    (re.compile(r"first.*review", I), re.compile(
        r"\b(?:first|1st|initial)[- ](?:pass|cut|level|tier|line|round|stage) (?:\w+ ){0,2}review\b|\b(?:first|1st|initial)[- ](?:pass|cut|level|tier|line|round) (?:coding|tagging|screen\w*)\b", I)),
]


def ai_task_wide_match(narrative, task_phrases):
    for trigger, regex in AI_TASK_EXPANSIONS:
        if any(trigger.search(p) for p in task_phrases):
            m = regex.search(narrative)
            if m:
                return m.group(0)
    return None


# ------------------------------------------------------------------ vague narratives

_GENERIC_ACT = (
    r"(?:review(?:ed|ing)?|work(?:ed|ing)? on|attention to|attend(?:ed)? to|follow(?:ed)?[- ]?up(?: on)?|handl(?:e|ed|ing)|misc\w*|various|continu\w+"
    r"|analysis|analy[sz]\w+|research(?:ed)?|emails?|e-mails?|calls?|phone calls?|correspondence|meetings?|conference|prepar\w+|draft\w*|file review"
    r"|case (?:management|administration|work)|administration|document review|trial prep\w*|discovery|strategy|update\w*|status|services rendered"
    r"|professional services|legal services|work|tasks?)"
)
_GENERIC_OBJECT = (
    r"(?:file|matter|case|documents?|docs|emails?|correspondence|issues?|status|items?|tasks?|same|discovery|pleadings?|strategy|materials"
    r"|things|work|matters|papers|records|misc\w*|various|etc)"
)
VAGUE_WIDE = re.compile(
    r"^\W*" + _GENERIC_ACT + r"(?:\W+(?:and|&)\W+" + _GENERIC_ACT + r")?(?:\W+(?:on|of|re|regarding|for|to|and))?(?:\W+(?:the|this|same|various|misc\w*|general|case|file))?(?:\W+" + _GENERIC_OBJECT + r")?"
    r"(?:\W+(?:and|&)\W+" + _GENERIC_OBJECT + r")?(?:\W+etc)?\W*$",
    I,
)


def vague_wide_match(narrative):
    """True when the whole narrative is a generic activity with at most a generic object."""
    return bool(VAGUE_WIDE.match(narrative.strip()))
