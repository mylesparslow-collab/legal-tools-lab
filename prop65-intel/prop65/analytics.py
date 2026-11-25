"""Settlement statistics from the public OAG record. Deterministic; no model involved."""
from __future__ import annotations
import math
from collections import Counter, defaultdict
from datetime import date

from .ingest import Notice, firm_key

MIN_N = 5   # below this many paid resolutions, percentiles are reported but flagged as thin


def percentile(values: list[float], p: float) -> float | None:
    """Linear-interpolated percentile (same method as Excel PERCENTILE.INC and numpy default)."""
    if not values:
        return None
    v = sorted(values)
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def summarize(res: list[dict]) -> dict:
    """p25/p50/p75 of total payment, penalty and fees over resolutions with a payment above zero."""
    paid = [r for r in res if r["total"] > 0]
    tot = [r["total"] for r in paid]
    pen = [r["civil_penalty"] for r in paid]
    fee = [r["attorney_fees"] for r in paid]
    oth = [r["other_payments"] for r in paid]
    s = sum(tot)
    return {
        "n_resolutions": len(res), "n_paid": len(paid), "n_zero": len(res) - len(paid),
        "thin_sample": len(paid) < MIN_N,
        "total_p25": percentile(tot, .25), "total_p50": percentile(tot, .5), "total_p75": percentile(tot, .75),
        "total_max": max(tot) if tot else None, "total_sum": s,
        "penalty_p50": percentile(pen, .5), "fees_p50": percentile(fee, .5),
        "fee_share": (sum(fee) / s) if s else None,
        "penalty_share": (sum(pen) / s) if s else None,
        "other_share": (sum(oth) / s) if s else None,
        "litigated_share": (sum(1 for r in paid if r["litigated"]) / len(paid)) if paid else None,
    }


def filter_resolutions(res, firm=None, chemical=None, product_class=None, since: date | None = None):
    fk = firm_key(firm) if firm else None
    out = []
    for r in res:
        if fk and fk not in (r["firm"], firm_key(r["noticing_party"])):
            continue
        if chemical and chemical not in r["chemicals"]:
            continue
        if product_class and r["product_class"] != product_class:
            continue
        if since and r["notice_date"] < since:
            continue
        out.append(r)
    return out


def benchmark(res, firm=None, chemical=None, product_class=None) -> list[dict]:
    """Settlement benchmark for a new notice, from most specific to least specific slice.

    The caller sees every slice with its sample size and decides which one is usable. The engine
    does not pick for them and never pads a thin slice with a wider one.
    """
    slices = [
        ("Same firm, chemical and product class", dict(firm=firm, chemical=chemical, product_class=product_class)),
        ("Same firm and chemical", dict(firm=firm, chemical=chemical)),
        ("Same firm, all matters", dict(firm=firm)),
        ("All firms, same chemical and product class", dict(chemical=chemical, product_class=product_class)),
        ("All firms, same chemical", dict(chemical=chemical)),
    ]
    out = []
    for label, kw in slices:
        if any(v is None for v in kw.values()):
            continue
        s = summarize(filter_resolutions(res, **kw))
        s["slice"] = label
        out.append(s)
    return out


def firm_table(notices: dict[str, Notice], res: list[dict], top: int = 40) -> list[dict]:
    by_firm_notices = defaultdict(list)
    for n in notices.values():
        by_firm_notices[n.firm].append(n)
    by_firm_res = defaultdict(list)
    for r in res:
        by_firm_res[r["firm"]].append(r)
    rows = []
    for fk, ns in by_firm_notices.items():
        if not fk:
            continue
        name = Counter(n.plaintiff_attorney or n.noticing_party for n in ns).most_common(1)[0][0]
        chems = Counter(c for n in ns for c in n.chemicals)
        classes = Counter(n.product_class for n in ns)
        parties = Counter(n.noticing_party for n in ns)
        row = {"firm_key": fk, "firm": name, "n_notices": len(ns),
               "first_notice": min(n.date for n in ns), "last_notice": max(n.date for n in ns),
               "top_chemicals": ", ".join(f"{c} ({k})" for c, k in chems.most_common(3)),
               "top_classes": ", ".join(f"{c} ({k})" for c, k in classes.most_common(3)),
               "noticing_parties": ", ".join(p for p, _ in parties.most_common(3)),
               "n_with_complaint": sum(1 for n in ns if n.has("complaint")),
               "n_withdrawn": sum(1 for n in ns if n.has("withdrawal"))}
        row.update(summarize(by_firm_res.get(fk, [])))
        rows.append(row)
    rows.sort(key=lambda r: -r["n_notices"])
    return rows[:top] if top else rows


def cohort_table(notices: dict[str, Notice]) -> list[dict]:
    """Outcome by notice year. Recent years look unresolved because settlements are reported later."""
    by_year = defaultdict(list)
    for n in notices.values():
        by_year[n.date.year].append(n)
    rows = []
    for y in sorted(by_year):
        ns = by_year[y]
        t = len(ns)
        rows.append({"year": y, "n_notices": t,
                     "pct_settlement_or_judgment": sum(1 for n in ns if n.has("settlement") or n.has("judgment")) / t,
                     "pct_complaint": sum(1 for n in ns if n.has("complaint")) / t,
                     "pct_withdrawn": sum(1 for n in ns if n.has("withdrawal")) / t,
                     "pct_nothing_reported": sum(1 for n in ns if not n.events) / t})
    return rows


def chemical_table(notices: dict[str, Notice], res: list[dict], top: int = 20) -> list[dict]:
    counts = Counter(c for n in notices.values() for c in n.chemicals)
    rows = []
    for chem, k in counts.most_common(top):
        row = {"chemical": chem, "n_notices": k}
        row.update(summarize(filter_resolutions(res, chemical=chem)))
        rows.append(row)
    return rows


def class_table(notices: dict[str, Notice], res: list[dict]) -> list[dict]:
    counts = Counter(n.product_class for n in notices.values())
    rows = []
    for pc, k in counts.most_common():
        row = {"product_class": pc, "n_notices": k}
        row.update(summarize(filter_resolutions(res, product_class=pc)))
        rows.append(row)
    return rows


def defendant_history(notices: dict[str, Notice], name: str) -> list[Notice]:
    """Prior notices naming a defendant (substring match on the normalized name)."""
    k = firm_key(name)
    return sorted((n for n in notices.values() if k and k in firm_key(n.violators)), key=lambda n: n.date)
