"""Deterministic first-pass checks on a 60-day notice. Every result names the rule it used.

Inputs are plain values. Where a value was extracted from a document (by a person or a model), the
caller should run it through prop65.verifier first; `triage_case` refuses unanchored values.
"""
from __future__ import annotations
from datetime import date, timedelta

from .rules import rule, cite, find_chemical


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _result(check, status, summary, rule_ids, detail=None, review=None):
    rules_used = [cite(r) for r in rule_ids]
    notes = [rule(r).get("attorney_review") for r in rule_ids if rule(r).get("attorney_review")]
    if review:
        notes.append(review)
    return {"check": check, "status": status, "summary": summary, "detail": detail or {},
            "rules": rules_used, "attorney_review": notes}


# ---------------------------------------------------------------- 12-month grace period
def grace_period(chemical: str, exposure_date: date) -> dict:
    rows = find_chemical(chemical)
    months = rule("grace_12_month")["params"]["months"]
    if not rows:
        return _result("grace_period", "NOT_IN_TABLE",
                       f"{chemical} is not in this demo's chemical table. Look up its listing date on the OEHHA list.",
                       ["grace_12_month"])
    seen, per = set(), []
    for r in rows:
        k = (r["endpoint"], r["date_listed"])
        if k in seen:
            continue
        seen.add(k)
        start = _add_months(r["date_listed"], months)
        per.append({"endpoint": r["endpoint"], "date_listed": r["date_listed"].isoformat(),
                    "warning_required_from": start.isoformat(), "in_grace": exposure_date < start})
    all_grace = all(p["in_grace"] for p in per)
    any_grace = any(p["in_grace"] for p in per)
    if all_grace:
        status, msg = "EXEMPT", f"The exposure date {exposure_date} is less than {months} months after every listing of {chemical}. No warning was required yet."
    elif any_grace:
        status, msg = "PARTIAL", f"On {exposure_date} the grace period had run for some listings of {chemical} but not all. The notice can rest only on the endpoints already past {months} months."
    else:
        status, msg = "NOT_EXEMPT", f"On {exposure_date} every listing of {chemical} was more than {months} months old. The grace period does not help."
    return _result("grace_period", status, msg, ["grace_12_month"], {"endpoints": per})


# ---------------------------------------------------------------- safe harbor dose math
_CONC_TO_UG_PER_G = {"ppm": 1.0, "mg/kg": 1.0, "ug/g": 1.0, "ppb": 0.001, "ug/kg": 0.001, "ng/g": 0.001,
                     "mg/g": 1000.0, "percent": 10000.0}
_CONC_TO_UG_PER_ML = {"ug/l": 0.001, "ppb_liquid": 0.001, "mg/l": 1.0, "ug/ml": 1.0}


def daily_exposure_ug(concentration: float, unit: str, amount_per_day: float) -> float:
    """Concentration times the amount of product taken in per day.

    amount_per_day is grams for solid units (ppm, ppb, mg/kg ...) and millilitres for liquid units.
    """
    u = unit.lower().replace("µ", "u").replace("μ", "u")
    if u in _CONC_TO_UG_PER_G:
        return concentration * _CONC_TO_UG_PER_G[u] * amount_per_day
    if u in _CONC_TO_UG_PER_ML:
        return concentration * _CONC_TO_UG_PER_ML[u] * amount_per_day
    raise ValueError(f"Unknown concentration unit {unit!r}. Known: {sorted(_CONC_TO_UG_PER_G) + sorted(_CONC_TO_UG_PER_ML)}")


def _route_matches(level_route: str, route: str) -> bool:
    lr = level_route.lower()
    if lr == "any":
        return True
    return route.lower() in lr or (route.lower() == "oral" and "ingestion" in lr)


def safe_harbor(chemical: str, concentration: float, unit: str, serving_size: float,
                servings_per_day: float, route: str = "oral") -> dict:
    """Compare lab concentration x average daily intake with the listed NSRL / MADL for the route."""
    rows = find_chemical(chemical)
    amount = serving_size * servings_per_day
    dose = daily_exposure_ug(concentration, unit, amount)
    detail = {"chemical": chemical, "concentration": concentration, "unit": unit, "serving_size": serving_size,
              "servings_per_day": servings_per_day, "amount_per_day": amount, "route": route,
              "daily_exposure_ug": round(dose, 6), "formula": "concentration x serving size x servings per day",
              "comparisons": []}
    if not rows:
        return _result("safe_harbor", "NOT_IN_TABLE",
                       f"Computed exposure is {dose:.4g} µg/day. {chemical} is not in this demo's table, so there is nothing to compare it with.",
                       ["safe_harbor_exemption"], detail)
    endpoints = {}
    for r in rows:
        ep = "cancer" if r["endpoint"].startswith("cancer") else "reproductive"
        endpoints.setdefault(ep, [])
        if r["level_ug_day"] is not None and _route_matches(r["route"], route):
            endpoints[ep].append(r)
    worst = "BELOW"
    for ep, lv in sorted(endpoints.items()):
        if not lv:
            detail["comparisons"].append({"endpoint": ep, "level_type": "NSRL" if ep == "cancer" else "MADL",
                                          "level_ug_day": None, "result": "NO_LISTED_LEVEL",
                                          "note": f"No level is listed for the {route} route. A custom assessment would be needed."})
            if worst == "BELOW":
                worst = "NO_LISTED_LEVEL"
            continue
        r = min(lv, key=lambda x: x["level_ug_day"])
        below = dose <= r["level_ug_day"]
        detail["comparisons"].append({"endpoint": ep, "level_type": r["level_type"], "level_ug_day": r["level_ug_day"],
                                      "level_route": r["route"], "ratio": round(dose / r["level_ug_day"], 4),
                                      "result": "AT_OR_BELOW" if below else "ABOVE", "source": r["source"]})
        if not below:
            worst = "ABOVE"
    msgs = {"BELOW": f"Computed exposure of {dose:.4g} µg/day is at or below every listed level for {chemical} by the {route} route. On these inputs the safe harbor exemption is available, and the defendant carries the burden of proving it.",
            "ABOVE": f"Computed exposure of {dose:.4g} µg/day is above at least one listed level for {chemical}. On these inputs the listed safe harbor does not apply.",
            "NO_LISTED_LEVEL": f"Computed exposure is {dose:.4g} µg/day, but at least one endpoint of {chemical} has no listed level for the {route} route."}
    return _result("safe_harbor", worst, msgs[worst], ["safe_harbor_exemption"], detail)


# ---------------------------------------------------------------- small business / government
def business_exemption(employee_count: int | None, entity_type: str = "private") -> dict:
    p = rule("small_business_exemption")["params"]
    if entity_type in {"city", "county", "district", "state", "federal", "public_water_system"}:
        return _result("business_exemption", "EXEMPT", f"A {entity_type.replace('_', ' ')} entity is not a person in the course of doing business.", ["small_business_exemption"])
    if employee_count is None:
        return _result("business_exemption", "NEEDS_INPUT", "Employee count not provided.", ["small_business_exemption"])
    if employee_count < p["min_employees"]:
        return _result("business_exemption", "EXEMPT", f"{employee_count} employees is fewer than {p['min_employees']}. The statute does not reach this business.", ["small_business_exemption"], {"employee_count": employee_count})
    return _result("business_exemption", "NOT_EXEMPT", f"{employee_count} employees is {p['min_employees']} or more.", ["small_business_exemption"], {"employee_count": employee_count})


# ---------------------------------------------------------------- 60-day clock
def sixty_day_clock(service_date: date, service_method: str = "mail_in_ca") -> dict:
    p = rule("private_action_60_day")["params"]
    if service_method not in p["mail_extension_days"]:
        raise ValueError(f"service_method must be one of {list(p['mail_extension_days'])}")
    ext = p["mail_extension_days"][service_method]
    sixtieth = service_date + timedelta(days=ext + p["wait_days"])
    rolled = sixtieth
    while rolled.weekday() >= 5:          # Saturday and Sunday are holidays under CCP 12a
        rolled += timedelta(days=1)
    earliest = rolled + timedelta(days=1)
    return _result("sixty_day_clock", "COMPUTED",
                   f"Served {service_date} ({service_method.replace('_', ' ')}, +{ext} days). The sixtieth day is {rolled}; a private suit may be filed on or after {earliest}.",
                   ["private_action_60_day"],
                   {"service_date": service_date.isoformat(), "extension_days": ext, "sixtieth_day_raw": sixtieth.isoformat(),
                    "sixtieth_day": rolled.isoformat(), "earliest_filing": earliest.isoformat(),
                    "rolled_for_weekend": rolled != sixtieth},
                   review="Court holidays other than weekends are not checked.")


# ---------------------------------------------------------------- AB 227 special compliance procedure
def special_compliance(exposure_type: str, service_date: date, today: date, facilities: int = 1,
                       used_before_for_same_exposure: bool = False) -> dict:
    p = rule("special_compliance_cure")["params"]
    rid = ["special_compliance_cure"]
    if exposure_type not in p["eligible_exposures"]:
        return _result("special_compliance", "NOT_ELIGIBLE",
                       "The 14-day special compliance procedure covers only four premises exposures (on-site alcohol, food cooked on site, tobacco smoke, parking-facility exhaust). This exposure is not one of them.",
                       rid, {"exposure_type": exposure_type, "eligible": p["eligible_exposures"]})
    if used_before_for_same_exposure and p["once_per_exposure_per_facility"]:
        return _result("special_compliance", "NOT_ELIGIBLE",
                       "The procedure can be used only once for the same exposure at the same facility, and it has been used.", rid)
    cure_by = service_date + timedelta(days=p["correct_and_agree_days"])
    pay_by = service_date + timedelta(days=p["pay_days"])
    amount = None
    for band in p["penalty_per_facility"]:
        if date.fromisoformat(band["from"]) <= service_date <= date.fromisoformat(band["to"]):
            amount = band["usd"]
    detail = {"exposure_type": exposure_type, "correct_agree_notify_by": cure_by.isoformat(), "pay_by": pay_by.isoformat(),
              "penalty_per_facility_usd": amount, "facilities": facilities,
              "total_penalty_usd": amount * facilities if amount else None, "days_left_to_cure": (cure_by - today).days}
    if amount is None:
        return _result("special_compliance", "NEEDS_REVIEW",
                       f"The exposure type qualifies, but no verified penalty amount is on file for a notice served {service_date}. Check Cal. Rules of Court, Appendix H.", rid, detail)
    if today > cure_by:
        return _result("special_compliance", "WINDOW_CLOSED",
                       f"The exposure type qualifies, but the 14-day window closed on {cure_by}.", rid, detail)
    return _result("special_compliance", "ELIGIBLE",
                   f"Eligible. By {cure_by}: correct the violation, agree to pay ${amount:,} per facility (${amount * facilities:,} for {facilities}), and send the completed proof of compliance form. Deliver payment by {pay_by}.",
                   rid, detail)


# ---------------------------------------------------------------- whole-case wrapper
def triage_case(case: dict, today: date | None = None) -> dict:
    """Run every applicable check on a case file. Values under case['claims'] must be anchored.

    A claim is {"value": ..., "anchor": {...}, "anchor_status": "VERIFIED"}; anchor_status is set by
    prop65.verifier.verify_claims. Any claim not VERIFIED blocks the checks that depend on it.
    """
    today = today or date.today()
    claims = case.get("claims", {})
    blocked = sorted(k for k, c in claims.items() if c.get("anchor_status") != "VERIFIED")

    def val(k):
        return claims[k]["value"]

    out = {"case_id": case.get("case_id"), "as_of": today.isoformat(), "blocked_claims": blocked, "checks": []}

    def need(*keys):
        return all(k in claims for k in keys) and not any(k in blocked for k in keys)

    def skip(check, keys):
        missing = [k for k in keys if k not in claims]
        bad = [k for k in keys if k in blocked]
        out["checks"].append({"check": check, "status": "BLOCKED",
                              "summary": "Not run. " + (f"Missing: {', '.join(missing)}. " if missing else "") +
                                         (f"Not anchored to the record: {', '.join(bad)}." if bad else ""),
                              "detail": {}, "rules": [], "attorney_review": []})

    if need("service_date"):
        out["checks"].append(sixty_day_clock(date.fromisoformat(val("service_date")), case.get("service_method", "mail_in_ca")))
    else:
        skip("sixty_day_clock", ["service_date"])
    out["checks"].append(business_exemption(case.get("employee_count"), case.get("entity_type", "private")))
    for chem in case.get("chemicals", []):
        name = chem["name"]
        if need("exposure_date"):
            out["checks"].append(grace_period(name, date.fromisoformat(val("exposure_date"))))
        else:
            skip("grace_period", ["exposure_date"])
        ck, sk, dk = chem.get("concentration_claim"), chem.get("serving_claim"), chem.get("servings_per_day_claim")
        if ck and sk and dk:
            if need(ck, sk, dk):
                out["checks"].append(safe_harbor(name, val(ck), chem["unit"], val(sk), val(dk), chem.get("route", "oral")))
            else:
                skip("safe_harbor", [ck, sk, dk])
    if case.get("exposure_type") and need("service_date"):
        out["checks"].append(special_compliance(case["exposure_type"], date.fromisoformat(val("service_date")), today,
                                                case.get("facilities", 1), case.get("special_compliance_used_before", False)))
    if case.get("label"):
        from .labelcheck import check_label
        lab = dict(case["label"])
        if isinstance(lab.get("text"), str) and lab["text"] in claims:
            if not need(lab["text"]):
                skip("label", [lab["text"]]); lab = None
            else:
                lab["text"] = val(lab["text"])
        if lab:
            out["checks"].append(check_label(**lab))
    return out
