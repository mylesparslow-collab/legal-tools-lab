"""Ties the pieces together for one proposed matter, and turns results into JSON-safe data."""

import json
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from . import bands, drift, pricing, stats
from . import backtest as bt
from .comps import InsufficientComps, SelectionRules, require_min, select_comps
from .cost import CostBook, TaskCodeMap, parse_reductions
from .loader import load_cost_rates, load_dataset, load_json, load_rate_card
from .money import ZERO, CENT, D, display_money
from .schema import PHASES

DISCLAIMER = ("Personal portfolio demo on synthetic data. Not financial, pricing or legal advice. "
              "The tool shows evidence and risk from past matters; a person decides the price.")
DEFAULT_SEED = 20260
P50 = Decimal("0.50")


class Workspace:
    """Everything loaded once: dataset, cost book, rate card, cost rates."""

    def __init__(self, export_dir, mapping_path, rate_card_path, cost_rates_path, task_codes_path):
        self.paths = {"export": export_dir, "mapping": mapping_path, "rate_card": rate_card_path,
                      "cost_rates": cost_rates_path, "task_codes": task_codes_path}
        self.dataset = load_dataset(export_dir, mapping_path)
        self.code_map = TaskCodeMap.from_dict(load_json(task_codes_path))
        self.book = CostBook(self.dataset, self.code_map)
        self.rate_card = load_rate_card(rate_card_path)
        self.cost_rates = load_cost_rates(cost_rates_path)
        self.cost_rates_note = load_json(cost_rates_path).get("note", "")
        self.rate_card_label = load_json(rate_card_path).get("current_label", "current")
        self._backtest = {}

    def backtest(self, min_comps=bt.DEFAULT_MIN_COMPS):
        """(records, summary) of the walk-forward back-test, run once per workspace."""
        if min_comps not in self._backtest:
            records = bt.walk_forward(self.dataset, self.book, self.rate_card, min_comps)
            self._backtest[min_comps] = (records, bt.summarize_backtest(records, self.dataset, self.book,
                                                                        self.rate_card, min_comps))
        return self._backtest[min_comps]


def default_paths(root):
    data = os.path.join(root, "data")
    return {
        "export_dir": os.path.join(data, "export_a"),
        "mapping_path": os.path.join(data, "mappings", "export_a.json"),
        "rate_card_path": os.path.join(data, "rate_card.json"),
        "cost_rates_path": os.path.join(data, "cost_rates.placeholder.json"),
        "task_codes_path": os.path.join(data, "task_code_phases.json"),
    }


def parse_date(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def _comp_row(mc, ws, flags, reductions):
    m = mc.matter
    return {
        "matter_id": m.matter_id, "open_date": m.open_date, "close_date": m.close_date,
        "forum": m.forum, "num_parties": m.num_parties, "amount_band": m.amount_band,
        "num_units": m.num_units, "hearing_occurred": m.hearing_occurred,
        "hours": mc.total_hours, "raw_worked": mc.raw_worked, "raw_billed": mc.raw_billed,
        "invoiced": mc.invoiced, "collected": mc.collected,
        "write_down": mc.write_down, "uncollected": mc.uncollected,
        "normalized_value": mc.value_total(ws.rate_card),
        "normalized_value_after_assumptions": mc.value_total(ws.rate_card, reductions),
        "internal_cost": mc.value_total(ws.cost_rates, reductions),
        "phase_confidence": mc.phase_confidence, "flags": list(flags),
    }


BAND_NOMINAL = {"p25": 25, "p50": 50, "p75": 75, "p90": 90}
BAND_ORDER = ("p25", "p50", "p75", "p90")


def backtest_for_type(ws, matter_type):
    """The walk-forward result for one matter type, shaped for the memo. Out of sample by construction.

    The headline, statements and under_band counts are for the planning bands. The descriptive comp
    quantiles' own result is under 'descriptive' for comparison.
    """
    _records, summary = ws.backtest()
    row = [r for r in summary["by_type"] if r["matter_type"] == matter_type]
    scope = ("Out of sample. Walk-forward back-test of every closed %s matter, each modeled only from matters "
             "that closed before it opened, with the change check and the band adjustment also run as of that "
             "day. Matched on matter type only (not this proposal's selection rules), minimum %d comps."
             % (matter_type, summary["min_comps"]))
    if not row or row[0]["n_tested"] == 0:
        return {"status": "not_tested", "n_tested": 0, "scope": scope, "usable": False,
                "headline": "This matter type has not been back-tested: no matter of this type ever had %d earlier "
                            "closed matters to model from. Nothing is known about how its bands hold up."
                            % summary["min_comps"], "statements": [], "descriptive_statements": []}
    row = row[0]
    n = row["n_tested"]
    usable = n >= bt.MIN_TESTED_TO_JUDGE
    desc = row["descriptive"]
    out = {"status": row["upper_band_status"], "n_tested": n, "scope": scope, "usable": usable,
           "headline": row["verdict_headline"], "verdict": row["verdict"],
           "statements": [row["overruns"]["p75"]["text"], row["overruns"]["p90"]["text"]],
           "under_band": row["under_band"], "overruns": row["overruns"], "inside_p25_p75": row["coverage"]["inside_p25_p75"],
           "descriptive_statements": [desc["overruns"]["p75"]["text"], desc["overruns"]["p90"]["text"]]
           if desc["n_tested"] else [],
           "descriptive_status": desc["upper_band_status"],
           "calibration": row["calibration"], "drift_flag": row["drift_flag"]}
    if not usable:
        out["headline"] = ("Only %d matters of this type could be back-tested; at least %d are needed to judge the "
                           "bands. The counts below are shown but support no conclusion."
                           % (n, bt.MIN_TESTED_TO_JUDGE))
    return out


def out_of_sample_for_fee(fee, plan, backtest_result):
    """Where a proposed fee sits among the planning bands, and what the walk-forward test found there."""
    if fee is None:
        return {"available": False, "position": None, "text": "No single fee to compare with a band."}
    below = [b for b in BAND_ORDER if plan[b] <= fee]
    above = [b for b in BAND_ORDER if plan[b] > fee]
    if not below:
        where = "Fee is below the planning P25 (%s)." % display_money(plan["p25"])
    elif not above:
        where = "Fee is at or above the planning P90 (%s)." % display_money(plan["p90"])
    else:
        lo, hi = below[-1], above[0]
        where = ("Fee is between the planning %s (%s) and %s (%s)."
                 % (lo.upper(), display_money(plan[lo]), hi.upper(), display_money(plan[hi])))
    out = {"available": False, "position": {"at_or_above": below[-1] if below else None,
                                            "below": above[0] if above else None}, "where": where}
    if not backtest_result.get("usable"):
        why = ("not back-tested" if backtest_result["n_tested"] == 0
               else "only %d back-tested matters" % backtest_result["n_tested"])
        out["text"] = "%s No out-of-sample result: %s." % (where, why)
        return out
    near = ([below[-1]] if below else []) + ([above[0]] if above else [])
    parts = []
    for b in near:
        c = backtest_result["under_band"][b]
        parts.append("%d of %d at or under their planning %s (the band implies %d%%)"
                     % (c["count"], c["n"], b.upper(), BAND_NOMINAL[b]))
    out.update({"available": True, "bands": {b: dict(backtest_result["under_band"][b]) for b in near},
                "text": "%s Walk-forward, back-tested matters of this type: %s." % (where, "; ".join(parts))})
    return out


def type_drift(ws, matter_type, as_of):
    """Change check on every clean closed matter of the type that had closed before as_of."""
    ms = [m for m in bt.clean_closed(ws.dataset, matter_type) if m.close_date < as_of]
    return drift.change_point_scan([(m.open_date, m.matter_id, ws.book.cost(m.matter_id).value_total(ws.rate_card))
                                    for m in ms])


def calibration_scores(ws, matter_type, as_of, change_date, quantiles):
    """{name: [actual / finite-sample band]} from back-tested matters of the type whose cost was known by as_of.

    Each ratio uses the band as it would have been set the day that matter opened. With a change
    date (the recent-only version), only matters opened from that date count, each against its own
    recent-only band where it had one.
    """
    records, _summary = ws.backtest()
    mine = [r for r in records if r["matter_type"] == matter_type and r["plan_tested"]
            and r["close_date"] < as_of and (change_date is None or r["open_date"] >= change_date)]
    out = {}
    for name, q in quantiles:
        vals = []
        for r in mine:
            comps = r.get("recent_values", r["plan_values"]) if change_date is not None else r["plan_values"]
            base, _ok = bands.finite_sample_quantile(comps, q)
            if base > 0:
                vals.append(r["actual"] / base)
        out[name] = vals
    return out


def planning_for(values, scores):
    """Planning bands for a set of comp values, with a plain note on how they were made."""
    pb = bands.planning_bands(values, scores)
    n, m = len(values), min(pb["m"].values())
    notes = []
    if pb["calibrated"]:
        raised = [b.upper() for b in BAND_ORDER if pb["factor"][b] > 1]
        notes.append("Adjusted from %d earlier matters of this type whose outcome against their own bands is known. "
                     "%s." % (m, ("Raised: " + ", ".join("%s x%s" % (b, pb["factor"][b.lower()].quantize(Decimal("0.01")))
                                                      for b in raised)) if raised
                              else "No band needed raising"))
    else:
        notes.append("Not adjusted: %d earlier matters of this type have a known outcome against their own bands; "
                     "%d are needed. These are finite-sample figures from the comps alone and are less tested."
                     % (m, bands.MIN_CAL_HISTORY))
    unreachable = [b.upper() for b in BAND_ORDER if not pb["reachable"][b]]
    if unreachable:
        notes.append("With %d comps the planning %s is the largest comp; a sample this small cannot place that band, "
                     "so treat it as a floor." % (n, " and ".join(unreachable)))
    return {"bands": pb["plan"], "base": pb["base"], "factor": pb["factor"], "calibrated": pb["calibrated"],
            "n_scores": m, "min_history": bands.MIN_CAL_HISTORY, "reachable": pb["reachable"], "n": n,
            "notes": notes, "unreachable": unreachable}


def _version(label, used, values, scores):
    q = {b: stats.quantile(values, p) for b, p in bands.BANDS}
    return {"label": label, "used": used, "n": len(values), "descriptive": q,
            "planning": planning_for(values, scores)["bands"]}


def scenario_at_planning(spec, s, plan, cost_share):
    """Revenue and margin if the matter came in at each planning band. Cost = band x the comps' cost share."""
    kind = spec.get("type")
    out = {}
    for b in ("p50", "p75", "p90"):
        v = plan[b]
        if kind == "fixed":
            rev = s["params"]["fee"]
        elif kind == "capped":
            rev = min(v, s["params"]["cap"])
        elif kind == "collar":
            fee, lo, hi = s["params"]["fee"], s["params"]["band_low"], s["params"]["band_high"]
            share = s["params"]["share_pct"] / 100
            rev = fee + share * (v - hi) if v > hi else fee - share * (lo - v) if v < lo else fee
        else:
            return None
        out[b] = {"value": v, "revenue": rev, "cost": v * cost_share, "margin": rev - v * cost_share}
    return out


def price_proposal(ws, proposal):
    """Model one proposed matter. Returns a result dict; refuses (status 'refused') below the comp minimum."""
    matter_type = proposal["matter_type"]
    attrs = dict(proposal.get("attributes", {}))
    as_of = parse_date(proposal["as_of"]) if proposal.get("as_of") else date.today()
    rules = SelectionRules.from_dict(proposal.get("selection_rules"))
    reductions = parse_reductions(proposal.get("ai_assumptions"))
    seed = int(proposal.get("seed", DEFAULT_SEED))
    sel = select_comps(ws.dataset, matter_type, attrs, rules, as_of)

    result = {
        "tool": "fee-modeler", "disclaimer": DISCLAIMER,
        "proposal": {"proposal_id": proposal.get("proposal_id"), "title": proposal.get("title"),
                     "matter_type": matter_type, "as_of": as_of, "attributes": attrs},
        "inputs": {"rate_card_label": ws.rate_card_label, "rate_card": dict(ws.rate_card),
                   "cost_rates": dict(ws.cost_rates), "cost_rates_note": ws.cost_rates_note,
                   "mapping": ws.dataset.mapping_name, "seed": seed},
        "selection": {
            "rules": sel.rule_lines(), "n": sel.n, "min_comps": rules.min_comps,
            "type_total": sel.type_total, "exclusion_counts": sel.exclusion_counts(),
            "relax_hints": dict(sel.relax_hints),
            "excluded": [{"matter_id": m.matter_id, "reasons": reasons} for m, reasons in sel.excluded],
        },
    }
    result["backtest"] = backtest_for_type(ws, matter_type)

    # Change check for the matter type as of the proposal date. No date is supplied; it is estimated.
    scan = type_drift(ws, matter_type, as_of)
    action = proposal.get("drift_action", "higher")
    if action not in ("higher", "ignore", "recent_only"):
        raise ValueError("drift_action must be 'higher' (default), 'recent_only' or 'ignore'")
    all_included = list(sel.included)
    change_date = None
    direction = None
    result["drift"] = dict(scan, action="none", n_all=len(all_included), n_used=len(all_included), versions=[])
    if scan["flagged"]:
        direction = "risen" if scan["after_over_before"] > 1 else "fallen"
        after = [m for m in all_included if m.open_date >= scan["change_date"]]
        result["drift"].update(direction=direction, n_after_selected=len(after),
                               n_before_selected=len(all_included) - len(after))
        if action == "recent_only":
            change_date = scan["change_date"]
            reason = "opened before the estimated change in costs (%s)" % change_date
            for m in all_included:
                if m.open_date < change_date:
                    sel.excluded.append((m, [reason]))
            sel.included = after
            result["drift"].update(action="recent_only", n_used=len(after))
            result["selection"].update(
                n=sel.n, exclusion_counts=sel.exclusion_counts(),
                excluded=[{"matter_id": m.matter_id, "reasons": reasons} for m, reasons in sel.excluded])
            result["selection"]["rules"] = sel.rule_lines() + [
                "Set in the proposal (drift_action recent_only): opened on or after %s, the estimated date this "
                "type's costs changed" % change_date]
        else:
            result["drift"]["action"] = "ignored_by_proposal" if action == "ignore" else "higher_of_two"
    costs = [ws.book.cost(m.matter_id) for m in sel.included]
    result["selection"]["comps"] = [_comp_row(mc, ws, sel.flags.get(mc.matter_id, []), reductions) for mc in costs]
    try:
        require_min(sel)
    except InsufficientComps as exc:
        result["status"] = "refused"
        result["refusal"] = str(exc)
        if result["drift"]["action"] == "recent_only":
            result["refusal"] = (
                "Not modeled: the proposal asks for recent comps only (drift_action recent_only). Costs for %s "
                "appear to have changed around %s (matters opened since cost %sx the earlier ones). "
                "Only %d of the %d selected comps opened since then; %d are required. Remove drift_action to "
                "get the default, which uses the whole history and never lowers a figure on a flag."
                % (matter_type, change_date, scan["after_over_before"], len(sel.included), len(all_included),
                   rules.min_comps))
        return result
    result["status"] = "modeled"

    econ = pricing.comp_economics(costs, ws.rate_card, ws.cost_rates, reductions)
    values = [c.value for c in econ]
    raw = [mc.raw_worked for mc in costs]
    by_phase = {}
    for i, p in enumerate(PHASES):
        vals = [c.phase_value[p] for c in econ if p in c.occurred]
        hrs = [mc.hours_by_phase(reductions)[p] for mc in costs if p in mc.phases_occurred()]
        by_phase[p] = {"n_occurred": len(vals), "n": len(econ),
                       "value": stats.summarize(vals, seed=seed + 1 + i),
                       "median_hours": stats.quantile(hrs, P50) if hrs else None}
    levels = sorted({lv for mc in costs for lv in mc.hours_by_level()}, key=lambda lv: -ws.rate_card.get(lv, ZERO))
    total_hours = sum((mc.total_hours for mc in costs), ZERO)
    by_level = []
    for lv in levels:
        hrs = [mc.hours_by_level(reductions).get(lv, ZERO) for mc in costs]
        raw_hrs = sum((mc.hours_by_level().get(lv, ZERO) for mc in costs), ZERO)
        by_level.append({"level": lv, "median_hours": stats.quantile(hrs, P50),
                         "share_of_hours_pct": (raw_hrs * 100 / total_hours).quantize(Decimal("1")) if total_hours else None,
                         "standard_rate": ws.rate_card.get(lv), "cost_rate": ws.cost_rates.get(lv), "n": len(costs)})
    result["distribution"] = {
        "n": len(econ),
        "basis": "Normalized value: hours worked x the %s rate card, after any hours-reduction assumptions."
                 % ws.rate_card_label,
        "normalized": stats.summarize(values, seed=seed),
        "raw_worked": stats.summarize(raw, with_intervals=False),
        "internal_cost": stats.summarize([c.cost for c in econ], with_intervals=False),
        "hours": stats.summarize([sum(mc.hours_by_phase(reductions).values(), ZERO) for mc in costs],
                                 with_intervals=False),
        "by_phase": by_phase,
        "by_level": by_level,
    }
    sums = {k: sum((getattr(mc, k) for mc in costs), ZERO)
            for k in ("raw_worked", "raw_billed", "invoiced", "collected", "written_off")}
    sums["normalized_value_before_assumptions"] = sum((mc.value_total(ws.rate_card) for mc in costs), ZERO)
    result["worked_billed_collected"] = {
        "n": len(costs), "totals": sums,
        "medians": {k: stats.quantile([getattr(mc, k) for mc in costs], P50)
                    for k in ("raw_worked", "raw_billed", "collected")},
        "write_off_known": all(mc.write_off_known for mc in costs),
        "billed_hours_assumed": any(mc.billed_assumed for mc in costs),
    }
    result["ai"] = pricing.ai_before_after(costs, ws.rate_card, reductions)
    # Planning bands: the figures to price from. The descriptive quantiles above stay, labelled as such.
    target = proposal.get("target_probability")
    qs = list(bands.BANDS) + ([("target", D(str(target)))] if target is not None else [])
    scores = calibration_scores(ws, matter_type, as_of, change_date, qs)
    planning = planning_for(values, scores)
    planning["label"] = "Planning figures"
    planning["descriptive_label"] = "Of the comps (descriptive)"
    planning["band_source"] = {b: "comps" for b in BAND_ORDER}
    total_value, total_cost = sum(values, ZERO), sum((c.cost for c in econ), ZERO)
    cost_share = total_cost / total_value if total_value > 0 else None
    planning["cost_share_of_value"] = cost_share.quantize(Decimal("0.001")) if cost_share is not None else None
    result["planning"] = planning
    recent_scores = None
    if scan["flagged"]:
        hist_values = [ws.book.cost(m.matter_id).value_total(ws.rate_card, reductions) for m in all_included]
        hist_scores = calibration_scores(ws, matter_type, as_of, None, qs)
        after_values = [ws.book.cost(m.matter_id).value_total(ws.rate_card, reductions) for m in all_included
                        if m.open_date >= scan["change_date"]]
        recent_scores = calibration_scores(ws, matter_type, as_of, scan["change_date"], qs)
        act = result["drift"]["action"]
        versions = [_version("All selected comps, whole history", act == "ignored_by_proposal", hist_values, hist_scores)]
        have_recent = len(after_values) >= rules.min_comps
        result["drift"]["recent_version_available"] = have_recent
        if have_recent:
            versions.insert(0, _version("Comps opened from %s only" % scan["change_date"], act == "recent_only",
                                        after_values, recent_scores))
        result["drift"]["versions"] = versions
        if act == "higher_of_two" and have_recent:
            rec = planning_for(after_values, recent_scores)
            raised = [b for b in BAND_ORDER if rec["bands"][b] > planning["bands"][b]]
            planning["bands_whole_history"] = dict(planning["bands"])
            planning["bands_recent_only"] = dict(rec["bands"])
            planning["bands"] = bands.higher_of(planning["bands"], rec["bands"])
            for b in raised:
                planning["base"][b], planning["factor"][b] = rec["base"][b], rec["factor"][b]
                planning["band_source"][b] = "recent"
            result["drift"]["raised"] = raised
            planning["notes"].append(
                "Change check: every band taken from the recent-only version because it is higher." if len(raised) == 4
                else ("Change check: %s taken from the recent-only version because it is higher; the rest from the "
                      "whole history." % ", ".join(b.upper() for b in raised)) if raised else
                "Change check: the whole-history version is the higher at every band, so the flag changed no figure.")
    plan = planning["bands"]

    result["scenarios"] = [pricing.evaluate_scenario(econ, spec) for spec in proposal.get("scenarios", [])]
    for spec, s in zip(proposal.get("scenarios", []), result["scenarios"]):
        s["in_sample_note"] = "In sample: counted on the same comps the bands were built from."
        s["out_of_sample"] = out_of_sample_for_fee(s["params"].get("fee") or s["params"].get("cap"), plan,
                                                   result["backtest"])
        s["at_planning"] = scenario_at_planning(spec, s, plan, cost_share) if cost_share is not None else None
    if target is not None:
        t = pricing.fee_for_target(econ, D(str(target)))
        p = D(str(target))
        base, reachable = bands.finite_sample_quantile(sorted(values), p)
        factor, source, m = bands.adjustment(scores["target"], p)
        from_recent = False
        if result["drift"]["action"] == "higher_of_two" and result["drift"].get("recent_version_available"):
            r_base, r_reach = bands.finite_sample_quantile(sorted(after_values), p)
            r_factor, r_source, r_m = bands.adjustment(recent_scores["target"], p)
            if r_base * r_factor > base * factor:       # the flag may raise the target fee, never lower it
                base, reachable, factor, source, m, from_recent = r_base, r_reach, r_factor, r_source, r_m, True
        # Keep it in order with the planning bands: never below a band for a lower probability.
        floor = max([plan[b] for b, q in bands.BANDS if q <= p] or [ZERO])
        fee_value = max(base * factor, floor)
        t.update({
            "planning_fee_covering_standard_value": fee_value, "planning_base": base, "planning_factor": factor,
            "planning_floored_at_band": fee_value > base * factor, "planning_from_recent_only": from_recent,
            "planning_calibrated": source == "type", "planning_n_scores": m, "planning_reachable": reachable,
            "planning_fee_no_loss_on_cost": fee_value * cost_share if cost_share is not None else None,
        })
        result["target"] = t
    else:
        result["target"] = None

    assumptions = pricing.scope_assumptions(sel, costs, ws.rate_card, attrs.get("unit_label", "units"))
    warnings = stats.sample_warnings(values)
    if result["backtest"]["status"] == "understated":
        warnings.append("Back-test for this matter type: %s" % result["backtest"]["verdict"])
    elif not result["backtest"]["usable"]:
        warnings.append("Back-test for this matter type: %s" % result["backtest"]["headline"])
    for note in planning["notes"][1:] if planning["calibrated"] else planning["notes"]:
        if not note.startswith("Change check:"):
            warnings.append("Planning figures: %s" % note)
    if scan["flagged"]:
        d = result["drift"]
        base_text = ("Costs for this matter type appear to have %s: the %d matters opened from %s cost %sx the %d "
                     "opened before, at the same rates (medians %s and %s). The date is estimated from the data, and "
                     "the check is a prompt to look, not a finding."
                     % (direction, scan["n_after"], scan["change_date"], scan["after_over_before"], scan["n_before"],
                        display_money(scan["median_after"]), display_money(scan["median_before"])))
        if d["action"] == "recent_only":
            text = ("%s The proposal sets drift_action to recent_only, so this memo uses only the %d selected comps "
                    "opened from that date; %d older ones are left out. That choice can lower the figures. Both "
                    "versions are shown below." % (base_text, d["n_after_selected"], d["n_before_selected"]))
        elif d["action"] == "ignored_by_proposal":
            text = ("%s The proposal sets drift_action to ignore, so the whole history is used as it stands. Both "
                    "versions are shown below." % base_text)
        elif not d["recent_version_available"]:
            text = ("%s Only %d of the selected comps opened from that date, too few for a recent-only version, so "
                    "the figures come from the whole history.%s"
                    % (base_text, d["n_after_selected"],
                       " If costs have risen, they are too low; check before quoting." if direction == "risen" else ""))
        elif direction == "fallen":
            text = ("%s This memo has not lowered the bands: each planning figure is the higher of the recent-only "
                    "and whole-history versions. A person may choose the recent-only version (drift_action "
                    "recent_only) after checking why. Both versions are shown below." % base_text)
        else:
            text = ("%s A flag can only raise a planning figure: each one is the higher of the recent-only and "
                    "whole-history versions. Both versions are shown below." % base_text)
        warnings.insert(0, text)
        assumptions.append({"kind": "drift", "text": text, "evidence": scan})
    if result["worked_billed_collected"]["billed_hours_assumed"]:
        warnings.append("Billed hours were missing for some entries and assumed equal to worked hours; "
                        "write-downs are understated.")
    result["assumptions"] = assumptions
    result["warnings"] = warnings
    return result


def to_jsonable(obj):
    """Decimals become strings (two places), dates ISO strings. No floats are produced."""
    if isinstance(obj, Decimal):
        if obj.as_tuple().exponent >= 0:
            return format(obj, "f")                       # whole numbers stay whole
        return format(obj.quantize(CENT, rounding=ROUND_HALF_UP), "f")
    if isinstance(obj, float):
        raise TypeError("float found in output; money and hours must stay Decimal")
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(to_jsonable(v) for v in obj)
    return obj


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(to_jsonable(obj), fh, indent=2, sort_keys=False)
        fh.write("\n")
