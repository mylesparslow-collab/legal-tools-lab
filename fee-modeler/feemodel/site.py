"""The static demo page (index.html). Built by run_demo.py from the same results as the memos.

The fee explorer recomputes shares in the browser from integer cents. The Python outputs are
the figures of record; the explorer is a way to see how the shares move with the fee.
"""

import json
from decimal import Decimal, ROUND_HALF_UP

from .memo import CSS, backtest_table, e, frac, page
from .money import display_money

EXTRA_CSS = """
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.ctrl{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:8px 0}
select,input[type=range]{font:inherit}
input[type=range]{flex:1;min-width:200px;accent-color:var(--fee)}
select{padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--text)}
code,pre{font:13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow-x:auto}
.big{font-size:1.3rem;font-weight:650;font-variant-numeric:tabular-nums}
"""

SCRIPT = """
(function(){
var DATA = JSON.parse(document.getElementById('explorer-data').textContent);
var sel = document.getElementById('ex-proposal'), slider = document.getElementById('ex-fee');
var svgNS = 'http://www.w3.org/2000/svg';
function money(cents){ var d = Math.round(cents/100); var step = Math.abs(d) >= 10000 ? 100 : 10;
  d = Math.round(d/step)*step; return (d<0?'-':'') + '$' + Math.abs(d).toLocaleString('en-US'); }
function el(name, attrs, text){ var n = document.createElementNS(svgNS, name);
  for (var k in attrs) n.setAttribute(k, attrs[k]); if (text != null) n.textContent = text; return n; }
function current(){ return DATA[sel.selectedIndex]; }
function setup(){ var p = current(); slider.min = 0; slider.max = p.max; slider.step = p.step; slider.value = p.start; draw(); }
function draw(){
  var p = current(), fee = Number(slider.value), n = p.comps.length, under = 0, noLoss = 0, margin = 0;
  p.comps.forEach(function(c){ if (c.v <= fee) under++; if (c.c <= fee) noLoss++; margin += fee - c.c; });
  document.getElementById('ex-fee-out').textContent = money(fee);
  document.getElementById('ex-under').textContent = under + ' of ' + n + ' (' + Math.round(under*100/n) + '%)';
  document.getElementById('ex-noloss').textContent = noLoss + ' of ' + n + ' (' + Math.round(noLoss*100/n) + '%)';
  document.getElementById('ex-margin').textContent = money(Math.round(margin/n));
  document.getElementById('ex-n').textContent = 'n=' + n + ' comps';
  var oos = document.getElementById('ex-oos'), note = document.getElementById('ex-oos-note');
  if (!p.bands.length){ oos.textContent = 'none'; note.textContent = p.oos_none; }
  else { var best = p.bands[0]; p.bands.forEach(function(b){ if (Math.abs(b.v-fee) < Math.abs(best.v-fee)) best = b; });
    oos.textContent = best.count + ' of ' + best.n + ' (' + Math.round(best.count*100/best.n) + '%)';
    note.textContent = 'back-tested matters at or under their planning ' + best.name + ' (' + money(best.v) + ' here); the band implies ' + best.nominal + '%'; }
  var svg = document.getElementById('ex-chart'); while (svg.firstChild) svg.removeChild(svg.firstChild);
  var W = 760, L = 14, R = 14, pw = W-L-R, nb = 44, r = 5, bins = {}, tallest = 1;
  p.comps.slice().sort(function(a,b){return a.v-b.v;}).forEach(function(c){
    var b = Math.min(nb-1, Math.floor(c.v / p.max * nb)); (bins[b] = bins[b] || []).push(c);
    tallest = Math.max(tallest, bins[b].length); });
  var plotH = Math.max(70, tallest*(2*r+1)+8), top = 14, base = top+plotH, H = base+44;
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  svg.appendChild(el('title', {}, 'Comp costs with the chosen fixed fee marked'));
  svg.appendChild(el('desc', {}, under + ' of ' + n + ' comps are at or under a fee of ' + money(fee) + '.'));
  for (var t = 0; t <= 4; t++){ var x = L + pw*t/4;
    svg.appendChild(el('line', {x1:x, y1:top, x2:x, y2:base, stroke:'var(--grid)', 'stroke-width':1}));
    svg.appendChild(el('text', {x:x, y:base+15, 'text-anchor': t==0?'start':t==4?'end':'middle', 'class':'mut'}, money(p.max*t/4))); }
  svg.appendChild(el('line', {x1:L, y1:base, x2:W-R, y2:base, stroke:'var(--line)', 'stroke-width':1}));
  Object.keys(bins).forEach(function(b){ var cx = L + (Number(b)+0.5)/nb*pw;
    bins[b].forEach(function(c, i){ var dot = el('circle', {cx:cx, cy:base-r-2-i*(2*r+1), r:r,
      fill: c.v <= fee ? 'var(--series)' : 'var(--series-soft)', stroke:'var(--surface)', 'stroke-width':1});
      dot.appendChild(el('title', {}, c.id + ': ' + money(c.v) + (c.v <= fee ? ' (at or under the fee)' : ' (over the fee)')));
      svg.appendChild(dot); }); });
  var fx = L + fee/p.max*pw;
  svg.appendChild(el('line', {x1:fx, y1:top-6, x2:fx, y2:base+3, stroke:'var(--fee)', 'stroke-width':2}));
  svg.appendChild(el('rect', {x:fx-4, y:base+24, width:8, height:8, rx:2, fill:'var(--fee)'}));
  var end = fx > W-170;
  svg.appendChild(el('text', {x: end ? fx-9 : fx+9, y:base+33, 'text-anchor': end?'end':'start'}, 'Fixed fee ' + money(fee)));
}
sel.addEventListener('change', setup); slider.addEventListener('input', draw); setup();
})();
"""


def _cents(d):
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def explorer_data(results):
    out = []
    for r in results:
        if r["status"] != "modeled":
            continue
        comps = [{"id": c["matter_id"], "v": _cents(c["normalized_value_after_assumptions"]), "c": _cents(c["internal_cost"])}
                 for c in r["selection"]["comps"]]
        q = r["planning"]["bands"]
        top_cents = max([c["v"] for c in comps] + [_cents(q["p90"])])
        quarter = Decimal(top_cents) / 400                       # dollars per axis tick, four ticks
        mag = Decimal(10) ** quarter.adjusted()
        tick = next(mag * Decimal(m) for m in ("1", "1.5", "2", "2.5", "3", "4", "5", "7.5", "10") if mag * Decimal(m) > quarter)
        top = int(tick * 4 * 100)
        step_dollars = 1000 if top >= 10000000 else 500
        fixed = [s for s in r["scenarios"] if s["type"] == "fixed"]
        start = _cents(fixed[0]["params"]["fee"]) if fixed else _cents(q["p75"])
        b = r["backtest"]
        out.append({"id": r["proposal"]["proposal_id"], "title": r["proposal"]["title"], "comps": comps, "max": top,
                    "step": step_dollars * 100, "start": start,
                    "bands": [{"name": k.upper(), "v": _cents(q[k]), "nominal": nominal,
                               "count": b["under_band"][k]["count"], "n": b["under_band"][k]["n"]}
                              for k, nominal in (("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))] if b["usable"] else [],
                    "oos_none": "" if b["usable"] else b["headline"]})
    return out


def render_index(results, summary, table):
    body = ["<h1>Fee modeler</h1>",
            '<p class="meta">Evidence for fixed and capped fees from past matters of the same type</p>',
            '<div class="banner">Personal portfolio demo. All data is synthetic: every client, matter, timekeeper and rate is '
            'invented. Not financial, pricing or legal advice. Never run on real matter data from this page. '
            'The tool shows evidence and risk; a person decides the price.</div>',
            "<p>For a proposed matter, the tool picks comparable closed matters, values their hours at today's rates, "
            "shows the spread of what they cost, and tests fee structures against that spread. It refuses to give a figure "
            "when there are too few comps, and the back-test below says how well its bands have held up.</p>"]

    body.append("<h2>1. Does it work on this data? Walk-forward back-test</h2>")
    body.append('<p class="small">%s</p><p class="small">%s</p>' % (e(summary["method"]), e(summary["bands_note"])))
    body.append(backtest_table(summary))
    body.append('<p class="small">%s</p><p class="small">%s</p>'
                '<p class="small">More overruns than a band implies is the direction that loses money on a fixed or capped fee, '
                'so it is the one judged. The planning bands are the fix for the shortfall the plain comp quantiles show in '
                'the right-hand columns; they are wider as a result. Measured on other generated firms: '
                '<a href="output/calibration_study.txt">calibration study</a>, '
                '<a href="output/drift_sensitivity.txt">drift study</a>.</p>'
                % (e(summary["overrun_rule"]), e(summary["drift_rule"])))

    body.append("<h2>2. Which matter types have enough clean history</h2>")
    rows = []
    for r in table["rows"]:
        rows.append("<tr><td>%s</td><td><strong>%s</strong><div class=small>%s</div></td><td class=num>%d</td><td class=num>%d</td>"
                    "<td class=num>%d</td><td class=num>%s</td></tr>"
                    % (e(r["matter_type"]), e(r["verdict"]), e(" ".join(r["notes"])), r["n_clean_closed"], r["n_abnormal"],
                       r["n_open"], ("%s%%" % r["task_coded_hours_pct"]) if r["task_coded_hours_pct"] is not None else "n/a"))
    body.append('<div class="card scroll"><table><tr><th>Matter type</th><th>Verdict</th><th class=num>Clean closed</th>'
                '<th class=num>Closed abnormally</th><th class=num>Open</th><th class=num>Hours with a usable task code</th></tr>%s</table>'
                '<p class="small"><a href="output/modelability.html">Full table with back-test detail</a></p></div>' % "".join(rows))

    body.append("<h2>3. Pricing memos for seven proposed matters</h2>")
    cards = []
    for r in results:
        p = r["proposal"]
        link = "output/memo_%s.html" % p["proposal_id"]
        if r["status"] == "modeled":
            q = r["planning"]["bands"]
            dq = r["distribution"]["normalized"]["quantiles"]
            detail = ('<div class="big">%s</div><div class="small">planning P50 at today\'s rates%s · planning P25 %s to P75 %s · '
                      'P90 %s · n=%d comps</div><div class="small">Of the comps (descriptive): P50 %s, P75 %s.</div>'
                      % (display_money(q["p50"]), "" if r["planning"]["calibrated"] else " (not adjusted)",
                         display_money(q["p25"]), display_money(q["p75"]), display_money(q["p90"]), r["distribution"]["n"],
                         display_money(dq["p50"]), display_money(dq["p75"])))
            if r["drift"]["flagged"]:
                d = r["drift"]
                how = {"higher_of_two": "Each planning figure is the higher of the recent-only and whole-history versions.",
                       "recent_only": "Proposal asks for the %d recent comps only." % d["n_used"],
                       "ignored_by_proposal": "Change check switched off in this proposal."}[d["action"]]
                detail += ('<div class="small"><strong>Change check: costs appear to have %s from %s (%sx).</strong> %s</div>'
                           % (d["direction"], e(d["change_date"]), e(d["after_over_before"]), how))
            detail += '<div class="small">Out of sample for this type: %s</div>' % e(
                " ".join(r["backtest"]["statements"]) if r["backtest"]["usable"] else r["backtest"]["headline"])
            if r["warnings"]:
                detail += '<div class="small">%d warning%s in the memo.</div>' % (len(r["warnings"]), "" if len(r["warnings"]) == 1 else "s")
        else:
            detail = ('<div class="big">Not modeled</div><div class="small">%d comps found, %d required. No figure is shown.</div>'
                      % (r["selection"]["n"], r["selection"]["min_comps"]))
            if r["drift"]["action"] == "recent_only":
                detail += ('<div class="small">Recent comps only were asked for (from %s).</div>' % e(r["drift"]["change_date"]))
        cards.append('<div class="tile"><div class="k">%s · %s</div><p><a href="%s">%s</a></p>%s</div>'
                     % (e(p["proposal_id"]), e(p["matter_type"]), e(link), e(p["title"]), detail))
    body.append('<div class="grid">%s</div>' % "".join(cards))

    data = explorer_data(results)
    body.append("<h2>4. Try a fixed fee against the comps</h2>")
    body.append(
        '<div class="card"><div class="ctrl"><label for="ex-proposal">Proposal</label><select id="ex-proposal">%s</select>'
        '<span class="small" id="ex-n"></span></div>'
        '<div class="ctrl"><label for="ex-fee">Fixed fee</label><input type="range" id="ex-fee"><span class="big" id="ex-fee-out"></span></div>'
        '<div class="tiles"><div class="tile"><div class="k">In sample: comps at or under the fee</div><div class="v" id="ex-under"></div>'
        '<div class="s">counted on the comps the figures were built from</div></div>'
        '<div class="tile"><div class="k">Out of sample: walk-forward at the nearest planning figure</div><div class="v" id="ex-oos"></div>'
        '<div class="s" id="ex-oos-note"></div></div>'
        '<div class="tile"><div class="k">Comps with no loss on cost</div><div class="v" id="ex-noloss"></div>'
        '<div class="s">against the placeholder cost rates</div></div>'
        '<div class="tile"><div class="k">Mean margin across comps</div><div class="v" id="ex-margin"></div>'
        '<div class="s">fee minus cost at placeholder cost rates</div></div></div>'
        '<svg id="ex-chart" role="img" aria-live="polite"></svg>'
        '<p class="small">One dot per comp, placed by cost at today\'s standard rates; lighter dots are over the fee. Hover a dot for the matter. '
        'The explorer recomputes in your browser from the comp amounts in whole cents. The memos are the figures of record.</p></div>'
        % "".join("<option>%s: %s</option>" % (e(d["id"]), e(d["title"])) for d in data))

    body.append("<h2>5. Run it</h2>")
    body.append("<pre>python run_demo.py                 # regenerate data, outputs and this page\n"
                "python -m feemodel profile data/export_b --mapping data/mappings/export_b.json\n"
                "python -m feemodel backtest\n"
                "python -m feemodel comps --proposal data/proposals/P-001.json\n"
                "python -m feemodel price --proposal data/proposals/P-001.json\n"
                "python -m feemodel calibration-study   # planning bands on 20 other generated firms\n"
                "python -m feemodel drift-sensitivity   # what the change check catches, old rule beside new\n"
                "python -m pytest -q</pre>")
    body.append('<p class="small">To try it on real data later, read SWAP_IN_REAL_DATA.md first. The order is: profile, then back-test, then price.</p>')
    html = page("Fee modeler demo", "\n".join(body))
    html = html.replace("</style>", EXTRA_CSS + "</style>", 1)
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("</main>", '</main>\n<script type="application/json" id="explorer-data">%s</script>\n<script>%s</script>'
                        % (payload, SCRIPT), 1)
    return html
