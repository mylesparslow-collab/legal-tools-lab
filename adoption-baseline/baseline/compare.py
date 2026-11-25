"""Compare two baselines.

Rule for calling a change, kept deliberately simple:

- both periods must describe at least `min_people` people in the group, and
- the rate must move by at least `min_change_points` percentage points.

If the group is too small the answer is "too small to call", whatever the
arithmetic says. No confidence intervals are reported, because the groups are
whole populations of modest size and a p-value would suggest precision that
is not there.
"""
import json

UP, DOWN, NO_CLEAR, TOO_SMALL, SUPPRESSED, MISSING = (
    "up", "down", "no clear change", "too small to call", "suppressed", "not in both periods")


class CompareError(ValueError):
    pass


def compare_cells(a, b, min_people, min_change_points):
    row = {"earlier": _slim(a), "later": _slim(b), "change_points": None}
    if a is None or b is None:
        row["call"] = MISSING
    elif a.get("suppressed") or b.get("suppressed"):
        row["call"] = SUPPRESSED
    elif a["rate"] is None or b["rate"] is None:
        row["call"] = TOO_SMALL
    else:
        change = 100 * (b["rate"] - a["rate"])
        row["change_points"] = round(change, 1)
        if min(a["people"], b["people"]) < min_people:
            row["call"] = TOO_SMALL
        elif abs(change) < min_change_points:
            row["call"] = NO_CLEAR
        else:
            row["call"] = UP if change > 0 else DOWN
    return row


def _slim(c):
    if c is None:
        return None
    return {k: c.get(k) for k in ("n", "d", "people", "rate", "suppressed")}


def compare(earlier, later, rules=None):
    if earlier.get("definitions_version") != later.get("definitions_version"):
        raise CompareError("the two baselines use different metric definitions (%s and %s); not comparable"
                           % (earlier.get("definitions_version"), later.get("definitions_version")))
    rules = rules or later["meta"].get("compare_rules") or {}
    min_people = int(rules.get("min_people", 30))
    min_change = float(rules.get("min_change_points", 5))
    out = {
        "definitions_version": later["definitions_version"],
        "earlier_period": [earlier["meta"]["period_start"], earlier["meta"]["period_end"]],
        "later_period": [later["meta"]["period_start"], later["meta"]["period_end"]],
        "earlier_weeks": [earlier["meta"]["last_weeks"][0], earlier["meta"]["last_weeks"][-1]],
        "later_weeks": [later["meta"]["last_weeks"][0], later["meta"]["last_weeks"][-1]],
        "rule": {"min_people": min_people, "min_change_points": min_change,
                 "text": "A change is called only when both periods cover at least %d people and the rate "
                         "moves by at least %g percentage points." % (min_people, min_change)},
        "headline": {}, "breakdowns": {},
    }
    for name, c in later["headline"].items():
        if name == "activated":
            continue        # cumulative over the period, so it depends on period length
        out["headline"][name] = compare_cells(earlier["headline"].get(name), c, min_people, min_change)
    for dim, table in later["breakdowns"].items():
        old = {r["group"]: r for r in earlier["breakdowns"].get(dim, {}).get("rows", [])}
        rows = []
        for r in table["rows"]:
            o = old.get(r["group"])
            rows.append({"group": r["group"], "measures": {
                m: compare_cells(o["cells"].get(m) if o else None, c, min_people, min_change)
                for m, c in r["cells"].items() if m in ("weekly_active_last_4_weeks", "regular_use")}})
        out["breakdowns"][dim] = rows
    return out


def to_markdown(result):
    def fmt(c):
        if c is None:
            return "n/a"
        if c.get("suppressed"):
            return "suppressed"
        if c["rate"] is None:
            return "n/a"
        return "%.0f%% (%d of %d)" % (100 * c["rate"], c["n"], c["d"])

    def change(r):
        return "" if r["change_points"] is None else "%+.1f" % r["change_points"]

    lines = ["# Change between two baselines", "",
             "Earlier period: %s to %s. Later period: %s to %s." % tuple(result["earlier_period"] + result["later_period"]),
             "Rates use the last weeks of each period: %s to %s, against %s to %s."
             % tuple(result["earlier_weeks"] + result["later_weeks"]),
             "", result["rule"]["text"], "",
             "Synthetic demo data.", "",
             "## Lawyers, firm-wide", "", "| Measure | Earlier | Later | Change (points) | Call |", "|---|---|---|---|---|"]
    for name, r in result["headline"].items():
        lines.append("| %s | %s | %s | %s | %s |" % (name.replace("_", " "), fmt(r["earlier"]), fmt(r["later"]), change(r), r["call"]))
    for dim, rows in result["breakdowns"].items():
        lines += ["", "## Weekly active, last 4 weeks, by %s" % dim, "",
                  "| Group | Earlier | Later | Change (points) | Call |", "|---|---|---|---|---|"]
        for row in rows:
            r = row["measures"]["weekly_active_last_4_weeks"]
            lines.append("| %s | %s | %s | %s | %s |" % (row["group"], fmt(r["earlier"]), fmt(r["later"]), change(r), r["call"]))
    return "\n".join(lines) + "\n"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
