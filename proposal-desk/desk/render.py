"""Render a build result: draft (Markdown, HTML), matrix (HTML, CSV), go/no-go, conflicts list, match report."""
import csv
import io

from .facts import BLOCKING
from .library import provenance_text
from .pipeline import ANSWERED, DONE, FAILED, NO_CONTENT, PARTIAL, PERSON, STATUS_LABELS
from .rfp import DEADLINE_LABELS, QTYPE_LABELS
from .util import esc, fmt_date

BANNER = ("WORKING DRAFT. Synthetic demo data. Not legal advice. Notes in [square brackets] are internal "
          "and must be removed or resolved before anything is submitted.")


def _deadline_line(g):
    d = g["deadline"]
    if not d:
        return "Submission deadline: NOT FOUND in the RFP."
    s = "Submission deadline: %s%s" % (fmt_date(d["date"]), (" at %s" % d["time"]) if d["time"] else "")
    if d["changed_by"]:
        s += " (changed by %s; was %s%s)" % (d["changed_by"], fmt_date(d["original_date"]),
                                             (" at %s" % d["original_time"]) if d["original_time"] else "")
    return s


def _owner_due(sec):
    s = "Owner: %s." % sec["owner"]
    if sec["due"]:
        s += " Due: %s%s." % (fmt_date(sec["due"]), " (this date has passed)" if sec["late"] else "")
    return s


def _section_markers(sec):
    """(kind, text) markers for a section, in order. Used by both Markdown and HTML."""
    out = []
    for p in sec["parts"]:
        if p["type"] == "person":
            out.append(("person", "NEEDS A PERSON: %s %s" % (p["text"], _owner_due(sec))))
        elif p["type"] == "gap":
            out.append(("gap", "GAP: %s %s" % (p["text"], _owner_due(sec))))
    return out


def draft_markdown(res):
    g, rfp = res["go_no_go"], res["rfp"]
    out = ["# Draft response: %s" % (rfp["meta"]["title"] or "Request for proposals"), "",
           "Agency: %s  " % g["agency"], "RFP number: %s  " % (g["rfp_number"] or "not found"),
           _deadline_line(g) + "  ", "Prepared as of: %s" % g["as_of"], "", "> " + BANNER, ""]
    for sec in res["sections"]:
        out += ["## %s %s" % (sec["label"], sec["title"]), "",
                "> RFP %s: %s" % (sec["label"], sec["rfp_text"]), ""]
        if sec["status"] == PARTIAL:
            out += ["[PARTIAL: %s. %s]" % ("; ".join(sec["notes"]) or "see notes", _owner_due(sec)), ""]
        for p in sec["parts"]:
            if p["type"] == "passage":
                for f in p["flags"]:
                    out += ["[%s: %s]" % ("BLOCKING" if f["level"] == BLOCKING else "CHECK", f["message"]), ""]
                out += [p["text"], "", "[%s]" % provenance_text(p["provenance"]), ""]
            elif p["type"] == "facts":
                out += [p["text"], "", "[Source: firm_facts.json as of %s]" % p["as_of"], ""]
            elif p["type"] == "team":
                if not p["items"]:
                    out += ["[GAP: no team could be proposed from the bios. %s]" % _owner_due(sec), ""]
                for it in p["items"]:
                    out += ["- %s" % it["text"], "  [Source: bio %s. Chosen because: %s]" % (it["bio_id"], "; ".join(it["reasons"]))]
                out.append("")
            elif p["type"] == "experience":
                if not p["items"]:
                    out += ["[GAP: no printable experience records matched. %s]" % _owner_due(sec), ""]
                for it in p["items"]:
                    out += ["- %s" % it["text"], "  [Source: experience record %s, %s. Chosen because: %s]" % (
                        it["record_id"], "client named with consent" if it["mode"] == "named"
                        else "client not named: no consent on file", "; ".join(it["reasons"]))]
                out.append("")
            elif p["type"] == "references":
                for it in p["items"]:
                    out += ["- %s" % it["text"], "  [Source: reference record %s, last confirmed %s%s]" % (
                        it["record_id"], it["last_confirmed"] or "never", "; RECONFIRM before use" if it["stale"] else "")]
                missing = p["needed"] - len(p["items"])
                if missing > 0:
                    out += ["", "[GAP: %d more reference(s) needed. Only contacts with consent on file are listed. %s]"
                            % (missing, _owner_due(sec))]
                out.append("")
        for kind, text in _section_markers(sec):
            out += ["[%s]" % text, ""]
        if sec["status"] != PARTIAL and sec["notes"]:
            out += ["[NOTE: %s]" % " ".join(sec["notes"]), ""]
    return "\n".join(out).rstrip() + "\n"


CSS = """
:root{--ink:#1c2430;--mute:#5d6875;--line:#d5dae0;--bg:#fff;--soft:#f4f6f8;--red:#a4262c;--redbg:#fdecec;
--amber:#8a5a00;--amberbg:#fff4d6;--green:#1e6b3a;--greenbg:#e6f4ea;--blue:#1f4e8c;--bluebg:#e8f0fb;--grey:#4a5360;--greybg:#eceff2}
*{box-sizing:border-box}body{font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:var(--bg);margin:0;line-height:1.45}
main{max-width:860px;margin:0 auto;padding:24px 16px}
h1{font-size:1.5em;margin:0 0 .4em}h2{font-size:1.15em;margin:1.6em 0 .4em;border-top:1px solid var(--line);padding-top:.8em}
table{border-collapse:collapse;width:100%;font-family:system-ui,Arial,sans-serif;font-size:.82em}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--soft)}
.meta,.note,.src,.banner,.pill,.panel,.tools{font-family:system-ui,Arial,sans-serif}
.meta{color:var(--mute);font-size:.9em}.banner{background:var(--amberbg);color:var(--amber);border:1px solid #e6c766;padding:8px 10px;font-size:.85em;margin:12px 0}
.quote{border-left:3px solid var(--line);padding:2px 10px;color:var(--mute);font-size:.92em;margin:.4em 0 .8em}
.src{color:var(--mute);font-size:.78em;margin:.2em 0 .9em}
.mark{font-family:system-ui,Arial,sans-serif;font-size:.85em;padding:6px 9px;margin:.5em 0;border-left:4px solid}
.gap,.blocking,.failed{background:var(--redbg);border-color:var(--red);color:var(--red)}
.person{background:var(--bluebg);border-color:var(--blue);color:var(--blue)}
.check,.partial{background:var(--amberbg);border-color:var(--amber);color:var(--amber)}
.pill{display:inline-block;padding:1px 7px;border-radius:9px;font-size:.78em;white-space:nowrap}
.s-answered{background:var(--greenbg);color:var(--green)}.s-partial{background:var(--amberbg);color:var(--amber)}
.s-no_content,.s-failed{background:var(--redbg);color:var(--red)}.s-person{background:var(--bluebg);color:var(--blue)}
.s-done{background:var(--greybg);color:var(--grey)}
.panel{border:1px solid var(--line);padding:10px 12px;margin:12px 0;font-size:.88em}
.panel.red{border-color:var(--red)}.panel h3{margin:0 0 6px;font-size:1em}
.tools{font-size:.82em;color:var(--mute);margin:8px 0}
ul{padding-left:1.2em}.late{color:var(--red);font-weight:bold}
#hide:checked ~ main .src,#hide:checked ~ main .mark.check{display:none}
@media print{.tools,#hide{display:none}main{max-width:none;padding:0}h2{break-after:avoid}.mark,.quote{break-inside:avoid}}
"""


def _page_css(rfp):
    font = next((m["value"] for m in rfp["mechanics"] if m["kind"] == "font"), None)
    margin = next((m["value"] for m in rfp["mechanics"] if m["kind"] == "margins"), None)
    css = "@page{margin:%sin}" % (margin if margin else 1)
    if font:
        css += "@media print{body{font-size:%spt}}" % font
    return css


def _html_page(title, body, extra_css="", toggle=False):
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>'
            '<style>%s%s</style></head><body>' % (esc(title), CSS, extra_css))
    tog = ('<input type="checkbox" id="hide" style="margin:12px 6px 0 16px">'
           '<label for="hide" class="tools">Hide source notes and check notes. Gaps, items for a person '
           'and blocking flags always stay visible.</label>') if toggle else ""
    return head + tog + "<main>" + body + "</main></body></html>\n"


def draft_html(res):
    g, rfp = res["go_no_go"], res["rfp"]
    b = ['<h1>Draft response: %s</h1>' % esc(rfp["meta"]["title"] or "Request for proposals"),
         '<p class="meta">Agency: %s<br>RFP number: %s<br>%s<br>Prepared as of: %s</p>' % (
             esc(g["agency"]), esc(g["rfp_number"] or "not found"), esc(_deadline_line(g)), esc(g["as_of"])),
         '<div class="banner">%s</div>' % esc(BANNER)]
    for sec in res["sections"]:
        b.append('<h2 id="%s">%s %s</h2>' % (esc(sec["id"]), esc(sec["label"]), esc(sec["title"])))
        b.append('<div class="quote">RFP %s: %s</div>' % (esc(sec["label"]), esc(sec["rfp_text"])))
        if sec["status"] == PARTIAL:
            b.append('<div class="mark partial">PARTIAL: %s. %s</div>' % (esc("; ".join(sec["notes"])), esc(_owner_due(sec))))
        for p in sec["parts"]:
            if p["type"] == "passage":
                for f in p["flags"]:
                    cls, word = ("blocking", "BLOCKING") if f["level"] == BLOCKING else ("check", "CHECK")
                    b.append('<div class="mark %s">%s: %s</div>' % (cls, word, esc(f["message"])))
                b.append("<p>%s</p>" % esc(p["text"]))
                b.append('<div class="src">%s</div>' % esc(provenance_text(p["provenance"])))
            elif p["type"] == "facts":
                b.append("<p>%s</p>" % esc(p["text"]))
                b.append('<div class="src">Source: firm_facts.json as of %s</div>' % esc(p["as_of"]))
            elif p["type"] == "team":
                if not p["items"]:
                    b.append('<div class="mark gap">GAP: no team could be proposed from the bios. %s</div>' % esc(_owner_due(sec)))
                b.append("<ul>")
                for it in p["items"]:
                    b.append('<li>%s<div class="src">Source: bio %s. Chosen because: %s</div></li>' % (
                        esc(it["text"]), esc(it["bio_id"]), esc("; ".join(it["reasons"]))))
                b.append("</ul>")
            elif p["type"] == "experience":
                if not p["items"]:
                    b.append('<div class="mark gap">GAP: no printable experience records matched. %s</div>' % esc(_owner_due(sec)))
                b.append("<ul>")
                for it in p["items"]:
                    b.append('<li>%s<div class="src">Source: experience record %s, %s. Chosen because: %s</div></li>' % (
                        esc(it["text"]), esc(it["record_id"]),
                        "client named with consent" if it["mode"] == "named" else "client not named: no consent on file",
                        esc("; ".join(it["reasons"]))))
                b.append("</ul>")
            elif p["type"] == "references":
                b.append("<ul>")
                for it in p["items"]:
                    b.append('<li>%s<div class="src">Source: reference record %s, last confirmed %s%s</div></li>' % (
                        esc(it["text"]), esc(it["record_id"]), esc(it["last_confirmed"] or "never"),
                        "; RECONFIRM before use" if it["stale"] else ""))
                b.append("</ul>")
                missing = p["needed"] - len(p["items"])
                if missing > 0:
                    b.append('<div class="mark gap">GAP: %d more reference(s) needed. Only contacts with consent on '
                             'file are listed. %s</div>' % (missing, esc(_owner_due(sec))))
        for kind, text in _section_markers(sec):
            b.append('<div class="mark %s">%s</div>' % (kind, esc(text)))
        if sec["status"] != PARTIAL and sec["notes"]:
            b.append('<div class="mark check">NOTE: %s</div>' % esc(" ".join(sec["notes"])))
    return _html_page("Draft: %s" % g["agency"], "\n".join(b), _page_css(rfp), toggle=True)


MATRIX_COLUMNS = ["id", "category", "section", "requirement", "mandatory", "where", "status_label", "detail",
                  "owner", "due", "late", "source_line"]


def matrix_csv(res):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "category", "section", "requirement", "mandatory", "answered_in", "status", "detail",
                "owner", "due", "due_date_passed", "rfp_line"])
    for r in res["matrix"]:
        w.writerow([r["id"], r["category"], r["section"], r["requirement"], "yes" if r["mandatory"] else "no",
                    r["where"], r["status_label"], r["detail"], r["owner"], r["due"],
                    "yes" if r["late"] else "no", r["source_line"] or ""])
    return buf.getvalue()


def _pill(r):
    return '<span class="pill s-%s">%s</span>' % (r["status"], esc(r["status_label"]))


def _disq_text(r):
    """Deadline and delivery rows lead with the tool's reading, so an addendum change is not missed."""
    if r["category"] in ("deadline", "submission") and r["auto_status"] == PERSON:
        return "%s RFP text: %s" % (r["detail"], r["requirement"][:120])
    return r["requirement"][:160]


def _disqualifier_panel(res):
    dq = res["disqualifiers"]
    b = ['<div class="panel red"><h3>Disqualifiers: %d mandatory item(s) not yet satisfied</h3>' % len(dq)]
    if not dq:
        b.append("<p>None open. This does not mean the proposal is compliant; it means every row is answered or marked done.</p>")
    else:
        b.append("<table><tr><th>Item</th><th>Requirement</th><th>Status</th><th>Owner</th><th>Due</th></tr>")
        for r in dq:
            b.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td%s>%s</td></tr>' % (
                esc(r["id"]), esc(_disq_text(r)), _pill(r), esc(r["owner"]),
                ' class="late"' if r["late"] else "", esc(fmt_date(r["due"]))))
        b.append("</table>")
    b.append("</div>")
    return "\n".join(b)


def matrix_html(res):
    g = res["go_no_go"]
    b = ['<h1>Compliance matrix: %s</h1>' % esc(g["agency"]),
         '<p class="meta">%s<br>Prepared as of %s. %s</p>' % (esc(_deadline_line(g)), esc(g["as_of"]), esc(g["holiday_note"])),
         '<div class="banner">Synthetic demo data. Not legal advice. The matrix lists what the parser found in the RFP text. '
         'Read the RFP itself before relying on it.</div>', _disqualifier_panel(res),
         "<table><tr><th>Item</th><th>Type</th><th>Requirement (RFP text)</th><th>Must</th><th>Answered in</th>"
         "<th>Status</th><th>Detail</th><th>Owner</th><th>Due</th></tr>"]
    for r in res["matrix"]:
        b.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td%s>%s</td></tr>' % (
            esc(r["id"]), esc(r["category"].replace("_", " ")), esc(r["requirement"]), "yes" if r["mandatory"] else "no",
            esc(r["where"]), _pill(r), esc(r["detail"]), esc(r["owner"]), ' class="late"' if r["late"] else "",
            esc(fmt_date(r["due"]))))
    b.append("</table>")
    return _html_page("Compliance matrix: %s" % g["agency"], "\n".join(b))


def go_no_go_markdown(res):
    g, rfp = res["go_no_go"], res["rfp"]
    c, mqs, pg = g["coverage"], g["min_quals"], g["page"]
    out = ["# Go / no-go summary: %s" % g["agency"], "",
           "%s%s  " % (rfp["meta"]["title"], (" (RFP %s)" % g["rfp_number"]) if g["rfp_number"] else ""),
           "Prepared as of %s. Synthetic demo data. Not legal advice." % g["as_of"], "",
           "This page gives the facts for the decision. The tool does not make the decision.", "",
           "## Deadline", ""]
    d = g["deadline"]
    if d:
        out.append("- " + _deadline_line(g))
        out.append("- Business days left: %d%s" % (d["business_days_left"], " (THE DEADLINE HAS PASSED)" if d["passed"] else ""))
    else:
        out.append("- NOT FOUND in the RFP. Set it by hand before anything else.")
    out.append("- %s%s" % (g["holiday_note"], " A holiday file was supplied." if g["holidays_supplied"] else ""))
    for x in rfp["deadlines"]:
        if x["kind"] == "submission_due":
            continue
        line = "- %s: %s%s" % (DEADLINE_LABELS.get(x["kind"], x["kind"]), fmt_date(x["date"]),
                               (" at %s" % x["time"]) if x["time"] else "")
        if x.get("end_date"):
            line += " to %s" % fmt_date(x["end_date"])
        if x.get("changed_by"):
            line += " (changed by %s; was %s)" % (x["changed_by"], fmt_date(x["original_date"]))
        if x["confidence"] == "check":
            line += " [CHECK: %s]" % x["check_reason"]
        out.append(line)
    out += ["", "## Minimum qualifications", "",
            "- Met: %d. Not met: %d. Not checkable from bio or firm data: %d." % (mqs["met"], mqs["not_met"], mqs["not_checkable"])]
    for q in mqs["items"]:
        out.append("- [%s] %s  \n  %s" % (q["status"].replace("_", " ").upper(), q["text"], q["detail"]))
    out += ["", "## Content coverage", "",
            "- %d of %d requirements that the library may answer are answered in full: %d%%." % (
                c["answered_of_answerable"], c["library_answerable"], c["pct"]),
            "- All %d requirements: %d answered, %d partial, %d with no content, %d that need a person." % (
                c["requirements"], c["answered"], c["partial"], c["no_content"], c["person"]),
            "- \"Answered\" means approved, current text was found and passed the fact guard. A person still has to read it."]
    if pg["limit"]:
        out.append("- Page limit %d%s. Estimate so far: about %d page(s) (%d words at %d a page), with %d section(s) still empty." % (
            pg["limit"], (" (changed by %s; was %s)" % (pg["changed_by"], pg["original_limit"])) if pg["changed_by"] else "",
            pg["estimated_pages"], pg["words"], pg["words_per_page"], len(pg["empty_sections"])))
    out += ["", "## Fact guard", "",
            "- Firm facts are as of %s (%d days old)%s." % (g["facts_as_of"], g["facts_age_days"],
                                                           ": OLD, confirm before use" if g["facts_old"] else ""),
            "- Blocking flags on inserted passages: %d." % len(g["blocking_flags"])]
    for f in g["blocking_flags"]:
        out.append("  - Section %s, answer %s: %s" % (f["section"], f["answer_id"], f["message"]))
    out.append("- Client names printed without consent: %d." % len(g["consent_flags"]))
    for m in g["consent_flags"]:
        out.append("  - %s" % m)
    out += ["", "## Open disqualifiers: %d" % g["open_disqualifiers"], "",
            "Every mandatory item that is not answered or marked done. %d of them have a due date that has already passed." % g["late_items"], ""]
    for r in res["disqualifiers"]:
        out.append("- %s | %s | %s | owner %s | due %s%s" % (
            r["id"], r["status_label"], r["requirement"][:110], r["owner"], fmt_date(r["due"]) or "not set",
            " (passed)" if r["late"] else ""))
    out += ["", "## Parser items to check: %d" % g["parser_checks"], ""]
    for ch in rfp["checks"]:
        out.append("- %s %s: %s%s" % (ch["category"], ch.get("id") or "", ch["reason"],
                                      (" | " + ch["text"][:100]) if ch.get("text") else ""))
    if not rfp["checks"]:
        out.append("- None. The parser can still be wrong without knowing it.")
    if g["unknown_status_marks"]:
        out += ["", "Status file names items that are not in the matrix: %s." % ", ".join(g["unknown_status_marks"])]
    if g["data_errors"]:
        out += ["", "%d library record(s) were rejected on load. Run `python -m desk check-data`." % g["data_errors"]]
    return "\n".join(out) + "\n"


PARTY_LABELS = {"agency": "Agency", "board": "Board or council member", "staff": "Agency staff",
                "adverse": "Adverse or counter-party", "other_organisation": "Other organisation mentioned"}


def conflicts_csv(res):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["name", "category", "role_in_rfp", "confidence", "check_reason", "rfp_line", "rfp_text"])
    for p in res["parties"]:
        src = p.get("source") or {}
        w.writerow([p["name"], PARTY_LABELS.get(p["category"], p["category"]), p["role"], p["confidence"],
                    p["check_reason"], src.get("line", ""), src.get("text", "")])
    return buf.getvalue()


def conflicts_markdown(res):
    g = res["go_no_go"]
    out = ["# Conflicts hand-off: %s" % g["agency"], "",
           "Input list for the conflicts team. These are the parties the parser found named in the RFP.",
           "The list may be incomplete. Read the RFP for parties the parser missed, and add parent and",
           "related entities. The tool does not run a conflicts check and does not write the conflicts section.", "",
           "| Name | Category | Role in the RFP | Confidence | RFP line |", "|---|---|---|---|---|"]
    for p in res["parties"]:
        src = p.get("source") or {}
        out.append("| %s | %s | %s | %s | %s |" % (p["name"], PARTY_LABELS.get(p["category"], p["category"]), p["role"],
                                                 p["confidence"] + ((": " + p["check_reason"]) if p["check_reason"] else ""),
                                                 src.get("line", "")))
    return "\n".join(out) + "\n"


def match_markdown(res):
    g = res["go_no_go"]
    out = ["# Experience and team match: %s" % g["agency"], "",
           "Agency type: %s. Practice: %s. Subjects found in the RFP: %s." % (
               res["rfp"]["meta"]["agency_type"].replace("_", " "), res["rfp"]["meta"]["practice"].replace("_", " "),
               ", ".join(res["rfp"]["meta"]["subjects"]) or "none"), "", "## Proposed team", ""]
    for m in res["team"]["members"]:
        b = m["bio"]
        out.append("- %s: %s (%s, %s office). Score %d. %s." % (m["role"], b["name"], b["title"], b.get("office", ""),
                                                                 m["score"], "; ".join(m["reasons"])))
    if res["team"]["excluded_departed"]:
        out.append("- Not considered (no longer with the firm): %s." % ", ".join(res["team"]["excluded_departed"]))
    out += ["", "## Minimum qualifications", ""]
    for q in res["min_quals"]:
        out.append("- [%s] %s  \n  %s" % (q["status"].replace("_", " ").upper(), q["text"], q["detail"]))
    out += ["", "## Experience records chosen", ""]
    for s in res["experience"]["selected"]:
        out.append("- %s | score %d | %s  \n  Printed as: %s  \n  Why: %s." % (
            s["record"]["id"], s["score"],
            "client named (consent on file)" if s["display"]["mode"] == "named" else "client NOT named (no consent)",
            s["display"]["text"], "; ".join(s["reasons"])))
    out += ["", "## Relevant records that cannot be printed", ""]
    if not res["experience"]["omitted"]:
        out.append("- None.")
    for s in res["experience"]["omitted"]:
        out.append("- %s | score %d | no consent and no approved anonymized description. Ask the client, or approve a description." % (
            s["record"]["id"], s["score"]))
    return "\n".join(out) + "\n"


def parse_summary(rfp):
    """Plain-text summary of a parsed RFP for the CLI."""
    m = rfp["meta"]
    out = ["Agency: %s (%s)" % (m["agency"] or "NOT FOUND", m["agency_type"]),
           "Title: %s   RFP number: %s   Practice: %s" % (m["title"], m["rfp_number"] or "not found", m["practice"]),
           "", "Deadlines:"]
    for d in rfp["deadlines"]:
        line = "  %-28s %s %s" % (DEADLINE_LABELS.get(d["kind"], d["kind"]), d["date"], d["time"] or "")
        if d.get("changed_by"):
            line += "  [changed by %s; was %s %s]" % (d["changed_by"], d["original_date"], d["original_time"] or "")
        if d["confidence"] == "check":
            line += "  [check: %s]" % d["check_reason"]
        out.append(line)
        out.append("      line %d: %s" % (d["source"]["line"], d["source"]["text"]))
    out += ["", "Submission mechanics:"]
    for x in rfp["mechanics"]:
        out.append("  %-16s %s%s" % (x["kind"], x["value"], ("  [changed by %s; was %s]" % (x["changed_by"], x.get("original_value")))
                                     if x.get("changed_by") else ""))
    out += ["", "Requirements (%d):" % len(rfp["requirements"])]
    for r in rfp["requirements"]:
        out.append("  %-7s %-28s %s%s" % (r["label"], QTYPE_LABELS[r["qtype"]], r["text"][:70],
                                         "  [check: %s]" % r["check_reason"] if r["confidence"] == "check" else ""))
    out += ["", "Forms and certifications (%d):" % len(rfp["forms"])]
    for f in rfp["forms"]:
        out.append("  %-14s %s%s" % (f["ref"], f["name"], "  [check: %s]" % f["check_reason"] if f["confidence"] == "check" else ""))
    ev = rfp["evaluation"]
    out += ["", "Evaluation criteria (%s, total %s):" % (ev["unit"], ev["total"])]
    for c in ev["criteria"]:
        out.append("  %-4s %s" % (c["weight"] if c["weight"] is not None else "?", c["name"]))
    out += ["", "Minimum qualifications (%d):" % len(rfp["min_quals"])]
    for q in rfp["min_quals"]:
        out.append("  [%s] %s" % (q["check_kind"], q["text"][:90]))
    out += ["", "Insurance statements (%d):" % len(rfp["insurance"])]
    for x in rfp["insurance"]:
        out.append("  %s" % x["text"][:100])
    for a in rfp["addenda"]:
        out += ["", "Addendum %s (issued %s): %d change(s) applied, %d item(s) to read" % (
            a["number"], a["issued"], len(a["changes"]), len(a["notes"]))]
        for c in a["changes"]:
            out.append("  %s: %s -> %s" % (c["kind"], c["from"], c["to"]))
    out += ["", "Items marked check: %d" % len(rfp["checks"])]
    for c in rfp["checks"]:
        out.append("  %s %s: %s" % (c["category"], c.get("id") or "", c["reason"]))
    return "\n".join(out) + "\n"
