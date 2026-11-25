"""Plain-text findings memo built from the engine's output."""
from __future__ import annotations

from .engine import FAIL, REVIEW, Rules


def _money(v) -> str:
    return f"${v:,.0f}"


def findings_markdown(audit: dict, rules: Rules) -> str:
    out = [f"# Buy America bill-of-materials audit: {audit['agency']}", ""]
    out += ["Synthetic data. This is a personal portfolio demo prepared by a non-attorney. It is not legal "
            "advice and not a compliance determination. Every result needs review by qualified counsel.", "",
            f"Generated {audit['generated_on']}.", ""]
    for p in audit["projects"]:
        out += [f"## {p['name']} ({p['project_id']}): {p['overall']}", "",
                f"Funding source: {p['funding']}. Stage: {p['stage'].replace('_', ' ') or 'not given'}.", ""]
        for r in p["rolling_stock"]:
            out += [f"### {r['description']}: {r['status']}", "",
                    f"Domestic content is {r['domestic_pct']:.2f}% ({_money(r['domestic_cost'])} of "
                    f"{_money(r['total_component_cost'])}). The requirement for an FY{r['fiscal_year']} delivery is "
                    f"more than {r['threshold_pct']}%, with final assembly in the United States "
                    f"({'yes' if r['final_assembly_us'] else 'no'}). Source: {r['cite']}.", ""]
            if r["shortfall_usd"]:
                out += [f"About {_money(r['shortfall_usd'])} more domestic component cost per vehicle is needed to reach the threshold.", ""]
            out += ["| Component | Origin | Cost | Counted | Basis |", "|---|---|---:|---:|---|"]
            for c in r["components"]:
                out.append(f"| {c['line_id']} {c['description']} | {c['mfg_country'] or '?'} | {_money(c['cost'])} | "
                           f"{_money(c['counted'])} | {c['basis']} |")
            out.append("")
            flags = [(c["line_id"], f) for c in r["components"] for f in c["flags"]] + [("vehicle", f) for f in r["flags"]]
            if flags:
                out += ["Items to check:", ""] + [f"- {lid}: {f}" for lid, f in flags] + [""]
        if p["infrastructure"]:
            out += ["### Steel, manufactured products and construction materials", "",
                    "| Item | Category | Cost | Result | FTA 661.5(d) | BABA 55% | Test applied |",
                    "|---|---|---:|---|---|---|---|"]
            for r in p["infrastructure"]:
                out.append(f"| {r['line_id']} {r['description']} | {r['category'].replace('_', ' ')} | {_money(r['cost'])} | "
                           f"{r['status']} | {r['fta_661_5d']} | {r['baba_184']} | {r.get('governing_test', '')} ({r.get('cite', '')}) |")
            out.append("")
            flags = [(r["line_id"], f) for r in p["infrastructure"] for f in r["flags"]]
            flags += [(r["line_id"], "Buy Clean California: " + r["buy_clean"]["note"])
                      for r in p["infrastructure"] if r.get("buy_clean")]
            if flags:
                out += ["Items to check:", ""] + [f"- {lid}: {f}" for lid, f in flags] + [""]
        if p["de_minimis"]:
            d = p["de_minimis"]
            out += [f"Non-compliant items total {_money(d['noncompliant_total'])}. The de minimis size limit for this "
                    f"project works out to {_money(d['cap'])}, so the total is "
                    f"{'within' if d['within_limits'] else 'over'} it. {d['note']}", ""]
        out += ["### Documents", "", "| Document | Status | Note | Source |", "|---|---|---|---|"]
        for d in p["documents"]:
            out.append(f"| {d['document']} | {d['status']} | {d['note']} | {d['cite']} |")
        out.append("")
    out += ["## Rules used", "", "| Rule | Source | Status | Checked |", "|---|---|---|---|"]
    for r in rules.entries.values():
        out.append(f"| {r['label']} | {r['source']} | {r['status'].replace('_', ' ')} | {r.get('verified_on') or 'not checked'} |")
    out.append("")
    return "\n".join(out)
