"""Evidence engine: decide whether a claim is true of a registry.

A claim's evidence rule is data (see data/claims.json). This module evaluates a
rule against the registry entries and returns one of three statuses:

  SUPPORTED      every condition the rule needs was found and holds
  NOT SUPPORTED  at least one registry entry or field contradicts the claim
  CANNOT TELL    a needed field is missing or recorded as unknown

Only SUPPORTED claims are printed. Dates are compared with an explicit as-of
date passed in by the caller. The system clock is never read.
"""
from __future__ import annotations

from datetime import date

SUPPORTED = "SUPPORTED"
NOT_SUPPORTED = "NOT SUPPORTED"
CANNOT_TELL = "CANNOT TELL"

_RANK = {SUPPORTED: 0, CANNOT_TELL: 1, NOT_SUPPORTED: 2}
_MISSING = object()


class RuleError(ValueError):
    """The rule itself is malformed (a library bug, not a registry gap)."""


def resolve(obj, path: str):
    """Follow a dotted path through nested dicts. Returns _MISSING if absent."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _norm(v, ci: bool):
    return v.strip().lower() if ci and isinstance(v, str) else v


def _expectation(cond: dict, expected) -> str:
    op, f = cond["op"], cond["field"]
    text = {
        "eq": f"{f} must be {expected!r}",
        "ne": f"{f} must not be {expected!r}",
        "in": f"{f} must be one of {expected!r}",
        "not_in": f"{f} must not be one of {expected!r}",
        "contains": f"{f} must include {expected!r}",
        "contains_any": f"{f} must include one of {expected!r}",
        "contains_none": f"{f} must include none of {expected!r}",
        "non_empty": f"{f} must be filled in",
        "is_missing": f"{f} must be absent",
        "not_startswith": f"{f} must not start with {expected!r}",
        "lte": f"{f} must be at most {expected!r}",
        "gte": f"{f} must be at least {expected!r}",
        "within_days": f"{f} must be a date no more than {expected!r} days before the as-of date",
        "on_or_before_as_of": f"{f} must be a date on or before the as-of date",
        "key_of": f"{f} must have an entry in {cond.get('value_from', 'the lookup table')}",
    }.get(op)
    if text is None:
        raise RuleError(f"unknown operator {op!r}")
    return text


def eval_condition(entry: dict, cond: dict, ctx: dict):
    """Evaluate one condition on one entry.

    Returns (result, detail). result is True, False, or None for "cannot tell".
    """
    field, op = cond["field"], cond["op"]
    ci = bool(cond.get("ci"))
    actual = resolve(entry, field)
    expected = cond.get("value")
    detail = {"field": field, "actual": None if actual is _MISSING else actual}

    if "value_from" in cond:
        expected = resolve(ctx, cond["value_from"])
        if expected is _MISSING or expected is None:
            detail.update(expected=_expectation(cond, "?"), reason=f"{cond['value_from']} is not set")
            return None, detail
    detail["expected"] = _expectation(cond, expected)

    missing = actual is _MISSING or actual is None or (isinstance(actual, str) and not actual.strip())
    if op == "is_missing":
        return missing, detail
    if missing:
        detail["reason"] = "field is missing or empty in the record"
        return None, detail
    if any(_norm(actual, True) == _norm(u, True) for u in cond.get("unknown_values", [])):
        detail["reason"] = f"recorded as {actual!r}"
        return None, detail

    a = _norm(actual, ci)
    if op in ("eq", "ne"):
        ok = (a == _norm(expected, ci)) == (op == "eq")
    elif op in ("in", "not_in"):
        ok = (a in [_norm(x, ci) for x in expected]) == (op == "in")
    elif op == "key_of":
        ok = isinstance(expected, dict) and actual in expected
    elif op in ("contains", "contains_any", "contains_none"):
        if not isinstance(actual, list):
            detail["reason"] = "field is not a list"
            return None, detail
        wanted = [expected] if op == "contains" else list(expected)
        hit = any(w in actual for w in wanted)
        ok = (not hit) if op == "contains_none" else hit
    elif op == "non_empty":
        ok = len(actual) > 0 if isinstance(actual, (list, dict, str)) else True
    elif op == "not_startswith":
        ok = not str(actual).strip().lower().startswith(str(expected).lower())
    elif op in ("lte", "gte"):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            detail["reason"] = "field is not a number"
            return None, detail
        ok = actual <= expected if op == "lte" else actual >= expected
    elif op in ("within_days", "on_or_before_as_of"):
        try:
            d = date.fromisoformat(str(actual))
        except ValueError:
            detail["reason"] = "field is not a date (YYYY-MM-DD)"
            return None, detail
        as_of = ctx["as_of"]
        if d > as_of:
            detail["reason"] = f"date is after the as-of date {as_of.isoformat()}"
            return None, detail
        ok = True if op == "on_or_before_as_of" else (as_of - d).days <= int(expected)
        if not ok:
            detail["reason"] = f"{(as_of - d).days} days before the as-of date {as_of.isoformat()}"
    else:
        raise RuleError(f"unknown operator {op!r}")
    return bool(ok), detail


def _eval_all(entry: dict, conds: list, ctx: dict):
    """AND of conditions. Returns (True|False|None, details of every condition)."""
    results = [eval_condition(entry, c, ctx) for c in conds]
    values = [r for r, _ in results]
    verdict = False if False in values else (None if None in values else True)
    return verdict, results


def _blank(universal: bool) -> dict:
    return {"status": SUPPORTED, "universal": universal, "scope": [], "passing": [],
            "failing": [], "unknown": [], "checked": [], "note": ""}


def _scope_conditions(rule: dict, scopes: dict) -> list:
    conds = []
    for name in rule.get("scope", []):
        if name not in scopes:
            raise RuleError(f"unknown scope {name!r}")
        conds += scopes[name]
    return conds + rule.get("where", [])


def is_universal(rule: dict) -> bool:
    """True when the rule makes a claim about every entry in scope (all / none)."""
    if "all_of" in rule:
        parts = [r for r in rule["all_of"] if "context" not in r]
        return bool(parts) and all(is_universal(r) for r in parts)
    if "context" in rule:
        return False
    return rule.get("quantifier") in ("all", "none")


def evaluate_rule(rule: dict, ctx: dict) -> dict:
    """Evaluate a rule. ctx holds registry, inputs, client, derived, scopes, as_of."""
    if "all_of" in rule:
        parts = [evaluate_rule(r, ctx) for r in rule["all_of"]]
        out = _blank(is_universal(rule))
        primary = next((p for r, p in zip(rule["all_of"], parts) if "context" not in r), parts[0])
        out["scope"], out["passing"] = primary["scope"], primary["passing"]
        for p in parts:
            if _RANK[p["status"]] > _RANK[out["status"]]:
                out["status"] = p["status"]
            for k in ("failing", "unknown", "checked"):
                out[k] += p[k]
        out["note"] = " ".join(p["note"] for p in parts if p["note"])
        return out

    if "context" in rule:
        out = _blank(False)
        verdict, results = _eval_all(ctx, rule["context"], ctx)
        for r, d in results:
            row = {"entry": "(inputs)", **d}
            out["checked"].append({"entry": row["entry"], "field": d["field"], "actual": d["actual"]})
            if r is False:
                out["failing"].append(row)
            elif r is None:
                out["unknown"].append(row)
        out["status"] = {True: SUPPORTED, False: NOT_SUPPORTED, None: CANNOT_TELL}[verdict]
        return out

    quant = rule.get("quantifier")
    if quant not in ("all", "none", "at_least"):
        raise RuleError(f"unknown quantifier {quant!r}")
    out = _blank(quant in ("all", "none"))
    scope_conds = _scope_conditions(rule, ctx["scopes"])
    require = rule.get("require", [])
    scope_unknown = False

    for tool in ctx["registry"]["tools"]:
        tid = tool["id"]
        in_scope, sres = _eval_all(tool, scope_conds, ctx)
        if in_scope is False:
            continue
        if in_scope is None:
            scope_unknown = True
            out["unknown"] += [{"entry": tid, **d, "reason": d.get("reason", "") + " (cannot tell whether this entry is in scope)"}
                               for r, d in sres if r is None]
            continue
        out["scope"].append(tid)
        verdict, results = _eval_all(tool, require, ctx)
        for r, d in results:
            out["checked"].append({"entry": tid, "field": d["field"], "actual": d["actual"]})
        if quant == "none":
            # The claim is "no entry in scope matches `require`". A match breaks it.
            if verdict is True:
                out["failing"] += [{"entry": tid, **d, "expected": "no entry in scope may match: " + d["expected"]}
                                   for _, d in results] or [{"entry": tid, "field": "id", "actual": tid,
                                                             "expected": "no entry may be in scope"}]
            elif verdict is None:
                out["unknown"] += [{"entry": tid, **d} for r, d in results if r is None]
            else:
                out["passing"].append(tid)
        else:
            if verdict is True:
                out["passing"].append(tid)
            elif verdict is False:
                out["failing"] += [{"entry": tid, **d} for r, d in results if r is False]
                out["unknown"] += [{"entry": tid, **d} for r, d in results if r is None]
            else:
                out["unknown"] += [{"entry": tid, **d} for r, d in results if r is None]

    n_scope, n_pass = len(out["scope"]), len(out["passing"])
    n_fail = len({f["entry"] for f in out["failing"]})
    if quant == "at_least":
        need = int(rule.get("n", 1))
        if n_pass >= need:
            out["status"] = SUPPORTED
        elif n_scope - n_fail >= need or scope_unknown:
            out["status"] = CANNOT_TELL
        else:
            out["status"] = NOT_SUPPORTED
            out["note"] = f"{n_pass} of {n_scope} entries in scope meet the rule; at least {need} needed."
        return out

    if out["failing"]:
        out["status"] = NOT_SUPPORTED
    elif out["unknown"] or scope_unknown:
        out["status"] = CANNOT_TELL
    elif n_scope == 0 and rule.get("on_empty", "not_supported") != "supported":
        out["status"] = NOT_SUPPORTED
        out["note"] = "No registry entry is in scope for this claim, so there is nothing to base it on."
    return out


def is_printable(result: dict) -> bool:
    """CANNOT TELL is treated the same as NOT SUPPORTED for printing."""
    return result["status"] == SUPPORTED
