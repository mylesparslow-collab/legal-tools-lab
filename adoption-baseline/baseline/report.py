"""Render one self-contained HTML report from a baseline dict.

No scripts, no external files. Charts are inline SVG with a title, a
description and a data table underneath. Colours come from CSS variables so
the page follows the reader's light or dark setting.
"""
import html

from .summary import build_summary, num, pct

W = 360          # chart viewBox width; narrow so text stays readable on a phone
MEASURE_LABELS = {
    "weekly_active_latest": "Active, latest week",
    "weekly_active_last_4_weeks": "Weekly active, last 4 weeks",
    "regular_use": "Regular use",
    "activated": "Any use in period",
}
DROP_LABELS = {
    "blank_row": "Blank row", "missing_user": "No user on the row", "bad_date": "Date could not be read",
    "bad_count": "Count could not be read", "zero_count": "Zero interactions on the row",
    "duplicate": "Exact duplicate of an earlier row", "conflicting_duplicate": "Same key as an earlier row, different counts (first kept)",
    "unknown_user": "User not on the roster", "ambiguous_user": "User matches more than one roster entry",
    "outside_period": "Date outside the period",
}
REPAIR_LABELS = {"identifier_repaired": "Email or name matched after fixing case or spacing",
                 "unmapped_feature": "Feature not in the mapping, counted as \"other\""}
FLAG_LABELS = {"usage_without_licence": "Use by someone without a licence for the tool",
               "usage_before_start_date": "Use dated before the person's start date",
               "usage_after_end_date": "Use dated after the person's end date"}
ROLE_ORDER = ["partner", "counsel", "associate", "paralegal", "staff"]
STATUS_MARK = {"pass": "\u25cf", "not yet": "\u25cb", "cannot tell": "?"}

e = html.escape


def fc(c, unit=""):
    """Format a cell: percentage with numerator and denominator always visible."""
    if c is None:
        return '<span class="mute">n/a</span>'
    if c.get("suppressed"):
        why = "fewer than the minimum group size" if c["suppressed"] == "small_group" else "hidden so a small group cannot be worked out from the total"
        return '<span class="mute" title="%s">not shown</span>' % why
    if c["rate"] is None:
        return '<span class="mute">n/a</span>'
    nd = "%d of %d%s" % (c["n"], c["d"], unit)
    return '<span title="%s">%s</span> <span class="nd">%s</span>' % (nd, pct(c["rate"]), nd)


def table(headers, rows, caption=None):
    out = ['<div class="scroll"><table>']
    if caption:
        out.append("<caption>%s</caption>" % e(caption))
    out.append("<thead><tr>%s</tr></thead><tbody>" % "".join('<th scope="col">%s</th>' % e(h) for h in headers))
    for r in rows:
        out.append("<tr><th scope=\"row\">%s</th>%s</tr>" % (r[0], "".join("<td>%s</td>" % c for c in r[1:])))
    out.append("</tbody></table></div>")
    return "".join(out)


def _bar(x, y, w, h, cls, title):
    r = min(3, h / 2, w)
    if w <= 0:
        return ""
    d = "M%.1f,%.1f h%.1f a%.1f,%.1f 0 0 1 %.1f,%.1f v%.1f a%.1f,%.1f 0 0 1 %.1f,%.1f h%.1f z" % (
        x, y, w - r, r, r, r, r, h - 2 * r, r, r, -r, r, -(w - r))
    return '<path class="%s" d="%s"><title>%s</title></path>' % (cls, d, e(title))


def _svg(height, title, desc, body, ident):
    return ('<svg viewBox="0 0 %d %d" role="img" aria-labelledby="%s-t %s-d" xmlns="http://www.w3.org/2000/svg">'
            '<title id="%s-t">%s</title><desc id="%s-d">%s</desc>%s</svg>'
            % (W, height, ident, ident, ident, e(title), ident, e(desc), body))


def _domain(values):
    top = max([v for v in values if v is not None] + [0.5])
    steps = int(top * 10 + 0.999)
    return min(1.0, max(0.5, steps / 10))


def bar_chart(ident, title, desc, rows, series, target=None, unit=""):
    """Horizontal bars. rows: [(label, [cell per series])]. series: [(css class, legend label)]."""
    rates = [c["rate"] for _, cells in rows for c in cells if c and not c.get("suppressed")]
    dom = _domain(rates + ([target[0]] if target else []))
    x0, span = 4, W - 4 - 110
    sx = lambda rate: span * rate / dom
    body, y = [], 4
    if len(series) > 1:
        lx = x0
        for cls, label in series:
            body.append('<rect class="%s" x="%d" y="%d" width="10" height="10" rx="2"/>'
                        '<text class="t" x="%d" y="%d">%s</text>' % (cls, lx, y, lx + 14, y + 9, e(label)))
            lx += 24 + 6.2 * len(label)
        y += 22
    top = y
    bar_h = 10 if len(series) == 1 else 8
    for label, cells in rows:
        body.append('<text class="t" x="%d" y="%d">%s</text>' % (x0, y + 11, e(label)))
        y += 16
        if all(c is None or c.get("suppressed") for c in cells):
            body.append('<text class="m" x="%d" y="%d">not shown, group too small</text>' % (x0, y + 9))
            y += bar_h + 2
        else:
            for (cls, slabel), c in zip(series, cells):
                if c is None or c.get("suppressed") or c["rate"] is None:
                    body.append('<text class="m" x="%d" y="%d">not shown</text>' % (x0, y + bar_h - 1))
                else:
                    w = max(sx(c["rate"]), 1.5)
                    tip = "%s%s: %s (%d of %d%s)" % (label, ", " + slabel if len(series) > 1 else "",
                                                    pct(c["rate"]), c["n"], c["d"], unit)
                    body.append(_bar(x0, y, w, bar_h, cls, tip))
                    body.append('<text class="t" x="%.1f" y="%d">%s <tspan class="m">%d of %d</tspan></text>'
                                % (x0 + w + 5, y + bar_h - 1, pct(c["rate"]), c["n"], c["d"]))
                y += bar_h + 2
        y += 8
    body.insert(0, '<line class="axis" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x0, top, x0, y - 4))
    if target:
        tx = x0 + sx(target[0])
        body.append('<line class="target" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (tx, top, tx, y - 4))
        body.append('<text class="m" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (tx, y + 8, e(target[1])))
        y += 12
    return _svg(y + 2, title, desc, "".join(body), ident)


def line_chart(ident, title, desc, trend, target=None):
    pts = [w for w in trend if w["rate"] is not None]
    dom = _domain([w["rate"] for w in pts] + ([target[0]] if target else []))
    left, right, top, bottom, H = 34, 30, 14, 28, 210
    pw, ph = W - left - right, H - top - bottom
    n = max(len(trend) - 1, 1)
    X = lambda i: left + pw * i / n
    Y = lambda r: top + ph * (1 - r / dom)
    body = []
    ticks = int(round(dom * 10))
    step = 2 if ticks > 6 else 1
    for k in range(0, ticks + 1, step):
        r = k / 10
        body.append('<line class="grid" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (left, Y(r), W - right, Y(r)))
        body.append('<text class="m" x="%d" y="%.1f" text-anchor="end">%d%%</text>' % (left - 5, Y(r) + 4, k * 10))
    if target:
        body.append('<line class="target" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>' % (left, Y(target[0]), W - right, Y(target[0])))
        body.append('<text class="m" x="%d" y="%.1f">%s</text>' % (left + 4, Y(target[0]) - 4, e(target[1])))
    idx = {w["week"]: i for i, w in enumerate(trend)}
    if pts:
        body.append('<polyline class="line" points="%s"/>' % " ".join("%.1f,%.1f" % (X(idx[w["week"]]), Y(w["rate"])) for w in pts))
        low = min(pts, key=lambda w: w["rate"])
        for w in pts:
            x, y = X(idx[w["week"]]), Y(w["rate"])
            tip = "%s: %s (%d of %d lawyers)" % (w["week"], pct(w["rate"]), w["n"], w["d"])
            body.append('<circle class="dot" cx="%.1f" cy="%.1f" r="3.5"/>' % (x, y))
            body.append('<circle class="hit" cx="%.1f" cy="%.1f" r="11"><title>%s</title></circle>' % (x, y, e(tip)))
        last = pts[-1]
        body.append('<text class="t" x="%.1f" y="%.1f">%s</text>' % (X(idx[last["week"]]) + 6, Y(last["rate"]) + 4, pct(last["rate"])))
        if low is not last:
            body.append('<text class="t" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                        % (X(idx[low["week"]]), Y(low["rate"]) + 16, pct(low["rate"])))
    every = max(1, len(trend) // 4)
    for i, w in enumerate(trend):
        if i % every == 0 or i == len(trend) - 1:
            if i != len(trend) - 1 and len(trend) - 1 - i < every / 2:
                continue
            body.append('<text class="m" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (X(i), H - 8, e(w["week"][5:])))
    return _svg(H, title, desc, "".join(body), ident)


def figure(title, note, svg, table_html):
    return ('<figure><figcaption><strong>%s</strong><br><span class="mute">%s</span></figcaption>%s'
            '<details><summary>Show the numbers</summary>%s</details></figure>' % (e(title), e(note), svg, table_html))


def render_report(b):
    meta = b["meta"]
    summary = build_summary(b)
    thr = meta["suppression_threshold"]
    targets = b["targets"]["targets"]
    target = (targets[0]["threshold"], "month %s target %s" % (targets[0]["due_month"], pct(targets[0]["threshold"]))) if targets else None
    m4 = "weekly_active_last_4_weeks"
    S = []
    S.append('<header><p class="label">%s</p><h1>AI tool adoption baseline</h1>'
             '<p class="mute">Period %s to %s (%d complete weeks, %s to %s). Lawyers are %s. '
             'Groups under %d people are not shown.</p></header>'
             % (e(meta.get("data_label") or ""), meta["period_start"], meta["period_end"], len(meta["weeks"]),
                meta["weeks"][0], meta["weeks"][-1], e(", ".join(meta["lawyer_roles"])), thr))
    S.append('<section aria-labelledby="h-sum"><h2 id="h-sum">Summary</h2><ul class="summary">%s</ul></section>'
             % "".join('<li data-summary="%s">%s</li>' % (s["id"], e(s["text"])) for s in summary))

    rows = []
    for t in b["targets"]["targets"] + b["targets"]["gates"]:
        c = {"n": t["n"], "d": t["d"], "rate": t["rate"], "suppressed": None} if t["rate"] is not None else None
        rows.append([e(t["label"]), pct(t["threshold"]), fc(c, " lawyer-weeks" if t["basis"] == "last_4_weeks" else ""),
                     '<span class="status"><span aria-hidden="true">%s</span> %s</span>' % (STATUS_MARK[t["status"]], e(t["status"])),
                     e(t["reason"])])
    S.append('<section aria-labelledby="h-tar"><h2 id="h-tar">Targets and gates</h2>%s'
             '<p class="mute">Targets are the firm\'s own, read from targets.json. Programme month now: %s. '
             '"Cannot tell" means the data cannot support a yes or no.</p></section>'
             % (table(["Target or gate", "Threshold", "Now", "Status", "Why"], rows), e(str(b["targets"]["programme_month"]))))

    figs = []
    trend = b["weekly_trend"]
    figs.append(figure(
        "Weekly active lawyers", "Share of eligible lawyers with at least one interaction in the ISO week.",
        line_chart("c-trend", "Weekly active lawyers by ISO week",
                   "Line chart of the weekly active rate for lawyers, one point per week. Exact values are in the table below.",
                   trend, target),
        table(["Week", "Active", "Not started", "On leave all week", "Left"],
              [[e(w["week"]), fc(w), str(w["excluded"]["not_started"]), str(w["excluded"]["on_leave"]), str(w["excluded"]["left"])]
               for w in trend], "People on leave all week, not yet started or left are outside that week's denominator.")))
    for dim, label, pop in (("practice", "By practice", "Lawyers"), ("role", "By role", "Everyone on the roster")):
        tb = b["breakdowns"][dim]
        figs.append(figure(
            label, "%s. Weekly active rate over the last %d weeks." % (pop, len(meta["last_weeks"])),
            bar_chart("c-" + dim, "Weekly active rate %s" % label.lower(),
                      "Horizontal bar chart, one bar per %s. Exact values are in the table below." % dim,
                      [(r["group"].capitalize() if dim == "role" else r["group"], [r["cells"][m4]])
                       for r in sorted(tb["rows"], key=lambda r: ROLE_ORDER.index(r["group"]) if dim == "role" and r["group"] in ROLE_ORDER else 0)],
                      [("s1", "Logged")],
                      target if dim == "practice" else None, " person-weeks"),
            breakdown_table(tb, meta)))
    s = b.get("survey")
    if s:
        rows_gap = s["by_practice"]
        figs.append(figure(
            "Survey answers against logs, by practice",
            "Lawyers, week %s. Survey bars describe respondents only. Log bars describe all eligible lawyers." % s["survey_week"],
            bar_chart("c-gap", "Survey-claimed use and logged use by practice",
                      "Paired horizontal bars per practice: share of survey respondents who said they used an approved tool in the last 7 days, and share of lawyers with logged use in the same week.",
                      [(r["group"], [r["claimed"], r["logged"]]) for r in rows_gap],
                      [("s2", "Survey: said they used a tool"), ("s1", "Logged use")]),
            table(["Practice", "Survey: used in last 7 days", "Logged, same week", "Gap (points)"],
                  [[e(r["group"]), fc(r["claimed"]), fc(r["logged"]),
                    '<span class="mute">not shown</span>' if r["gap_points"] is None else "%+.1f" % r["gap_points"]]
                   for r in rows_gap + [s["overall"]]])))
        bl = s["tallies"].get("blockers")
        if bl and bl["answered"]:
            cells = []
            for k, v in bl["counts"].items():
                c = {"n": v, "d": bl["answered"], "rate": v / bl["answered"], "suppressed": None} if v is not None else {"suppressed": "small_group"}
                cells.append((bl["labels"][k], c))
            cells.sort(key=lambda lc: -(lc[1].get("rate") or -1))
            figs.append(figure(
                "What limits use", "Survey, all roles, %d responses. People could pick more than one." % bl["answered"],
                bar_chart("c-block", "Reported limits on use",
                          "Horizontal bar chart of the share of survey responses that selected each limit.",
                          [(lab, [c]) for lab, c in cells], [("s2", "Survey")]),
                table(["Limit", "Responses"], [[e(lab), fc(c)] for lab, c in cells])))
    S.append('<section aria-labelledby="h-ch"><h2 id="h-ch">Charts</h2><div class="grid">%s</div></section>' % "".join(figs))

    S.append('<section aria-labelledby="h-off"><h2 id="h-off">By office</h2>%s</section>' % breakdown_table(b["breakdowns"]["office"], meta))

    rows = []
    for t in b["tools"]:
        c = t["cells"]
        rows.append([e(t["tool"]), "not shown" if t["licensed"] is None else str(t["licensed"]), fc(c["activated"]),
                     fc(c["weekly_active_last_4_weeks"], " person-weeks"), fc(c["regular_use"]), fc(c["unused_licences"]),
                     fc(c["unused_licences_absent_throughout"])])
    S.append('<section aria-labelledby="h-lic"><h2 id="h-lic">Licences</h2>%s<p class="mute">All roles. '
             'Unused means no interaction with that tool in the last %d days of the period.</p></section>'
             % (table(["Tool", "Licensed", "Any use in period", "Weekly active, last 4 weeks", "Regular use",
                       "Unused in last %d days" % meta["unused_licence_days"], "Of the unused: away throughout"], rows),
                meta["unused_licence_days"]))

    rows = []
    for tool, d in b["intensity"]["by_tool"].items():
        br = b["breadth"]["by_tool"][tool]
        if d["suppressed"] or not d["people"]:
            rows.append([e(tool)] + ['<span class="mute">not shown</span>'] * 6)
            continue
        rows.append([e(tool), str(d["people"]), "%s / %s / %s" % (num(d["p25"]), num(d["median"]), num(d["p75"])),
                     num(d["mean"]), pct(d["top_decile_share"]),
                     "%s / %s / %s" % (num(br["p25"]), num(br["median"]), num(br["p75"])) if br.get("median") is not None else "n/a",
                     fc(br.get("two_or_more_features"))])
    S.append('<section aria-labelledby="h-int"><h2 id="h-int">How much and how broadly</h2>%s<p class="mute">'
             'People on the roster at period end with at least one interaction in the last %d weeks, all roles. The rows for a named '
             'tool count only people who hold that tool\'s licence; the "any approved tool" row counts everyone, including use without a '
             'licence, so it can cover people who are in neither tool row. The mean is shown next to the median because a few heavy '
             'users pull it up.</p></section>'
             % (table(["Tool", "Active people", "Interactions: lower quartile / median / upper quartile", "Mean",
                       "Share of interactions from top tenth", "Features used: lower quartile / median / upper quartile",
                       "Used 2 or more features"], rows), b["intensity"]["window_weeks"]))

    S.append(quality_panel(b))
    S.append(DEFINITIONS % {"thr": thr, "min": meta["regular_use"]["min_active_weeks"], "win": meta["regular_use"]["window_weeks"],
                            "days": meta["unused_licence_days"], "ver": e(b["definitions_version"])})
    return PAGE % {"body": "\n".join(S)}


def breakdown_table(tb, meta):
    cols = ["weekly_active_latest", "weekly_active_last_4_weeks", "regular_use", "activated"] + [
        "weekly_active_last_4_weeks:" + t for t in meta["tools"]]
    heads = [tb["dimension"].capitalize()] + [MEASURE_LABELS.get(c) or "%s, licensed, last 4 weeks" % c.split(":")[1] for c in cols]
    unit = lambda c: " person-weeks" if "last_4_weeks" in c else ""
    rows = [[e(r["group"])] + [fc(r["cells"][c], unit(c)) for c in cols] for r in tb["rows"] + [tb["total"]]]
    return table(heads, rows)


def quality_panel(b):
    dq = b["data_quality"]
    ing, ro = dq["ingestion"], dq["roster"]
    parts = ['<section aria-labelledby="h-dq"><h2 id="h-dq">Data quality</h2>'
             '<p>Every export row is accounted for: rows read equals rows kept plus rows dropped. Nothing is discarded without a count.</p>']
    heads = ["Check"] + [q["source"] for q in ing["sources"]]
    rows = [["Rows read"] + [str(q["rows_read"]) for q in ing["sources"]],
            ["Rows kept"] + [str(q["rows_kept"]) for q in ing["sources"]],
            ["Rows dropped"] + [str(q["rows_dropped"]) for q in ing["sources"]]]
    for k, label in DROP_LABELS.items():
        if any(q["dropped"].get(k) for q in ing["sources"]):
            rows.append(["Dropped: " + e(label)] + [str(q["dropped"].get(k, 0)) for q in ing["sources"]])
    for k, label in REPAIR_LABELS.items():
        if any(q["repaired"].get(k) for q in ing["sources"]):
            rows.append(["Repaired and kept: " + e(label)] + [str(q["repaired"].get(k, 0)) for q in ing["sources"]])
    for k, label in FLAG_LABELS.items():
        if any(q["flagged_but_kept"].get(k) for q in ing["sources"]):
            rows.append(["Flagged and kept: " + e(label)] + [str(q["flagged_but_kept"].get(k, 0)) for q in ing["sources"]])
    rows.append(["Distinct users not on the roster"] + [str(q["unknown_user_distinct_identifiers"]) for q in ing["sources"]])
    rows.append(["Dates kept"] + ["%s to %s" % (q["first_date_kept"], q["last_date_kept"]) if q["first_date_kept"] else "none" for q in ing["sources"]])
    parts.append(table(heads, rows))
    ex = ro["person_weeks_excluded"]
    items = [
        "%d people on the roster; %d on it at period end." % (ro["people_on_roster"], ro["people_on_roster_at_period_end"]),
        "%d roster people have no usage in the period. They count as zero, not as missing." % ro["people_with_no_usage_counted_as_zero"],
        "%d of %d person-weeks are outside the denominators: %d not yet started, %d on leave all week, %d after leaving."
        % (sum(ex.values()), ro["person_weeks_total"], ex["not_started"], ex["on_leave"], ex["left"]),
        "%d person-weeks have usage logged during a week of full leave. They are left out of that week's numerator and denominator."
        % ro["person_weeks_with_usage_during_full_leave"],
        "%d people changed practice during the period. Each week counts under the practice in effect that week." % ro["people_who_changed_practice"],
        "%d roster rows could not be read and were skipped." % ro["roster_file"]["rows_skipped_invalid"],
    ]
    if ing["tools_with_no_rows"]:
        items.append("No usage rows at all for: %s. Rates will be understated." % e(", ".join(ing["tools_with_no_rows"])))
    s = b.get("survey")
    if s:
        q = s["quality"]
        items.append("Survey: %d responses read, %d used, %d answers removed as not on the option list, %d responses missing a required answer, %d free-text comments (not reproduced)."
                     % (q["responses_read"], q["responses_used"], q["invalid_answers_removed"], q["responses_missing_required"], s["free_text_comments"]))
    elif dq.get("survey_note"):
        items.append(e(dq["survey_note"]))
    parts.append("<ul>%s</ul></section>" % "".join("<li>%s</li>" % i for i in items))
    return "".join(parts)


DEFINITIONS = """<footer aria-labelledby="h-def"><h2 id="h-def">Definitions</h2>
<dl>
<dt>Weekly active</dt><dd>At least one logged interaction with an approved tool in an ISO week (Monday to Sunday). The denominator is the roster, less people on leave for every weekday of that week, not yet started, or left. "Last 4 weeks" pools those weeks, so the unit is person-weeks.</dd>
<dt>Regular use</dt><dd>Active in at least %(min)d of the last %(win)d weeks, among people eligible in at least %(min)d of them.</dd>
<dt>Any use in period</dt><dd>At least one interaction in the whole period, among people on the roster at period end.</dd>
<dt>Per-tool and any-tool figures</dt><dd>Every figure for a named tool (any use, weekly active, regular use, unused licences, interactions, features) counts only people who hold that tool's licence. Figures for "any approved tool" count everyone in the population, so use by someone without a licence appears there and under data quality, and in no per-tool figure.</dd>
<dt>Interactions and features</dt><dd>Per person over the last %(win)d weeks, among people of any role on the roster at period end who had at least one interaction in those weeks.</dd>
<dt>Unused licence</dt><dd>A licence held at period end with no interaction with that tool in the last %(days)d days.</dd>
<dt>Survey gap</dt><dd>Share of survey respondents in a group who said they used an approved tool in the last 7 days, minus the logged weekly active rate for that group in the same week. Groups are compared; people are not matched.</dd>
<dt>Not shown</dt><dd>Any figure describing fewer than %(thr)d people is withheld, and so is one further figure where a total would otherwise reveal it. This is a privacy choice. This report has no individual-level output.</dd>
</dl>
<p class="mute">Full definitions are in METRICS.md (version %(ver)s). Targets are the firm's own inputs. No comparison with other organisations is made. Personal portfolio demo; not legal advice.</p>
</footer>"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI tool adoption baseline</title>
<style>
:root { color-scheme: light dark; --bg: #ffffff; --text: #191919; --muted: #666666; --grid: #e3e3e3; --axis: #8a8a8a; --s1: #257de0; --s2: #f47230; }
@media (prefers-color-scheme: dark) { :root { --bg: #191919; --text: #efefef; --muted: #9c9c9c; --grid: #383838; --axis: #7a7a7a; --s1: #338ced; --s2: #e76624; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.page { max-width: 64rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }
h1 { font-size: 1.6rem; line-height: 1.2; margin: .2rem 0 .4rem; }
h2 { font-size: 1.15rem; margin: 2rem 0 .6rem; padding-top: .8rem; border-top: 1px solid var(--grid); }
.label { margin: 0; font-size: .8rem; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.mute, .nd { color: var(--muted); }
.nd { font-size: .85em; white-space: nowrap; }
.summary { padding-left: 1.1rem; margin: 0; max-width: 46rem; }
.summary li { margin: .35rem 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%%, 300px), 1fr)); gap: 1.5rem 2rem; }
figure { margin: 0; min-width: 0; }
figcaption { margin-bottom: .4rem; font-size: .95rem; }
svg { display: block; width: 100%%; max-width: 460px; height: auto; }
svg text { font: 11.5px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.t { fill: var(--text); } .m { fill: var(--muted); }
.s1 { fill: var(--s1); } .s2 { fill: var(--s2); }
path.s1:hover, path.s2:hover { opacity: .75; }
.axis { stroke: var(--axis); stroke-width: 1; } .grid line, line.grid { stroke: var(--grid); stroke-width: 1; }
.target { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 4 3; }
.line { fill: none; stroke: var(--s1); stroke-width: 2; stroke-linejoin: round; }
.dot { fill: var(--s1); stroke: var(--bg); stroke-width: 2; } .hit { fill: transparent; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; font-size: .9rem; margin: .4rem 0; min-width: 100%%; }
caption { text-align: left; color: var(--muted); padding-bottom: .3rem; }
th, td { text-align: left; padding: .35rem .7rem .35rem 0; border-bottom: 1px solid var(--grid); vertical-align: top; }
thead th { font-weight: 600; color: var(--muted); font-size: .82rem; }
tbody th { font-weight: 500; min-width: 8.5rem; }
td { font-variant-numeric: tabular-nums; }
.status { white-space: nowrap; font-weight: 600; }
details { margin-top: .4rem; } summary { cursor: pointer; color: var(--muted); font-size: .9rem; }
:focus-visible { outline: 2px solid var(--s1); outline-offset: 2px; }
dl { margin: 0; max-width: 46rem; } dt { font-weight: 600; margin-top: .6rem; } dd { margin: 0; }
footer { font-size: .92rem; }
@media print { details > *:not(summary) { display: block; } }
</style>
</head>
<body>
<div class="page">
%(body)s
</div>
</body>
</html>
"""
