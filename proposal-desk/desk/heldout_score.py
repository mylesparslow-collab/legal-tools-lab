"""Score the parser against the independently written keys under heldout/.

These keys carry more than the in-sample keys do (see heldout/README.md), so this
scorer is separate from desk/evaluate.py. Rules:

- Every parsed item counts, including items the parser marked "check".
- Requirements match on the printed label or one of the key's alt_labels; unnumbered
  requirements, and anything the label did not match, match on text. Question type is
  scored separately and accepts alt_qtypes.
- A requirement the key lists under deleted_requirements must not be parsed. If it is, it
  is an extra requirement and a failed addendum check.
- A deadline the key marks kind_not_in_existing_keys is reported on its own line and is
  neither a hit nor an extra.
- Parsed deadlines on a date the key lists under dates_that_are_not_deadlines, and extra
  requirements, are extras; they are also listed as "negatives hit".
- Addendum handling is its own line: each value the key says an addendum changed is
  checked in the parsed result as in force (date, time, page limit, form, criterion,
  weight, insurance amount, deleted requirement). It is not part of the overall figure,
  because the same values are already counted in their own categories.
"""
import re

CATEGORIES = ["deadlines", "requirements", "forms", "evaluation", "min_quals", "insurance",
              "mechanics", "parties"]


def _norm(s):
    return re.sub(r"[^a-z0-9$]+", " ", str(s).lower()).strip()


_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _dates_in_note(s):
    """Dates written out in a key's free-text note. Kept apart from the parser's own date code."""
    out = set()
    for m in re.finditer(r"([A-Za-z]{3,9})\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", s):
        if m.group(1)[:3].lower() in _MONTHS:
            out.add("%s-%02d-%02d" % (m.group(3), _MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2))))
    for m in re.finditer(r"(\d{1,2})(?:st|nd|rd|th)? (?:of )?([A-Za-z]{3,9})\.?,? (\d{4})", s):
        if m.group(2)[:3].lower() in _MONTHS:
            out.add("%s-%02d-%02d" % (m.group(3), _MONTHS.index(m.group(2)[:3].lower()) + 1, int(m.group(1))))
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", s):
        out.add(m.group(0))
    return out


def _label(s):
    return re.sub(r"[\s.:]+$", "", str(s).strip().lower())


def _match(parsed_items, key_items, same):
    left = list(parsed_items)
    pairs, missed = [], []
    for k in key_items:
        hit = next((p for p in left if same(p, k)), None)
        if hit is None:
            missed.append(k)
        else:
            left.remove(hit)
            pairs.append((hit, k))
    return pairs, left, missed


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return round(p, 3), round(r, 3)


def _text_same(parsed_text, key_text):
    a, b = _norm(parsed_text), _norm(key_text)
    if not a or not b:
        return False
    head = " ".join(b.split()[:8])
    if head in a:
        return True
    phead = " ".join(a.split()[:8])
    return len(a.split()) >= 6 and phead in b


def match_requirements(parsed, key_reqs):
    left = list(parsed)
    pairs, pending = [], []
    for k in key_reqs:
        labels = {_label(k["label"])} | {_label(x) for x in k.get("alt_labels", [])}
        hit = None
        if k.get("numbered", True):
            hit = next((p for p in left if _label(p["label"]) in labels and
                        (len(labels) == 1 or _label(p["label"]) == _label(k["label"]) or _text_same(p["text"], k["text"]))),
                       None)
        if hit is None:
            pending.append(k)
        else:
            left.remove(hit)
            pairs.append((hit, k))
    missed = []
    for k in pending:
        hit = next((p for p in left if _text_same(p["text"], k.get("text", ""))), None)
        if hit is None:
            missed.append(k)
        else:
            left.remove(hit)
            pairs.append((hit, k))
    return pairs, left, missed


def _form_names(k):
    base = re.sub(r"\([^)]*\)", " ", k)
    inner = re.findall(r"\(([^)]*)\)", k)
    return [x for x in [_norm(base)] + [_norm(i) for i in inner] if x]


def _form_same(p, k):
    a = _norm(re.sub(r"\([^)]*\)", " ", p["name"]))
    full = _norm(p["name"])
    for b in _form_names(k):
        if a == b or full == b or (len(b.split()) >= 2 and (b in full or (len(a.split()) >= 2 and a in b))):
            return True
    return False


def _crit_same(p, k):
    a, b = _norm(p["name"]), _norm(k["name"])
    a2, b2 = re.sub(r"^the ", "", a), re.sub(r"^the ", "", b)
    return bool(a2) and (a2 == b2 or a2 in b2 or b2 in a2)


def evaluate(parsed, key):
    out = {}

    def record(cat, pairs, extra, missed, show=str, show_key=str):
        p, r = _prf(len(pairs), len(extra), len(missed))
        out[cat] = {"tp": len(pairs), "fp": len(extra), "fn": len(missed), "precision": p, "recall": r,
                    "extra": [show(x) for x in extra], "missed": [show_key(x) for x in missed]}

    # deadlines
    key_dl = [d for d in key["deadlines"] if not d.get("kind_not_in_existing_keys")]
    other_dl = [d for d in key["deadlines"] if d.get("kind_not_in_existing_keys")]
    parsed_dl = list(parsed["deadlines"])
    other_found = []
    for d in other_dl:
        hit = next((p for p in parsed_dl if p["date"] == d["date"]), None)
        other_found.append({"kind": d["kind"], "date": d["date"], "found": hit is not None})
        if hit is not None:
            parsed_dl.remove(hit)
    pairs, extra, missed = _match(parsed_dl, key_dl,
                                  lambda p, k: (p["kind"], p["date"], p["time"]) == (k["kind"], k["date"], k.get("time")))
    record("deadlines", pairs, extra, missed, lambda d: "%s %s %s" % (d["kind"], d["date"], d["time"]),
           lambda d: "%s %s %s" % (d["kind"], d["date"], d.get("time")))
    out["deadlines"]["date_right_time_or_kind_wrong"] = sum(
        1 for k in missed if any(p["date"] == k["date"] for p in extra))
    out["deadline_kinds_outside_existing_keys"] = other_found
    not_dates = set()
    for s in key.get("dates_that_are_not_deadlines", []):
        not_dates |= _dates_in_note(s)
    neg_dl = ["%s %s" % (p["kind"], p["date"]) for p in extra if p["date"] in not_dates]

    sub = next((d for d in key["deadlines"] if d["kind"] == "submission_due"), None)
    psub = [p for p in parsed["deadlines"] if p["kind"] == "submission_due"]
    out["submission_deadline"] = {
        "key": "%s %s" % (sub["date"], sub.get("time")) if sub else None,
        "parsed": ["%s %s" % (p["date"], p["time"]) for p in psub],
        "correct": bool(sub) and len(psub) == 1 and (psub[0]["date"], psub[0]["time"]) == (sub["date"], sub.get("time"))}

    # requirements
    pairs, extra, missed = match_requirements(parsed["requirements"], key["requirements"])
    record("requirements", pairs, extra, missed, lambda r: "%s | %s" % (r["label"], r["text"][:70]),
           lambda r: "%s | %s" % (r["label"], r.get("text", "")[:70]))
    wrong = []
    for p, k in pairs:
        if p["qtype"] not in [k["qtype"]] + k.get("alt_qtypes", []):
            wrong.append("%s: %s, key says %s" % (k["label"], p["qtype"], "/".join([k["qtype"]] + k.get("alt_qtypes", []))))
    out["question_type"] = {"correct": len(pairs) - len(wrong), "of_found": len(pairs),
                            "of": len(key["requirements"]), "wrong": wrong}
    num = [k for k in key["requirements"] if k.get("numbered", True)]
    found_keys = [id(k) for _, k in pairs]
    out["requirements"]["numbered_found"] = "%d of %d" % (sum(1 for k in num if id(k) in found_keys), len(num))
    out["requirements"]["unnumbered_found"] = "%d of %d" % (
        sum(1 for k in key["requirements"] if not k.get("numbered", True) and id(k) in found_keys),
        len(key["requirements"]) - len(num))
    deleted_parsed = []
    for k in key.get("deleted_requirements", []):
        if any(_label(p["label"]) == _label(k["label"]) or _text_same(p["text"], k.get("text", "")) for p in extra):
            deleted_parsed.append(k["label"])

    # forms
    pairs, extra, missed = _match(parsed["forms"], key["forms"], _form_same)
    record("forms", pairs, extra, missed, lambda f: f["name"])

    # evaluation
    crit = parsed["evaluation"]["criteria"]
    pairs, extra, missed = _match(crit, key["evaluation"], lambda p, k: _crit_same(p, k) and p["weight"] == k["weight"])
    record("evaluation", pairs, extra, missed, lambda c: "%s %s" % (c["name"], c["weight"]),
           lambda c: "%s %s" % (c["name"], c["weight"]))
    out["evaluation"]["weights_parsed_sum"] = sum(c["weight"] or 0 for c in crit)

    # minimum qualifications
    def mq_same(p, k):
        alt = k.get("alt_check_kind") or []
        kinds = [k["check_kind"]] + (alt if isinstance(alt, list) else [alt])
        if _norm(k["starts"]) not in _norm(p["text"]):
            return False
        if p["check_kind"] not in kinds:
            return False
        return p["check_kind"] != k["check_kind"] or p["value"] == k.get("value")
    pairs, extra, missed = _match(parsed["min_quals"], key["min_quals"], mq_same)
    record("min_quals", pairs, extra, missed, lambda q: "%s | %s %s" % (q["text"][:60], q["check_kind"], q["value"]),
           lambda q: "%s | %s %s" % (q["starts"][:60], q["check_kind"], q.get("value")))

    # insurance
    pairs, extra, missed = _match(
        parsed["insurance"], key["insurance"],
        lambda p, k: _norm(k["contains"]) in _norm(p["text"]) and (k.get("amount") is None or k["amount"] in p["amounts"]))
    record("insurance", pairs, extra, missed, lambda x: x["text"][:70],
           lambda x: "%s %s" % (x["contains"], x.get("amount")))

    # mechanics
    km = key["mechanics"]
    want = [("kind", k) for k in km.get("kinds", [])]
    for name, kind in (("page_limit", "page_limit"), ("font_pt", "font"), ("margin_in", "margins")):
        if km.get(name) is not None:
            want.append((kind, km[name]))
    got = [("kind", k) for k in sorted({m["kind"] for m in parsed["mechanics"]})]
    got += [(m["kind"], m["value"]) for m in parsed["mechanics"] if m["kind"] in ("page_limit", "font", "margins")]
    pairs, extra, missed = _match(got, want, lambda p, k: p == k)
    record("mechanics", pairs, extra, missed)
    pl = [m["value"] for m in parsed["mechanics"] if m["kind"] == "page_limit"]
    out["page_limit"] = {"key": km.get("page_limit"), "parsed": pl, "correct": pl == [km.get("page_limit")]}

    # parties
    either = bool(key.get("party_notes"))

    def party_same(p, k):
        if p["name"] != k["name"]:
            return False
        if p["category"] == k["category"]:
            return True
        return either and {p["category"], k["category"]} <= {"adverse", "other_organisation"}
    pairs, extra, missed = _match(parsed["parties"], key["parties"], party_same)
    record("parties", pairs, extra, missed, lambda x: "%s (%s)" % (x["name"], x["category"]),
           lambda x: "%s (%s)" % (x["name"], x["category"]))

    out["negatives_hit"] = {"deadlines": neg_dl, "requirements": list(out["requirements"]["extra"])}
    out["addendum_handling"] = _addenda(parsed, key, deleted_parsed)

    tp = sum(out[c]["tp"] for c in CATEGORIES)
    fp = sum(out[c]["fp"] for c in CATEGORIES)
    fn = sum(out[c]["fn"] for c in CATEGORIES)
    p, r = _prf(tp, fp, fn)
    out["overall"] = {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r}
    out["agency_correct"] = parsed["meta"]["agency"] == key["agency"]
    return out


def _addenda(parsed, key, deleted_parsed):
    """One check per value the key says an addendum changed, as in force after the last addendum."""
    changes = key.get("addendum_changes", [])
    checks = []
    last = {}
    for c in changes:
        target = (c["kind"], c.get("criterion") or c.get("coverage") or (c["from"] if c["kind"] in (
            "requirement_deleted", "criterion_removed", "form_removed") else c["to"] if c["kind"] == "form_added" else ""))
        last[target] = c
    crit = parsed["evaluation"]["criteria"]
    for (kind, _), c in last.items():
        if kind in ("questions_due", "answers_issued", "submission_due", "interview", "award", "conference", "issued"):
            got = [p for p in parsed["deadlines"] if p["kind"] == kind]
            ok = len(got) == 1 and got[0]["date"] == c["to"]
            if ok and c.get("time_to"):
                ok = got[0]["time"] == c["time_to"]
            what = "%s in force %s%s" % (kind, c["to"], " " + c["time_to"] if c.get("time_to") else "")
            if ok:
                first = next(x for x in changes if x["kind"] == kind)
                shown = got[0].get("original_date") == first["from"]
                checks.append({"check": "%s: date as issued (%s) still shown" % (kind, first["from"]), "ok": bool(shown)})
        elif kind == "page_limit":
            got = [m for m in parsed["mechanics"] if m["kind"] == "page_limit"]
            ok = len(got) == 1 and got[0]["value"] == c["to"]
            what = "page limit in force %s" % c["to"]
        elif kind == "form_added":
            ok = any(_form_same(f, c["to"]) for f in parsed["forms"])
            what = "form added: %s" % c["to"]
        elif kind == "form_removed":
            ok = not any(_form_same(f, c["from"]) for f in parsed["forms"])
            what = "form removed: %s" % c["from"]
        elif kind == "requirement_deleted":
            ok = c["from"] not in deleted_parsed and not any(_label(p["label"]) == _label(c["from"]) for p in parsed["requirements"])
            what = "requirement %s deleted" % c["from"]
        elif kind == "criterion_removed":
            ok = bool(crit) and not any(_crit_same(p, {"name": c["from"]}) for p in crit)
            what = "criterion removed: %s" % c["from"]
        elif kind == "weight_changed":
            ok = any(_crit_same(p, {"name": c["criterion"]}) and p["weight"] == c["to"] for p in crit)
            what = "weight of %s now %s" % (c["criterion"], c["to"])
        elif kind == "insurance_changed":
            got = [p for p in parsed["insurance"] if _norm(c["coverage"]) in _norm(p["text"])]
            ok = any(c["to"] in p["amounts"] and c["from"] not in p["amounts"] for p in got)
            what = "insurance %s now %s" % (c["coverage"], c["to"])
        else:
            ok, what = False, "unknown change kind %s" % kind
        checks.append({"check": what, "ok": bool(ok)})
    return {"passed": sum(1 for c in checks if c["ok"]), "of": len(checks), "checks": checks,
            "deleted_requirements_still_parsed": deleted_parsed}


def combine(results):
    total = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORIES + ["overall"]}
    qt = {"correct": 0, "of_found": 0, "of": 0}
    ad = {"passed": 0, "of": 0}
    pl = {"correct": 0, "of": 0}
    sd = {"correct": 0, "of": 0}
    for res in results.values():
        for c in total:
            for k in ("tp", "fp", "fn"):
                total[c][k] += res[c][k]
        for k in qt:
            qt[k] += res["question_type"][k]
        for k in ad:
            ad[k] += res["addendum_handling"][k]
        pl["correct"] += 1 if res["page_limit"]["correct"] else 0
        pl["of"] += 1
        sd["correct"] += 1 if res["submission_deadline"]["correct"] else 0
        sd["of"] += 1
    for c in total:
        total[c]["precision"], total[c]["recall"] = _prf(total[c]["tp"], total[c]["fp"], total[c]["fn"])
    total.update({"question_type": qt, "addendum_handling": ad, "page_limit": pl, "submission_deadline": sd})
    return total


def _table(t):
    lines = ["| Category | Correct | Extra | Missed | Precision | Recall |", "|---|---|---|---|---|---|"]
    for c in CATEGORIES + ["overall"]:
        lines.append("| %s | %d | %d | %d | %.3f | %.3f |" % (c, t[c]["tp"], t[c]["fp"], t[c]["fn"],
                                                              t[c]["precision"], t[c]["recall"]))
    return lines


def report_markdown(title, intro, results):
    comb = combine(results)
    lines = ["# %s" % title, ""] + intro + ["", "## All RFPs in the batch together", ""] + _table(comb)
    lines += ["", "- Submission deadline (date and time in force) right on %d of %d RFPs." % (
        comb["submission_deadline"]["correct"], comb["submission_deadline"]["of"]),
        "- Page limit in force right on %d of %d RFPs." % (comb["page_limit"]["correct"], comb["page_limit"]["of"]),
        "- Addendum handling: %d of %d checks passed." % (comb["addendum_handling"]["passed"], comb["addendum_handling"]["of"]),
        "- Question type right on %d of the %d requirements found (%d in the keys)." % (
            comb["question_type"]["correct"], comb["question_type"]["of_found"], comb["question_type"]["of"]), ""]
    for name, res in results.items():
        lines += ["## %s" % name, "", "Agency name correct: %s" % ("yes" if res["agency_correct"] else "no"), ""] + _table(res)
        lines += ["", "- Requirements: numbered %s, unnumbered %s." % (res["requirements"]["numbered_found"],
                                                                     res["requirements"]["unnumbered_found"]),
                  "- Submission deadline: key %s, parsed %s." % (res["submission_deadline"]["key"],
                                                                ", ".join(res["submission_deadline"]["parsed"]) or "none"),
                  "- Page limit: key %s, parsed %s." % (res["page_limit"]["key"], res["page_limit"]["parsed"] or "none"),
                  "- Addendum handling: %d of %d." % (res["addendum_handling"]["passed"], res["addendum_handling"]["of"])]
        for c in res["addendum_handling"]["checks"]:
            lines.append("  - %s: %s" % ("ok" if c["ok"] else "FAILED", c["check"]))
        for d in res["deadline_kinds_outside_existing_keys"]:
            lines.append("- Deadline kind outside the existing keys (%s %s): %s; not counted either way." % (
                d["kind"], d["date"], "date found" if d["found"] else "not found"))
        if res["negatives_hit"]["deadlines"]:
            lines.append("- Dates wrongly read as deadlines: %s." % "; ".join(res["negatives_hit"]["deadlines"]))
        notes = []
        for c in CATEGORIES:
            for x in res[c]["extra"]:
                notes.append("- extra %s: %s" % (c, x))
            for x in res[c]["missed"]:
                notes.append("- missed %s: %s" % (c, x))
        for x in res["question_type"]["wrong"]:
            notes.append("- question type: %s" % x)
        lines += [""] + (notes or ["No differences from the key."]) + [""]
    return "\n".join(lines)
