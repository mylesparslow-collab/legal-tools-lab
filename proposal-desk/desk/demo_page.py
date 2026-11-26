"""Static demo page for one RFP. Self-contained: inline CSS and a few lines of inline script."""
from . import render
from .facts import BLOCKING
from .rfp import DEADLINE_LABELS
from .util import esc, fmt_date

EXTRA_CSS = """
main{max-width:1080px}nav{font-family:system-ui,Arial,sans-serif;font-size:.85em;margin:10px 0 18px;display:flex;flex-wrap:wrap;gap:6px 14px}
nav a{color:var(--blue)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:12px 0}
.card{border:1px solid var(--line);padding:10px 12px;font-family:system-ui,Arial,sans-serif}
.card .k{font-size:.75em;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.card .v{font-size:1.5em;margin:2px 0}.card .d{font-size:.8em;color:var(--mute)}
.card.red{border-color:var(--red)}.card.red .v{color:var(--red)}
.filters{font-family:system-ui,Arial,sans-serif;font-size:.82em;margin:8px 0}
.filters button{font:inherit;padding:3px 9px;margin:0 4px 4px 0;border:1px solid var(--line);background:#fff;cursor:pointer;border-radius:3px}
.filters button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}
.scroll{overflow-x:auto}.changed{background:var(--amberbg)}del{color:var(--mute)}
section{margin-bottom:28px}h2{font-size:1.25em}h3{font-size:1.02em;margin:1.3em 0 .3em}
.draft{border:1px solid var(--line);padding:6px 18px 14px;background:#fff}
"""

SCRIPT = """
(function(){
  var rows=document.querySelectorAll('#matrix tbody tr'), btns=document.querySelectorAll('.filters button');
  function apply(f){rows.forEach(function(r){r.style.display=(f==='all'||r.getAttribute('data-status')===f||
    (f==='open'&&r.getAttribute('data-open')==='1'))?'':'none';});
    btns.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-f')===f?'true':'false');});
    var n=0;rows.forEach(function(r){if(r.style.display!=='none')n++;});
    document.getElementById('count').textContent=n+' of '+rows.length+' rows shown';}
  btns.forEach(function(b){b.addEventListener('click',function(){apply(b.getAttribute('data-f'));});});
  apply('all');
})();
"""


def _card(k, v, d="", red=False):
    return '<div class="card%s"><div class="k">%s</div><div class="v">%s</div><div class="d">%s</div></div>' % (
        " red" if red else "", esc(k), esc(v), esc(d))


def demo_html(res, parser_eval=None, rfp_file=""):
    g, rfp = res["go_no_go"], res["rfp"]
    d, c, mq, pg = g["deadline"], g["coverage"], g["min_quals"], g["page"]
    b = ['<h1>Proposal desk: %s</h1>' % esc(g["agency"]),
         '<p class="meta">%s%s. Prepared as of %s. Source file: %s</p>' % (
             esc(rfp["meta"]["title"]), esc((" (RFP %s)" % g["rfp_number"]) if g["rfp_number"] else ""),
             esc(g["as_of"]), esc(rfp_file)),
         '<div class="banner">Personal portfolio demo. Every agency, person, matter and past proposal on this page is '
         'invented. Not legal advice. Do not run this tool on real proposals. Drafting here is retrieval and assembly '
         'of previously approved text; no model writes anything.</div>',
         '<nav><a href="#go">Go / no-go</a><a href="#dates">Deadlines</a><a href="#disq">Disqualifiers</a>'
         '<a href="#matrixsec">Compliance matrix</a><a href="#draft">Draft</a><a href="#match">Experience and team</a>'
         '<a href="#conflicts">Conflicts hand-off</a><a href="#parser">Parser checks</a></nav>']

    # go / no-go
    b.append('<section id="go"><h2>Go / no-go summary</h2><p class="meta">Facts for the decision. The tool does not decide.</p><div class="cards">')
    if d:
        sub = "at %s" % d["time"] if d["time"] else ""
        if d["changed_by"]:
            sub += " (changed by %s; was %s)" % (d["changed_by"], fmt_date(d["original_date"]))
        b.append(_card("Submission deadline", fmt_date(d["date"]), sub))
        b.append(_card("Business days left", d["business_days_left"], "weekends skipped; holidays only if a file is supplied", d["passed"]))
    else:
        b.append(_card("Submission deadline", "NOT FOUND", "set it by hand", True))
    b.append(_card("Minimum qualifications", "%d met, %d not met" % (mq["met"], mq["not_met"]),
                   "%d cannot be checked from bio or firm data" % mq["not_checkable"], mq["not_met"] > 0))
    b.append(_card("Content coverage", "%d%%" % c["pct"], "%d of %d library-answerable requirements answered in full; %d more need a person" % (
        c["answered_of_answerable"], c["library_answerable"], c["person"])))
    b.append(_card("Open disqualifiers", g["open_disqualifiers"], "mandatory items not answered or marked done", g["open_disqualifiers"] > 0))
    b.append(_card("Blocking fact flags", len(g["blocking_flags"]), "on passages inserted in the draft", bool(g["blocking_flags"])))
    if pg["limit"]:
        b.append(_card("Page estimate", "%d of %d" % (pg["estimated_pages"], pg["limit"]),
                       "%d words at %d a page; %d section(s) still empty" % (pg["words"], pg["words_per_page"], len(pg["empty_sections"])),
                       pg["estimated_pages"] > pg["limit"]))
    b.append("</div>")
    b.append("<h3>Minimum qualifications</h3><table><tr><th>Result</th><th>RFP text</th><th>Basis</th></tr>")
    for q in mq["items"]:
        st = {"met": "answered", "not_met": "failed", "not_checkable": "person"}[q["status"]]
        b.append('<tr><td><span class="pill s-%s">%s</span></td><td>%s</td><td>%s</td></tr>' % (
            st, esc(q["status"].replace("_", " ")), esc(q["text"]), esc(q["detail"])))
    b.append("</table></section>")

    # deadlines
    b.append('<section id="dates"><h2>Deadlines</h2><p class="meta">Each date is shown with the RFP line it came from. '
             'Rows changed by an addendum are highlighted.</p><table><tr><th>Event</th><th>Date in force</th><th>Source line</th><th>Note</th></tr>')
    for x in rfp["deadlines"]:
        when = fmt_date(x["date"]) + ((" at " + x["time"]) if x["time"] else "")
        if x.get("end_date"):
            when += " to " + fmt_date(x["end_date"])
        note = ""
        if x.get("changed_by"):
            note = "Changed by %s. Was <del>%s</del>. Addendum text: &ldquo;%s&rdquo;" % (
                esc(x["changed_by"]), esc(fmt_date(x["original_date"]) + ((" at " + x["original_time"]) if x["original_time"] else "")),
                esc(x["change_source"]["text"]))
        if x["confidence"] == "check":
            note += " CHECK: " + esc(x["check_reason"])
        b.append('<tr%s><td>%s</td><td>%s</td><td>line %d: %s</td><td>%s</td></tr>' % (
            ' class="changed"' if x.get("changed_by") else "", esc(DEADLINE_LABELS.get(x["kind"], x["kind"])), esc(when),
            x["source"]["line"], esc(x["source"]["text"]), note))
    b.append("</table>")
    for a in rfp["addenda"]:
        b.append('<p class="meta">Addendum %s, issued %s: %d change(s) applied, %d item(s) left for a person to read.</p>' % (
            esc(a["number"]), esc(fmt_date(a["issued"])), len(a["changes"]), len(a["notes"])))
    b.append("</section>")

    b.append('<section id="disq"><h2>Disqualifiers</h2>%s</section>' % render._disqualifier_panel(res))

    # matrix
    b.append('<section id="matrixsec"><h2>Compliance matrix</h2><p class="meta">%s</p><div class="filters">' % esc(g["holiday_note"]))
    b.append('<button data-f="all">All</button><button data-f="open">Open mandatory</button>')
    for key in ("answered", "partial", "no_content", "person", "failed", "done"):
        b.append('<button data-f="%s">%s</button>' % (key, esc(res["status_labels"][key])))
    b.append('<span id="count"></span></div><div class="scroll"><table id="matrix"><thead><tr><th>Item</th><th>Type</th>'
             '<th>Requirement (RFP text)</th><th>Must</th><th>Answered in</th><th>Status</th><th>Detail</th><th>Owner</th><th>Due</th></tr></thead><tbody>')
    open_ids = {r["id"] for r in res["disqualifiers"]}
    for r in res["matrix"]:
        b.append('<tr data-status="%s" data-open="%s"><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td%s>%s</td></tr>' % (
            r["status"], "1" if r["id"] in open_ids else "0", esc(r["id"]), esc(r["category"].replace("_", " ")),
            esc(r["requirement"]), "yes" if r["mandatory"] else "no", esc(r["where"]), render._pill(r), esc(r["detail"]),
            esc(r["owner"]), ' class="late"' if r["late"] else "", esc(fmt_date(r["due"]))))
    b.append("</tbody></table></div></section>")

    # draft
    draft = render.draft_html(res)
    inner = draft[draft.index("<main>") + 6:draft.index("</main>")]
    inner = inner.replace("<h1>", "<h3>").replace("</h1>", "</h3>").replace("<h2 ", "<h3 ").replace("</h2>", "</h3>")
    b.append('<section id="draft"><h2>Draft response</h2><p class="meta">In the RFP\'s own order and numbering. '
             'Red marks are gaps and blocking flags. Blue marks need a person. Grey lines give the source of each passage.</p>'
             '<div class="draft">%s</div></section>' % inner)

    # match
    b.append('<section id="match"><h2>Experience and team</h2><h3>Proposed team</h3><table><tr><th>Role</th><th>Attorney</th><th>Why</th></tr>')
    for m in res["team"]["members"]:
        bio = m["bio"]
        b.append("<tr><td>%s</td><td>%s, %s, %s office</td><td>%s</td></tr>" % (
            esc(m["role"]), esc(bio["name"]), esc(bio["title"]), esc(bio.get("office", "")), esc("; ".join(m["reasons"]))))
    b.append("</table>")
    if res["team"]["excluded_departed"]:
        b.append('<p class="meta">Never proposed (no longer with the firm): %s.</p>' % esc(", ".join(res["team"]["excluded_departed"])))
    b.append("<h3>Experience records</h3><table><tr><th>Record</th><th>Printed as</th><th>Client named?</th><th>Why chosen</th></tr>")
    for s in res["experience"]["selected"]:
        named = s["display"]["mode"] == "named"
        b.append('<tr><td>%s</td><td>%s</td><td><span class="pill s-%s">%s</span></td><td>%s</td></tr>' % (
            esc(s["record"]["id"]), esc(s["display"]["text"]), "answered" if named else "person",
            "yes, consent to name on file" if named else "no consent to name: anonymized", esc("; ".join(s["reasons"]))))
    for s in res["experience"]["omitted"]:
        b.append('<tr><td>%s</td><td><em>not printed</em></td><td><span class="pill s-failed">no consent to name, no approved description</span></td><td>%s</td></tr>' % (
            esc(s["record"]["id"]), esc("; ".join(s["reasons"]))))
    b.append("</table></section>")

    # conflicts
    b.append('<section id="conflicts"><h2>Conflicts hand-off</h2><p class="meta">Input list for the conflicts team: parties the parser '
             'found named in the RFP. The tool does not run a conflicts check and never writes the conflicts section.</p>'
             '<table><tr><th>Name</th><th>Category</th><th>Role in the RFP</th><th>RFP line</th><th>Confidence</th></tr>')
    for p in res["parties"]:
        src = p.get("source") or {}
        b.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            esc(p["name"]), esc(render.PARTY_LABELS.get(p["category"], p["category"])), esc(p["role"]), esc(src.get("line", "")),
            esc(p["confidence"] + ((": " + p["check_reason"]) if p["check_reason"] else ""))))
    b.append("</table></section>")

    # parser
    b.append('<section id="parser"><h2>Parser checks</h2><p class="meta">Items the parser was unsure of. They are kept and marked, not dropped.</p><ul>')
    for ch in rfp["checks"]:
        b.append("<li>%s %s: %s%s</li>" % (esc(ch["category"]), esc(ch.get("id") or ""), esc(ch["reason"]),
                                          esc((" | " + ch["text"][:140]) if ch.get("text") else "")))
    if not rfp["checks"]:
        b.append("<li>None. The parser can still be wrong without knowing it.</li>")
    b.append("</ul>")
    if parser_eval:
        o = parser_eval["overall"]
        b.append('<p class="meta">Against the hand-written answer key for this RFP: %d items correct, %d extra, %d missed '
                 '(precision %.3f, recall %.3f). The key and the parser were written for the same document, so this is an '
                 'in-sample figure. On unseen RFPs the parser found about half of what the keys list; see output/parser_evaluation.md.</p>' % (
                     o["tp"], o["fp"], o["fn"], o["precision"], o["recall"]))
    b.append("</section>")
    page = render._html_page("Proposal desk demo: %s" % g["agency"], "\n".join(b), EXTRA_CSS + render._page_css(rfp))
    return page.replace("</main></body>", "</main><script>%s</script></body>" % SCRIPT)
