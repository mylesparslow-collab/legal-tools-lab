"""Election memo (Word and Markdown) and the deadline calendar file."""
from datetime import date, datetime, timedelta

from .quotes import verify_quote

DISCLAIMER = ("Demo output on invented data. Not legal advice and not reviewed by an attorney. "
              "Screening results are prompts for a lawyer to read the clause, not conclusions.")
ORDER = ["FLAG", "MISSING", "GAP", "REVIEW", "ADDRESSED", "NO_CLAUSE", "NOT_APPLICABLE"]


def _money(n):
    return f"${n:,}"


def build_markdown(r):
    L = [f"# Side-letter gate and MFN election memo", "", f"_{DISCLAIMER}_", "",
         f"**Investor:** {r['investor']['name']}  ", f"**Fund:** {r['fund']['name']}  ",
         f"**Commitment counted for MFN tiers:** {_money(r['aggregated_commitment'])}  ",
         f"**Election deadline:** {r['deadline']['deadline']} ({r['deadline']['window']} from compendium delivery on {r['deadline']['delivery_date']}"
         + (f"; {r['deadline']['raw_deadline']} falls on a weekend and rolls forward" if r['deadline']['rolled'] else "") + ")", "",
         "## 1. Statutory gate on the draft side letter", "",
         "| Status | Rule | Where | Why | Quote from the draft |", "|---|---|---|---|---|"]
    for f in sorted(r["gate"], key=lambda f: ORDER.index(f["status"])):
        L.append(f"| {f['status']} | {f['citation']} ({f['verification_status'].replace('_', ' ')}) | {f['section'] or ''} | {f['why']} | {('“' + f['quote'] + '”') if f['quote'] else ''} |")
    for verdict, head in (("ELECTABLE", "## 2. Provisions the investor can elect"), ("REVIEW", "## 3. Provisions a person must read"), ("NOT_ELECTABLE", "## 4. Provisions the investor cannot elect")):
        rows = [d for d in r["mfn"] if d["verdict"] == verdict]
        L += ["", f"{head} ({len(rows)})", ""]
        cats = []
        for d in rows:
            if d["category_label"] not in cats:
                cats.append(d["category_label"])
        for c in sorted(cats):
            L += [f"### {c}", "", "| Provision | Page | Why | Text (verbatim) | Own draft |", "|---|---|---|---|---|"]
            for d in rows:
                if d["category_label"] == c:
                    why = " ".join(x["text"] for x in d["reasons"])
                    L.append(f"| {d['id']} | {d['page']} | {why} | “{d['text']}” | {d.get('own_draft', '')} |")
            L.append("")
    if r.get("model"):
        L += ["## 5. Model-proposed items", "", f"Accepted after quote check: {len(r['model']['accepted'])}. Rejected: {len(r['model']['rejected'])}.", ""]
        for b in r["model"]["rejected"]:
            L.append(f"- Rejected, provision {b.get('provision_id')}: {b['rejected']}. Proposed quote: “{b.get('quote', '')}”")
    return "\n".join(L) + "\n"


def build_docx(r, path):
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Pt

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    doc.styles["Normal"].font.size = Pt(9.5)
    doc.add_heading("Side-letter gate and MFN election memo", 0)
    doc.add_paragraph(DISCLAIMER).runs[0].italic = True
    dl = r["deadline"]
    for k, v in (("Investor", r["investor"]["name"]), ("Fund", r["fund"]["name"]),
                 ("Commitment counted for MFN tiers", _money(r["aggregated_commitment"])),
                 ("Election deadline", f"{dl['deadline']} ({dl['window']} from delivery on {dl['delivery_date']}" + ("; weekend roll-forward applied" if dl["rolled"] else "") + ")")):
        p = doc.add_paragraph()
        p.add_run(k + ": ").bold = True
        p.add_run(v)

    def table(headers, rows):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Light Grid Accent 1"
        for i, h in enumerate(headers):
            t.rows[0].cells[i].text = h
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = str(v)

    doc.add_heading("1. Statutory gate on the draft side letter", 1)
    table(["Status", "Rule", "Where", "Why", "Quote from the draft"],
          [(f["status"], f"{f['citation']} ({f['verification_status'].replace('_', ' ')})", f["section"] or "", f["why"],
            f"“{f['quote']}”" if f["quote"] else "") for f in sorted(r["gate"], key=lambda f: ORDER.index(f["status"]))])
    for n, (verdict, head) in enumerate((("ELECTABLE", "Provisions the investor can elect"), ("REVIEW", "Provisions a person must read"), ("NOT_ELECTABLE", "Provisions the investor cannot elect")), 2):
        rows = [d for d in r["mfn"] if d["verdict"] == verdict]
        doc.add_heading(f"{n}. {head} ({len(rows)})", 1)
        for c in sorted({d["category_label"] for d in rows}):
            doc.add_heading(c, 2)
            table(["Prov.", "Page", "Why", "Text (verbatim)", "Own draft"],
                  [(d["id"], d["page"], " ".join(x["text"] for x in d["reasons"]), f"“{d['text']}”", d.get("own_draft", ""))
                   for d in rows if d["category_label"] == c])
    if r.get("model"):
        doc.add_heading("5. Model-proposed items", 1)
        doc.add_paragraph(f"Accepted after quote check: {len(r['model']['accepted'])}. Rejected: {len(r['model']['rejected'])}.")
        for b in r["model"]["rejected"]:
            doc.add_paragraph(f"Rejected, provision {b.get('provision_id')}: {b['rejected']}. Proposed quote: “{b.get('quote', '')}”", style="List Bullet")
    doc.save(path)


def build_ics(r):
    d = date.fromisoformat(r["deadline"]["deadline"])
    stamp = datetime(2026, 1, 1).strftime("%Y%m%dT%H%M%SZ")  # fixed so output is reproducible
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//pension-mfn-engine demo//EN", "BEGIN:VEVENT",
        f"UID:mfn-election-{d.isoformat()}@demo.invalid", f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:MFN election deadline (demo) - {r['fund']['name']}",
        "DESCRIPTION:Contract deadline computed from the fund file. Demo data. Confirm against the fund agreement.",
        "BEGIN:VALARM", "TRIGGER:-P7D", "ACTION:DISPLAY", "DESCRIPTION:MFN election due in 7 days", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])


def assert_quotes(r, draft_text, compendium_text):
    """Last check before anything is written: every quote in the memo is verbatim in its source."""
    for f in r["gate"]:
        if f["quote"]:
            assert verify_quote(f["quote"], draft_text), f["rule_id"]
    for d in r["mfn"]:
        assert verify_quote(d["text"], compendium_text), d["id"]
        for x in d["reasons"]:
            if x["quote"]:
                assert verify_quote(x["quote"], compendium_text), d["id"]
