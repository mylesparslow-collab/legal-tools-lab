"""Outputs: pre-bill review report (HTML, JSON, CSV), summary paragraph, timekeeper notes, index page."""

import csv
import io
import json
from collections import Counter, defaultdict
from decimal import Decimal
from html import escape

from . import guidelines as G
from .model import ZERO, fmt_money, fmt_num, money

NOTICE = "Personal portfolio demo. Fictional data. Not legal or billing advice."
AT_RISK_RULE = (
    "Amount at risk counts each entry once: the largest single reduction among its open findings, "
    "capped at the entry amount. Invoice-level findings (budget, phase, totals) overlap with entry "
    "reductions, so the invoice figure is the larger of the per-entry sum and the largest "
    "invoice-level amount, capped at the sum of the lines. Waived findings count for nothing."
)

CSS = """
:root{--bg:#fbfaf7;--ink:#1d2430;--muted:#5d6675;--line:#d9d5cc;--card:#ffffff;--accent:#27496d;
--reject:#9b2c2c;--reduce:#8a5a00;--review:#3b5b7a;--waived:#4a6b4f;--rejectbg:#fbeaea;--reducebg:#fdf3dc;--reviewbg:#e8eff6;--waivedbg:#e9f1ea}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151a21;--ink:#e6e8eb;--muted:#9aa4b2;--line:#323a46;--card:#1c232c;--accent:#8fb4dc;
--reject:#f0a3a3;--reduce:#e6c170;--review:#a9c4e0;--waived:#a8cbae;--rejectbg:#3a2224;--reducebg:#3a3018;--reviewbg:#1f2d3b;--waivedbg:#21301f}}
:root[data-theme="dark"]{--bg:#151a21;--ink:#e6e8eb;--muted:#9aa4b2;--line:#323a46;--card:#1c232c;--accent:#8fb4dc;
--reject:#f0a3a3;--reduce:#e6c170;--review:#a9c4e0;--waived:#a8cbae;--rejectbg:#3a2224;--reducebg:#3a3018;--reviewbg:#1f2d3b;--waivedbg:#21301f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Georgia,"Times New Roman",serif}
main{max-width:1320px;margin:0 auto;padding:24px 16px 56px}
h1{font-size:26px;margin:0 0 4px;font-weight:600}
h2{font-size:18px;margin:32px 0 8px;font-weight:600}
p{margin:8px 0}
.notice{font:13px/1.4 system-ui,sans-serif;color:var(--muted);border:1px solid var(--line);padding:8px 12px;border-radius:4px;background:var(--card)}
.meta,.small{font:13px/1.45 system-ui,sans-serif;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:10px 12px}
.card b{display:block;font:600 21px/1.2 system-ui,sans-serif;font-variant-numeric:tabular-nums}
.card span{font:12px/1.3 system-ui,sans-serif;color:var(--muted)}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:4px;background:var(--card)}
table{border-collapse:collapse;width:100%;font:13px/1.45 system-ui,sans-serif}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{white-space:nowrap;font-weight:600;background:var(--card);position:sticky;top:0}
th button{all:unset;cursor:pointer;font-weight:600}
th button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
th[aria-sort="ascending"] button::after{content:" \\25B2";font-size:10px}
th[aria-sort="descending"] button::after{content:" \\25BC";font-size:10px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr:last-child td{border-bottom:0}
.sev{display:inline-block;padding:1px 7px;border-radius:3px;font-weight:600;white-space:nowrap}
.sev-reject{color:var(--reject);background:var(--rejectbg)}
.sev-reduce{color:var(--reduce);background:var(--reducebg)}
.sev-review{color:var(--review);background:var(--reviewbg)}
.sev-waived{color:var(--waived);background:var(--waivedbg)}
tr.waived td{color:var(--muted)}
blockquote{margin:4px 0 0;padding-left:8px;border-left:2px solid var(--line);font-style:italic}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;font:13px system-ui,sans-serif;align-items:center}
.controls button,.controls select{font:13px system-ui,sans-serif;padding:5px 10px;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--ink);cursor:pointer}
a{color:var(--accent)}
ul{padding-left:20px}
td.wide{min-width:170px}
.nowrap{white-space:nowrap}
@media print{body{background:#fff;color:#000;font-size:11px}.controls,.noprint{display:none}.wrap{overflow:visible;border:0}th{position:static}
main{max-width:none;padding:0}tr{break-inside:avoid}a{color:#000;text-decoration:none}}
"""

SORT_JS = """
(function(){
  document.querySelectorAll('table[data-sortable]').forEach(function(table){
    var body = table.tBodies[0];
    function sortBy(index, direction){
      var rows = Array.prototype.slice.call(body.rows);
      rows.sort(function(a, b){
        var x = a.cells[index].getAttribute('data-sort'), y = b.cells[index].getAttribute('data-sort');
        var nx = Number(x), ny = Number(y), result;
        if (x !== '' && y !== '' && !isNaN(nx) && !isNaN(ny)) { result = nx - ny; }
        else { result = String(x).localeCompare(String(y)); }
        if (result === 0) { result = Number(a.getAttribute('data-order')) - Number(b.getAttribute('data-order')); }
        return direction * result;
      });
      rows.forEach(function(row){ body.appendChild(row); });
      Array.prototype.forEach.call(table.tHead.rows[0].cells, function(th, i){
        if (i === index) { th.setAttribute('aria-sort', direction > 0 ? 'ascending' : 'descending'); }
        else { th.removeAttribute('aria-sort'); }
      });
    }
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function(th, index){
      var button = th.querySelector('button');
      if (!button) { return; }
      button.addEventListener('click', function(){
        sortBy(index, th.getAttribute('aria-sort') === 'ascending' ? -1 : 1);
      });
    });
    document.querySelectorAll('[data-sort-table="' + table.id + '"]').forEach(function(control){
      control.addEventListener('click', function(){ sortBy(Number(control.getAttribute('data-col')), 1); });
    });
  });
  document.querySelectorAll('[data-filter-table]').forEach(function(select){
    select.addEventListener('change', function(){
      var table = document.getElementById(select.getAttribute('data-filter-table'));
      var selects = document.querySelectorAll('[data-filter-table="' + table.id + '"]');
      Array.prototype.forEach.call(table.tBodies[0].rows, function(row){
        var show = true;
        selects.forEach(function(s){
          if (s.value && row.getAttribute(s.getAttribute('data-attr')) !== s.value) { show = false; }
        });
        row.style.display = show ? '' : 'none';
      });
    });
  });
})();
"""


def page(title, body):
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main>\n%s\n</main>\n<script>%s</script>\n</body>\n</html>\n"
        % (escape(title), CSS, body, SORT_JS)
    )


def _percent(part, whole):
    if whole <= ZERO:
        return "0.0"
    return format((part * Decimal(100) / whole).quantize(Decimal("0.1")), "f")


def summary_paragraph(result):
    """One paragraph for the billing attorney, built only from the numbers."""
    inv = result.invoice
    counts = result.severity_counts()
    open_findings = result.open_findings
    lines_hit = len({f.line_no for f in open_findings if f.line_no is not None})
    parts = [
        "Draft invoice %s for %s (matter %s) totals %s across %d lines."
        % (inv.invoice_id, result.guideline.client_name, inv.matter_id, fmt_money(inv.line_total), len(inv.lines)),
        "The check ran %d confirmed client rules plus the arithmetic checks." % len(result.rules_run),
    ]
    if not open_findings:
        parts.append("It found no open findings.")
    else:
        parts.append(
            "It found %d open finding%s on %d line%s: %d will likely be rejected, %d likely reduced and %d for review."
            % (
                len(open_findings), "" if len(open_findings) == 1 else "s",
                lines_hit, "" if lines_hit == 1 else "s",
                counts["reject"], counts["reduce"], counts["review"],
            )
        )
        parts.append(
            "The amount at risk is %s, or %s%% of the invoice, counting each line once at its largest single reduction."
            % (fmt_money(result.total_at_risk), _percent(result.total_at_risk, inv.line_total))
        )
        common = Counter(f.rule_label for f in open_findings).most_common(1)[0]
        if common[1] > 1:
            label = common[0] if common[0].startswith("AI") else common[0][0].lower() + common[0][1:]
            parts.append("The most frequent issue is %s (%d findings)." % (label, common[1]))
    if result.waived_findings:
        n = len(result.waived_findings)
        parts.append("%d finding%s covered by a client waiver and not counted." % (n, " is" if n == 1 else "s are"))
    if result.rules_not_enforced:
        n = len(result.rules_not_enforced)
        parts.append("%d proposed rule%s not enforced because %s not confirmed." % (n, " was" if n == 1 else "s were", "it is" if n == 1 else "they are"))
    if result.not_checked:
        n = len(result.not_checked)
        parts.append("%d check%s could not be completed from the file; see the report." % (n, "" if n == 1 else "s"))
    parts.append("Every finding is a prompt for review; nothing on the bill has been changed.")
    return " ".join(parts)


def timekeeper_notes(result):
    """A plain-text note per timekeeper with open findings. Returns {timekeeper_id: text}."""
    inv = result.invoice
    by_tk = defaultdict(list)
    for f in result.open_findings:
        if f.timekeeper_id:
            by_tk[f.timekeeper_id].append(f)
    notes = {}
    for tk in sorted(by_tk):
        items = sorted(by_tk[tk], key=lambda f: (f.line_no if f.line_no is not None else 0, f.rule_id))
        name = next((f.timekeeper_name for f in items if f.timekeeper_name), tk)
        lines_hit = sorted({f.line_no for f in items if f.line_no is not None})
        at_risk = sum((result.entry_at_risk.get(n, ZERO) for n in lines_hit), ZERO)
        out = [
            "To: %s (%s)" % (name, tk),
            "Re: draft invoice %s, %s, matter %s" % (inv.invoice_id, result.guideline.client_name, inv.matter_id),
            "",
            "Before this bill goes out, please look at the %d item%s below. Each one cites the client's own billing rule."
            % (len(items), "" if len(items) == 1 else "s"),
            "Amount at risk on your entries: %s. Please correct entries from your own records; nothing has been changed for you."
            % fmt_money(at_risk),
            "",
        ]
        for f in items:
            where = "Line %d, %s, %s" % (f.line_no, f.entry_date.isoformat(), fmt_money(f.entry_amount)) if f.line_no is not None else "Across your entries"
            out.append("- %s [%s, %s]" % (where, f.rule_label, f.severity_label))
            if f.line_no is not None:
                out.append('  Your entry: "%s" (%s)' % (f.entry_narrative, entry_text(f)))
            out.append("  What the check saw: %s" % f.explanation)
            out.append("  Suggested fix: %s" % f.suggested_fix)
            out.append('  Client rule (%s, %s): "%s"' % (f.rule_id, f.source_ref, f.source_quote))
            if f.note:
                out.append("  Note: %s" % f.note)
            out.append("")
        out.append(NOTICE)
        notes[tk] = "\n".join(out) + "\n"
    return notes


def findings_csv(results):
    if not isinstance(results, (list, tuple)):
        results = [results]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "invoice_id", "line_no", "entry_date", "timekeeper_id", "timekeeper_name", "entry_narrative", "entry_units", "entry_rate", "entry_amount",
            "severity", "status", "rule_id", "rule_type", "amount_at_risk", "explanation",
            "suggested_fix", "source_ref", "source_quote", "note",
        ]
    )
    for result in results:
        for f in result.findings:
            d = f.to_dict()
            writer.writerow(
                [
                    d["invoice_id"], "" if d["line_no"] is None else d["line_no"], d["entry_date"] or "",
                    d["timekeeper_id"], d["timekeeper_name"], d["entry_narrative"], d["entry_units"] or "", d["entry_rate"] or "",
                    d["entry_amount"] or "", d["severity_label"],
                    d["status"], d["rule_id"], d["rule_type"], d["amount_at_risk"], d["explanation"],
                    d["suggested_fix"], d["source_ref"], d["source_quote"], d["note"],
                ]
            )
    return buf.getvalue()


def result_json(result):
    data = result.to_dict()
    data["summary"] = summary_paragraph(result)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def entry_text(f):
    """Plain description of the entry a finding is about, copied from the invoice."""
    if f.line_no is None:
        return ""
    unit = "h" if f.entry_kind == "fee" else "unit(s)"
    return "%s %s x %s = %s" % (fmt_num(f.entry_units), unit, fmt_money(f.entry_rate), fmt_money(f.entry_amount))


def _entry_html(f):
    if f.line_no is None:
        return '<span class="small">whole invoice%s</span>' % (", this timekeeper" if f.timekeeper_id else "")
    return '<span class="nowrap">%s</span><br>%s<br><span class="small">%s</span>' % (
        f.entry_date.isoformat(), escape(f.entry_narrative), escape(entry_text(f))
    )


def _finding_row(f, order, with_invoice=False):
    sev_class = "waived" if f.status == "waived" else f.severity
    sev_text = "waived" if f.status == "waived" else f.severity_label
    sev_sort = 9 if f.status == "waived" else G.SEVERITY_ORDER[f.severity]
    line_text = str(f.line_no) if f.line_no is not None else "invoice"
    who = escape(f.timekeeper_name or f.timekeeper_id or "")
    if f.timekeeper_id and f.timekeeper_name:
        who += '<br><span class="small">%s</span>' % escape(f.timekeeper_id)
    cells = []
    if with_invoice:
        cells.append('<td data-sort="%s">%s</td>' % (escape(f.invoice_id), escape(f.invoice_id)))
    cells += [
        '<td data-sort="%d"><span class="sev sev-%s">%s</span></td>' % (sev_sort, sev_class, escape(sev_text)),
        '<td class="num" data-sort="%s">%s</td>' % (f.line_no if f.line_no is not None else 0, line_text),
        '<td class="wide" data-sort="%s">%s</td>' % (f.entry_date.isoformat() if f.entry_date else "", _entry_html(f)),
        '<td data-sort="%s">%s</td>' % (escape(f.timekeeper_name or f.timekeeper_id or "~"), who),
        '<td data-sort="%s">%s<br><span class="small">%s</span></td>' % (escape(f.rule_label), escape(f.rule_label), escape(f.rule_id)),
        '<td class="wide" data-sort="">%s%s</td>' % (escape(f.explanation), '<br><span class="small">%s</span>' % escape(f.note) if f.note else ""),
        '<td class="wide" data-sort=""><span class="small">%s</span><blockquote>%s</blockquote></td>' % (escape(f.source_ref), escape(f.source_quote)),
        '<td class="wide" data-sort="">%s</td>' % escape(f.suggested_fix),
        '<td class="num" data-sort="%s">%s</td>' % (format(f.amount_at_risk, "f"), fmt_money(f.amount_at_risk)),
    ]
    return '<tr class="%s" data-order="%d" data-invoice="%s" data-severity="%s">%s</tr>' % (
        "waived" if f.status == "waived" else "", order, escape(f.invoice_id), sev_class, "".join(cells)
    )


def _findings_table(findings, table_id, with_invoice=False):
    heads = (["Invoice"] if with_invoice else []) + [
        "Severity", "Line", "Entry", "Timekeeper", "Rule", "What the check saw", "Client guideline", "Suggested fix", "At risk",
    ]
    sortable = {"Invoice", "Severity", "Line", "Entry", "Timekeeper", "Rule", "At risk"}
    head_html = "".join(
        '<th%s>%s</th>' % (' class="num"' if h in ("Line", "At risk") else "", "<button type=\"button\">%s</button>" % h if h in sortable else h)
        for h in heads
    )
    rows = "\n".join(_finding_row(f, i, with_invoice) for i, f in enumerate(findings))
    return '<div class="wrap"><table id="%s" data-sortable><thead><tr>%s</tr></thead><tbody>\n%s\n</tbody></table></div>' % (
        table_id, head_html, rows
    )


def html_report(result):
    inv = result.invoice
    counts = result.severity_counts()
    body = [
        "<h1>Pre-bill review: %s</h1>" % escape(inv.invoice_id),
        '<p class="meta">%s &middot; matter %s &middot; invoice date %s &middot; %d lines &middot; read from %s</p>'
        % (escape(result.guideline.client_name), escape(inv.matter_id), inv.invoice_date.isoformat(), len(inv.lines), escape(inv.source_format)),
        '<p class="notice">%s Findings are prompts for a person. Nothing on the bill has been changed.</p>' % NOTICE,
        "<h2>Summary for the billing attorney</h2>",
        "<p>%s</p>" % escape(summary_paragraph(result)),
        '<div class="cards">',
        '<div class="card"><b>%s</b><span>invoice total (sum of lines)</span></div>' % fmt_money(inv.line_total),
        '<div class="card"><b>%s</b><span>amount at risk</span></div>' % fmt_money(result.total_at_risk),
        '<div class="card"><b>%d</b><span>will likely be rejected</span></div>' % counts["reject"],
        '<div class="card"><b>%d</b><span>likely reduced</span></div>' % counts["reduce"],
        '<div class="card"><b>%d</b><span>for review</span></div>' % counts["review"],
        '<div class="card"><b>%d</b><span>waived by the client</span></div>' % len(result.waived_findings),
        "</div>",
        '<p class="small">%s</p>' % escape(AT_RISK_RULE),
        "<h2>Findings</h2>",
    ]
    if result.findings:
        body.append(
            '<div class="controls"><span>Sort:</span>'
            '<button type="button" data-sort-table="findings" data-col="0">by severity</button>'
            '<button type="button" data-sort-table="findings" data-col="3">by timekeeper</button>'
            '<button type="button" data-sort-table="findings" data-col="1">by line</button>'
            '<button type="button" onclick="window.print()">Print</button></div>'
        )
        body.append(_findings_table(result.findings, "findings"))
    else:
        body.append("<p>No findings.</p>")

    by_tk = defaultdict(lambda: {"count": 0, "lines": set(), "name": ""})
    for f in result.open_findings:
        if not f.timekeeper_id:
            continue
        slot = by_tk[f.timekeeper_id]
        slot["count"] += 1
        slot["name"] = slot["name"] or f.timekeeper_name
        if f.line_no is not None:
            slot["lines"].add(f.line_no)
    if by_tk:
        body.append("<h2>By timekeeper</h2>")
        rows = []
        for tk in sorted(by_tk):
            slot = by_tk[tk]
            risk = sum((result.entry_at_risk.get(n, ZERO) for n in slot["lines"]), ZERO)
            rows.append(
                "<tr><td>%s</td><td>%s</td><td class=\"num\">%d</td><td class=\"num\">%d</td><td class=\"num\">%s</td></tr>"
                % (escape(slot["name"]), escape(tk), slot["count"], len(slot["lines"]), fmt_money(risk))
            )
        body.append(
            '<div class="wrap"><table><thead><tr><th>Timekeeper</th><th>ID</th><th class="num">Open findings</th>'
            '<th class="num">Lines</th><th class="num">At risk</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(rows)
        )
    if result.waived_findings:
        body.append("<h2>Waived by the client</h2><ul>")
        for f in result.waived_findings:
            w = f.waiver
            body.append(
                "<li>Line %s, %s (%s): approved by %s on %s. Reference: %s. Expires %s. Waiver %s.</li>"
                % (
                    f.line_no if f.line_no is not None else "invoice", escape(f.rule_label), escape(f.rule_id),
                    escape(w["approved_by"]), escape(w["approved_on"]), escape(w["reference"]),
                    escape(w["expires_on"]), escape(w["waiver_id"]),
                )
            )
        body.append("</ul>")
    body.append("<h2>What was and was not checked</h2><ul>")
    body.append("<li>Confirmed rules run (%d): %s</li>" % (len(result.rules_run), escape(", ".join(result.rules_run)) or "none"))
    if result.rules_not_enforced:
        body.append(
            "<li>Proposed rules not enforced because no one has confirmed them (%d): %s</li>"
            % (len(result.rules_not_enforced), escape(", ".join(result.rules_not_enforced)))
        )
    for note in result.not_checked:
        body.append("<li>Not checked: %s</li>" % escape(note))
    body.append("</ul>")
    return page("Pre-bill review %s" % inv.invoice_id, "\n".join(body))


# ------------------------------------------------------------- comparison table


def _param_summary(rule):
    p = rule.params
    t = rule.type
    if t == "block_billing":
        return "over %s h" % fmt_num(p["min_hours"]) if G.dec(p["min_hours"]) > ZERO else "any entry"
    if t == "minimum_increment":
        return "%s h" % fmt_num(p["increment"])
    if t == "daily_hour_cap":
        return "%s h a day" % fmt_num(p["max_hours"])
    if t == "staffing_matter_limit":
        return "max %d" % p["max_timekeepers"]
    if t == "staffing_event_limit":
        return "max %d at %s" % (p["max_attendees"], "/".join(p["events"]))
    if t == "rate_increase_notice":
        return "%d days notice" % p["notice_days"]
    if t == "non_billable_task":
        return ", ".join(name.replace("_", " ") for name in p["categories"])
    if t == "internal_conference_limit":
        return "%s h an entry" % fmt_num(p["max_hours_per_entry"])
    if t == "research_approval":
        return "over %s h" % fmt_num(p["max_hours"])
    if t == "travel_time":
        return "approval needed" if p["requires_approval"] else "%s%% of rate" % fmt_num(p["billable_percent"])
    if t == "expense_receipt_threshold":
        return "%s%s" % (fmt_money(p["threshold"]), " or more" if p.get("inclusive", True) else ", over")
    if t == "expense_per_diem":
        return ", ".join("%s %s" % (k, fmt_money(v)) for k, v in p["caps"].items())
    if t == "late_time":
        return "over %d days" % p["max_age_days"]
    if t == "required_codes":
        names = [n for n, key in (("task", "require_task"), ("activity", "require_activity"), ("expense", "require_expense")) if p[key]]
        return ", ".join(names)
    if t == "ai_disclosure_required":
        return "marker %s" % p["disclosure_marker"]
    return ""


def comparison(guides):
    """Return (clients, rows). Each row: (rule_type, label, {client_id: cell text})."""
    guides = sorted(guides, key=lambda g: g.client_name)
    rows = []
    for rule_type, spec in G.RULE_TYPES.items():
        cells = {}
        for g in guides:
            rule = g.rule_of_type(rule_type)
            if rule is None:
                cells[g.client_id] = ""
            else:
                detail = _param_summary(rule)
                state = "yes" if rule.confirmed else "proposed, not enforced"
                cells[g.client_id] = state + (" (%s)" % detail if detail else "")
        rows.append((rule_type, spec["label"], cells))
    return guides, rows


def comparison_csv(guides):
    guides, rows = comparison(guides)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["rule_type", "rule"] + [g.client_name for g in guides])
    for rule_type, label, cells in rows:
        writer.writerow([rule_type, label] + [cells[g.client_id] for g in guides])
    return buf.getvalue()


def comparison_text(guides):
    guides, rows = comparison(guides)
    width = max(len(label) for _, label, _ in rows)
    out = ["Rule".ljust(width) + " | " + " | ".join(g.client_id for g in guides)]
    for _, label, cells in rows:
        out.append(label.ljust(width) + " | " + " | ".join((cells[g.client_id] or "-") for g in guides))
    return "\n".join(out) + "\n"


def comparison_table_html(guides):
    guides, rows = comparison(guides)
    head = "<th>Rule type</th>" + "".join("<th>%s</th>" % escape(g.client_name) for g in guides)
    body = []
    for _, label, cells in rows:
        tds = "".join("<td>%s</td>" % (escape(cells[g.client_id]) or '<span class="small">&ndash;</span>') for g in guides)
        body.append("<tr><td>%s</td>%s</tr>" % (escape(label), tds))
    totals = "".join("<td>%d confirmed, %d proposed</td>" % (len(g.confirmed_rules), len(g.proposed_rules)) for g in guides)
    body.append("<tr><td><b>Rules on file</b></td>%s</tr>" % totals)
    return '<div class="wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, "".join(body))


def comparison_html(guides):
    body = [
        "<h1>Guidelines comparison</h1>",
        '<p class="notice">%s</p>' % NOTICE,
        "<p>Which clients have which rule types. A rule marked proposed is on file but not enforced until a person confirms it.</p>",
        comparison_table_html(guides),
    ]
    return page("Guidelines comparison", "\n".join(body))


# ------------------------------------------------------------- index page


def index_html(results, guides, score=None, intake_rows=None, report_dir="output/reports", heldout=None):
    body = [
        "<h1>Billing-guideline check</h1>",
        '<p class="notice">%s</p>' % NOTICE,
        "<p>Compares a draft bill to that client's billing rules before it goes out. The checks are fixed rules in code. "
        "A person decides every change. This page is a static snapshot built by <code>run_demo.py</code> from the sample data.</p>",
        "<h2>Sample draft invoices</h2>",
    ]
    rows = []
    for r in results:
        inv = r.invoice
        c = r.severity_counts()
        rows.append(
            '<tr><td><a href="%s/%s.html">%s</a></td><td>%s</td><td>%s</td><td class="num">%d</td><td class="num">%s</td>'
            '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num">%s</td></tr>'
            % (
                report_dir, escape(inv.invoice_id), escape(inv.invoice_id), escape(r.guideline.client_name),
                escape(inv.source_format), len(inv.lines), fmt_money(inv.line_total),
                c["reject"], c["reduce"], c["review"], len(r.waived_findings), fmt_money(r.total_at_risk),
            )
        )
    body.append(
        '<div class="wrap"><table><thead><tr><th>Invoice</th><th>Client</th><th>Format</th><th class="num">Lines</th>'
        '<th class="num">Total</th><th class="num">Rejected</th><th class="num">Reduced</th><th class="num">Review</th>'
        '<th class="num">Waived</th><th class="num">At risk</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(rows)
    )
    body.append('<p class="small">%s</p>' % escape(AT_RISK_RULE))

    all_findings = [f for r in results for f in r.findings]
    body.append("<h2>All findings</h2>")
    options = "".join('<option value="%s">%s</option>' % (escape(r.invoice.invoice_id), escape(r.invoice.invoice_id)) for r in results)
    body.append(
        '<div class="controls"><label>Invoice <select data-filter-table="all" data-attr="data-invoice"><option value="">all</option>%s</select></label>'
        '<label>Severity <select data-filter-table="all" data-attr="data-severity"><option value="">all</option>'
        '<option value="reject">will likely be rejected</option><option value="reduce">likely reduced</option>'
        '<option value="review">review</option><option value="waived">waived</option></select></label>'
        '<button type="button" data-sort-table="all" data-col="1">Sort by severity</button>'
        '<button type="button" data-sort-table="all" data-col="4">Sort by timekeeper</button></div>' % options
    )
    body.append(_findings_table(all_findings, "all", with_invoice=True))

    body.append("<h2>Guidelines comparison</h2>")
    body.append("<p>Which clients have which rule types.</p>")
    body.append(comparison_table_html(guides))

    if intake_rows:
        body.append("<h2>Guideline intake</h2>")
        body.append(
            "<p>The intake helper reads each client's plain-text document and proposes rules by pattern. "
            "Every proposal is marked &ldquo;%s&rdquo; and is not enforced until a person confirms it in the JSON.</p>" % escape(G.PROPOSED_CONFIDENCE)
        )
        rows = "".join(
            "<tr><td>%s</td><td class=\"num\">%d</td><td class=\"num\">%d</td><td class=\"num\">%d</td><td class=\"num\">%d</td><td>%s</td></tr>"
            % (escape(r["client_name"]), r["rules_on_file"], r["proposed"], r["matched"], r["extra"], escape(", ".join(r["missed"]) or "none"))
            for r in intake_rows
        )
        body.append(
            '<div class="wrap"><table><thead><tr><th>Client</th><th class="num">Rules on file</th><th class="num">Candidates proposed</th>'
            '<th class="num">Match a rule on file</th><th class="num">Extra candidates</th><th>Rules on file the patterns missed</th></tr></thead>'
            "<tbody>%s</tbody></table></div>" % rows
        )
    if score or heldout:
        body.append("<h2>Accuracy</h2>")
    if heldout:
        body.append(
            "<p>Held-out test sets were written by a separate author who did not read the checking code. "
            "Batch A was used to improve the tool, so only its first run is an unseen result. Batch B was run once, after all changes. "
            "The held-out sets test new invoices and new guideline documents more than new phrase vocabulary, "
            "because their rule files reuse this tool's standard phrase lists.</p>"
        )
        rows = []
        for label, h in heldout:
            a = h["intake"]["summary"]
            cells = ["%d of %d" % (a["proposed_correctly"], a["expected_rules"])]
            for name in ("engine_with_hand_confirmed_rules", "engine_with_intake_proposals_only"):
                e = h[name]
                cells.append("%d of %d" % (e["planted_found"], e["planted_counted"]))
                cells.append("%d of %d" % (e["must_not_flag_lines_flagged"], e["must_not_flag_lines"]))
            rows.append("<tr><td>%s</td>%s</tr>" % (escape(label), "".join('<td class="num">%s</td>' % c for c in cells)))
        body.append(
            '<div class="wrap"><table><thead><tr><th>Run</th><th class="num">Intake: rules proposed correctly</th>'
            '<th class="num">Rules confirmed by hand: planted found</th><th class="num">must-not-flag lines flagged</th>'
            '<th class="num">Intake proposals only: planted found</th><th class="num">must-not-flag lines flagged</th></tr></thead>'
            "<tbody>%s</tbody></table></div>" % "".join(rows)
        )
    if score:
        body.append(
            "<p>In-sample check, on data written by the same author as the checks: the sample invoices contain %d planted violations. "
            "The check found %d of them. "
            "Findings that are not in the answer key: %d. Lines with no planted violation: %d; of those, %d were flagged. "
            "This number says the sample data and the code agree. It does not say how the tool does on bills it has not seen.</p>"
            % (score["planted_total"], score["planted_found"], score["false_positive_count"], score["clean_lines"], len(score["clean_lines_flagged"]))
        )
    body.append(
        '<p class="small">Other outputs are in the <code>output/</code> folder: JSON and CSV per invoice, a summary paragraph, '
        "a note per timekeeper, the comparison table as CSV, and the intake proposals.</p>"
    )
    return page("Billing-guideline check", "\n".join(body))
