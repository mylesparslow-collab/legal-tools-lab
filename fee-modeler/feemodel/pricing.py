"""Pricing scenarios evaluated against the comps. Evidence for a person to price from; not a price.

Terms used throughout:
- value: a comp's hours x today's standard rates (normalized worked value)
- cost: a comp's hours x the user-supplied cost rate per level
- revenue: what the fee arrangement would have paid on that comp
- margin: revenue minus cost
"""

from dataclasses import dataclass, field as dc_field
from decimal import Decimal

from . import stats
from .money import D, ZERO, HUNDRED, display_money, ratio
from .schema import PHASES, PHASE_LABELS

P10 = Decimal("0.10")
P50 = Decimal("0.50")
P75 = Decimal("0.75")
P90 = Decimal("0.90")
MIN_GROUP = 3
RATIO_WORTH_NOTING = Decimal("1.25")


@dataclass
class CompEcon:
    matter_id: str
    value: Decimal
    cost: Decimal
    phase_value: dict = dc_field(default_factory=dict)
    phase_cost: dict = dc_field(default_factory=dict)
    occurred: frozenset = frozenset()


def comp_economics(matter_costs, rate_card, cost_rates, reductions=None):
    out = []
    for mc in matter_costs:
        pv = mc.value_by_phase(rate_card, reductions)
        pc = mc.value_by_phase(cost_rates, reductions)
        out.append(CompEcon(mc.matter_id, sum(pv.values(), ZERO), sum(pc.values(), ZERO), pv, pc,
                            frozenset(mc.phases_occurred())))
    return out


def _summarize(kind, label, params, comps, revenues, under_count, notes, extra=None):
    n = len(comps)
    if n == 0:
        raise ValueError("no comps to evaluate a scenario against")
    margins = [r - c.cost for r, c in zip(revenues, comps)]
    total_rev = sum(revenues, ZERO)
    total_cost = sum((c.cost for c in comps), ZERO)
    total_value = sum((c.value for c in comps), ZERO)
    result = {
        "type": kind,
        "label": label,
        "params": params,
        "n": n,
        "under_fee": {"count": under_count, "n": n},
        "no_loss": {"count": sum(1 for m in margins if m >= 0), "n": n},
        "expected_revenue": total_rev / n,
        "expected_cost": total_cost / n,
        "expected_margin": (total_rev - total_cost) / n,
        "margin_pct_of_revenue": (ratio((total_rev - total_cost) * HUNDRED, total_rev, "0.1") if total_rev else None),
        "revenue_vs_standard_value_pct": (ratio(total_rev * HUNDRED, total_value, "0.1") if total_value else None),
        "downside_p90_margin": stats.quantile(margins, P10),
        "notes": list(notes),
        "per_comp": [{"matter_id": c.matter_id, "value": c.value, "cost": c.cost, "revenue": r, "margin": m}
                     for c, r, m in zip(comps, revenues, margins)],
    }
    if extra:
        result.update(extra)
    return result


def evaluate_fixed(comps, fee):
    fee = D(fee)
    under = sum(1 for c in comps if c.value <= fee)
    return _summarize("fixed", "Fixed fee %s" % display_money(fee), {"fee": fee}, comps,
                      [fee for _ in comps], under,
                      ["Revenue is the fee on every comp, whatever the work turned out to be."])


def evaluate_capped(comps, cap):
    cap = D(cap)
    revenues = [min(c.value, cap) for c in comps]
    under = sum(1 for c in comps if c.value <= cap)
    return _summarize("capped", "Capped fee, cap %s" % display_money(cap), {"cap": cap}, comps, revenues, under,
                      ["Billed hourly at standard rates up to the cap; work above the cap is not paid."],
                      {"hit_cap": {"count": len(comps) - under, "n": len(comps)}})


def evaluate_collar(comps, fee, band_pct, share_pct):
    """Fixed fee with a collar: outside a +/- band around the fee, overrun and underrun are shared."""
    fee, band, share = D(fee), D(band_pct) / HUNDRED, D(share_pct) / HUNDRED
    upper, lower = fee * (1 + band), fee * (1 - band)
    revenues, above, below = [], 0, 0
    for c in comps:
        if c.value > upper:
            revenues.append(fee + share * (c.value - upper))
            above += 1
        elif c.value < lower:
            revenues.append(fee - share * (lower - c.value))
            below += 1
        else:
            revenues.append(fee)
    n = len(comps)
    under = sum(1 for c in comps if c.value <= fee)
    return _summarize(
        "collar", "Fixed fee %s with %s%% collar, %s%% shared" % (display_money(fee), D(band_pct), D(share_pct)),
        {"fee": fee, "band_pct": D(band_pct), "share_pct": D(share_pct), "band_low": lower, "band_high": upper},
        comps, revenues, under,
        ["Inside the band the fee stands. Above it the client pays the shared part of the overrun; "
         "below it the client gets back the shared part of the underrun."],
        {"above_band": {"count": above, "n": n}, "below_band": {"count": below, "n": n},
         "inside_band": {"count": n - above - below, "n": n}})


def evaluate_phased(comps, phase_fees):
    """A fixed fee per phase. A phase fee is charged only when that phase happened.

    Phases left out of phase_fees, or set to "hourly", are billed at standard rates.
    """
    fees = {}
    for phase, fee in phase_fees.items():
        if phase not in PHASES:
            raise ValueError("unknown phase %r in phased fee" % phase)
        if fee != "hourly":
            fees[phase] = D(fee)
    hourly = [p for p in PHASES if p not in fees]
    revenues = []
    for c in comps:
        r = ZERO
        for p in PHASES:
            if p in fees:
                if p in c.occurred:
                    r += fees[p]
            else:
                r += c.phase_value.get(p, ZERO)
        revenues.append(r)
    under = sum(1 for c, r in zip(comps, revenues) if c.value <= r)
    by_phase = []
    for p in PHASES:
        if p not in fees:
            continue
        vals = [c.phase_value.get(p, ZERO) for c in comps if p in c.occurred]
        costs = [c.phase_cost.get(p, ZERO) for c in comps if p in c.occurred]
        by_phase.append({
            "phase": p, "fee": fees[p], "n_occurred": len(vals), "n": len(comps),
            "under_fee": {"count": sum(1 for v in vals if v <= fees[p]), "n": len(vals)},
            "no_loss": {"count": sum(1 for v in costs if v <= fees[p]), "n": len(costs)},
            "median_value": stats.quantile(vals, P50) if vals else None,
        })
    notes = ["Each phase fee is charged only on comps where that phase happened."]
    if hourly:
        notes.append("Billed hourly at standard rates: %s." % ", ".join(PHASE_LABELS[p].lower() for p in hourly))
    full = sum(fees.values(), ZERO)
    return _summarize("phased", "Phased fixed fee, %s if every fixed phase occurs" % display_money(full),
                      {"phase_fees": fees, "hourly_phases": hourly}, comps, revenues, under, notes,
                      {"by_phase": by_phase})


def evaluate_scenario(comps, spec):
    kind = spec.get("type")
    if kind == "fixed":
        return evaluate_fixed(comps, spec["fee"])
    if kind == "capped":
        return evaluate_capped(comps, spec["cap"])
    if kind == "collar":
        return evaluate_collar(comps, spec["fee"], spec["band_pct"], spec["share_pct"])
    if kind == "phased":
        return evaluate_phased(comps, spec["phase_fees"])
    raise ValueError("unknown scenario type %r; use fixed, capped, phased or collar" % kind)


def fee_for_target(comps, probability):
    """Smallest fixed fee at which at least `probability` of the comps would not have lost money.

    Uses an observed comp cost (no interpolation), so the stated share holds exactly in the comps.
    """
    probability = D(probability)
    if not (0 < probability <= 1):
        raise ValueError("target probability must be above 0 and at most 1")
    costs = [c.cost for c in comps]
    values = [c.value for c in comps]
    fee = stats.order_stat(costs, probability)
    at_value = stats.order_stat(values, probability)
    return {
        "target_probability": probability,
        "fee_no_loss_on_cost": fee,
        "no_loss": {"count": sum(1 for v in costs if v <= fee), "n": len(costs)},
        "fee_covering_standard_value": at_value,
        "under_fee": {"count": sum(1 for v in values if v <= at_value), "n": len(values)},
        "n": len(comps),
    }


def ai_before_after(matter_costs, rate_card, reductions):
    """Before/after table for the user's hours-reduction assumptions. Zero assumptions = identical columns."""
    rows = []

    def med(vals):
        return stats.quantile(vals, P50) if vals else None

    for p in PHASES:
        hb = [mc.hours_by_phase()[p] for mc in matter_costs]
        ha = [mc.hours_by_phase(reductions)[p] for mc in matter_costs]
        vb = [mc.value_by_phase(rate_card)[p] for mc in matter_costs]
        va = [mc.value_by_phase(rate_card, reductions)[p] for mc in matter_costs]
        rows.append({"phase": p, "reduction_pct": (reductions or {}).get(p, ZERO) * HUNDRED,
                     "median_hours_before": med(hb), "median_hours_after": med(ha),
                     "median_value_before": med(vb), "median_value_after": med(va)})
    tb = [mc.value_total(rate_card) for mc in matter_costs]
    ta = [mc.value_total(rate_card, reductions) for mc in matter_costs]
    hb = [mc.total_hours for mc in matter_costs]
    ha = [sum(mc.hours_by_phase(reductions).values(), ZERO) for mc in matter_costs]
    return {
        "label": "User assumptions, not predictions. The tool does not estimate any effect of AI on hours.",
        "any_applied": bool(reductions),
        "n": len(matter_costs),
        "rows": rows,
        "total": {"median_hours_before": med(hb), "median_hours_after": med(ha),
                  "median_value_before": med(tb), "median_value_after": med(ta)},
    }


def _x(numerator, denominator):
    return ratio(numerator, denominator, "0.1")


def scope_assumptions(selection, matter_costs, rate_card, unit_label="units"):
    """Scope assumptions and exclusions, each tied to what the comps show."""
    out = []
    n = len(matter_costs)
    if n == 0:
        return out
    value = {mc.matter_id: mc.value_total(rate_card) for mc in matter_costs}
    pvalue = {mc.matter_id: mc.value_by_phase(rate_card) for mc in matter_costs}

    # Hearing vs no hearing.
    with_h = [mc for mc in matter_costs if "hearing" in mc.phases_occurred()]
    without_h = [mc for mc in matter_costs if "hearing" not in mc.phases_occurred()]
    if len(with_h) >= MIN_GROUP and len(without_h) >= MIN_GROUP:
        mw = stats.quantile([value[m.matter_id] for m in with_h], P50)
        mo = stats.quantile([value[m.matter_id] for m in without_h], P50)
        if mo > 0 and mw / mo >= RATIO_WORTH_NOTING:
            out.append({
                "kind": "hearing",
                "text": "Comps with a hearing (n=%d) had a median cost of %s, %sx the median of comps without one "
                        "(%s, n=%d). Quote the hearing as a separate phase, or state that it is excluded."
                        % (len(with_h), display_money(mw), _x(mw, mo), display_money(mo), len(without_h)),
                "evidence": {"n_with": len(with_h), "n_without": len(without_h), "median_with": mw,
                             "median_without": mo, "ratio": _x(mw, mo),
                             "matter_ids_with": [m.matter_id for m in with_h]},
            })

    # Which phase drove the expensive comps.
    if n >= 8:
        p75 = stats.quantile(list(value.values()), P75)
        high = [mc for mc in matter_costs if value[mc.matter_id] > p75]
        rest = [mc for mc in matter_costs if value[mc.matter_id] <= p75]
        if high and rest:
            gaps = {}
            for p in PHASES:
                gaps[p] = (stats.mean([pvalue[m.matter_id][p] for m in high])
                           - stats.mean([pvalue[m.matter_id][p] for m in rest]))
            total_gap = sum(gaps.values(), ZERO)
            top = max(PHASES, key=lambda p: gaps[p])
            if total_gap > 0 and gaps[top] > 0:
                share = (gaps[top] * HUNDRED / total_gap).quantize(Decimal("1"))
                out.append({
                    "kind": "overrun_phase",
                    "text": "The %d comps above the P75 cost %s more on average than the other %d. "
                            "%s accounts for %s%% of that gap (%s). Set a scope limit or a separate fee for that phase."
                            % (len(high), display_money(total_gap), len(rest), PHASE_LABELS[top], share,
                               display_money(gaps[top])),
                    "evidence": {"n_above_p75": len(high), "n_rest": len(rest), "p75": p75, "gap_total": total_gap,
                                 "gap_by_phase": gaps, "top_phase": top, "top_share_pct": share,
                                 "matter_ids_above_p75": [m.matter_id for m in high]},
                })

    # Scoping attributes that move cost.
    for attr, noun in (("num_units", unit_label), ("num_parties", "parties")):
        known = [mc for mc in matter_costs if getattr(mc.matter, attr) is not None]
        if len(known) < 2 * MIN_GROUP:
            continue
        counts = sorted(getattr(mc.matter, attr) for mc in known)
        cut = counts[(len(counts) - 1) // 2]
        hi = [mc for mc in known if getattr(mc.matter, attr) > cut]
        lo = [mc for mc in known if getattr(mc.matter, attr) <= cut]
        if len(hi) < MIN_GROUP or len(lo) < MIN_GROUP:
            continue
        mh = stats.quantile([value[m.matter_id] for m in hi], P50)
        ml = stats.quantile([value[m.matter_id] for m in lo], P50)
        if ml > 0 and mh / ml >= RATIO_WORTH_NOTING:
            out.append({
                "kind": attr,
                "text": "Comps with more than %d %s (n=%d) had a median cost of %s, %sx the median of the rest "
                        "(%s, n=%d). State the number of %s the fee covers and price extra ones separately."
                        % (cut, noun, len(hi), display_money(mh), _x(mh, ml), display_money(ml), len(lo), noun),
                "evidence": {"cut": cut, "n_more": len(hi), "n_rest": len(lo), "median_more": mh,
                             "median_rest": ml, "ratio": _x(mh, ml)},
            })

    # Abnormal closes left out.
    abnormal = [m for m, reasons in selection.excluded if "abnormal close excluded" in reasons]
    if abnormal:
        out.append({
            "kind": "abnormal_excluded",
            "text": "%d matters of this type closed abnormally (settled early, transferred or other) and are not in "
                    "the comps. The figures assume the matter runs to completion; say what happens to the fee if it "
                    "ends early." % len(abnormal),
            "evidence": {"n_excluded": len(abnormal), "matter_ids": [m.matter_id for m in abnormal]},
        })

    # Phase confidence.
    low = [mc for mc in matter_costs if mc.phase_confidence == "date_window"]
    if low:
        out.append({
            "kind": "phase_confidence",
            "text": "The phase split for %d of %d comps comes from the date-window fallback, not task codes. "
                    "Treat per-phase figures as lower confidence; totals are not affected." % (len(low), n),
            "evidence": {"n_low_confidence": len(low), "n": n, "matter_ids": [m.matter_id for m in low]},
        })

    # Write-downs and uncollected fees.
    worked = sum((mc.raw_worked for mc in matter_costs), ZERO)
    billed = sum((mc.raw_billed for mc in matter_costs), ZERO)
    invoiced = sum((mc.invoiced for mc in matter_costs), ZERO)
    collected = sum((mc.collected for mc in matter_costs), ZERO)
    if worked > 0:
        wd = (worked - billed) * HUNDRED / worked
        unc = ((invoiced - collected) * HUNDRED / invoiced) if invoiced > 0 else ZERO
        if wd >= 2 or unc >= 2:
            out.append({
                "kind": "write_downs",
                "text": "Across the %d comps, %s%% of worked value was written down before billing and %s%% of "
                        "invoiced fees was not collected. A fee built from billed amounts would understate the "
                        "work; the figures here use worked hours."
                        % (n, wd.quantize(Decimal("0.1")), unc.quantize(Decimal("0.1"))),
                "evidence": {"n": n, "raw_worked": worked, "raw_billed": billed, "invoiced": invoiced,
                             "collected": collected, "write_down_pct": wd.quantize(Decimal("0.1")),
                             "uncollected_pct": unc.quantize(Decimal("0.1"))},
            })
    return out
