"""Clearance engine: one decision per tool feature for a matter.

The engine holds no rule content. It reads rules from data/policy.json and applies them with a
small generic evaluator. The most restrictive rule that fires wins. Unknown never clears
restricted data.
"""
import re
from datetime import date

from . import DECISION_LABELS

UNKNOWN = "unknown"
DISCLAIMER = ("Personal portfolio demo with fictional data. Every rule shown is a configurable firm policy "
              "default, not a statement of law. Not legal advice. Not reviewed by an attorney.")


# ------------------------------------------------------------------ evaluator

def lookup(ctx, path):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return UNKNOWN
    return UNKNOWN if cur is None else cur


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def test(cond, ctx):
    """Evaluate a condition tree: {"all": [...]}, {"any": [...]}, {"not": c} or a leaf."""
    if "all" in cond:
        return all(test(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(test(c, ctx) for c in cond["any"])
    if "not" in cond:
        return not test(cond["not"], ctx)
    val = lookup(ctx, cond["fact"])
    op = cond["op"]
    other = lookup(ctx, cond["value_fact"]) if "value_fact" in cond else cond.get("value")
    if op == "eq":
        return val == other and type(val) == type(other)
    if op == "ne":
        return not (val == other and type(val) == type(other))
    if op == "in":
        return val in other
    if op == "not_in":
        return val not in other
    if op == "contains":
        return isinstance(val, list) and other in val
    if op == "not_contains":
        return not (isinstance(val, list) and other in val)
    if op == "gt":
        return _is_number(val) and _is_number(other) and val > other
    if op == "is_unknown":
        return val == UNKNOWN
    if op == "is_number":
        return _is_number(val)
    if op == "is_list":
        return isinstance(val, list)
    raise ValueError("unknown operator: %s" % op)


def fill(template, ctx):
    return re.sub(r"\{([a-z_.]+)\}", lambda m: str(lookup(ctx, m.group(1))), template)


def most_restrictive(decisions, precedence):
    return min(decisions, key=precedence.index)


# ---------------------------------------------------------------------- facts

def build_parties(matter, store, patterns):
    """One terms summary per party whose terms govern the matter: the client, then any insurer or co-counsel."""
    client = store.party_record(matter["client_id"])
    out = []
    summary = store.party_summary(matter["client_id"], matter.get("terms_document_ids", []), patterns)
    out.append(_party_facts(summary, client, matter.get("consents", []),
                            [n for n in matter.get("notices", []) if n.get("to") == matter["client_id"]]))
    for extra in matter.get("additional_terms", []):
        rec = dict(store.party_record(extra["party_id"]))
        for k in ("approved_tools", "analyst_findings"):
            if k in extra:
                rec[k] = extra[k]
        summary = store.party_summary(extra["party_id"], extra.get("document_ids", []), patterns)
        summary["role"] = extra.get("role", summary["role"])
        out.append(_party_facts(summary, rec, matter.get("consents", []), extra.get("notices", [])))
    return out


def _party_facts(summary, record, consents, notices):
    return {
        "summary": summary,
        "consents": [c for c in consents if c.get("from") == summary["party_id"]],
        "notices": notices,
        "terms": {
            "party_id": summary["party_id"],
            "party_name": summary["party_name"],
            "party_short": summary["party_short"],
            "role": summary["role"],
            "status": summary["status"],
            "classes": summary["classes"],
            "has_conflict": bool(summary["conflicts"]),
            "has_review_hits": bool(summary["review_hits"]),
            "approved_tools": record.get("approved_tools", UNKNOWN),
            "findings": record.get("analyst_findings", {}),
        },
    }


def _in_scope(hit, feature, data_class, approved_tools):
    scope = hit.get("scope")
    if not scope:
        return True
    if "data_classes" in scope and data_class not in scope["data_classes"]:
        return False
    if scope.get("only_tools_off_approved_list") and isinstance(approved_tools, list) \
            and feature["tool_id"] in approved_tools:
        return False
    return True


def _party_ctx(party, feature, data_class):
    """Facts for one party, one feature and one data class. Returns (ctx, hits in scope by class)."""
    covering = [c for c in party["consents"]
                if c.get("feature_ids") == "all" or feature["id"] in (c.get("feature_ids") or [])]
    summary = party["summary"]
    scoped = {}
    for cls, hits in summary["hits_by_class"].items():
        keep = [h for h in hits if _in_scope(h, feature, data_class, party["terms"]["approved_tools"])]
        if keep:
            scoped[cls] = keep
    terms = dict(party["terms"])
    terms["classes"] = ["silent"] if summary["status"] == "silent" else [c for c in summary["classes"] if c in scoped]
    ctx = {
        "terms": terms,
        "consent": {"covers_feature": bool(covering),
                    "reference": covering[0].get("reference", UNKNOWN) if covering else "none"},
        "notice": {"given": "yes" if party["notices"] else "no",
                   "reference": party["notices"][0].get("reference", UNKNOWN) if party["notices"] else "none"},
    }
    return ctx, scoped


def classes_in_play(matter, policy):
    out = []
    ctx = {"matter": matter}
    for dc in policy["data_classes"]:
        rule = dc["in_play"]
        if rule == "always":
            out.append(dc["id"])
        elif isinstance(rule, dict) and lookup(ctx, rule["fact"]) != rule["unless"]:
            out.append(dc["id"])
    return out


# ------------------------------------------------------------------- evidence

def _span(h):
    return {"document_id": h["document_id"], "start": h["start"], "end": h["end"], "class": h["class"], "quote": h["quote"]}


def _evidence(rule, party, matter, scoped=None):
    ev = rule.get("evidence") or {}
    out = []
    if party:
        s = party["summary"]
        if "clause_class" in ev:
            out += [_span(h) for h in (scoped or {}).get(ev["clause_class"], [])]
        if ev.get("conflicts"):
            for c in s["conflicts"]:
                out += [_span(h) for h in c["spans"]]
        if ev.get("review_hits"):
            out += [_span(h) for h in s["review_hits"]]
    if "po_field" in ev:
        po = matter.get("protective_order", {})
        for q in po.get("quoted_terms", []):
            if q.get("field") == ev["po_field"]:
                out.append({"document_id": po.get("document_id", "protective order"), "start": None, "end": None,
                            "class": "protective_order." + ev["po_field"], "quote": q["quote"],
                            "note": "Quoted by the person who completed intake. The tool does not read the order."})
    seen, uniq = set(), []
    for e in out:
        key = (e["document_id"], e["start"], e["class"], e["quote"])
        if key not in seen:
            seen.add(key)
            uniq.append(e)
    return uniq


# --------------------------------------------------------------------- engine

def _evaluate_class(feature, data_class, matter, parties, policy, as_of):
    precedence = policy["decision_precedence"]
    fired = []
    for rule in policy["rules"]:
        if rule.get("kind") == "unknown_guard":
            continue
        if "*" not in rule["data_classes"] and data_class not in rule["data_classes"]:
            continue
        for party in (parties if rule.get("per") == "terms_party" else [None]):
            ctx = {"matter": matter, "feature": feature, "ctx": {"data_class": data_class}}
            scoped = None
            if party:
                pctx, scoped = _party_ctx(party, feature, data_class)
                ctx.update(pctx)
            if test(rule["when"], ctx):
                fired.append(_driver(rule, data_class, party, matter, ctx, as_of, scoped))
    decision = most_restrictive([d["decision"] for d in fired] + ["ALLOWED"], precedence)
    guard = policy.get("unknown_guard", {})
    dc = next(c for c in policy["data_classes"] if c["id"] == data_class)
    if dc.get("restricted") and decision in ("ALLOWED", "ALLOWED_WITH_CONDITIONS"):
        ctx = {"matter": matter, "feature": feature}
        unknown = [f for f in guard.get("facts", {}).get(data_class, []) if lookup(ctx, f) == UNKNOWN]
        if unknown:
            rule = next(r for r in policy["rules"] if r["id"] == guard["rule_id"])
            d = _driver(rule, data_class, None, matter, ctx, as_of)
            d["unknown_facts"] = unknown
            fired.append(d)
            decision = most_restrictive([decision, rule["decision"]], precedence)
    for d in fired:
        d["decisive"] = d["decision"] == decision
    return decision, fired


def _driver(rule, data_class, party, matter, ctx, as_of, scoped=None):
    d = {
        "rule_id": rule["id"], "rule_text": rule["text"], "source": rule.get("source", ""),
        "owner_role": rule["owner_role"], "review_date": rule["review_date"],
        "past_review_date": rule["review_date"] < as_of,
        "decision": rule["decision"], "data_classes": [data_class],
        "party_id": party["terms"]["party_id"] if party else None,
        "party_name": party["terms"]["party_name"] if party else None,
        "evidence": _evidence(rule, party, matter, scoped),
        "banner": rule.get("banner"), "open_question": rule.get("open_question"),
    }
    if rule.get("condition"):
        d["condition"] = {"short": fill(rule["condition"]["short"], ctx), "text": fill(rule["condition"]["text"], ctx),
                          "rule_id": rule["id"]}
    return d


def clear_feature(feature, matter, parties, policy, in_play, as_of):
    precedence = policy["decision_precedence"]
    rollup = policy["rollup"]
    by_class, drivers = {}, {}
    for dc in in_play:
        decision, fired = _evaluate_class(feature, dc, matter, parties, policy, as_of)
        by_class[dc] = {"decision": decision, "rule_ids": sorted({d["rule_id"] for d in fired if d["decisive"]})}
        for d in fired:
            key = (d["rule_id"], d["party_id"])
            if key in drivers:
                drivers[key]["data_classes"].append(dc)
                drivers[key]["decisive"] = drivers[key]["decisive"] or d["decisive"]
            else:
                drivers[key] = d

    def conditions_for(dc):
        return [d["condition"] for d in drivers.values()
                if d.get("condition") and dc in d["data_classes"] and d["decision"] == "ALLOWED_WITH_CONDITIONS"]

    base = rollup["base_class"]
    overall = by_class[base]["decision"]
    conditions = list(conditions_for(base)) if overall == "ALLOWED_WITH_CONDITIONS" else []
    excluded, pending = [], []
    # If intake does not say whether a restricted class is present at all, its rules were run on
    # unknown facts. Their result is not a finding about the feature, so it neither blocks nor
    # excludes: the feature is held until intake is completed.
    hold_unknown = rollup.get("unknown_class_status", "hold_feature") == "hold_feature"
    status_unknown = []
    for meta in policy["data_classes"]:
        rule = meta.get("in_play")
        if isinstance(rule, dict) and meta.get("restricted") and lookup({"matter": matter}, rule["fact"]) == UNKNOWN:
            status_unknown.append(meta["id"])
    if overall != "NOT_ALLOWED":
        for dc in in_play:
            if dc == base or (hold_unknown and dc in status_unknown):
                continue
            d = by_class[dc]["decision"]
            meta = next(c for c in policy["data_classes"] if c["id"] == dc)
            if d in ("NOT_ALLOWED", "HOLD_FOR_REVIEW") and rollup["restricted_class_denied"] == "block_feature":
                # The feature takes the restricted class result for the whole matter. A hold stays a hold.
                overall = most_restrictive([overall, d], precedence)
            elif d == "HOLD_FOR_REVIEW" and rollup.get("hold_propagates", False):
                overall = most_restrictive([overall, "HOLD_FOR_REVIEW"], precedence)
            elif d in ("NOT_ALLOWED", "HOLD_FOR_REVIEW"):
                excluded.append(dc)
                cond = dict(meta["exclude_condition"], rule_id=",".join(by_class[dc]["rule_ids"]))
                if d == "HOLD_FOR_REVIEW":
                    pending.append(dc)
                    cond["text"] = cond["text"].rstrip(".") + " until the hold is cleared."
                conditions.append(cond)
                overall = most_restrictive([overall, "ALLOWED_WITH_CONDITIONS"], precedence)
            elif d == "ALLOWED_WITH_CONDITIONS":
                conditions += conditions_for(dc)
                overall = most_restrictive([overall, "ALLOWED_WITH_CONDITIONS"], precedence)
    if hold_unknown and status_unknown and overall != "NOT_ALLOWED":
        overall = "HOLD_FOR_REVIEW"
        for d in drivers.values():
            if d["decision"] == "HOLD_FOR_REVIEW" and set(d["data_classes"]) & set(status_unknown):
                d["decisive"] = True
    uniq, seen = [], set()
    for c in conditions:
        if (c["rule_id"], c["text"]) not in seen:
            seen.add((c["rule_id"], c["text"]))
            uniq.append(c)
    cleared = overall in ("ALLOWED", "ALLOWED_WITH_CONDITIONS")
    driver_list = sorted(drivers.values(), key=lambda d: (precedence.index(d["decision"]), d["rule_id"]))
    blocking = [d for d in driver_list if d["decisive"] and d["decision"] == overall] if not cleared else []
    return {
        "feature_id": feature["id"], "tool_id": feature["tool_id"], "tool_name": feature["tool_name"],
        "feature": feature["feature"], "short_name": feature.get("short_name", feature["id"]),
        "category": feature.get("category", ""),
        "decision": overall, "decision_label": DECISION_LABELS[overall],
        "conditions": uniq if overall == "ALLOWED_WITH_CONDITIONS" else [],
        "conditions_if_cleared": uniq if not cleared else [],
        "excluded_data_classes": excluded if cleared else [],
        "pending_data_classes": pending if cleared else [],
        "by_data_class": by_class,
        "reasons": _unique([d["banner"] or d["rule_text"] for d in blocking]),
        "rule_ids": sorted({d["rule_id"] for d in driver_list if d["decisive"]}),
        "drivers": driver_list,
    }


def _unique(items):
    out = []
    for i in items:
        if i not in out:
            out.append(i)
    return out


def clear_matter(matter, store, features, policy, patterns, as_of=None):
    """Return the full clearance record for one matter."""
    as_of = as_of or date.today().isoformat()
    parties = build_parties(matter, store, patterns)
    in_play = classes_in_play(matter, policy)
    decisions = [clear_feature(f, matter, parties, policy, in_play, as_of) for f in features]
    stale = [{"rule_id": r["id"], "review_date": r["review_date"], "owner_role": r["owner_role"],
              "used_on_this_matter": any(r["id"] in d["rule_ids"] or any(x["rule_id"] == r["id"] for x in d["drivers"])
                                         for d in decisions)}
             for r in policy["rules"] if r["review_date"] < as_of]
    unknown_inputs = []
    for path in ("data_flags.phi", "data_flags.sealed", "protective_order.present"):
        if lookup(matter, path) == UNKNOWN:
            unknown_inputs.append(path)
    if lookup(matter, "protective_order.present") == "yes":
        for k in ("ai_use", "vendor_processing", "no_retention_after_matter", "attorneys_eyes_only_tier"):
            if lookup(matter, "protective_order.restrictions." + k) == UNKNOWN:
                unknown_inputs.append("protective_order.restrictions." + k)
    terms = []
    for p in parties:
        s = p["summary"]
        terms.append({
            "party_id": s["party_id"], "party_name": s["party_name"], "role": s["role"], "status": s["status"],
            "documents": s["documents"], "classes": s["classes"],
            "conflicts": [{"pair": c["pair"], "documents": c["documents"], "spans": [_span(h) for h in c["spans"]]}
                          for c in s["conflicts"]],
            "review_spans": [_span(h) for h in s["review_hits"]],
            "dismissed_by_analyst": [{"document_id": h["document_id"], "class": h["class"], "quote": h["quote"],
                                      "start": h["start"], "end": h["end"], "by": h["dismissed_by"],
                                      "date": h["dismissed_on"], "reason": h["reason"]} for h in s["dismissed"]],
            "guarded": s["guarded"],
            "consent_on_file": [c.get("reference") for c in p["consents"]],
            "notice_on_file": [n.get("reference") for n in p["notices"]],
        })
    needs_review = any(t["status"] == "needs_analyst_review" for t in terms)
    counts = {k: sum(1 for d in decisions if d["decision"] == k) for k in DECISION_LABELS}
    oq = sorted({x["open_question"] for d in decisions for x in d["drivers"] if x.get("open_question")})
    record = {
        "matter": {k: matter.get(k) for k in ("id", "name", "client_id", "matter_type", "responsible_attorney",
                                               "intake_date", "data_flags", "protective_order", "intake_note")},
        "client_name": store.party_record(matter["client_id"])["name"],
        "as_of": as_of,
        "policy_version": policy.get("version", ""),
        "pattern_version": patterns.version,
        "data_classes_in_play": in_play,
        "flags": {"needs_analyst_review": needs_review, "unknown_inputs": unknown_inputs},
        "terms": terms,
        "decisions": decisions,
        "counts": counts,
        "rules_past_review": stale,
        "open_questions": oq,
        "disclaimer": DISCLAIMER,
    }
    record["banner"] = banner(record, policy)
    return record


# --------------------------------------------------------------------- banner

def _names(group, all_decisions):
    """Short names for the banner. A tool whose every feature is in the group is named once."""
    out, done = [], set()
    for d in group:
        tool = d["tool_id"]
        if tool in done:
            continue
        total = [x for x in all_decisions if x["tool_id"] == tool]
        mine = [x for x in group if x["tool_id"] == tool]
        if len(total) > 1 and len(mine) == len(total):
            out.append("%s (all %d features)" % (d["tool_name"], len(total)))
            done.add(tool)
        else:
            out.append(d["short_name"])
    return out


def banner(record, policy):
    """One line for the matter header."""
    decisions = record["decisions"]
    in_play = record["data_classes_in_play"]
    labels = {c["id"]: c for c in policy["data_classes"]}
    exclusion_shorts = {c["exclude_condition"]["short"] for c in policy["data_classes"] if "exclude_condition" in c}
    cleared = [d for d in decisions if d["decision"] in ("ALLOWED", "ALLOWED_WITH_CONDITIONS")]
    held = [d for d in decisions if d["decision"] == "HOLD_FOR_REVIEW"]
    parts = []
    if cleared:
        plain = [d for d in cleared if d["decision"] == "ALLOWED"]
        cond = [d for d in cleared if d["decision"] == "ALLOWED_WITH_CONDITIONS"]
        bits = []
        if plain:
            bits.append("%s allowed" % ", ".join(_names(plain, decisions)))
        if cond:
            shorts = _unique([c["short"] for d in cond for c in d["conditions"] if c["short"] not in exclusion_shorts])
            text = "%s allowed" % ", ".join(_names(cond, decisions))
            if shorts:
                text += " with " + ", ".join(shorts)
            bits.append(text)
        parts.append("; ".join(bits))
        if held:
            parts.append("%d other feature%s on hold" % (len(held), "" if len(held) == 1 else "s"))
    elif held:
        reasons = _unique([r for d in held for r in d["reasons"]])
        parts.append("on hold for review (%s)" % "; ".join(reasons[:3]))
    else:
        common = [r for r in decisions[0]["reasons"] if all(r in d["reasons"] for d in decisions)] if decisions else []
        if not common:
            counts = {}
            for d in decisions:
                for r in d["reasons"]:
                    counts[r] = counts.get(r, 0) + 1
            common = sorted(counts, key=lambda r: -counts[r])[:2]
        more = " and %d more" % (len(common) - 3) if len(common) > 3 else ""
        parts.append("not allowed on this matter (%s%s)" % ("; ".join(common[:3]), more))
    for dc in in_play:
        meta = labels[dc]
        if not meta.get("restricted"):
            continue
        ok = [d["short_name"] for d in cleared
              if d["by_data_class"][dc]["decision"] in ("ALLOWED", "ALLOWED_WITH_CONDITIONS")]
        waiting = [d["short_name"] for d in cleared if dc in d.get("pending_data_classes", [])]
        text = "no %s in any tool" % meta["label"]
        if ok:
            text += " except " + ", ".join(ok)
        if waiting:
            text += " (%s pending review)" % ", ".join(waiting)
        parts.append(text)
    if record["flags"]["needs_analyst_review"]:
        parts.append("terms need analyst review")
    return "AI: " + "; ".join(parts)
