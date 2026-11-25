"""Compare a warning label with the safe harbor content in 27 CCR 25603 and 25607.2(b).

Pattern matching only. It reports which safe harbor form the text matches and what is missing.
A label that matches no safe harbor form is flagged for review, not failed: the safe harbor is one
way to comply, not the only way (27 CCR 25600(f)).
"""
from __future__ import annotations
import re
from datetime import date

from .rules import rule, cite, find_chemical, _norm

CHEM = r"(?P<c{n}>[^.;]+?)"
_SHORT_NEW = [
    ("cancer", r"Cancer risk from exposure to " + CHEM.format(n=1) + r"\."),
    ("cancer", r"Can expose you to " + CHEM.format(n=1) + r", a carcinogen\."),
    ("reproductive", r"Risk of reproductive harm from exposure to " + CHEM.format(n=1) + r"\."),
    ("reproductive", r"Can expose you to " + CHEM.format(n=1) + r", a reproductive toxicant\."),
    ("both", r"Risk of cancer from exposure to " + CHEM.format(n=1) + r" and reproductive harm from exposure to " + CHEM.format(n=2) + r"\."),
    ("both", r"Can expose you to " + CHEM.format(n=1) + r", a carcinogen, and " + CHEM.format(n=2) + r", a reproductive toxicant\."),
    ("both", r"Risk of cancer and reproductive harm from exposure to " + CHEM.format(n=1) + r"\."),
    ("both", r"Can expose you to " + CHEM.format(n=1) + r", a carcinogen and reproductive toxicant\."),
]
_SHORT_OLD = [("both", r"Cancer and Reproductive Harm"), ("cancer", r"Cancer"), ("reproductive", r"Reproductive Harm")]
_LONG = [
    ("both", r"can expose you to (?:chemicals including )?" + CHEM.format(n=1) + r", which (?:is|are) known to the State of California to cause cancer,? and " + CHEM.format(n=2) + r", which (?:is|are) known to the State of California to cause birth defects or other reproductive harm\."),
    ("both", r"can expose you to (?:chemicals including )?" + CHEM.format(n=1) + r", which (?:is|are) known to the State of California to cause cancer and birth defects or other reproductive harm\."),
    ("cancer", r"can expose you to (?:chemicals including )?" + CHEM.format(n=1) + r", which (?:is|are) known to the State of California to cause cancer\."),
    ("reproductive", r"can expose you to (?:chemicals including )?" + CHEM.format(n=1) + r", which (?:is|are) known to the State of California to cause birth defects or other reproductive harm\."),
]
_URL = r"www\.P65Warnings\.ca\.gov(?P<path>/[a-z]+)?"


def _clean(text: str) -> str:
    t = text.replace("–", "-").replace("—", "-").replace("’", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"^[⚠️!▲△\s]+", "", t)


def _f(code, level, message, rule_id):
    return {"code": code, "level": level, "message": message, **cite(rule_id)}


def check_label(text: str, category: str = "consumer", endpoints=("cancer",), chemicals=(),
                manufactured_labeled: str | date | None = None, has_symbol: bool | None = None,
                type_size_pt: float | None = None) -> dict:
    """category: 'consumer' or 'food'. endpoints: the endpoints the warning must cover."""
    sf = rule("short_form_warning")["params"]
    need = set(endpoints)
    t = _clean(text)
    findings, form, covered, named = [], None, set(), []

    sig = re.match(r"(CALIFORNIA WARNING|CA WARNING|WARNING):\s*", t)
    if not sig:
        findings.append(_f("SIGNAL_WORD", "FAIL", "No signal word in capitals (WARNING:, CA WARNING: or CALIFORNIA WARNING:) at the start of the text.", "short_form_warning"))
        body = t
    else:
        body = t[sig.end():]

    for ep, pat in _SHORT_NEW:
        m = re.match(pat + r"\s*See " + _URL + r"\.?$", body, re.I)
        if m:
            form, covered = "short_form_2025", ({"cancer", "reproductive"} if ep == "both" else {ep})
            named = [v.strip() for v in m.groupdict().values() if v and not v.startswith("/")]
            url_path = m.group("path") or ""
            break
    if not form:
        for ep, pat in _SHORT_OLD:
            m = re.match(pat + r"\s*-+\s*" + _URL + r"\.?$", body, re.I)
            if m:
                form, covered = "short_form_pre_2025", ({"cancer", "reproductive"} if ep == "both" else {ep})
                url_path = m.group("path") or ""
                break
    if not form:
        for ep, pat in _LONG:
            m = re.search(pat + r"\s*For more information go to " + _URL + r"\.?", body, re.I)
            if m:
                form, covered = "long_form", ({"cancer", "reproductive"} if ep == "both" else {ep})
                named = [v.strip() for k, v in m.groupdict().items() if v and k.startswith("c")]
                url_path = m.group("path") or ""
                break

    if not form:
        findings.append(_f("NO_SAFE_HARBOR_MATCH", "REVIEW", "The text does not match any safe harbor wording checked here. It may still be clear and reasonable, but it does not get the safe harbor presumption.", "safe_harbor_not_exclusive"))
        return {"check": "label", "status": "REVIEW" if sig else "FAIL", "form": None, "summary": "No safe harbor form recognized.",
                "detail": {"findings": findings}, "rules": [cite("short_form_warning"), cite("safe_harbor_not_exclusive")],
                "attorney_review": [rule("short_form_warning")["attorney_review"]]}

    findings.append(_f("FORM", "PASS", f"Matches the {form.replace('_', ' ')} wording.", "long_form_warning" if form == "long_form" else "short_form_warning"))

    missing = need - covered
    if missing:
        findings.append(_f("ENDPOINT", "FAIL", f"The warning does not cover: {', '.join(sorted(missing))}.", "short_form_warning"))

    if form == "short_form_pre_2025":
        cutoff = date.fromisoformat(sf["old_short_form_cutoff_manufactured_and_labeled_before"])
        if sig and sig.group(1) != "WARNING":
            findings.append(_f("OLD_FORM_SIGNAL", "REVIEW", "The pre-2025 short form is written with the word WARNING: only.", "short_form_warning"))
        if category == "food":
            findings.append(_f("OLD_FORM_FOOD", "REVIEW", "Pre-2025 short form on a food label. The transition sentence sits in § 25603(c); whether it reaches food labels under § 25607.2 needs attorney review.", "short_form_warning"))
        elif manufactured_labeled is None:
            findings.append(_f("OLD_FORM_DATE", "REVIEW", f"Pre-2025 short form with no chemical named. It is allowed only if the product was manufactured and labeled before {cutoff}. No date was given.", "short_form_warning"))
        else:
            d = manufactured_labeled if isinstance(manufactured_labeled, date) else date.fromisoformat(manufactured_labeled)
            if d < cutoff:
                findings.append(_f("OLD_FORM_DATE", "PASS", f"Pre-2025 short form, product manufactured and labeled {d}, before the {cutoff} cutoff. Allowed whenever the product is sold.", "short_form_warning"))
            else:
                findings.append(_f("OLD_FORM_DATE", "FAIL", f"Pre-2025 short form on a product manufactured and labeled {d}, on or after {cutoff}. A chemical must be named.", "short_form_warning"))
    else:
        alleged = set()
        for c in chemicals:
            alleged.add(_norm(c)); alleged.update(k for r in find_chemical(c) for k in r["_keys"])
        for nm in named:
            parts = [p for p in re.split(r",| and ", nm) if p.strip()]
            if alleged and not any(_norm(p) in alleged for p in parts):
                findings.append(_f("CHEMICAL_NAME", "REVIEW", f"The warning names \"{nm}\", which is not one of the chemicals in the notice ({', '.join(chemicals)}).", "short_form_warning"))
            else:
                findings.append(_f("CHEMICAL_NAME", "PASS", f"Names a chemical: {nm}.", "short_form_warning"))

    want_path = "/food" if category == "food" else ""
    if url_path != want_path and not (category == "food" and url_path == "/acrylamide"):
        findings.append(_f("URL", "REVIEW", f"Points to www.P65Warnings.ca.gov{url_path}; the {category} safe harbor text uses www.P65Warnings.ca.gov{want_path}.", "short_form_warning"))

    if category != "food":
        if has_symbol is False:
            findings.append(_f("SYMBOL", "FAIL", "The yellow triangle symbol is missing.", "long_form_warning" if form == "long_form" else "short_form_warning"))
        elif has_symbol is None:
            findings.append(_f("SYMBOL", "REVIEW", "Symbol presence not stated.", "short_form_warning"))
    if form.startswith("short") and type_size_pt is not None and type_size_pt < sf["min_type_pt"]:
        findings.append(_f("TYPE_SIZE", "FAIL", f"Type is {type_size_pt}-point. A short-form warning may never be smaller than {sf['min_type_pt']}-point.", "short_form_warning"))

    levels = {f["level"] for f in findings}
    status = "FAIL" if "FAIL" in levels else "REVIEW" if "REVIEW" in levels else "PASS"
    summary = {"PASS": "Matches safe harbor content on every point checked.",
               "REVIEW": "Matches a safe harbor form, with points for attorney review.",
               "FAIL": "Does not meet the safe harbor content on at least one point."}[status]
    return {"check": "label", "status": status, "form": form, "summary": summary,
            "detail": {"findings": findings, "named_chemicals": named, "endpoints_covered": sorted(covered)},
            "rules": [cite("short_form_warning"), cite("long_form_warning"), cite("safe_harbor_not_exclusive")],
            "attorney_review": [rule("short_form_warning")["attorney_review"]]}
