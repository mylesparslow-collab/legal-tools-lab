"""Ties the pieces together for one proposed matter, and turns results into JSON-safe data."""

import json
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from . import pricing, stats
from . import backtest as bt
from .backtest import drift_check
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


def backtest_for_type(ws, matter_type):
    """The walk-forward result for one matter type, shaped for the memo. Out of sample by construction."""
    _records, summary = ws.backtest()
    row = [r for r in summary["by_type"] if r["matter_type"] == matter_type]
    scope = ("Out of sample. Walk-forward back-test of every closed %s matter, each modeled only from matters "
             "that closed before it opened. Matched on matter type only (not this proposal's selection rules), "
             "minimum %d comps." % (matter_type, summary["min_comps"]))
    if not row or row[0]["n_tested"] == 0:
        return {"status": "not_tested", "n_tested": 0, "scope": scope, "usable": False,
                "headline": "This matter type has not been back-tested: no matter of this type ever had %d earlier "
                            "closed matters to model from. Nothing is known about how its bands hold up."
                            % summary["min_comps"], "statements": []}
    row = row[0]
    n = row["n_tested"]
    usable = n >= bt.MIN_TESTED_TO_JUDGE
    out = {"status": row["upper_band_status"], "n_tested": n, "scope": scope, "usable": usable,
           "headline": row["verdict_headline"], "verdict": row["verdict"],
           "statements": [row["overruns"]["p75"]["text"], row["overruns"]["p90"]["text"]],
           "under_band": row["under_band"], "overruns": row["overruns"], "inside_p25_p75": row["coverage"]["inside_p25_p75"],
           "drift_flag": row["drift_flag"]}
    if not usable:
        out["headline"] = ("Only %d matters of this type could be back-tested; at least %d are needed to judge the "
                           "bands. The counts below are shown but support no conclusion."
                           % (n, bt.MIN_TESTED_TO_JUDGE))
    return out


def out_of_sample_for_fee(fee, quantiles, backtest_result):
    """What the walk-forward test found at the comp band nearest a proposed fee."""
    if fee is None:
        return {"available": False, "text": "No single fee to compare with a band."}
    if not backtest_result.get("usable"):
        why = ("not back-tested" if backtest_result["n_tested"] == 0
               else "only %d back-tested matters" % backtest_result["n_tested"])
        return {"available": False, "text": "No out-of-sample result: %s." % why}
    band = min(BAND_NOMINAL, key=lambda b: (abs(quantiles[b] - fee), b))
    c = backtest_result["under_band"][band]
    return {"available": True, "nearest_band": band, "band_value": quantiles[band], "at_or_under": dict(c),
            "nominal_pct": BAND_NOMINAL[band],
            "text": "Fee is nearest the comp %s (%s). Walk-forward: %d of %d back-tested matters came in at or under "
                    "their predicted %s; the band implies %d%%."
                    % (band.upper(), display_money(quantiles[band]), c["count"], c["n"], band.upper(),
                       BAND_NOMINAL[band])}


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
    costs = [ws.book.cost(m.matter_id) for m in sel.included]
    result["selection"]["comps"] = [_comp_row(mc, ws, sel.flags.get(mc.matter_id, []), reductions) for mc in costs]
    try:
        require_min(sel)
    except InsufficientComps as exc:
        result["status"] = "refused"
        result["refusal"] = str(exc)
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
    result["scenarios"] = [pricing.evaluate_scenario(econ, spec) for spec in proposal.get("scenarios", [])]
    quantiles = result["distribution"]["normalized"]["quantiles"]
    for s in result["scenarios"]:
        s["in_sample_note"] = "In sample: counted on the same comps the bands were built from."
        s["out_of_sample"] = out_of_sample_for_fee(s["params"].get("fee") or s["params"].get("cap"), quantiles,
                                                   result["backtest"])
    target = proposal.get("target_probability")
    result["target"] = pricing.fee_for_target(econ, D(str(target))) if target is not None else None

    drift = drift_check([(mc.matter.close_date, mc.value_total(ws.rate_card)) for mc in costs])
    result["drift"] = drift
    assumptions = pricing.scope_assumptions(sel, costs, ws.rate_card, attrs.get("unit_label", "units"))
    warnings = stats.sample_warnings(values)
    if result["backtest"]["status"] == "understated":
        warnings.append("Back-test for this matter type: %s" % result["backtest"]["verdict"])
    elif not result["backtest"]["usable"]:
        warnings.append("Back-test for this matter type: %s" % result["backtest"]["headline"])
    if drift["shifted"]:
        text = ("Comps that closed in the later half (n=%d) cost %sx those in the earlier half (n=%d) at the same "
                "rates (medians %s and %s). Older comps may no longer be representative; consider the "
                "closed_within_years rule."
                % (drift["n_late"], drift["late_over_early"], drift["n_early"], display_money(drift["median_late"]),
                   display_money(drift["median_early"])))
        warnings.append(text)
        assumptions.append({"kind": "drift", "text": text, "evidence": drift})
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
