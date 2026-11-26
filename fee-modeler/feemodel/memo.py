"""Self-contained HTML outputs: the pricing memo, the refusal memo and the modelability page.

No scripts, no external files. Charts are inline SVG. Pixel positions are the only floats in
the project: Decimal amounts are converted to float here, at the drawing boundary, and never
flow back into any figure.
"""

from decimal import Decimal
from html import escape

from .money import D, display_hours, display_money, display_pct
from .schema import PHASES, PHASE_LABELS

CSS = """
:root{color-scheme:light;--bg:#f6f6f4;--surface:#ffffff;--text:#191919;--muted:#5f5f5f;--line:#dcdcd8;
--grid:#e9e9e5;--series:#257de0;--series-soft:#b6d5f8;--fee:#f47230;--warn-bg:#fff6e0;--warn-line:#d28e05;
--stop-bg:#fdecec;--stop-line:#c93a3b;--note-bg:#eef4fc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#121212;--surface:#191919;
--text:#efefef;--muted:#a3a3a3;--line:#3a3a3a;--grid:#2a2a2a;--series:#338ced;--series-soft:#1757ac;--fee:#e76624;
--warn-bg:#2e2610;--warn-line:#d28e05;--stop-bg:#331616;--stop-line:#eb6263;--note-bg:#15202e}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#121212;--surface:#191919;--text:#efefef;--muted:#a3a3a3;
--line:#3a3a3a;--grid:#2a2a2a;--series:#338ced;--series-soft:#1757ac;--fee:#e76624;--warn-bg:#2e2610;
--warn-line:#d28e05;--stop-bg:#331616;--stop-line:#eb6263;--note-bg:#15202e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 56px}
h1{font-size:1.5rem;line-height:1.25;margin:0 0 4px}
h2{font-size:1.05rem;margin:28px 0 8px}
h3{font-size:.95rem;margin:16px 0 6px}
p{margin:6px 0}
.meta,.small{color:var(--muted);font-size:.87rem}
.banner{border:1px solid var(--line);background:var(--note-bg);border-radius:8px;padding:8px 12px;margin:12px 0;font-size:.87rem}
.warn{border-left:4px solid var(--warn-line);background:var(--warn-bg);border-radius:4px;padding:8px 12px;margin:8px 0}
.stop{border-left:4px solid var(--stop-line);background:var(--stop-bg);border-radius:4px;padding:10px 12px;margin:12px 0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:12px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:12px 0}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.tile .k{color:var(--muted);font-size:.8rem}
.tile .v{font-size:1.45rem;font-weight:650;font-variant-numeric:tabular-nums}
.tile .s{color:var(--muted);font-size:.8rem}
.tile .v.range{font-size:1.1rem;line-height:2.1rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.87rem}
.scroll table{min-width:660px}
th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.num,td.nw,span.nw{white-space:nowrap}td.wide{min-width:260px}td.oos{min-width:230px;font-size:.82rem}
tr.vr td{font-size:.84rem;padding:2px 8px 12px;color:var(--muted)}tr.vr strong{color:var(--text)}
.stop h3,.warn h3,.card h3{margin-top:0}
ul{margin:6px 0;padding-left:20px}
li{margin:4px 0}
svg{display:block;width:100%;height:auto}
svg text{fill:var(--text);font:12px system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
svg .mut{fill:var(--muted)}
.tag{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:0 8px;font-size:.78rem;color:var(--muted)}
.assume{border:1px dashed var(--warn-line);border-radius:8px;padding:10px 14px;margin:12px 0}
.appendix{margin-top:36px}
a{color:var(--series)}
@media print{:root{--bg:#fff;--surface:#fff;--text:#000;--muted:#444;--line:#bbb;--grid:#ddd;--series:#257de0;
--series-soft:#b6d5f8;--fee:#f47230;--warn-bg:#fff;--stop-bg:#fff;--note-bg:#fff}
body{font-size:11px}main{max-width:none;padding:0}.card,.tile{break-inside:avoid}.appendix{break-before:page}
h2{margin-top:14px}.scroll{overflow:visible}}
"""


def e(value):
    return escape("" if value is None else str(value))


def page(title, body):
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main>\n%s\n</main>\n</body>\n</html>\n"
            % (e(title), CSS, body))


def frac(c):
    """'31 of 42 (74%)' from a {count, n} pair: the share always travels with its n."""
    if not c or not c.get("n"):
        return "n/a"
    return "%d of %d (%s)" % (c["count"], c["n"], display_pct(c["count"], c["n"]))


def _nice_step(span, target=6):
    span = D(span)
    if span <= 0:
        return Decimal(1)
    raw = span / target
    mag = Decimal(10) ** (raw.adjusted())
    for m in (1, 2, 5, 10):
        if raw <= mag * m:
            return mag * m
    return mag * 10


def _axis_label(v):
    v = D(v)
    if v >= 1000:
        k = (v / 1000).quantize(Decimal("0.1")).normalize()
        return "$%sk" % format(k, "f")
    return "$%s" % format(v.quantize(Decimal("1")), "f")


def distribution_chart(result):
    """Dot plot of comp normalized values with the planning figures and the proposed fees marked."""
    comps = result["selection"]["comps"]
    q = result["planning"]["bands"]
    values = [(c["normalized_value_after_assumptions"], c["matter_id"]) for c in comps]
    fees = []
    for s in result.get("scenarios", []):
        amount = s["params"].get("fee") or s["params"].get("cap")
        if amount is not None and all(a != amount for a, _ in fees):
            name = {"fixed": "Fixed fee", "capped": "Cap", "collar": "Collar fee"}.get(s["type"], "Fee")
            fees.append((amount, name))
    fees = fees[:3]
    top = max([v for v, _ in values] + [a for a, _ in fees] + [q["p90"]])
    step = _nice_step(top)
    xmax = (top / step).to_integral_value(rounding="ROUND_CEILING") * step
    if xmax <= top:
        xmax += step
    W, L, R = 760, 14, 14
    pw = W - L - R
    nb = 44
    bins = {}
    for v, mid in sorted(values):
        b = min(nb - 1, int(float(v) / float(xmax) * nb))
        bins.setdefault(b, []).append((v, mid))
    tallest = max(len(v) for v in bins.values())
    r = 5.0
    plot_h = max(70.0, tallest * (2 * r + 1) + 8)
    top_pad = 40
    H = top_pad + plot_h + 24 + 16 * max(1, len(fees)) + 6
    base = top_pad + plot_h

    def x(v):
        return L + float(v) / float(xmax) * pw

    n = len(values)
    desc = ("Each dot is one comparable matter, placed by its cost at today's standard rates. n=%d. "
            "Planning figures: P25 %s, P50 %s, P75 %s, P90 %s." % (n, display_money(q["p25"]), display_money(q["p50"]),
                                                  display_money(q["p75"]), display_money(q["p90"])))
    for amount, name in fees:
        desc += " %s %s." % (name, display_money(amount))
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-labelledby="dist-t dist-d">' % (W, H),
           '<title id="dist-t">Distribution of comp costs with the planning figures and the proposed fee marked</title>',
           '<desc id="dist-d">%s</desc>' % e(desc)]
    t = Decimal(0)
    while t <= xmax:
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--grid)" stroke-width="1"/>'
                   % (x(t), top_pad, x(t), base))
        anchor = "start" if t == 0 else "end" if t == xmax else "middle"
        out.append('<text class="mut" x="%.1f" y="%.1f" text-anchor="%s">%s</text>' % (x(t), base + 15, anchor, _axis_label(t)))
        t += step
    out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--line)" stroke-width="1"/>' % (L, base, W - R, base))
    for row, key in enumerate(("p25", "p50", "p75", "p90")):
        px = x(q[key])
        ly = 12 if row % 2 == 0 else 26
        anchor = "end" if px > W - 110 else "start"
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--muted)" stroke-width="1" stroke-dasharray="3 3"/>'
                   % (px, ly + 3, px, base))
        out.append('<text x="%.1f" y="%d" text-anchor="%s">%s %s</text>'
                   % (px + (-4 if anchor == "end" else 4), ly, anchor, key.upper(), display_money(q[key])))
    for b, items in sorted(bins.items()):
        cx = L + (b + 0.5) / nb * pw
        for i, (v, mid) in enumerate(items):
            cy = base - r - 2 - i * (2 * r + 1)
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="var(--series)" stroke="var(--surface)" stroke-width="1">'
                       '<title>%s: %s</title></circle>' % (cx, cy, r, e(mid), display_money(v)))
    for i, (amount, name) in enumerate(fees):
        px = x(amount)
        ly = base + 34 + 16 * i
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--fee)" stroke-width="2"/>'
                   % (px, top_pad - 4, px, base + 3))
        anchor = "end" if px > W - 170 else "start"
        tx = px - 9 if anchor == "end" else px + 9
        out.append('<rect x="%.1f" y="%.1f" width="8" height="8" rx="2" fill="var(--fee)"/>' % (px - 4, ly - 9))
        out.append('<text x="%.1f" y="%.1f" text-anchor="%s">%s %s</text>' % (tx, ly, anchor, e(name), display_money(amount)))
    out.append("</svg>")
    return "\n".join(out)


def phase_chart(result):
    """Median cost per phase with the P25 to P75 range, among comps where the phase occurred."""
    bp = result["distribution"]["by_phase"]
    rows = [(p, bp[p]) for p in PHASES if bp[p]["n_occurred"] > 0]
    top = max(d["value"]["quantiles"]["p75"] for _p, d in rows)
    W, L, R = 760, 170, 150
    pw = W - L - R
    rh = 32
    H = len(rows) * rh + 8
    parts = []
    for p, d in rows:
        qq = d["value"]["quantiles"]
        parts.append("%s median %s, P25 %s to P75 %s, n=%d" % (PHASE_LABELS[p], display_money(qq["p50"]),
                                                              display_money(qq["p25"]), display_money(qq["p75"]),
                                                              d["n_occurred"]))
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-labelledby="ph-t ph-d">' % (W, H),
           '<title id="ph-t">Cost by phase across the comps</title>',
           '<desc id="ph-d">%s.</desc>' % e("; ".join(parts))]

    def x(v):
        return L + float(v) / float(top) * pw

    for i, (p, d) in enumerate(rows):
        qq = d["value"]["quantiles"]
        y = 4 + i * rh
        out.append('<text x="%d" y="%d" text-anchor="end">%s</text>' % (L - 10, y + 17, e(PHASE_LABELS[p])))
        out.append('<path d="M%d %d h%.1f a4 4 0 0 1 4 4 v10 a4 4 0 0 1 -4 4 h-%.1f z" fill="var(--series)" opacity=".75">'
                   '<title>%s: median %s (n=%d)</title></path>'
                   % (L, y + 5, max(0.0, x(qq["p50"]) - L - 4), max(0.0, x(qq["p50"]) - L - 4), e(PHASE_LABELS[p]),
                      display_money(qq["p50"]), d["n_occurred"]))
        out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--text)" stroke-width="2"/>'
                   % (x(qq["p25"]), y + 14, x(qq["p75"]), y + 14))
        for k in ("p25", "p75"):
            out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--text)" stroke-width="2"/>'
                       % (x(qq[k]), y + 9, x(qq[k]), y + 19))
        out.append('<text x="%.1f" y="%d">%s <tspan class="mut">n=%d</tspan></text>'
                   % (x(qq["p75"]) + 8, y + 18, display_money(qq["p50"]), d["n_occurred"]))
    out.append("</svg>")
    return "\n".join(out)


def _rules_block(result):
    sel = result["selection"]
    out = ["<h2>How the comps were chosen</h2>", '<div class="card"><ul>']
    out += ["<li>%s</li>" % e(line) for line in sel["rules"]]
    out.append("</ul>")
    out.append('<p class="small">%d matters of this type on file; %d selected as comps.</p>' % (sel["type_total"], sel["n"]))
    if sel["exclusion_counts"]:
        out.append('<p class="small">Left out: %s.</p>' % e("; ".join(
            "%s (%d)" % (k, v) for k, v in sorted(sel["exclusion_counts"].items(), key=lambda kv: -kv[1]))))
    out.append('<p class="small">Rules are set in the proposal file under selection_rules and can be changed.</p></div>')
    return "\n".join(out)


def _comps_table(result):
    comps = result["selection"]["comps"]
    if not comps:
        return "<p>No comps.</p>"
    head = ("<tr><th>Matter</th><th>Closed</th><th>Forum</th><th class=num>Parties</th><th>Band</th>"
            "<th class=num>Units</th><th>Hearing</th><th class=num>Hours</th><th class=num>Worked, raw</th>"
            "<th class=num>Billed</th><th class=num>Collected</th><th class=num>Normalized</th>"
            "<th>Phase source</th><th>Flags</th></tr>")
    rows = []
    for c in comps:
        rows.append(
            "<tr><td class=nw>%s</td><td class=nw>%s</td><td>%s</td><td class=num>%s</td><td>%s</td><td class=num>%s</td><td>%s</td>"
            "<td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
            "<td>%s</td><td>%s</td></tr>"
            % (e(c["matter_id"]), e(c["close_date"]), e(c["forum"]), e(c["num_parties"]), e(c["amount_band"]),
               e(c["num_units"]), "yes" if c["hearing_occurred"] else "no", display_hours(c["hours"]),
               display_money(c["raw_worked"]), display_money(c["raw_billed"]), display_money(c["collected"]),
               display_money(c["normalized_value"]),
               "task codes" if c["phase_confidence"] == "task_code" else "date windows (low confidence)",
               e("; ".join(c["flags"]))))
    return '<div class="scroll"><table>%s%s</table></div>' % (head, "".join(rows))


def _header(result, kind):
    p = result["proposal"]
    return "\n".join([
        "<h1>%s</h1>" % e(p.get("title") or p.get("proposal_id") or "Pricing memo"),
        '<p class="meta">%s · proposal %s · matter type %s · as of %s</p>'
        % (kind, e(p.get("proposal_id")), e(p["matter_type"]), e(p["as_of"])),
        '<div class="banner">%s Synthetic data only: every client, matter, timekeeper and rate here is invented.</div>'
        % e(result["disclaimer"]),
    ])


def _backtest_card(result):
    """The matter type's own walk-forward result, shown beside the figures it qualifies."""
    b = result["backtest"]
    cls = "stop" if b["status"] == "understated" else "warn" if not b["usable"] else "card"
    out = ['<div class="%s"><h3>Out-of-sample check: how the planning bands have held up for this matter type</h3>' % cls,
           "<p><strong>%s</strong></p>" % e(b["headline"])]
    if b["statements"]:
        out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % e(t) for t in b["statements"]))
        mid = b["inside_p25_p75"]
        out.append('<p class="small">Inside planning P25 to P75: %s of back-tested matters; the band implies 50%%.</p>' % frac(mid))
    if b.get("descriptive_statements"):
        out.append('<p class="small">For comparison, the plain comp quantiles in the same test: %s</p>'
                   % e(" ".join(b["descriptive_statements"])))
    out.append('<p class="small">%s</p></div>' % e(b["scope"]))
    return "\n".join(out)


def _planning_block(result):
    """Planning figures beside the descriptive comp quantiles, and how the first were made."""
    pl = result["planning"]
    nz = result["distribution"]["normalized"]
    q, iv = nz["quantiles"], nz["intervals"]
    rows = []
    for b in ("p25", "p50", "p75", "p90"):
        f = pl["factor"][b]
        rows.append("<tr><td>%s</td><td class=num><strong>%s</strong></td><td class=num>%s</td><td class=num>%s</td>"
                    "<td class=num>%s</td><td class=num>%s to %s</td></tr>"
                    % (b.upper(), display_money(pl["bands"][b]), display_money(pl["base"][b]),
                       ("x%s" % f.quantize(Decimal("0.01"))) if pl["calibrated"] else "not adjusted",
                       display_money(q[b]), display_money(iv[b][0]), display_money(iv[b][1])))
    return ('<div class="card scroll"><h3>Planning figures and comp quantiles (n=%d)</h3>'
            '<table><tr><th>Band</th><th class=num>Planning figure</th><th class=num>Step 1: comp at position ceil((n+1) x q)</th>'
            '<th class=num>Step 2: adjustment from past outcomes</th><th class=num>Of the comps (descriptive)</th>'
            '<th class=num>90%% interval on the descriptive figure</th></tr>%s</table>'
            '<p class="small"><strong>Planning figures are the ones to price from.</strong> They are built to hold up on the next '
            'matter: a quantile position that allows for the small sample, then raised (never lowered) by how far earlier '
            'matters of this type ran over their own bands. %s</p>'
            '<p class="small">Of the comps (descriptive): the interpolated quantile of the %d comps. It describes these comps; '
            'in the back-test it understated overruns. Its interval is a bootstrap interval (%d resamples, seed %d) showing how '
            'much the figure would move with a different draw of %d matters; it is not a forecast range.</p></div>'
            % (pl["n"], "".join(rows), e(" ".join(pl["notes"])), pl["n"], nz["n_boot"], nz["seed"], pl["n"]))


def _drift_block(result):
    """Both versions, side by side, when the change check flagged this matter type."""
    d = result.get("drift") or {}
    if not d.get("flagged") or not d.get("versions"):
        return ""
    rows = []
    for v in d["versions"]:
        rows.append("<tr><td>%s%s</td><td class=num>%d</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                    "<td class=num>%s</td><td class=num>%s</td></tr>"
                    % (e(v["label"]), " <strong>(used in this memo)</strong>" if v["used"] else "", v["n"],
                       display_money(v["planning"]["p50"]), display_money(v["planning"]["p75"]),
                       display_money(v["planning"]["p90"]), display_money(v["descriptive"]["p50"]),
                       display_money(v["descriptive"]["p75"])))
    if d["action"] == "higher_of_two":
        plan = result["planning"]["bands"]
        rows.append("<tr><td><strong>Used in this memo: the higher of the two at each band</strong></td><td class=num>%d</td>"
                    "<td class=num><strong>%s</strong></td><td class=num><strong>%s</strong></td><td class=num><strong>%s</strong></td>"
                    "<td class=num></td><td class=num></td></tr>"
                    % (d["n_all"], display_money(plan["p50"]), display_money(plan["p75"]), display_money(plan["p90"])))
    if d["action"] == "recent_only":
        foot = ("This proposal sets drift_action to recent_only: a person has chosen the recent comps only. Remove the "
                "setting to go back to the default, which takes the higher of the two versions.")
    elif d["action"] == "ignored_by_proposal":
        foot = ("This proposal sets drift_action to ignore, so the whole history is used. Remove the setting to go back "
                "to the default, which takes the higher of the two versions.")
    elif d["direction"] == "fallen":
        foot = ("Default rule: a flag can raise a planning figure but never lower it. Costs appear to have fallen, so the "
                "bands were not lowered. If the practice group confirms a real change, set drift_action to recent_only "
                "in the proposal to use the recent comps only. Set it to ignore to drop the check.")
    else:
        foot = ("Default rule: a flag can raise a planning figure but never lower it. Set drift_action to recent_only to "
                "use the recent comps only once the change is confirmed, or to ignore to drop the check.")
    return ('<div class="%s"><h3>Change check: costs for this matter type appear to have %s</h3><p>The %d matters opened from %s '
            'cost <strong>%sx</strong> the %d opened before, at the same rates. The date was estimated from the data, not '
            'supplied; %d of %d seeded reshuffles of the same costs looked as lopsided. This check is a prompt to look: it '
            'also flags types where nothing changed.</p>'
            '<div class="scroll"><table><tr><th>Version</th><th class=num>Comps (n)</th><th class=num>Planning P50</th>'
            '<th class=num>Planning P75</th><th class=num>Planning P90</th><th class=num>Comp P50 (descriptive)</th>'
            '<th class=num>Comp P75 (descriptive)</th></tr>%s</table></div>'
            '<p class="small">%s</p></div>'
            % ("stop" if d["direction"] == "risen" else "warn", d["direction"], d["n_after"], e(d["change_date"]),
               e(d["after_over_before"]), d["n_before"], d["shuffles_as_extreme"], d["n_shuffles"], "".join(rows), foot))


def render_refusal(result):
    sel = result["selection"]
    body = [_header(result, "Not modeled"),
            '<div class="stop"><strong>No fee figures are shown.</strong> %s</div>' % e(result["refusal"].replace("Not modeled: ", "", 1)),
            "<h2>What would be needed</h2>", '<div class="card"><ul>',
            "<li>At least %d comparable closed matters. %d found.</li>" % (sel["min_comps"], sel["n"])]
    for rule, gain in sorted(sel["relax_hints"].items(), key=lambda kv: -kv[1]):
        body.append("<li>Relaxing the rule &ldquo;%s&rdquo; on its own would add %d.</li>" % (e(rule), gain))
    body.append("<li>Lowering the minimum is possible but not advised: below it, a quantile is one or two matters.</li>")
    body.append("</ul></div>")
    if (result.get("drift") or {}).get("action") == "recent_only":
        d = result["drift"]
        body.append('<div class="warn">Costs for this matter type appear to have changed around %s: matters opened since cost %sx the earlier '
                    'ones. %d of the %d selected comps opened since then, and the proposal asks for those only.</div>'
                    % (e(d["change_date"]), e(d["after_over_before"]), d["n_used"], d["n_all"]))
    body.append(_backtest_card(result))
    body.append(_rules_block(result))
    body.append("<h2>Matters found (n=%d)</h2>" % sel["n"])
    body.append(_comps_table(result))
    return page("Not modeled: %s" % (result["proposal"].get("title") or ""), "\n".join(body))


def render_memo(result):
    """One-page pricing memo, with the comp list as an appendix."""
    if result["status"] == "refused":
        return render_refusal(result)
    dist = result["distribution"]
    nz = dist["normalized"]
    q, iv, n = nz["quantiles"], nz["intervals"], dist["n"]
    body = [_header(result, "Pricing memo")]

    pl = result["planning"]
    plan = pl["bands"]
    tag = "Planning" if pl["calibrated"] else "Planning (not adjusted)"
    tiles = []
    for key, name in (("p50", "P50"), ("p75", "P75"), ("p90", "P90")):
        tiles.append('<div class="tile"><div class="k">%s %s at %s rates</div><div class="v">%s</div>'
                     '<div class="s">of the comps: %s (descriptive) · n=%d</div></div>'
                     % (tag, name, e(result["inputs"]["rate_card_label"]), display_money(plan[key]), display_money(q[key]), n))
    tiles.append('<div class="tile"><div class="k">%s middle half (P25 to P75)</div><div class="v range">%s &ndash; %s</div>'
                 '<div class="s">median hours of the comps %s · n=%d</div></div>'
                 % (tag, display_money(plan["p25"]), display_money(plan["p75"]),
                    display_hours(dist["hours"]["quantiles"]["p50"]), n))
    body.append('<div class="tiles">%s</div>' % "".join(tiles))
    body.append('<p class="small">%s Planning figures are the ones to price from; the smaller figure under each is the plain '
                'quantile of the comps, which describes them and no more.</p>' % e(dist["basis"]))
    for w in result["warnings"]:
        body.append('<div class="warn">%s</div>' % e(w))
    body.append(_drift_block(result))
    body.append(_planning_block(result))
    body.append(_backtest_card(result))

    body.append("<h2>Comp distribution, planning figures and proposed fee (n=%d)</h2>" % n)
    body.append('<div class="card">%s<p class="small">One dot per comp. Dashed lines are the planning figures, which can sit '
                'beyond the comps. Hover a dot for the matter. The same data is in the appendix table.</p></div>'
                % distribution_chart(result))

    if result["scenarios"]:
        body.append("<h2>Pricing scenarios against the comps (n=%d)</h2>" % n)
        rows = []
        for s in result["scenarios"]:
            margin_pct = ("%s%%" % s["margin_pct_of_revenue"]) if s["margin_pct_of_revenue"] is not None else "n/a"
            ap = s.get("at_planning")
            at = (" / ".join(display_money(ap[b]["margin"]) for b in ("p50", "p75", "p90"))) if ap else "n/a"
            rows.append("<tr><td>%s</td><td class=oos>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                        "<td class=num>%s</td><td class=num>%s<div class=small>%s of revenue</div></td></tr>"
                        % (e(s["label"]), e(s["out_of_sample"]["text"]), at, frac(s["under_fee"]), frac(s["no_loss"]),
                           display_money(s["expected_revenue"]),
                           display_money(s["expected_margin"]), margin_pct))
        body.append('<div class="card scroll"><table><tr><th>Scenario</th>'
                    '<th>Against the planning figures, and how those held up out of sample</th>'
                    '<th class=num>Margin if the matter comes in at planning P50 / P75 / P90</th>'
                    '<th class=num>In sample: comps at or under the fee</th>'
                    '<th class=num>In sample: comps with no loss on cost</th><th class=num>In sample: mean revenue</th>'
                    '<th class=num>In sample: mean margin</th></tr>%s</table>'
                    '<p class="small">Read the planning columns first. They place the fee among the planning figures and give the '
                    'walk-forward back-test for this matter type at the bands either side: each past matter judged against '
                    'bands set only from what was known the day it opened. The in-sample columns count the same comps the '
                    'figures were built from, so they flatter the fee.</p>'
                    '<p class="small">Margin at a planning figure: revenue under the scenario if the work came to that figure at '
                    'standard rates, less cost taken as %s%% of that figure (the comps\' total cost over their total standard '
                    'value). A phased fee has no single figure to compare and is judged in sample only. Cost uses the cost '
                    'rates in the input file: %s</p><ul class="small">%s</ul></div>'
                    % ("".join(rows), (result["planning"]["cost_share_of_value"] * 100).quantize(Decimal("0.1")),
                       e(result["inputs"]["cost_rates_note"]),
                       "".join("<li>%s: %s</li>" % (e(s["label"]), e(" ".join(s["notes"]))) for s in result["scenarios"])))
        for s in result["scenarios"]:
            if s["type"] == "phased":
                prow = "".join(
                    "<tr><td>%s</td><td class=num>%s</td><td class=num>%d of %d</td><td class=num>%s</td><td class=num>%s</td>"
                    "<td class=num>%s</td></tr>" % (e(PHASE_LABELS[b["phase"]]), display_money(b["fee"]), b["n_occurred"],
                                                    b["n"], display_money(b["median_value"]), frac(b["under_fee"]),
                                                    frac(b["no_loss"])) for b in s["by_phase"])
                body.append('<div class="card scroll"><h3>Phased fee, phase by phase</h3><table><tr><th>Phase</th>'
                            '<th class=num>Fee</th><th class=num>Comps where it occurred</th><th class=num>Median cost when it occurred</th>'
                            '<th class=num>At or under the phase fee</th><th class=num>No loss on cost</th></tr>%s</table></div>' % prow)
            if s["type"] == "collar":
                body.append('<p class="small">Collar: %s inside the band, %s above it, %s below it.</p>'
                            % (frac(s["inside_band"]), frac(s["above_band"]), frac(s["below_band"])))
    t = result.get("target")
    if t:
        pct = (t["target_probability"] * 100).quantize(Decimal("1"))
        how = ("the comp at position ceil((n+1) x %s) (%s), raised x%s from %d past outcomes of this type"
               % (t["target_probability"], display_money(t["planning_base"]), t["planning_factor"].quantize(Decimal("0.01")),
                  t["planning_n_scores"])) if t["planning_calibrated"] else (
               "the comp at position ceil((n+1) x %s), not adjusted (%d past outcomes of this type, %d needed)"
               % (t["target_probability"], t["planning_n_scores"], result["planning"]["min_history"]))
        if t.get("planning_from_recent_only"):
            how += "; taken from the recent-only version because it is higher"
        if t["planning_floored_at_band"]:
            how += "; that came out below a planning band for a lower target, so the band is used instead"
        if not t["planning_reachable"]:
            how += "; with n=%d that position is past the largest comp, so the largest comp is used and the figure is a floor" % t["n"]
        body.append('<div class="card"><h3>Fee for a target chance of staying within the fee</h3>'
                    '<p>Target %s%%. Planning figure: a fixed fee of <strong>%s</strong> to cover the work at standard rates; '
                    '<strong>%s</strong> to cover cost at the input cost rates.</p>'
                    '<p class="small">How it was made: %s. The cost figure is the first one times the comps\' cost share of '
                    'standard value.</p>'
                    '<p class="small">In sample, for comparison: %s would have covered the standard-rate value on %s comps and %s '
                    'would have covered cost on %s comps (observed comp amounts, n=%d). Past shares are not probabilities for '
                    'the next matter. Out of sample: %s</p></div>'
                    % (pct, display_money(t["planning_fee_covering_standard_value"]),
                       display_money(t["planning_fee_no_loss_on_cost"]), e(how),
                       display_money(t["fee_covering_standard_value"]), frac(t["under_fee"]),
                       display_money(t["fee_no_loss_on_cost"]), frac(t["no_loss"]), t["n"],
                       e(" ".join(result["backtest"]["statements"]) if result["backtest"]["usable"]
                         else result["backtest"]["headline"])))

    body.append("<h2>Cost by phase and by level (n=%d)</h2>" % n)
    body.append('<div class="card">%s<p class="small">Bar: median. Line: P25 to P75. Each phase uses only the comps where '
                'that phase occurred, so n differs by phase.</p>' % phase_chart(result))
    prow = []
    for p in PHASES:
        d = dist["by_phase"][p]
        if not d["n_occurred"]:
            continue
        qq = d["value"]["quantiles"]
        prow.append("<tr><td>%s</td><td class=num>%d of %d</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                    "<td class=num>%s</td><td class=num>%s</td></tr>"
                    % (e(PHASE_LABELS[p]), d["n_occurred"], d["n"], display_hours(d["median_hours"]), display_money(qq["p25"]),
                       display_money(qq["p50"]), display_money(qq["p75"]), display_money(qq["p90"])))
    body.append('<div class="scroll"><table><tr><th>Phase</th><th class=num>Comps where it occurred</th><th class=num>Median hours</th>'
                '<th class=num>P25</th><th class=num>P50</th><th class=num>P75</th><th class=num>P90</th></tr>%s</table></div>' % "".join(prow))
    lrow = "".join("<tr><td>%s</td><td class=num>%s</td><td class=num>%s%%</td><td class=num>%s</td><td class=num>%s</td></tr>"
                   % (e(lv["level"].replace("_", " ")), display_hours(lv["median_hours"]), lv["share_of_hours_pct"],
                      display_money(lv["standard_rate"]), display_money(lv["cost_rate"])) for lv in dist["by_level"])
    body.append('<h3>By timekeeper level</h3><div class="scroll"><table><tr><th>Level</th><th class=num>Median hours per comp</th><th class=num>Share of all comp hours</th>'
                '<th class=num>Standard rate</th><th class=num>Cost rate (input)</th></tr>%s</table></div></div>' % lrow)

    w = result["worked_billed_collected"]
    tot = w["totals"]
    body.append("<h2>Worked, billed and collected (n=%d)</h2>" % w["n"])
    body.append('<div class="card scroll"><table><tr><th>Across all comps</th><th class=num>Total</th><th class=num>Share of worked, raw</th></tr>'
                + "".join("<tr><td>%s</td><td class=num>%s</td><td class=num>%s</td></tr>" % (name, display_money(tot[k]),
                          display_pct(tot[k], tot["raw_worked"]))
                          for name, k in (("Worked value at the rates of the time (raw)", "raw_worked"),
                                          ("Billed after write-downs", "raw_billed"), ("Invoiced", "invoiced"),
                                          ("Collected", "collected")))
                + "<tr><td>Same hours at %s rates (normalized)</td><td class=num>%s</td><td class=num>%s</td></tr></table>"
                % (e(result["inputs"]["rate_card_label"]), display_money(tot["normalized_value_before_assumptions"]),
                   display_pct(tot["normalized_value_before_assumptions"], tot["raw_worked"]))
                + '<p class="small">Median comp: raw worked %s, normalized %s. Figures above use worked hours, because billed and '
                  'collected amounts hide write-downs and write-offs.</p></div>'
                % (display_money(dist["raw_worked"]["quantiles"]["p50"]),
                   display_money(stats_median_before(result))))

    ai = result["ai"]
    body.append("<h2>Hours-reduction assumptions</h2>")
    arow = "".join("<tr><td>%s</td><td class=num>%s%%</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td></tr>"
                   % (e(PHASE_LABELS[r["phase"]]), r["reduction_pct"].quantize(Decimal("1")), display_hours(r["median_hours_before"]),
                      display_hours(r["median_hours_after"]), display_money(r["median_value_before"]),
                      display_money(r["median_value_after"])) for r in ai["rows"])
    tt = ai["total"]
    body.append('<div class="assume"><p><span class="tag">user assumption</span> %s %s</p>'
                '<div class="scroll"><table><tr><th>Phase</th><th class=num>Assumed reduction</th><th class=num>Median hours before</th>'
                '<th class=num>after</th><th class=num>Median cost before</th><th class=num>after</th></tr>%s'
                '<tr><td><strong>Whole matter</strong></td><td></td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>'
                '<td class=num>%s</td></tr></table></div><p class="small">Medians across all %d comps, counting zero where a phase did not occur.</p></div>'
                % (e(ai["label"]), "Reductions below were typed into the proposal file and are applied to every figure in this memo."
                   if ai["any_applied"] else "None were entered, so before and after are the same.", arow,
                   display_hours(tt["median_hours_before"]), display_hours(tt["median_hours_after"]),
                   display_money(tt["median_value_before"]), display_money(tt["median_value_after"]), ai["n"]))

    body.append("<h2>Scope assumptions and exclusions from the comp evidence</h2>")
    if result["assumptions"]:
        body.append('<div class="card"><ul>%s</ul></div>' % "".join("<li>%s</li>" % e(a["text"]) for a in result["assumptions"]))
    else:
        body.append('<div class="card"><p>Nothing in the comps stood out. That is not the same as no scope risk.</p></div>')
    body.append(_rules_block(result))
    body.append('<p class="small">Inputs: mapping &ldquo;%s&rdquo;; rate card %s; cost rates from the input file. '
                'A person decides the price. Run the back-test before relying on any band.</p>'
                % (e(result["inputs"]["mapping"]), e(result["inputs"]["rate_card_label"])))
    body.append('<div class="appendix"><h2>Appendix: the %d comps</h2>%s</div>' % (n, _comps_table(result)))
    return page("Pricing memo: %s" % (result["proposal"].get("title") or ""), "\n".join(body))


def stats_median_before(result):
    from . import stats
    return stats.quantile([c["normalized_value"] for c in result["selection"]["comps"]], Decimal("0.50"))


def over_cell(o):
    """Overruns as 'count of n (pct)' against what the band implies."""
    if not o["n"]:
        return "n/a"
    return "%d of %d (%s)" % (o["count"], o["n"], display_pct(o["count"], o["n"]))


def backtest_table(summary):
    """Overruns above P75 and P90 by matter type: planning bands, and the descriptive quantiles for comparison."""
    rows = []
    items = list(summary["by_type"]) + [{
        "matter_type": "All types", "overruns": summary["overall_overruns"], "n_tested": summary["n_tested"],
        "descriptive": summary["overall_descriptive"], "verdict": summary["overall_verdict"],
        "verdict_headline": summary["overall_headline"], "drift_flag": False, "drift": {}}]
    for r in items:
        d = r["descriptive"]
        rows.append("<tr><td>%s</td><td class=num>%d</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>"
                    "<td class=num>%s</td><td>%s</td></tr>%s"
                    % (("<strong>%s</strong>" if r["matter_type"] == "All types" else "%s") % e(r["matter_type"]), r["n_tested"],
                       over_cell(r["overruns"]["p75"]), over_cell(r["overruns"]["p90"]),
                       over_cell(d["overruns"]["p75"]), over_cell(d["overruns"]["p90"]),
                       ("<span class=nw>from %s</span>, %sx" % (e(r["drift"]["change_date"]), e(r["drift"]["after_over_before"])))
                       if r["drift_flag"] else "no",
                       verdict_row(r["verdict_headline"], r["verdict"], 7)))
    return ('<div class="card scroll"><table><tr><th>Matter type</th><th class=num>Tested (n)</th>'
            '<th class=num>Planning: cost more than P75 (implied 25%%)</th><th class=num>Planning: cost more than P90 (implied 10%%)</th>'
            '<th class=num>Comp quantiles: more than P75</th><th class=num>Comp quantiles: more than P90</th>'
            '<th>Costs changed</th></tr>%s</table></div>' % "".join(rows))


def verdict_row(headline, full, colspan):
    """A back-test verdict on its own full-width row, so the counts are never squeezed or clipped."""
    rest = full[len(headline):].strip() if full.startswith(headline) else full
    return ('<tr class="vr"><td colspan="%d"><strong>%s</strong> %s</td></tr>' % (colspan, e(headline), e(rest)))


def render_modelability(table, summary):
    """Matter-type modelability table plus back-test coverage."""
    body = ["<h1>Which matter types can be modeled</h1>",
            '<p class="meta">Matter-type modelability and walk-forward back-test · minimum %d comps</p>' % table["min_comps"],
            '<div class="banner">Personal portfolio demo on synthetic data. Not financial, pricing or legal advice.</div>',
            "<h2>Modelability</h2>"]
    rows = []
    for r in table["rows"]:
        rows.append("<tr><td>%s</td><td><strong>%s</strong><div class=small>%s</div></td><td class=num>%d</td><td class=num>%d</td>"
                    "<td class=num>%d</td><td class=num>%s</td><td class=num>%d</td></tr>"
                    % (e(r["matter_type"]), e(r["verdict"]), e(" ".join(r["notes"])), r["n_clean_closed"], r["n_abnormal"],
                       r["n_open"], ("%s%%" % r["task_coded_hours_pct"]) if r["task_coded_hours_pct"] is not None else "n/a",
                       r["n_backtested"]))
    body.append('<div class="card scroll"><table><tr><th>Matter type</th><th>Verdict</th><th class=num>Clean closed</th>'
                '<th class=num>Closed abnormally</th><th class=num>Open</th><th class=num>Hours with a usable task code</th>'
                '<th class=num>Back-tested</th></tr>%s</table></div>' % "".join(rows))
    body.append("<h2>Back-test by matter type: planning bands, with the plain comp quantiles beside them</h2>")
    body.append('<p class="small">%s</p><p class="small">%s</p>' % (e(summary["method"]), e(summary["bands_note"])))
    body.append(backtest_table(summary))
    body.append('<p class="small">%s</p><p class="small">%s</p>' % (e(summary["overrun_rule"]), e(summary["drift_rule"])))
    return page("Matter-type modelability", "\n".join(body))
