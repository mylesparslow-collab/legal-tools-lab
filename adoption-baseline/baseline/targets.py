"""Targets and gates: pass, not yet, or cannot tell."""

PASS, NOT_YET, CANNOT_TELL = "pass", "not yet", "cannot tell"


def _measure(analysis, spec, where=None):
    population = spec.get("population", "lawyers")
    basis = spec.get("basis", "last_4_weeks")
    if spec.get("measure", "weekly_active") == "regular_use" or basis == "regular_use":
        return analysis.regular_use(population, None, where), len(analysis.weeks) >= analysis.window
    if basis == "latest_week":
        return analysis.weekly_active([analysis.weeks[-1]], population, None, where), True
    return (analysis.weekly_active(analysis.last_weeks, population, None, where),
            len(analysis.weeks) >= analysis.window)


def evaluate_one(analysis, spec, quality, defaults, where=None, label=None, ident=None):
    c, enough_weeks = _measure(analysis, spec, where)
    min_people = int(spec.get("min_people", defaults.get("min_people", 20)))
    max_unknown = float(defaults.get("max_unknown_user_row_share", 0.10))
    result = {
        "id": ident or spec["id"], "label": label or spec["label"],
        "basis": spec.get("basis", "last_4_weeks"), "threshold": spec["threshold"],
        "due_month": spec.get("due_month"), "min_people": min_people,
        "n": None, "d": None, "people": None, "rate": None,
    }
    reasons = []
    if not enough_weeks:
        reasons.append("fewer than %d complete weeks in the period" % analysis.window)
    if (c["people"] or 0) < max(min_people, analysis.threshold):
        reasons.append("fewer than %d people in the group" % max(min_people, analysis.threshold))
    if quality["tools_with_no_rows"]:
        reasons.append("no usage rows for: " + ", ".join(quality["tools_with_no_rows"]))
    share = quality["totals"]["unknown_user_row_share"]
    if share is not None and share > max_unknown:
        reasons.append("%.0f%% of export rows could not be matched to the roster" % (100 * share))
    # Numbers for a group under the suppression threshold are never shown.
    if (c["people"] or 0) >= analysis.threshold:
        result.update({k: c[k] for k in ("n", "d", "people", "rate")})
    if reasons:
        result["status"], result["reason"] = CANNOT_TELL, "; ".join(reasons)
    elif c["rate"] >= spec["threshold"]:
        result["status"], result["reason"] = PASS, "at or above the threshold"
    else:
        result["status"], result["reason"] = NOT_YET, "below the threshold"
    return result


def evaluate(analysis, targets, quality):
    out = {"programme_month": targets.get("programme_month"), "targets": [], "gates": []}
    for spec in targets.get("targets", []):
        out["targets"].append(evaluate_one(analysis, spec, quality, targets))
    for spec in targets.get("gates", []):
        practices = spec.get("each_practice")
        if not practices:
            out["gates"].append(evaluate_one(analysis, spec, quality, targets))
            continue
        for practice in practices:
            r = evaluate_one(analysis, spec, quality, targets,
                             where=lambda rec, practice=practice: rec["practice"] == practice,
                             label="%s: %s" % (spec["label"], practice),
                             ident="%s:%s" % (spec["id"], practice))
            r["practice"] = practice
            out["gates"].append(r)
    return out
