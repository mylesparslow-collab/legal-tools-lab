"""Outputs: matter memo (HTML), client-terms tracker (CSV and HTML), change report, demo page."""
import copy
import csv
import io
from html import escape as e

from . import DECISION_LABELS
from . import engine

CSS = """
:root{--bg:#fbfaf7;--ink:#1d2230;--muted:#5d6475;--line:#d9d6cd;--card:#fff;--ok:#1f6b45;--okbg:#e3f1e8;
--cond:#7a5a00;--condbg:#fbf0cc;--hold:#3d4f8a;--holdbg:#e3e8f7;--no:#8f2a22;--nobg:#f8e2df;--accent:#2f4a6d}
@media (prefers-color-scheme: dark){:root{--bg:#15181f;--ink:#e7e9ee;--muted:#a2a9b8;--line:#343a48;--card:#1c2029;
--ok:#8fd4ad;--okbg:#173527;--cond:#ecd27a;--condbg:#3a3010;--hold:#aebcf0;--holdbg:#222b4a;--no:#f0a49c;--nobg:#42201c;--accent:#9db8dc}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}h3{font-size:14px;margin:16px 0 6px}
p{margin:6px 0}.muted{color:var(--muted)}.small{font-size:13px}
.notice{border:1px solid var(--line);background:var(--card);padding:8px 12px;border-radius:6px;font-size:13px;color:var(--muted)}
.banner{border-left:5px solid var(--accent);background:var(--card);padding:12px 14px;margin:14px 0;font-weight:600;border-radius:0 6px 6px 0}
.flag{border:1px solid var(--no);background:var(--nobg);color:var(--no);padding:8px 12px;border-radius:6px;margin:8px 0;font-size:14px}
.flag.hold{border-color:var(--hold);background:var(--holdbg);color:var(--hold)}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;background:var(--card);font-size:14px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
.chip{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:700;white-space:nowrap}
.ALLOWED{color:var(--ok);background:var(--okbg)}.ALLOWED_WITH_CONDITIONS{color:var(--cond);background:var(--condbg)}
.HOLD_FOR_REVIEW{color:var(--hold);background:var(--holdbg)}.NOT_ALLOWED{color:var(--no);background:var(--nobg)}
ul{margin:4px 0;padding-left:18px}
blockquote{margin:6px 0;padding:6px 10px;border-left:3px solid var(--line);background:var(--card);font-size:14px}
code{font:12px ui-monospace,Menlo,Consolas,monospace;color:var(--muted)}
details{margin:4px 0}summary{cursor:pointer}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 14px;margin:8px 0}dt{color:var(--muted)}dd{margin:0}
nav.tabs{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0}
nav.tabs button{font:inherit;padding:7px 12px;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;cursor:pointer}
nav.tabs button[aria-selected=true]{border-color:var(--accent);box-shadow:inset 0 -3px 0 var(--accent);font-weight:600}
section.tab[hidden]{display:none}
footer{margin-top:32px;font-size:13px;color:var(--muted)}
"""

CLASS_LABELS = {"client_confidential": "Client confidential", "phi": "PHI",
                "protective_order_material": "Protective-order material", "sealed": "Sealed material"}


def page(title, body):
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>%s</title><style>%s</style></head><body><main>%s</main></body></html>\n" % (e(title), CSS, body))


def chip(decision):
    return '<span class="chip %s">%s</span>' % (decision, e(DECISION_LABELS[decision]))


def _quote(span):
    where = e(span["document_id"])
    if span.get("start") is not None:
        where += ", characters %d to %d" % (span["start"], span["end"])
    note = ' <span class="muted small">%s</span>' % e(span["note"]) if span.get("note") else ""
    return "<blockquote>&ldquo;%s&rdquo;<br><code>%s &middot; %s</code>%s</blockquote>" % (
        e(span["quote"]), where, e(span["class"]), note)


def memo_body(rec):
    m = rec["matter"]
    po = m.get("protective_order") or {}
    out = []
    out.append("<h1>AI clearance memo: %s</h1>" % e(m["name"]))
    out.append('<p class="muted">%s &middot; %s &middot; as of %s &middot; policy %s</p>' % (
        e(m["id"]), e(rec["client_name"]), e(rec["as_of"]), e(rec["policy_version"])))
    out.append('<div class="banner">%s</div>' % e(rec["banner"]))
    if rec["flags"]["needs_analyst_review"]:
        out.append('<div class="flag">Needs analyst review. The terms on file conflict or are ambiguous. '
                   "The tool has not picked a reading. See the quoted clauses below.</div>")
    if rec["flags"]["unknown_inputs"]:
        out.append('<div class="flag hold">Intake is incomplete: %s. Unknown never clears restricted data.</div>'
                   % e(", ".join(rec["flags"]["unknown_inputs"])))
    r = (po.get("restrictions") or {})
    out.append("<dl>")
    for k, v in (("Matter type", m.get("matter_type")), ("Responsible attorney", m.get("responsible_attorney")),
                 ("Intake date", m.get("intake_date")),
                 ("PHI", m["data_flags"].get("phi")), ("Sealed material", m["data_flags"].get("sealed")),
                 ("Protective order", po.get("present")),
                 ("Order terms entered at intake", "; ".join("%s: %s" % (a.replace("_", " "), b) for a, b in r.items()) or None),
                 ("Intake note", m.get("intake_note"))):
        if v:
            out.append("<dt>%s</dt><dd>%s</dd>" % (e(k), e(str(v))))
    out.append("</dl>")

    out.append("<h2>Decision for each tool feature</h2><div class=\"wrap\"><table><tr><th>Tool and feature</th>"
               "<th>Decision</th><th>Conditions or reason</th><th>By data class</th><th>Rules</th></tr>")
    for d in rec["decisions"]:
        if d["decision"] == "ALLOWED_WITH_CONDITIONS":
            detail = "<ul>%s</ul>" % "".join("<li>%s <code>%s</code></li>" % (e(c["text"]), e(c["rule_id"]))
                                             for c in d["conditions"])
        elif d["decision"] == "ALLOWED":
            detail = "Within the feature's lane."
        else:
            detail = "<ul>%s</ul>" % "".join("<li>%s</li>" % e(x[0].upper() + x[1:]) for x in d["reasons"])
        by = "<br>".join("%s: %s" % (e(CLASS_LABELS.get(k, k)), e(DECISION_LABELS[v["decision"]].lower()))
                         for k, v in d["by_data_class"].items())
        out.append("<tr><td><strong>%s</strong><br>%s<br><code>%s</code></td><td>%s</td><td>%s</td>"
                   "<td class=\"small\">%s</td><td><code>%s</code></td></tr>" % (
                       e(d["tool_name"]), e(d["feature"]), e(d["feature_id"]), chip(d["decision"]), detail, by,
                       e(", ".join(d["rule_ids"]))))
    out.append("</table></div>")

    out.append("<h2>Terms that drove the decision</h2>")
    for t in rec["terms"]:
        out.append("<h3>%s (%s): %s</h3>" % (e(t["party_name"]), e(t["role"].replace("_", " ")),
                                             e(t["status"].replace("_", " "))))
        out.append('<p class="small muted">Documents: %s. Classes found: %s.</p>' % (
            e(", ".join(t["documents"]) or "none on file"), e(", ".join(t["classes"]) or "none")))
        for c in t["conflicts"]:
            out.append('<div class="flag">Conflict: %s against %s, in %s.</div>' % (
                e(c["pair"][0]), e(c["pair"][1]), e(", ".join(c["documents"]))))
        if t["consent_on_file"]:
            out.append('<p class="small">Consent on file: %s</p>' % e("; ".join(t["consent_on_file"])))
        if t["notice_on_file"]:
            out.append('<p class="small">Notice on file: %s</p>' % e("; ".join(t["notice_on_file"])))
        for x in t["dismissed_by_analyst"]:
            out.append('<p class="small muted">Dismissed by %s on %s (%s): &ldquo;%s&rdquo; %s</p>' % (
                e(x["by"]), e(x["date"]), e(x["class"]), e(x["quote"]), e(x["reason"])))
    spans, seen = [], set()
    for d in rec["decisions"]:
        for drv in d["drivers"]:
            for s in drv["evidence"]:
                key = (s["document_id"], s["start"], s["class"], s["quote"])
                if key not in seen:
                    seen.add(key)
                    spans.append((s, drv["rule_id"]))
    if spans:
        out.append("<h3>Quoted clauses</h3>")
        for s, rid in spans:
            out.append(_quote(s))
    else:
        out.append('<p class="small muted">No quoted clause drove a decision on this matter.</p>')

    out.append("<h2>Rules applied</h2>")
    rules = {}
    for d in rec["decisions"]:
        for drv in d["drivers"]:
            rules.setdefault(drv["rule_id"], drv)
    out.append("<div class=\"wrap\"><table><tr><th>Rule</th><th>Firm policy text</th><th>Owner</th><th>Review date</th></tr>")
    for rid in sorted(rules):
        drv = rules[rid]
        late = ' <span class="chip NOT_ALLOWED">past review date</span>' if drv["past_review_date"] else ""
        oq = ' <code>%s</code>' % e(drv["open_question"]) if drv.get("open_question") else ""
        out.append("<tr><td><code>%s</code></td><td>%s%s</td><td>%s</td><td>%s%s</td></tr>" % (
            e(rid), e(drv["rule_text"]), oq, e(drv["owner_role"]), e(drv["review_date"]), late))
    out.append("</table></div>")
    stale = rec["rules_past_review"]
    if stale:
        out.append('<p class="small">Rules past their review date: %s.</p>' % e(", ".join(
            "%s (%s, %s)" % (s["rule_id"], s["review_date"], s["owner_role"]) for s in stale)))
    out.append('<p class="small muted">Codes such as OQ-04 point to OPEN_QUESTIONS.md: the attorney decision behind the default.</p>')
    out.append("<footer>%s</footer>" % e(rec["disclaimer"]))
    return "".join(out)


def memo_html(rec):
    return page("AI clearance memo " + rec["matter"]["id"], memo_body(rec))


# -------------------------------------------------------------------- tracker

def tracker_rows(store, patterns):
    rows = []
    parties = [(c, "client") for c in store.clients.values()] + [(p, p.get("role", "other")) for p in store.other_parties.values()]
    for rec, role in parties:
        doc_ids = [d["id"] for d in rec.get("documents", [])]
        s = store.party_summary(rec["id"], doc_ids, patterns)
        row = {"party_id": rec["id"], "party_name": rec["name"], "role": role, "status": s["status"],
               "documents": doc_ids, "pending_documents": [d["id"] for d in rec.get("pending_documents", [])],
               "classes": {}, "conflicts": s["conflicts"], "review_hits": s["review_hits"],
               "dismissed": s["dismissed"],
               "scoped": [h for hits in s["hits_by_class"].values() for h in hits if h.get("scope")],
               "approved_list_on_file": isinstance(rec.get("approved_tools"), list),
               "findings_recorded": bool(rec.get("analyst_findings", {}).get("recorded"))}
        for cls in patterns.class_ids:
            if cls == "silent":
                row["classes"][cls] = ["all documents"] if s["status"] == "silent" else []
            else:
                hits = s["hits_by_class"].get(cls, [])
                row["classes"][cls] = sorted({h["document_id"] for h in hits})
        rows.append(row)
    return rows


def tracker_csv(rows, patterns):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["party_id", "party_name", "role", "status", "documents", "pending_documents"] + patterns.class_ids +
               ["conflicts", "ambiguous_spans", "dismissed_by_analyst", "scoped_by_analyst",
                "approved_list_on_file", "residency_retention_findings_recorded"])
    for r in rows:
        w.writerow([r["party_id"], r["party_name"], r["role"], r["status"], "; ".join(r["documents"]),
                    "; ".join(r["pending_documents"])] +
                   ["; ".join(r["classes"][c]) for c in patterns.class_ids] +
                   [" | ".join("%s vs %s (%s)" % (c["pair"][0], c["pair"][1], ", ".join(c["documents"])) for c in r["conflicts"]),
                    len(r["review_hits"]), len(r["dismissed"]), len(r["scoped"]),
                    "yes" if r["approved_list_on_file"] else "no", "yes" if r["findings_recorded"] else "no"])
    return buf.getvalue()


def tracker_html(rows, patterns, evaluation=None):
    out = ["<h1>Client terms tracker</h1>",
           '<p class="notice">Fictional clients. Classes come from keyword patterns, not from a person or a model. '
           "A mark means a clause of that class was found; open the scan output for the quoted span. "
           "Not legal advice. Not reviewed by an attorney.</p>"]
    cols = [c for c in patterns.class_ids]
    out.append('<div class="wrap"><table><tr><th>Party</th><th>Status</th>%s<th>Conflicts and review</th></tr>' %
               "".join("<th>%s</th>" % e(patterns.class_labels[c]) for c in cols))
    status_chip = {"clear": "ALLOWED", "silent": "ALLOWED_WITH_CONDITIONS", "needs_analyst_review": "NOT_ALLOWED",
                   "not_on_file": "HOLD_FOR_REVIEW"}
    status_text = {"clear": "no conflict found", "silent": "silent on AI", "needs_analyst_review": "needs analyst review",
                   "not_on_file": "terms not on file"}
    for r in rows:
        cells = []
        for c in cols:
            docs = r["classes"][c]
            cells.append('<td class="small">%s</td>' % ("<br>".join(e(d) for d in docs) if docs else ""))
        notes = []
        for c in r["conflicts"]:
            notes.append("<strong>Conflict</strong>: %s against %s (%s)" % (e(c["pair"][0]), e(c["pair"][1]), e(", ".join(c["documents"]))))
        for h in r["review_hits"]:
            notes.append("Ambiguous: &ldquo;%s&rdquo; <code>%s %d-%d</code>" % (e(h["quote"]), e(h["document_id"]), h["start"], h["end"]))
        if r["dismissed"]:
            notes.append("%d hit(s) dismissed by an analyst" % len(r["dismissed"]))
        if r["scoped"]:
            notes.append("%d clause(s) scoped by an analyst" % len(r["scoped"]))
        if r["pending_documents"]:
            notes.append("Update pending: %s" % e(", ".join(r["pending_documents"])))
        out.append('<tr><td><strong>%s</strong><br><span class="small muted">%s &middot; %s</span></td>'
                   '<td><span class="chip %s">%s</span></td>%s<td class="small">%s</td></tr>' % (
                       e(r["party_name"]), e(r["role"].replace("_", " ")), e(", ".join(r["documents"]) or "no documents"),
                       status_chip[r["status"]], e(status_text[r["status"]]), "".join(cells), "<br>".join(notes)))
    out.append("</table></div>")
    if evaluation:
        o = evaluation["overall"]
        out.append('<p class="small">Classifier measured against the hand-labeled answer key: precision %.3f, recall %.3f '
                   "over %d labeled spans (%d hard negatives). Misses are listed in output/classifier_evaluation.txt.</p>" % (
                       o["precision"], o["recall"], evaluation["labeled_spans"], evaluation["hard_negative_spans"]))
    return page("Client terms tracker", "".join(out))


# ---------------------------------------------------------------- change report

def diff_terms(client_id, replace_id, with_id, store, features, policy, patterns, as_of):
    """What changes when one terms document replaces another: clause classes and matter decisions."""
    client = store.party_record(client_id)
    before_docs = [d["id"] for d in client.get("documents", [])]
    after_docs = [with_id if d == replace_id else d for d in before_docs]
    if with_id not in after_docs:
        after_docs.append(with_id)
    sb = store.party_summary(client_id, before_docs, patterns)
    sa = store.party_summary(client_id, after_docs, patterns)

    def spans(summary, cls):
        return [{"document_id": h["document_id"], "start": h["start"], "end": h["end"], "quote": h["quote"]}
                for h in summary["hits_by_class"].get(cls, [])]
    added = [c for c in sa["classes"] if c not in sb["classes"]]
    removed = [c for c in sb["classes"] if c not in sa["classes"]]
    matters = []
    total = 0
    for m in store.matters_for_client(client_id):
        m_after = copy.deepcopy(m)
        ids = [with_id if d == replace_id else d for d in m.get("terms_document_ids", [])]
        if with_id not in ids:
            ids.append(with_id)
        m_after["terms_document_ids"] = ids
        rb = engine.clear_matter(m, store, features, policy, patterns, as_of)
        ra = engine.clear_matter(m_after, store, features, policy, patterns, as_of)
        flips = []
        for db, da in zip(rb["decisions"], ra["decisions"]):
            cond_b = [c["text"] for c in db["conditions"]]
            cond_a = [c["text"] for c in da["conditions"]]
            if db["decision"] != da["decision"] or cond_b != cond_a:
                flips.append({
                    "feature_id": db["feature_id"], "tool_name": db["tool_name"], "feature": db["feature"],
                    "before": db["decision"], "after": da["decision"],
                    "decision_changed": db["decision"] != da["decision"],
                    "rules_added": [r for r in da["rule_ids"] if r not in db["rule_ids"]],
                    "rules_removed": [r for r in db["rule_ids"] if r not in da["rule_ids"]],
                    "conditions_added": [c for c in cond_a if c not in cond_b],
                    "conditions_removed": [c for c in cond_b if c not in cond_a],
                    "reasons_after": da["reasons"],
                })
        total += sum(1 for f in flips if f["decision_changed"])
        matters.append({"matter_id": m["id"], "matter_name": m["name"], "banner_before": rb["banner"],
                        "banner_after": ra["banner"], "changes": flips,
                        "unchanged_features": len(rb["decisions"]) - len(flips)})
    return {
        "client_id": client_id, "client_name": client["name"], "as_of": as_of,
        "replaced_document": replace_id, "new_document": with_id,
        "documents_before": before_docs, "documents_after": after_docs,
        "status_before": sb["status"], "status_after": sa["status"],
        "classes_before": sb["classes"], "classes_after": sa["classes"],
        "classes_added": [{"class": c, "spans": spans(sa, c)} for c in added],
        "classes_removed": [{"class": c, "spans": spans(sb, c)} for c in removed],
        "matters": matters, "decisions_flipped": total,
        "disclaimer": engine.DISCLAIMER,
    }


def diff_html(rep):
    out = ["<h1>Change report: %s</h1>" % e(rep["client_name"]),
           '<p class="muted">%s replaces %s &middot; as of %s</p>' % (e(rep["new_document"]), e(rep["replaced_document"]), e(rep["as_of"])),
           '<div class="banner">%d feature decision%s change across %d open matter%s.</div>' % (
               rep["decisions_flipped"], "" if rep["decisions_flipped"] == 1 else "s",
               len(rep["matters"]), "" if len(rep["matters"]) == 1 else "s"),
           "<dl><dt>Status before</dt><dd>%s</dd><dt>Status after</dt><dd>%s</dd></dl>" % (
               e(rep["status_before"].replace("_", " ")), e(rep["status_after"].replace("_", " ")))]
    for title, key in (("Clause classes added", "classes_added"), ("Clause classes removed", "classes_removed")):
        out.append("<h2>%s</h2>" % title)
        if not rep[key]:
            out.append('<p class="muted small">None.</p>')
        for c in rep[key]:
            out.append("<h3>%s</h3>" % e(c["class"]))
            for s in c["spans"]:
                out.append(_quote(dict(s, **{"class": c["class"]})))
    if rep["classes_removed"]:
        out.append('<p class="flag hold">A class that disappears may be a classifier miss in the new document. '
                   "An analyst should read the new document before relying on a removal.</p>")
    out.append("<h2>Matters</h2>")
    for m in rep["matters"]:
        out.append("<h3>%s: %s</h3>" % (e(m["matter_id"]), e(m["matter_name"])))
        out.append('<p class="small"><strong>Before.</strong> %s<br><strong>After.</strong> %s</p>' % (
            e(m["banner_before"]), e(m["banner_after"])))
        if not m["changes"]:
            out.append('<p class="muted small">No decision changes.</p>')
            continue
        out.append('<div class="wrap"><table><tr><th>Feature</th><th>Before</th><th>After</th><th>Why</th></tr>')
        for f in m["changes"]:
            why = []
            if f["rules_added"]:
                why.append("Rules now firing: <code>%s</code>" % e(", ".join(f["rules_added"])))
            if f["rules_removed"]:
                why.append("Rules no longer firing: <code>%s</code>" % e(", ".join(f["rules_removed"])))
            if f["reasons_after"]:
                why.append(e("; ".join(f["reasons_after"])))
            out.append("<tr><td><strong>%s</strong><br>%s</td><td>%s</td><td>%s</td><td class=\"small\">%s</td></tr>" % (
                e(f["tool_name"]), e(f["feature"]), chip(f["before"]), chip(f["after"]), "<br>".join(why)))
        out.append("</table></div>")
    out.append("<footer>%s</footer>" % e(rep["disclaimer"]))
    return page("Change report " + rep["client_id"], "".join(out))


def diff_text(rep):
    lines = ["Change report: %s (%s replaces %s)" % (rep["client_name"], rep["new_document"], rep["replaced_document"]),
             "  status: %s -> %s" % (rep["status_before"], rep["status_after"]),
             "  classes added: %s" % (", ".join(c["class"] for c in rep["classes_added"]) or "none"),
             "  classes removed: %s" % (", ".join(c["class"] for c in rep["classes_removed"]) or "none"),
             "  feature decisions flipped: %d" % rep["decisions_flipped"]]
    if rep["classes_removed"]:
        lines.insert(4, "  note: a removed class may be a classifier miss in the new document; an analyst should check")
    for m in rep["matters"]:
        lines.append("  %s %s" % (m["matter_id"], m["matter_name"]))
        lines.append("    before: %s" % m["banner_before"])
        lines.append("    after:  %s" % m["banner_after"])
        for f in m["changes"]:
            if f["decision_changed"]:
                lines.append("    %-28s %s -> %s" % (f["feature_id"], DECISION_LABELS[f["before"]], DECISION_LABELS[f["after"]]))
    return "\n".join(lines)


# ------------------------------------------------------------------ demo page

def index_html(records, evaluation=None):
    out = ["<h1>Matter clearance for AI</h1>",
           '<p class="notice">Personal portfolio demo. Fictional clients, matters, tools and contract terms. '
           "Every rule is a configurable firm policy default, not a statement of law. Not legal advice. "
           "Not reviewed by an attorney.</p>",
           "<p>At intake the tool reads three things: the client's own AI terms, the matter's data flags, and any "
           "protective order terms entered by the intake team. It returns one decision for each tool feature and a "
           "one-line banner for the matter. Sample matters shown: %d.</p>" % len(records),
           '<nav class="tabs" role="tablist">']
    for i, r in enumerate(records):
        out.append('<button role="tab" id="tab-%d" aria-controls="panel-%d" aria-selected="%s" data-i="%d">%s</button>' % (
            i, i, "true" if i == 0 else "false", i, e(r["matter"]["id"] + ": " + r["matter"]["name"])))
    out.append("</nav>")
    for i, r in enumerate(records):
        out.append('<section class="tab" role="tabpanel" id="panel-%d" aria-labelledby="tab-%d"%s>%s</section>' % (
            i, i, "" if i == 0 else " hidden", memo_body(r).replace("<h1>", "<h2>").replace("</h1>", "</h2>")))
    if evaluation:
        o = evaluation["overall"]
        out.append('<p class="small muted">Clause classifier on the sample documents: precision %.3f, recall %.3f '
                   "against %d hand-labeled spans. See README.md for the misses.</p>" % (
                       o["precision"], o["recall"], evaluation["labeled_spans"]))
    out.append("<script>document.querySelectorAll('nav.tabs button').forEach(function(b){b.addEventListener('click',function(){"
               "document.querySelectorAll('nav.tabs button').forEach(function(x){x.setAttribute('aria-selected',x===b?'true':'false')});"
               "document.querySelectorAll('section.tab').forEach(function(s){s.hidden=s.id!=='panel-'+b.dataset.i})})});</script>")
    return page("Matter clearance for AI: demo", "".join(out))


def memo_text(rec):
    lines = [rec["matter"]["id"] + "  " + rec["matter"]["name"], "  " + rec["banner"]]
    for d in rec["decisions"]:
        extra = "; ".join(c["short"] for c in d["conditions"]) or "; ".join(d["reasons"])
        lines.append("  %-28s %-24s %s" % (d["feature_id"], d["decision_label"], extra))
        lines.append("  %-28s rules: %s" % ("", ", ".join(d["rule_ids"])))
    if rec["flags"]["needs_analyst_review"]:
        lines.append("  NEEDS ANALYST REVIEW: terms conflict or are ambiguous")
    if rec["flags"]["unknown_inputs"]:
        lines.append("  intake incomplete: " + ", ".join(rec["flags"]["unknown_inputs"]))
    stale = [s["rule_id"] for s in rec["rules_past_review"]]
    if stale:
        lines.append("  rules past review date: " + ", ".join(stale))
    return "\n".join(lines)
