"""IFOA risk/reward pool: amendment ledger checks and closeout waterfall.

Deterministic arithmetic only. Every contract term here (tier order, savings
split, caps) is an input taken from the ledger file, because IFOA terms are
negotiated per project. Nothing in this module is a statement of law.
"""
from __future__ import annotations

from decimal import Decimal

from .common import D, Finding, money, parse_date

TOTAL_KEYS = ("target_cost", "shared_contingency", "owner_contingency", "emp")
AMENDMENT_TYPES = {
    "BASE", "JOINING", "VALIDATION_GATE", "TARGET_COST_ADJUSTMENT",
    "CONTINGENCY_DRAW", "ICL_REALLOCATION",
}
PROVENANCE_KEYS = ("document", "exhibit", "page", "quote")
SHARE_TOL = D("0.01")  # percentage points


def run_ledger(ledger: dict):
    """Replay the amendments in order.

    Returns (states, findings). states[i] holds the running totals after
    amendment i, computed only from deltas; the 'stated' block of each
    amendment (what its exhibit says the totals are) is then compared to them.
    """
    findings: list[Finding] = []
    states: list[dict] = []
    run = {k: D(0) for k in TOTAL_KEYS}
    icl: dict[str, Decimal] = {}
    joined: dict[str, int] = {}
    drawn = {"shared": D(0), "owner": D(0)}
    prev_no, prev_date = None, None

    terms = ledger.get("terms", {})
    o, t = D(terms.get("owner_savings_pct", 0)), D(terms.get("team_savings_pct", 0))
    if o + t != D(100):
        findings.append(Finding("L8", "error", "terms",
                                f"Savings split is {o}% owner + {t}% team = {o + t}%, not 100%."))

    for am in ledger["amendments"]:
        no = am["no"]
        where = f"Amendment {no}"
        d = parse_date(am["date"])

        if am["type"] not in AMENDMENT_TYPES:
            findings.append(Finding("L1", "error", where, f"Unknown amendment type {am['type']!r}."))
        if prev_no is not None and no != prev_no + 1:
            findings.append(Finding("L1", "error", where,
                                    f"Amendment numbers are not sequential ({prev_no} then {no})."))
        if prev_date is not None and d < prev_date:
            findings.append(Finding("L1", "error", where,
                                    f"Dated {d}, before the prior amendment ({prev_date})."))
        prev_no, prev_date = no, d

        prov = am.get("provenance") or {}
        missing = [k for k in PROVENANCE_KEYS if prov.get(k) in (None, "")]
        if missing:
            findings.append(Finding("L9", "error", where,
                                    "Record has no source reference for: " + ", ".join(missing) + "."))

        j = am.get("joining")
        if j:
            joined[j["member"]] = no
            status = j.get("counsel_status", "unknown")
            if status == "unknown":
                findings.append(Finding("L10", "warn", where,
                                        f"{j['member']}: whether the joining party has its own counsel is not recorded."))
            elif status == "unrepresented" and not j.get("nonrep_notice_logged"):
                findings.append(Finding("L10", "warn", where,
                                        f"{j['member']} is recorded as unrepresented and no non-representation notice is logged."))
        if am["type"] == "BASE":
            for m in am.get("base_members", []):
                joined[m] = no

        for k in TOTAL_KEYS:
            run[k] += D(am.get("deltas", {}).get(k, 0))
        for ch in am.get("icl_changes", []):
            m = ch["member"]
            if m not in joined:
                findings.append(Finding("L5", "error", where,
                                        f"{m} receives ICL but has not signed the base agreement or a joining agreement."))
            icl[m] = icl.get(m, D(0)) + D(ch["delta"])
            if icl[m] < 0:
                findings.append(Finding("L6", "error", where, f"{m} ICL is negative ({icl[m]})."))
        if am["type"] == "ICL_REALLOCATION":
            net = sum((D(c["delta"]) for c in am.get("icl_changes", [])), D(0))
            if net != 0:
                findings.append(Finding("L4", "error", where,
                                        f"Reallocation changes total ICL by {net}; it should net to zero."))
        for pool, amt in (am.get("draws") or {}).items():
            drawn[pool] += D(amt)

        icl_total = sum(icl.values(), D(0))
        bal_shared = run["shared_contingency"] - drawn["shared"]
        bal_owner = run["owner_contingency"] - drawn["owner"]
        if bal_shared < 0:
            findings.append(Finding("L6", "error", where,
                                    f"Shared contingency is overdrawn by {-bal_shared:,.2f}."))
        if bal_owner < 0:
            findings.append(Finding("L6", "error", where,
                                    f"Owner contingency is overdrawn by {-bal_owner:,.2f}."))

        floor = run["target_cost"] + run["shared_contingency"] + icl_total
        if run["emp"] < floor:
            findings.append(Finding("L7", "error", where,
                                    f"EMP {run['emp']:,.2f} is below target cost + shared contingency + ICL ({floor:,.2f})."))

        computed_shares = {m: (v / icl_total * 100 if icl_total else D(0)) for m, v in icl.items()}
        stated = am.get("stated") or {}
        for k in TOTAL_KEYS:
            if k in stated and D(stated[k]) != run[k]:
                findings.append(Finding("L2", "error", where,
                                        f"Exhibit states {k.replace('_', ' ')} of {D(stated[k]):,.2f}; "
                                        f"prior total plus this amendment's change is {run[k]:,.2f} "
                                        f"(difference {D(stated[k]) - run[k]:,.2f})."))
        if "icl_total" in stated and D(stated["icl_total"]) != icl_total:
            findings.append(Finding("L2", "error", where,
                                    f"Exhibit states total ICL of {D(stated['icl_total']):,.2f}; computed {icl_total:,.2f}."))
        stated_shares = stated.get("icl_shares")
        share_sum = None
        if stated_shares is not None:
            share_sum = sum((D(v) for v in stated_shares.values()), D(0))
            if share_sum != D(100):
                findings.append(Finding("L3", "error", where,
                                        f"Stated ICL shares sum to {share_sum:.2f}%, not 100.00%."))
            for m in sorted(set(stated_shares) | set(icl)):
                s = D(stated_shares.get(m, 0))
                c = computed_shares.get(m, D(0))
                if m not in icl or icl[m] == 0:
                    if s != 0:
                        findings.append(Finding("L4", "error", where, f"{m} has a stated share but no ICL."))
                elif m not in stated_shares:
                    findings.append(Finding("L4", "error", where, f"{m} has ICL but no stated share."))
                elif abs(s - c) > SHARE_TOL:
                    findings.append(Finding("L4", "error", where,
                                            f"{m}: stated share {s:.2f}% vs {c:.2f}% computed from ICL dollars."))

        states.append({
            "no": no, "date": d, "type": am["type"], "title": am.get("title", ""),
            **{k: run[k] for k in TOTAL_KEYS},
            "icl_total": icl_total, "icl": dict(icl),
            "shared_drawn": drawn["shared"], "owner_drawn": drawn["owner"],
            "shared_balance": bal_shared, "owner_balance": bal_owner,
            "stated_share_sum": share_sum, "computed_shares": computed_shares,
        })
    return states, findings


def waterfall(state: dict, terms: dict, actual_cost) -> dict:
    """Closeout waterfall for a given actual (or forecast) reimbursable cost.

    Overrun above target cost is absorbed in this order:
      1. shared contingency (as authorized by the amendments)
      2. the team's ICL, up to 100% of it
      3. owner contingency
      4. the owner, at cost with no profit
    Reimbursable costs are always paid; only profit is at risk. Savings below
    target cost are split owner/team, with an optional cap on the ICL pool.
    """
    ac = D(actual_cost)
    tc, sc, oc = state["target_cost"], state["shared_contingency"], state["owner_contingency"]
    icl, emp = state["icl_total"], state["emp"]
    team_pct = D(terms["team_savings_pct"]) / 100
    cap_mult = terms.get("icl_cap_multiple")

    overrun = max(D(0), ac - tc)
    t1 = min(overrun, sc)
    t2 = min(overrun - t1, icl)
    t3 = min(overrun - t1 - t2, oc)
    t4 = overrun - t1 - t2 - t3

    savings = max(D(0), tc - ac)
    team_savings = money(savings * team_pct)
    pool = icl - t2 + team_savings
    capped = D(0)
    if cap_mult is not None and pool > icl * D(cap_mult):
        capped = pool - icl * D(cap_mult)
        pool = icl * D(cap_mult)
    owner_savings = savings - team_savings + capped
    owner_total = ac + pool
    payouts = {m: money(pool * v / icl) if icl else D(0) for m, v in state["icl"].items()}

    return {
        "actual_cost": ac, "overrun": overrun, "savings": savings,
        "tier1_shared_contingency": t1, "tier2_icl": t2,
        "tier3_owner_contingency": t3, "tier4_owner_at_cost": t4,
        "team_savings": team_savings - capped, "owner_savings": owner_savings,
        "icl_pool_final": pool, "icl_pool_pct_of_base": (pool / icl * 100 if icl else D(0)),
        "owner_total": owner_total, "emp": emp, "emp_headroom": emp - owner_total,
        "over_emp": owner_total > emp,
        "payouts": payouts, "payout_rounding_gap": sum(payouts.values(), D(0)) - money(pool),
    }


def waterfall_findings(state: dict, wf: dict) -> list[Finding]:
    out = []
    if wf["over_emp"]:
        out.append(Finding("W1", "error", "Waterfall",
                           f"Owner's total payment {wf['owner_total']:,.2f} is {-wf['emp_headroom']:,.2f} over the EMP. "
                           "Who bears cost above the EMP depends on the contract; the engine does not allocate it."))
    if wf["tier2_icl"] > 0:
        pct = wf["tier2_icl"] / state["icl_total"] * 100
        out.append(Finding("W2", "warn", "Waterfall",
                           f"Forecast overrun uses all shared contingency and {pct:.1f}% of the ICL."))
    if wf["tier3_owner_contingency"] > 0 or wf["tier4_owner_at_cost"] > 0:
        out.append(Finding("W3", "warn", "Waterfall", "Forecast overrun eliminates the ICL and reaches owner funds."))
    unpapered = wf["overrun"] - state["shared_drawn"] - state["owner_drawn"]
    if unpapered > 0:
        out.append(Finding("W4", "info", "Waterfall",
                           f"{unpapered:,.2f} of the forecast overrun is not yet covered by a logged contingency draw."))
    return out
