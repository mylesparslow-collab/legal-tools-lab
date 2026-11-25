"""Score the parser against a hand-written answer key.

Every parsed item counts, including items the parser marked "check". An item
the key does not list is a false positive even if it was flagged for review.
"""
import re

CATEGORIES = ["deadlines", "addendum_changes", "requirements", "forms", "evaluation", "min_quals",
              "insurance", "mechanics", "parties"]


def _norm(s):
    return re.sub(r"[^a-z0-9$]+", " ", str(s).lower()).strip()


def _match(parsed_items, key_items, same):
    """Greedy one-to-one matching. Returns (tp, extra parsed, missed key)."""
    left = list(parsed_items)
    missed, tp = [], 0
    for k in key_items:
        hit = next((p for p in left if same(p, k)), None)
        if hit is None:
            missed.append(k)
        else:
            left.remove(hit)
            tp += 1
    return tp, left, missed


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return round(p, 3), round(r, 3)


def evaluate(parsed, key):
    out = {}

    def record(cat, tp, extra, missed, show=lambda x: x):
        p, r = _prf(tp, len(extra), len(missed))
        out[cat] = {"tp": tp, "fp": len(extra), "fn": len(missed), "precision": p, "recall": r,
                    "extra": [show(x) for x in extra], "missed": [str(x) for x in missed]}

    tp, extra, missed = _match(
        parsed["deadlines"], key["deadlines"],
        lambda p, k: (p["kind"], p["date"], p["time"]) == (k["kind"], k["date"], k["time"]))
    record("deadlines", tp, extra, missed, lambda d: "%s %s %s" % (d["kind"], d["date"], d["time"]))

    changes = [c for a in parsed["addenda"] for c in a["changes"]]
    tp, extra, missed = _match(
        changes, key["addendum_changes"],
        lambda p, k: (p["kind"], p["from"], p["to"]) == (k["kind"], k["from"], k["to"]))
    record("addendum_changes", tp, extra, missed, lambda c: "%s %s -> %s" % (c["kind"], c["from"], c["to"]))

    tp, extra, missed = _match(parsed["requirements"], key["requirements"],
                               lambda p, k: p["label"] == k["label"])
    record("requirements", tp, extra, missed, lambda r: "%s %s" % (r["label"], r["text"][:50]))
    by_label = {r["label"]: r for r in parsed["requirements"]}
    typed = [(k, by_label[k["label"]]) for k in key["requirements"] if k["label"] in by_label]
    out["question_type"] = {"correct": sum(1 for k, p in typed if p["qtype"] == k["qtype"]),
                            "of": len(key["requirements"]),
                            "wrong": ["%s: %s, key says %s" % (k["label"], p["qtype"], k["qtype"])
                                      for k, p in typed if p["qtype"] != k["qtype"]]}

    def form_same(p, k):
        a, b = _norm(p["name"]), _norm(k)
        return a == b or a.startswith(b) or b.startswith(a)
    tp, extra, missed = _match(parsed["forms"], key["forms"], form_same)
    record("forms", tp, extra, missed, lambda f: f["name"])

    tp, extra, missed = _match(
        parsed["evaluation"]["criteria"], key["evaluation"],
        lambda p, k: _norm(p["name"]) == _norm(k["name"]) and p["weight"] == k["weight"])
    record("evaluation", tp, extra, missed, lambda c: "%s %s" % (c["name"], c["weight"]))

    tp, extra, missed = _match(
        parsed["min_quals"], key["min_quals"],
        lambda p, k: p["text"].startswith(k["starts"]) and p["check_kind"] == k["check_kind"]
        and p["value"] == k["value"])
    record("min_quals", tp, extra, missed, lambda q: "%s %s %s" % (q["text"][:50], q["check_kind"], q["value"]))

    tp, extra, missed = _match(
        parsed["insurance"], key["insurance"],
        lambda p, k: _norm(k["contains"]) in _norm(p["text"]) and (k["amount"] is None or k["amount"] in p["amounts"]))
    record("insurance", tp, extra, missed, lambda x: x["text"][:60])

    km = key["mechanics"]
    want = [("kind", k) for k in km["kinds"]]
    for name, kind in (("page_limit", "page_limit"), ("font_pt", "font"), ("margin_in", "margins")):
        if km.get(name) is not None:
            want.append((kind, km[name]))
    got = [("kind", k) for k in sorted({m["kind"] for m in parsed["mechanics"]})]
    got += [(m["kind"], m["value"]) for m in parsed["mechanics"] if m["kind"] in ("page_limit", "font", "margins")]
    tp, extra, missed = _match(got, want, lambda p, k: p == k)
    record("mechanics", tp, extra, missed, str)

    tp, extra, missed = _match(parsed["parties"], key["parties"],
                               lambda p, k: p["name"] == k["name"] and p["category"] == k["category"])
    record("parties", tp, extra, missed, lambda x: "%s (%s)" % (x["name"], x["category"]))

    tp = sum(out[c]["tp"] for c in CATEGORIES)
    fp = sum(out[c]["fp"] for c in CATEGORIES)
    fn = sum(out[c]["fn"] for c in CATEGORIES)
    p, r = _prf(tp, fp, fn)
    out["overall"] = {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r}
    out["agency_correct"] = parsed["meta"]["agency"] == key["agency"]
    return out


def combine(results):
    """Micro-average over several RFPs. results: {name: evaluate() output}."""
    total = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORIES + ["overall"]}
    qt = {"correct": 0, "of": 0}
    for res in results.values():
        for c in total:
            for k in ("tp", "fp", "fn"):
                total[c][k] += res[c][k]
        qt["correct"] += res["question_type"]["correct"]
        qt["of"] += res["question_type"]["of"]
    for c in total:
        total[c]["precision"], total[c]["recall"] = _prf(total[c]["tp"], total[c]["fp"], total[c]["fn"])
    total["question_type"] = qt
    return total


def report_markdown(results):
    lines = ["# Parser check against hand-written answer keys", "",
             "The keys were written by hand from the RFP text. The parser and the keys were written",
             "by the same person for the same four documents, so these figures are in-sample.",
             "They show that the parser does what it was built to do on these files. They do not",
             "predict accuracy on other RFPs. Items the parser marked \"check\" are counted like any",
             "other item.", ""]
    comb = combine(results)
    lines += ["## All four RFPs together", "", "| Category | Correct | Extra | Missed | Precision | Recall |",
              "|---|---|---|---|---|---|"]
    for c in CATEGORIES + ["overall"]:
        t = comb[c]
        lines.append("| %s | %d | %d | %d | %.3f | %.3f |" % (c, t["tp"], t["fp"], t["fn"], t["precision"], t["recall"]))
    lines += ["", "Question type correct on %d of %d requirements." % (comb["question_type"]["correct"],
                                                                     comb["question_type"]["of"]), ""]
    for name, res in results.items():
        lines += ["## %s" % name, "", "Agency name correct: %s" % ("yes" if res["agency_correct"] else "no"), "",
                  "| Category | Correct | Extra | Missed | Precision | Recall |", "|---|---|---|---|---|---|"]
        for c in CATEGORIES + ["overall"]:
            t = res[c]
            lines.append("| %s | %d | %d | %d | %.3f | %.3f |" % (c, t["tp"], t["fp"], t["fn"], t["precision"], t["recall"]))
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
