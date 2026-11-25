"""Fact guard.

A draft may state firm facts only if they agree with firm_facts.json. Reused
passages are checked for:

  * another agency's name left in from the source proposal (full name,
    possessive, place name alone, abbreviation), and agency words that do not
    fit this RFP ("the City" in a proposal to a District);
  * attorneys who have left the firm;
  * head counts, founding year, office names and counts, client counts, matter
    counts and bar admissions that disagree with firm_facts.json;
  * placeholders that were not filled.

Flags are "blocking" (must be fixed before the passage can be used) or
"warning" (a person should look). The guard checks what it has patterns for.
A passage with no flags has not been proved correct.
"""
import re

from .util import NUMWORD, count_value, sentences

BLOCKING, WARNING = "blocking", "warning"

TYPE_WORDS = {"water", "fire", "protection", "sanitary", "irrigation", "park", "and", "recreation",
              "community", "services", "harbor", "unified", "elementary", "school", "college", "transit",
              "regional", "district", "authority", "agency", "commission", "high", "joint", "union",
              "municipal", "utility", "public", "transportation", "port", "airport", "flood", "control"}
TYPE_NOUNS = ["District", "City", "Town", "Authority", "County", "Agency", "Commission"]
BODY_TERMS = ["City Council", "Town Council", "Board of Directors", "Board of Trustees", "Board of Supervisors",
              "Board of Education", "Harbor Commission", "Planning Commission", "Mayor"]
EXEC_TERMS = ["City Manager", "Town Manager", "General Manager", "Superintendent", "Executive Director",
              "City Attorney"]
DEFAULT_TERMS = {
    "city": {"City Council", "Town Council", "City Manager", "Town Manager", "City Attorney", "Mayor",
             "Planning Commission"},
    "special_district": {"Board of Directors", "General Manager"},
    "school_district": {"Board of Trustees", "Board of Education", "Superintendent"},
    "transit": {"Board of Directors", "Executive Director", "General Manager"},
    "county": {"Board of Supervisors", "Planning Commission"},
}


def flag(level, kind, message, match=""):
    return {"level": level, "kind": kind, "message": message, "match": match}


# ------------------------------------------------------------------ agency names

def place_of(name):
    """'Harlan Springs Fire Protection District' -> 'Harlan Springs'; 'City of X Y' -> 'X Y'."""
    m = re.match(r"(?:City|Town|County|Village)\s+of\s+(.+)$", name.strip(), re.I)
    if m:
        return m.group(1).strip()
    words = name.split()
    while len(words) > 1 and words[-1].lower() in TYPE_WORDS:
        words.pop()
    return " ".join(words)


def abbreviations(name):
    """Likely initialisms: 'Quarry Hollow Transit District' -> {'QHTD'}."""
    words = re.findall(r"[A-Za-z]+", name)
    a1 = "".join(w[0].upper() for w in words if w.lower() not in ("of", "and", "the"))
    a2 = "".join(w[0].upper() for w in words)
    return {a for a in (a1, a2) if len(a) >= 3}


def _norm_name(name):
    return re.sub(r"\s+", " ", name.replace("’", "'")).strip().casefold()


def _words_re(name, flags=0):
    parts = [re.escape(w) for w in name.split()]
    return re.compile(r"(?<![A-Za-z])" + r"\s+".join(parts) + r"(?![A-Za-z])", flags)


def _abbr_re(abbr):
    return re.compile(r"(?<![A-Za-z0-9.])" + r"\.?".join(re.escape(c) for c in abbr) + r"\.?(?![A-Za-z0-9])")


def find_wrong_agency(text, current_agency, other_agencies, office_cities=(), extra_abbreviations=None):
    """Names of agencies other than the one this proposal is for.

    extra_abbreviations: optional {agency name: [abbreviations]} for names the
    initialism rule would not guess.
    """
    flags, seen = [], set()
    cur = _norm_name(current_agency)
    cur_abbr = abbreviations(current_agency)
    offices = {c.casefold() for c in office_cities}
    extra_abbreviations = extra_abbreviations or {}
    masked = list(text)

    def mask(m):
        for i in range(m.start(), m.end()):
            masked[i] = "\x00"

    def add(level, name, m, how):
        got = text[m.start():m.end()]
        key = (_norm_name(name), how)
        if key in seen:
            return
        seen.add(key)
        flags.append(flag(level, "wrong_agency",
                          "another agency is named (%s): \"%s\". This proposal is for %s."
                          % (how, got, current_agency), got))

    # the current agency's own name must not be mistaken for a shorter name inside it
    for m in _words_re(current_agency, re.I).finditer(text):
        mask(m)
    others = sorted({o for o in other_agencies if o and _norm_name(o) != cur}, key=len, reverse=True)
    for name in others:
        for m in _words_re(name, re.I).finditer("".join(masked)):
            add(BLOCKING, name, m, "full name")
            mask(m)
    for name in others:
        abbrs = abbreviations(name) | set(extra_abbreviations.get(name, []))
        for ab in abbrs - cur_abbr:
            for m in _abbr_re(ab).finditer("".join(masked)):
                add(BLOCKING, name, m, "abbreviation")
                mask(m)
    for name in others:
        place = place_of(name)
        if len(place) < 4 or place.casefold() in cur:
            continue
        for m in _words_re(place).finditer("".join(masked)):
            if place.casefold() in offices:
                add(WARNING, name, m, "place name that is also a firm office; check which is meant")
            else:
                add(BLOCKING, name, m, "place name")
            mask(m)
    return flags


def find_wrong_agency_words(text, agency_short, agency_type, rfp_text=""):
    """'the City' in a proposal to a District, or a governing body this agency does not have."""
    flags, seen = [], set()
    # "the City Manager" is reported once, as a term, not also as "the City"
    for m in re.finditer(r"\b[Tt]he\s+(" + "|".join(TYPE_NOUNS) + r")\b(?!\s+(?:Council|Manager|Attorney|Clerk)\b)", text):
        noun = m.group(1)
        if noun != agency_short and noun not in seen:
            seen.add(noun)
            flags.append(flag(BLOCKING, "wrong_agency_word",
                              "\"the %s\" does not fit this RFP; the agency is \"the %s\"." % (noun, agency_short),
                              m.group(0)))
    allowed = set(DEFAULT_TERMS.get(agency_type, set()))
    for term in BODY_TERMS + EXEC_TERMS:
        if term in allowed or term in seen:
            continue
        if re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![a-z])", text) and term not in rfp_text:
            seen.add(term)
            flags.append(flag(BLOCKING, "wrong_agency_word",
                              "\"%s\" is not a term this RFP uses for the agency." % term, term))
    return flags


# ------------------------------------------------------------------ people

def find_departed(text, departed_names):
    flags = []
    for name in departed_names:
        last = name.split()[-1]
        m = _words_re(name).search(text)
        if not m:
            m = re.search(r"\b(?:Mr|Ms|Mrs|Mx|Dr)\.?\s+" + re.escape(last) + r"\b", text)
        if m:
            flags.append(flag(BLOCKING, "departed_attorney",
                              "%s is no longer with the firm and is named in the text." % name, m.group(0)))
        elif len(last) >= 5 and re.search(r"(?<![A-Za-z])" + re.escape(last) + r"(?![a-z])", text):
            flags.append(flag(WARNING, "departed_attorney",
                              "the surname of %s, who has left the firm, appears in the text." % name, last))
    return flags


# ------------------------------------------------------------------ firm facts

_NUM = r"(\d[\d,]*|" + NUMWORD + r")"
_QUAL = r"(?:(more than|over|at least|nearly|almost|approximately|about|roughly)\s+)?"
_PLACE = r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)?"
_PLACE_LIST = _PLACE + r"(?:,\s" + _PLACE + r")*(?:,?\sand\s" + _PLACE + r")?"


def _agrees(n, actual, qual):
    q = (qual or "").lower()
    if q in ("more than", "over"):
        return n < actual
    if q == "at least":
        return n <= actual
    if q in ("nearly", "almost"):
        return actual < n <= actual * 1.15
    if q in ("approximately", "about", "roughly"):
        return abs(n - actual) <= 0.1 * actual
    return n == actual


def find_fact_conflicts(text, facts):
    """Compare firm facts stated in text with firm_facts.json. Returns (flags, checked spans)."""
    flags, spans = [], []
    as_of = facts.get("as_of", "")

    def number_rule(pattern, actual, label, re_flags=re.I):
        for m in re.finditer(pattern, text, re_flags):
            spans.append((m.start(), m.end()))
            n = count_value(m.group(2))[0]
            if actual is None:
                flags.append(flag(BLOCKING, "fact_not_on_file",
                                  "the text states a %s (\"%s\") but firm_facts.json has no such fact."
                                  % (label, m.group(0)), m.group(0)))
            elif n is None or not _agrees(n, actual, m.group(1)):
                flags.append(flag(BLOCKING, "fact_mismatch",
                                  "%s: the text says \"%s\"; firm_facts.json (as of %s) says %s."
                                  % (label, m.group(0), as_of, actual), m.group(0)))

    number_rule(r"\b(?:has|have|with|of|employs|firm's|our)\s+" + _QUAL + _NUM + r"\s+(?:attorneys|lawyers)\b",
                facts.get("attorney_count"), "attorney count")
    number_rule(r"\b(?:has|have|with|of|including)\s+" + _QUAL + _NUM + r"\s+partners\b",
                facts.get("partner_count"), "partner count")
    number_rule(r"\b" + _QUAL + _NUM + r"\s+offices\b", len(facts.get("offices", [])), "number of offices")
    number_rule(r"\b(?:represents?|serves?|advises?)\s+" + _QUAL + _NUM + r"\s+public\s+(?:agencies|agency clients|entities)\b",
                facts.get("public_agency_clients"), "number of public agency clients")
    mc = facts.get("matter_counts", {})
    number_rule(r"\b" + _QUAL + _NUM + r"\s+(?:completed\s+)?(?:labor\s+)?negotiations\b",
                mc.get("negotiations"), "number of negotiations")
    number_rule(r"\b" + _QUAL + _NUM + r"\s+(?:public\s+)?(?:capital|construction)\s+projects\b",
                mc.get("capital_projects"), "number of capital projects")

    founded = facts.get("founded_year")
    for m in re.finditer(r"\b(?:founded|established|formed)\s+in\s+(\d{4})\b", text, re.I):
        spans.append((m.start(), m.end()))
        if int(m.group(1)) != founded:
            flags.append(flag(BLOCKING, "fact_mismatch", "founding year: the text says %s; firm_facts.json says %s."
                              % (m.group(1), founded), m.group(0)))
    pos = 0
    for sent in sentences(text):
        start = text.find(sent[:20], pos)
        pos = max(pos, start)
        if re.search(r"\bfirm\b", sent, re.I):
            for m in re.finditer(r"\bsince\s+(\d{4})\b", sent):
                if start >= 0:
                    spans.append((start + m.start(), start + m.end()))
                if int(m.group(1)) != founded:
                    flags.append(flag(BLOCKING, "fact_mismatch",
                                      "\"%s\" in a sentence about the firm; firm_facts.json says the firm was founded in %s."
                                      % (m.group(0), founded), m.group(0)))
        if re.search(r"\badmitted\b", sent, re.I):
            admitted = {a.casefold() for a in facts.get("bar_admissions", [])}
            for m in re.finditer(r"State of [A-Z][a-z]+", sent):
                if m.group(0).casefold() not in admitted:
                    flags.append(flag(BLOCKING, "fact_mismatch",
                                      "bar admission \"%s\" is not in firm_facts.json." % m.group(0), m.group(0)))

    cities = {o["city"] for o in facts.get("offices", [])}
    for pat in (r"\boffices?\s+(?:are\s+|is\s+)?in\s+(" + _PLACE_LIST + r")",
                r"\boffices:\s+(" + _PLACE_LIST + r")",
                r"\b[Oo]ur\s+(" + _PLACE + r")\s+office\b"):
        for m in re.finditer(pat, text):
            spans.append((m.start(), m.end()))
            named = [p.strip() for p in re.split(r",\s*|\s+and\s+", m.group(1)) if p.strip()]
            wrong = [p for p in named if p not in cities]
            if wrong:
                flags.append(flag(BLOCKING, "fact_mismatch",
                                  "office not in firm_facts.json: %s. Current offices: %s."
                                  % (", ".join(wrong), ", ".join(sorted(cities))), m.group(0)))
            elif len(named) > 1 and set(named) != cities:
                flags.append(flag(BLOCKING, "fact_mismatch",
                                  "office list is incomplete: the text lists %s; current offices are %s."
                                  % (", ".join(named), ", ".join(sorted(cities))), m.group(0)))
    return flags, spans


def find_unverified_numbers(text, spans):
    loose = []
    for m in re.finditer(r"\$?\d[\d,]*(?:\.\d+)?%?", text):
        if not any(a <= m.start() < b for a, b in spans):
            loose.append(m.group(0).rstrip(","))
    if not loose:
        return []
    return [flag(WARNING, "unverified_number",
                 "numbers not checked against firm facts: %s. Confirm each one." % ", ".join(sorted(set(loose))),
                 ", ".join(sorted(set(loose))))]


def find_placeholders(text):
    left = sorted(set(re.findall(r"\{[A-Z_]+\}", text)))
    if not left:
        return []
    return [flag(BLOCKING, "unfilled_placeholder", "placeholder not filled: %s." % ", ".join(left), ", ".join(left))]


# ------------------------------------------------------------------ entry points

def known_agencies(data):
    """Every agency name the library knows: past proposals, experience and references."""
    names = {a["proposal_agency"] for a in data.answers}
    names |= {e["client_name"] for e in data.experience}
    names |= {r["client_name"] for r in data.references}
    return sorted(n for n in names if n)


def departed_names(data):
    names = {b["name"] for b in data.bios if b.get("status") == "departed"}
    names |= set(data.facts.get("departed_attorneys", []))
    return sorted(names)


def make_context(rfp_meta, data, rfp_text=""):
    return {"agency": rfp_meta["agency"], "agency_short": rfp_meta["agency_short"],
            "agency_type": rfp_meta["agency_type"], "facts": data.facts,
            "departed": departed_names(data), "other_agencies": known_agencies(data),
            "office_cities": [o["city"] for o in data.facts.get("offices", [])], "rfp_text": rfp_text}


def check_passage(text, ctx):
    """All checks on one reused passage, after placeholders are filled."""
    flags = []
    flags += find_wrong_agency(text, ctx["agency"], ctx["other_agencies"], ctx.get("office_cities", ()),
                               ctx.get("extra_abbreviations"))
    flags += find_wrong_agency_words(text, ctx["agency_short"], ctx["agency_type"], ctx.get("rfp_text", ""))
    flags += find_departed(text, ctx["departed"])
    fact_flags, spans = find_fact_conflicts(text, ctx["facts"])
    flags += fact_flags
    flags += find_placeholders(text)
    flags += find_unverified_numbers(text, spans)
    return flags


def has_blocking(flags):
    return any(f["level"] == BLOCKING for f in flags)


def check_consent(text, data, current_agency=""):
    """Client or reference names printed without consent anywhere in a draft."""
    flags = []
    cur = _norm_name(current_agency)
    consented = {_norm_name(e["client_name"]) for e in data.experience if e["client_consent"]}
    for e in data.experience:
        name = e["client_name"]
        if e["client_consent"] or _norm_name(name) == cur:
            continue
        if _words_re(name, re.I).search(text):
            flags.append(flag(BLOCKING, "no_client_consent",
                              "%s is named but experience record %s has no client consent." % (name, e["id"]), name))
    for r in data.references:
        if r["client_consent"]:
            continue
        if _words_re(r["contact_name"]).search(text):
            flags.append(flag(BLOCKING, "no_client_consent",
                              "reference contact %s is named but record %s has no consent." % (r["contact_name"], r["id"]),
                              r["contact_name"]))
        elif (_norm_name(r["client_name"]) not in consented and _norm_name(r["client_name"]) != cur
              and _words_re(r["client_name"], re.I).search(text)
              and not any(f["match"] == r["client_name"] for f in flags)):
            flags.append(flag(BLOCKING, "no_client_consent",
                              "%s is named but reference record %s has no consent." % (r["client_name"], r["id"]),
                              r["client_name"]))
    return flags


NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def join_list(items):
    items = list(items)
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def facts_block(facts):
    """Firm facts paragraph built only from firm_facts.json."""
    offices = [o["city"] for o in facts["offices"]]
    n = len(offices)
    parts = ["%s was founded in %d." % (facts["firm_name"], facts["founded_year"])]
    s = "The firm has %d attorneys" % facts["attorney_count"]
    if facts.get("partner_count"):
        s += ", including %d partners," % facts["partner_count"]
    s += " in %s office%s: %s." % (NUMBER_WORDS[n] if n <= 10 else str(n), "" if n == 1 else "s", join_list(offices))
    parts.append(s)
    if facts.get("public_agency_clients"):
        parts.append("The firm currently represents %d public agencies." % facts["public_agency_clients"])
    if facts.get("bar_admissions"):
        parts.append("Its attorneys are admitted in %s." % join_list("the " + a for a in facts["bar_admissions"]))
    return " ".join(parts)
