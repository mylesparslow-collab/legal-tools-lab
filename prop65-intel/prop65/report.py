"""Builds the outputs: an Excel workbook and a single-file HTML report."""
from __future__ import annotations
import html, json, re
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from . import analytics
from .ingest import product_class_labels
from .rules import load_rules, load_levels, ROOT
from .verifier import CITE_RE

HEAD = PatternFill("solid", fgColor="1F4E4A")


def _sheet(wb, title, header, rows, widths=None, money=(), pct=()):
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = HEAD; c.alignment = Alignment(wrap_text=True, vertical="top")
    for r in rows:
        ws.append(r)
    for i, _ in enumerate(header, start=1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(i, 16)
    for col in money:
        for cell in ws[get_column_letter(col)][1:]:
            cell.number_format = '"$"#,##0'
    for col in pct:
        for cell in ws[get_column_letter(col)][1:]:
            cell.number_format = "0%"
    ws.freeze_panes = "A2"
    return ws


def build_workbook(notices, res, triage_results, verify_reports, out_path, data_note: str):
    wb = Workbook()
    ws = wb.active; ws.title = "Read me"
    for line in [
        "Proposition 65 notice intelligence - portfolio demo",
        "Built by a non-attorney as a personal project. Not legal advice. Every output needs attorney review.",
        data_note,
        "Settlement statistics come from the public Attorney General 60-day notice database. Amounts are as reported by the settling parties.",
        "A 'payment event' is a settlement or judgment after removing duplicates (see README, 'How duplicates are handled').",
        "Percentiles use only events with a payment above zero. Slices with fewer than 5 paid events are marked thin.",
        "The triage and record-check sheets use synthetic documents. Every person and company in them is fictional.",
        "Values in this workbook are computed by the Python engine and written as numbers. The 'Payment events' sheet holds the rows behind them.",
    ]:
        ws.append([line])
    ws.column_dimensions["A"].width = 140
    ws["A1"].font = Font(bold=True, size=14)

    lab = product_class_labels()
    ft = analytics.firm_table(notices, res, top=60)
    _sheet(wb, "Firms", ["Plaintiff firm (as filed)", "Notices", "First notice", "Last notice", "Noticing parties", "Top chemicals", "Top product classes",
                         "Notices with complaint", "Notices withdrawn", "Paid events", "Total p25", "Total p50", "Total p75", "Largest", "Median penalty", "Median fees", "Fee share of dollars", "Share litigated", "Thin sample"],
           [[r["firm"], r["n_notices"], r["first_notice"], r["last_notice"], r["noticing_parties"], r["top_chemicals"], r["top_classes"], r["n_with_complaint"], r["n_withdrawn"],
             r["n_paid"], r["total_p25"], r["total_p50"], r["total_p75"], r["total_max"], r["penalty_p50"], r["fees_p50"], r["fee_share"], r["litigated_share"], "yes" if r["thin_sample"] else ""] for r in ft],
           {1: 34, 5: 40, 6: 40, 7: 40}, money=(11, 12, 13, 14, 15, 16), pct=(17, 18))
    _sheet(wb, "Chemicals", ["Chemical", "Notices", "Paid events", "Total p25", "Total p50", "Total p75", "Median penalty", "Median fees", "Fee share"],
           [[r["chemical"], r["n_notices"], r["n_paid"], r["total_p25"], r["total_p50"], r["total_p75"], r["penalty_p50"], r["fees_p50"], r["fee_share"]] for r in analytics.chemical_table(notices, res, 30)],
           {1: 36}, money=(4, 5, 6, 7, 8), pct=(9,))
    _sheet(wb, "Product classes", ["Product class", "Notices", "Paid events", "Total p25", "Total p50", "Total p75", "Median penalty", "Median fees"],
           [[lab[r["product_class"]], r["n_notices"], r["n_paid"], r["total_p25"], r["total_p50"], r["total_p75"], r["penalty_p50"], r["fees_p50"]] for r in analytics.class_table(notices, res)],
           {1: 44}, money=(4, 5, 6, 7, 8))
    _sheet(wb, "By notice year", ["Notice year", "Notices", "Settlement or judgment reported", "Complaint filed", "Withdrawn", "Nothing reported yet"],
           [[r["year"], r["n_notices"], r["pct_settlement_or_judgment"], r["pct_complaint"], r["pct_withdrawn"], r["pct_nothing_reported"]] for r in analytics.cohort_table(notices)],
           {3: 22, 6: 22}, pct=(3, 4, 5, 6))
    _sheet(wb, "Payment events", ["Kind", "AG numbers", "Earliest notice date", "Noticing party", "Plaintiff attorney", "Chemicals", "Product class", "Alleged violators", "Case name", "Docket", "Court entered", "Civil penalty", "Attorney fees", "Other payments", "Total"],
           [[r["kind"], ", ".join(r["ag_numbers"]), r["notice_date"], r["noticing_party"], r["plaintiff_attorney"], ", ".join(r["chemicals"]), lab[r["product_class"]], r["violators"][:300], r["case_name"][:200], r["docket"][:60],
             "yes" if r["court_entered"] else "", r["civil_penalty"], r["attorney_fees"], r["other_payments"], r["total"]] for r in sorted(res, key=lambda r: r["notice_date"], reverse=True)],
           {2: 24, 4: 30, 5: 30, 6: 24, 7: 30, 8: 40, 9: 40}, money=(12, 13, 14, 15))
    rows = []
    for t in triage_results:
        for c in t["checks"]:
            rows.append([t["case_id"], c["check"], c["status"], c["summary"], "; ".join(r["citation"] for r in c["rules"]),
                         "; ".join(sorted({r["status"] for r in c["rules"]})), " | ".join(c["attorney_review"])])
    _sheet(wb, "Triage (synthetic)", ["Case", "Check", "Result", "What the engine found", "Rule", "Rule verification", "For attorney review"], rows, {1: 18, 2: 20, 4: 90, 5: 50, 6: 20, 7: 80})
    rows = []
    for rep in verify_reports:
        for r in rep["results"]:
            rows.append([rep["draft"], r["id"], r["cite"] or "(none)", r["status"], r["assertion"][:300], " | ".join(f"{i['type']}: {i['message']}" for i in r["items"]), "", "", ""])
    _sheet(wb, "Record check (synthetic)", ["Draft", "Item", "Record cite", "Result", "Draft text", "What the checker found", "Verified by", "Date", "Resolution note"], rows, {1: 24, 5: 70, 6: 90, 9: 40})
    _sheet(wb, "Rules", ["Rule id", "Citation", "Summary", "Verification status", "Source read", "Status note", "Attorney review"],
           [[r["id"], r["citation"], r["summary"], r["status"], r["source"], r.get("status_note", ""), r.get("attorney_review", "")] for r in load_rules().values()], {1: 26, 2: 44, 3: 100, 4: 18, 5: 50, 6: 50, 7: 60})
    _sheet(wb, "Safe harbor levels", ["Chemical", "Endpoint", "Date listed", "Level type", "Level (µg/day)", "Route", "Source"],
           [[r["chemical"], r["endpoint"], r["date_listed"], r["level_type"], r["level_ug_day"], r["route"], r["source"]] for r in load_levels()], {1: 50, 2: 26, 6: 24, 7: 50})
    wb.save(out_path)


# --------------------------------------------------------------------------- HTML
def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _usd(v) -> str:
    return "n/a" if v is None else f"${v:,.0f}"


def _pill(status: str) -> str:
    cls = {"PASS": "ok", "VERIFIED": "ok", "BELOW": "ok", "EXEMPT": "ok", "ELIGIBLE": "ok", "COMPUTED": "info", "NOT_EXEMPT": "info", "MANUAL": "info",
           "WARN": "warn", "REVIEW": "warn", "PARTIAL": "warn", "NO_LISTED_LEVEL": "warn", "NEEDS_REVIEW": "warn", "NEEDS_INPUT": "warn", "NOT_IN_TABLE": "warn",
           "FAIL": "bad", "ABOVE": "bad", "BLOCKED": "bad", "NOT_ELIGIBLE": "info", "WINDOW_CLOSED": "bad"}.get(status, "info")
    return f'<span class="pill {cls}">{_e(status.replace("_", " ").lower())}</span>'


def _draft_html(text: str, report: dict) -> str:
    by_cite = {}
    for r in report["results"]:
        if r["cite"]:
            by_cite.setdefault(r["cite"], []).append(r)
    out = []
    for para in [p for p in re.split(r"\n\s*\n", text) if p.strip()]:
        if para.lstrip().startswith("#"):
            out.append(f"<h4>{_e(para.lstrip('# ').strip())}</h4>"); continue
        pos, buf = 0, ""
        for m in CITE_RE.finditer(para):
            buf += _e(para[pos:m.start()])
            cite = m.group(0)[1:-1]
            r = (by_cite.get(cite) or [None]).pop(0) if by_cite.get(cite) else None
            st = r["status"] if r else "MANUAL"
            target = None
            if r:
                for i in r["items"]:
                    f = i.get("found") or {}
                    if f.get("page"):
                        target = (f["page"], f.get("lines")); break
            if not target:
                target = (cite.split(":")[0], None)
            lines = json.dumps(target[1]) if target[1] else "null"
            msgs = " ".join(i["message"] for i in r["items"]) if r else ""
            buf += (f'<button class="cite {st.lower()}" data-page="{_e(target[0])}" data-lines=\'{lines}\' title="{_e(msgs)}">{_e(cite)}</button>')
            if r and st != "PASS":
                buf += f'<span class="note {st.lower()}">{_e(msgs)}</span>'
            pos = m.end()
        tail = para[pos:]
        buf += _e(tail)
        for r in report["results"]:
            if r["cite"] is None and r["assertion"].strip('"“” ')[:20] in tail:
                buf += f'<span class="note fail">{_e(r["items"][0]["message"])}</span>'
        out.append(f"<p>{buf}</p>")
    return "\n".join(out)


def _record_html(record) -> str:
    out = []
    for d in record.index["documents"]:
        out.append(f'<h4>{_e(d["title"])}</h4>')
        for p in sorted((p for p in record.pages.values() if p.doc == d["prefix"]), key=lambda p: p.number):
            rows = "".join(f'<div class="ln" data-n="{i}"><span class="n">{i}</span><span class="t">{_e(l) or "&nbsp;"}</span></div>' for i, l in enumerate(p.lines, 1))
            out.append(f'<div class="page" id="pg-{p.bates}"><div class="bates">{p.bates}</div>{rows}</div>')
    return "\n".join(out)


def build_html(notices, res, triage_results, verify_reports, drafts: dict, record, out_path, data_note: str, corrections_md: str):
    lab = product_class_labels()
    overall = analytics.summarize(res)
    firms = analytics.firm_table(notices, res, top=15)
    chems = analytics.chemical_table(notices, res, 12)
    cohorts = analytics.cohort_table(notices)
    bench = {}
    for c in [r["chemical"] for r in analytics.chemical_table(notices, res, 14)]:
        for pc in lab:
            s = analytics.summarize(analytics.filter_resolutions(res, chemical=c, product_class=pc))
            if s["n_paid"] >= 1:
                bench[f"{c}|{pc}"] = [s["n_paid"], s["total_p25"], s["total_p50"], s["total_p75"], s["penalty_p50"], s["fees_p50"]]
        s = analytics.summarize(analytics.filter_resolutions(res, chemical=c))
        bench[f"{c}|*"] = [s["n_paid"], s["total_p25"], s["total_p50"], s["total_p75"], s["penalty_p50"], s["fees_p50"]]
    dmin, dmax = min(n.date for n in notices.values()), max(n.date for n in notices.values())

    firm_rows = "".join(
        f'<tr><td>{_e(r["firm"])}<div class="sub">{_e(r["noticing_parties"])}</div></td><td class="num">{r["n_notices"]:,}</td><td class="num">{r["n_paid"]:,}</td>'
        f'<td class="num">{_usd(r["total_p25"])}</td><td class="num"><b>{_usd(r["total_p50"])}</b></td><td class="num">{_usd(r["total_p75"])}</td>'
        f'<td class="num">{(r["fee_share"] or 0):.0%}</td><td>{_e(r["top_chemicals"])}</td></tr>' for r in firms)
    chem_rows = "".join(
        f'<tr><td>{_e(r["chemical"])}</td><td class="num">{r["n_notices"]:,}</td><td class="num">{r["n_paid"]:,}</td><td class="num">{_usd(r["total_p25"])}</td>'
        f'<td class="num"><b>{_usd(r["total_p50"])}</b></td><td class="num">{_usd(r["total_p75"])}</td></tr>' for r in chems)
    cohort_rows = "".join(
        f'<div class="bar-row"><span class="yr">{r["year"]}</span><span class="cnt">{r["n_notices"]:,}</span><div class="bar">'
        f'<i class="s1" style="width:{r["pct_settlement_or_judgment"]*100:.1f}%"></i><i class="s2" style="width:{max(0, 1 - r["pct_settlement_or_judgment"] - r["pct_nothing_reported"])*100:.1f}%"></i></div>'
        f'<span class="pc">{r["pct_settlement_or_judgment"]:.0%}</span></div>' for r in cohorts)

    tri = []
    for t in triage_results:
        items = []
        for c in t["checks"]:
            rules = "; ".join(f'{_e(r["citation"])} <span class="vs">{_e(r["status"].replace("_", " "))}</span>' for r in c["rules"])
            extra = ""
            for comp in c.get("detail", {}).get("comparisons", []):
                lvl = "none listed" if comp.get("level_ug_day") is None else f'{comp["level_ug_day"]:g} µg/day'
                extra += f'<div class="calc">{_e(comp["endpoint"])}: {_e(comp["level_type"])} {lvl}' + (f', exposure is {comp["ratio"]:.0%} of the level' if comp.get("ratio") is not None else "") + "</div>"
            for f in c.get("detail", {}).get("findings", []):
                extra += f'<div class="calc">{_pill(f["level"])} {_e(f["message"])}</div>'
            for ep in c.get("detail", {}).get("endpoints", []):
                extra += f'<div class="calc">{_e(ep["endpoint"])}: listed {_e(ep["date_listed"])}, warning required from {_e(ep["warning_required_from"])}</div>'
            rev = "".join(f"<li>{_e(a)}</li>" for a in c["attorney_review"])
            items.append(f'<div class="check"><div class="ch">{_pill(c["status"])}<b>{_e(c["check"].replace("_", " "))}</b></div><p>{_e(c["summary"])}</p>{extra}'
                         + (f'<div class="rule">{rules}</div>' if rules else "") + (f'<details><summary>For attorney review</summary><ul>{rev}</ul></details>' if rev else "") + "</div>")
        blocked = f'<p class="blocked">Values rejected by the record check: {_e(", ".join(t["blocked_claims"]))}</p>' if t["blocked_claims"] else ""
        tri.append(f'<section class="case"><h3>{_e(t.get("title") or t["case_id"])}</h3><p class="sub">{_e(t.get("note", ""))}</p>{blocked}{"".join(items)}</section>')

    tabs = "".join(f'<button class="tab" data-draft="{_e(rep["draft"])}">{_e(rep["draft"].replace("_", " "))} <span class="cnts">{rep["counts"]["PASS"]} pass · {rep["counts"]["WARN"]} warn · {rep["counts"]["FAIL"]} fail</span></button>' for rep in verify_reports)
    drafts_html = "".join(f'<div class="draft" data-draft="{_e(rep["draft"])}" hidden>{_draft_html(drafts[rep["draft"]], rep)}</div>' for rep in verify_reports)

    rules_rows = "".join(f'<tr><td>{_e(r["citation"])}</td><td>{_e(r["summary"])}</td><td><span class="vs {r["status"]}">{_e(r["status"].replace("_", " "))}</span></td></tr>' for r in load_rules().values())
    corr = "".join(f"<li>{_e(l[2:].strip())}</li>" for l in corrections_md.split("## Where the report is wrong or incomplete")[-1].split("\n## ")[0].splitlines() if l.startswith("- "))
    corr = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", corr)

    tpl = (ROOT / "prop65" / "report_template.html").read_text(encoding="utf-8")
    page = (tpl.replace("{{DATA_NOTE}}", _e(data_note)).replace("{{N_NOTICES}}", f"{len(notices):,}").replace("{{N_EVENTS}}", f"{overall['n_paid']:,}")
            .replace("{{P25}}", _usd(overall["total_p25"])).replace("{{P50}}", _usd(overall["total_p50"])).replace("{{P75}}", _usd(overall["total_p75"]))
            .replace("{{FEE_SHARE}}", f"{overall['fee_share']:.0%}").replace("{{PEN_SHARE}}", f"{overall['penalty_share']:.0%}")
            .replace("{{RANGE}}", f"{dmin:%B %-d, %Y} to {dmax:%B %-d, %Y}")
            .replace("{{FIRM_ROWS}}", firm_rows).replace("{{CHEM_ROWS}}", chem_rows).replace("{{COHORT_ROWS}}", cohort_rows)
            .replace("{{TRIAGE}}", "".join(tri)).replace("{{TABS}}", tabs).replace("{{DRAFTS}}", drafts_html).replace("{{RECORD}}", _record_html(record))
            .replace("{{RULES_ROWS}}", rules_rows).replace("{{CORRECTIONS}}", corr)
            .replace("{{BENCH_JSON}}", json.dumps(bench)).replace("{{CLASS_JSON}}", json.dumps(lab)))
    Path(out_path).write_text(page, encoding="utf-8")
