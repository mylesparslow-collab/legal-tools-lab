"""Small shared helpers: dates, counts written as words, business days, text."""
import datetime as dt
import html as _html
import json
import re

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MON = (r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
DATE_TEXT_RE = re.compile(_MON + r"\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?,?\s+(\d{4})")
DATE_NUM_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")
TIME_RE = re.compile(r"(?<![\d/:,])(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?|noon)(?![a-z])", re.I)


def _mk_date(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def find_dates(text):
    """Return dates found in text, in order. Each: date, end (for a range), start, stop, raw, valid."""
    out = []
    for m in DATE_TEXT_RE.finditer(text):
        mon = MONTHS[m.group(1)[:3].lower()]
        d = _mk_date(m.group(4), mon, m.group(2))
        end = _mk_date(m.group(4), mon, m.group(3)) if m.group(3) else None
        out.append({"date": d, "end": end, "start": m.start(), "stop": m.end(),
                    "raw": m.group(0), "valid": d is not None})
    for m in DATE_NUM_RE.finditer(text):
        d = _mk_date(m.group(3), m.group(1), m.group(2))
        out.append({"date": d, "end": None, "start": m.start(), "stop": m.end(),
                    "raw": m.group(0), "valid": d is not None})
    out.sort(key=lambda x: x["start"])
    return out


def find_time(text):
    """First clock time in text as HH:MM (24h), or None."""
    m = TIME_RE.search(text)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower().replace(".", "")
    if h > 12 or mi > 59:
        return None
    if ap == "noon":
        h = 12
    elif ap == "pm" and h != 12:
        h += 12
    elif ap == "am" and h == 12:
        h = 0
    return "%02d:%02d" % (h, mi)


_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
          "eighteen", "nineteen"]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_WORDVAL = {w: i for i, w in enumerate(_UNITS)}
_WORDVAL.update({w: 20 + 10 * i for i, w in enumerate(_TENS)})
NUMWORD = (r"(?:(?:" + "|".join(_TENS) + r")(?:[- ](?:" + "|".join(_UNITS[1:10]) + r"))?|"
           + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")")
# "ten (10)", "10" or "ten"
COUNT = r"(?:" + NUMWORD + r"\s*\(\d+\)|\d[\d,]*|" + NUMWORD + r")"
COUNT_RE = re.compile(COUNT, re.I)


def word_to_int(word):
    parts = re.split(r"[- ]", word.strip().lower())
    try:
        return sum(_WORDVAL[p] for p in parts if p)
    except KeyError:
        return None


def count_value(text):
    """Value of a count such as 'ten (10)', '10' or 'ten'.

    Returns (value, consistent). consistent is False when the word and the
    digits disagree, for example 'ten (12)'.
    """
    text = text.strip()
    m = re.match(r"(?i)(" + NUMWORD + r")\s*\((\d+)\)$", text)
    if m:
        w, d = word_to_int(m.group(1)), int(m.group(2))
        return d, w == d
    if re.match(r"\d", text):
        return int(text.replace(",", "")), True
    return word_to_int(text), True


def parse_iso(value):
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def is_business_day(d, holidays=()):
    return d.weekday() < 5 and d not in holidays


def shift_business_days(d, n, holidays=()):
    """Move n business days from d (negative n moves back). Weekends are skipped.

    Holidays are skipped only if supplied. With n == 0 the date is moved back to
    the nearest business day if it is not one.
    """
    step = 1 if n > 0 else -1
    cur = d
    if n == 0:
        while not is_business_day(cur, holidays):
            cur -= dt.timedelta(days=1)
        return cur
    left = abs(n)
    while left:
        cur += dt.timedelta(days=step)
        if is_business_day(cur, holidays):
            left -= 1
    return cur


def business_days_between(a, b, holidays=()):
    """Business days after a, up to and including b. Negative if b is before a."""
    if b < a:
        return -business_days_between(b, a, holidays)
    n, cur = 0, a
    while cur < b:
        cur += dt.timedelta(days=1)
        if is_business_day(cur, holidays):
            n += 1
    return n


def load_holidays(path):
    """Holiday file: a JSON list of ISO dates, or one ISO date per line (# comments allowed)."""
    if not path:
        return frozenset()
    raw = open(path, encoding="utf-8").read()
    try:
        items = json.loads(raw)
    except ValueError:
        items = [ln.split("#")[0].strip() for ln in raw.splitlines()]
    return frozenset(dt.date.fromisoformat(x) for x in items if x)


STOPWORDS = set("""a an and are as at be been by for from has have how in is it its of on or that the
this to was were will with would your you our we any each which who whom their they them than then
there these those not no do does if so such can may shall must should about into over under per
also other all both more most up out us he she his her i""".split())


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


def norm_ws(text):
    return re.sub(r"\s+", " ", text).strip()


_ABBR = r"\b(No|Inc|Dr|Mr|Ms|Mrs|Mx|St|Co|Corp|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Mon|Tue|Wed|Thu|Fri|Sat|Sun|a\.m|p\.m|e\.g|i\.e)\."


def sentences(text):
    """Split text into sentences. Conservative: common abbreviations do not end a sentence."""
    text = norm_ws(text)
    protected = re.sub(_ABBR, lambda m: m.group(0).replace(".", "\x00"), text, flags=re.I)
    # "Inc." at a real sentence end followed by a capitalised sentence stays joined; acceptable.
    parts = re.split(r"(?<=[.?!])[\"”)]?\s+(?=[A-Z(\"“])", protected)
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


def esc(text):
    return _html.escape("" if text is None else str(text), quote=True)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def fmt_date(iso):
    """2026-12-17 -> 'Thu 17 Dec 2026'."""
    if not iso:
        return ""
    d = parse_iso(iso)
    return d.strftime("%a %d %b %Y")
