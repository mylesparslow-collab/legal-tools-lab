"""HTML for the printable one-page verification record. No scripts, no external files."""
from __future__ import annotations

from html import escape as h

CSS = """
*{box-sizing:border-box}
body{font:13px/1.45 Georgia,'Times New Roman',serif;color:#1b1b1b;background:#fff;margin:0;padding:24px}
main{max-width:820px;margin:0 auto}
h1{font-size:20px;margin:0 0 2px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #999;margin:18px 0 6px;padding-bottom:2px;font-family:Arial,Helvetica,sans-serif}
p{margin:4px 0}
table{border-collapse:collapse;width:100%;font-size:12px}
th,td{border:1px solid #bbb;padding:4px 6px;text-align:left;vertical-align:top}
th{background:#f0f0f0;font-family:Arial,Helvetica,sans-serif;font-weight:600}
.kv td:first-child{width:190px;background:#f7f7f7;font-family:Arial,Helvetica,sans-serif}
.mono{font-family:Consolas,Menlo,monospace;font-size:11px;word-break:break-all}
.notice{border:1px solid #999;padding:6px 8px;font-family:Arial,Helvetica,sans-serif;font-size:11px;margin:8px 0}
.st{font-family:Arial,Helvetica,sans-serif;font-weight:700;white-space:nowrap}
.PASS{color:#0b6b2e}.FAIL{color:#a40e0e}.ATT{color:#8a5a00}.NA{color:#555}
.sign{border:1px solid #333;padding:8px 10px;margin-top:8px}
.small{font-size:11px;color:#444}
.tablewrap{overflow-x:auto}
@media print{body{padding:0}h2{break-after:avoid}tr{break-inside:avoid}}
"""


def _cls(status: str) -> str:
    return {"PASS": "PASS", "FAIL": "FAIL", "NEEDS ATTENTION": "ATT", "NOT APPLICABLE": "NA"}.get(status, "NA")


def _row(k, v, mono=False):
    cls = ' class="mono"' if mono else ""
    return f"<tr><td>{h(k)}</td><td{cls}>{h('' if v is None else str(v))}</td></tr>"


def _yn(v):
    return "yes" if v is True else "no" if v is False else "not recorded"


def record_html(rec: dict, ledger_entry: dict | None = None) -> str:
    m = rec.get("matter") or {}
    att = rec.get("responsible_attorney") or {}
    doc = rec["document"]
    ai = rec["ai_use"]
    d = rec["disclosure"]
    jl = rec["judge_order_snapshot"]
    out = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
           f"<title>Verification record {h(rec['filing_id'])}</title><style>{CSS}</style></head><body><main>",
           f"<h1>Filing verification record: {h(rec['filing_id'])}</h1>",
           f"<p class=\"small\">{h(rec['notice'])}</p>",
           "<h2>Filing</h2><table class=\"kv\">",
           _row("Matter", f"{m.get('number', '')} {m.get('client', '')}".strip()),
           _row("Caption", m.get("caption")),
           _row("Court", rec.get("court") or rec.get("court_id")),
           _row("Judge id", rec.get("judge_id")),
           _row("Document", f"{doc.get('title') or doc['path']} ({doc['type']})"),
           _row("Planned filing date", rec.get("planned_filing_date")),
           _row("Responsible attorney", f"{att.get('name', '')} {att.get('bar_number', '')}".strip()),
           _row("Document SHA-256", doc["sha256"], mono=True),
           _row("Checklist result", f"{rec['checklist']['result']} (policy {rec['checklist']['policy_version']})"),
           "</table>",
           "<p class=\"notice\">This record covers the document only while its SHA-256 equals the value above. "
           "Any edit after sign-off makes the record invalid for the edited file.</p>"]

    out.append("<h2>Citations and attorney attestation</h2><div class=\"tablewrap\"><table><tr><th>#</th><th>Citation</th>"
               "<th>Machine</th><th>Verified by</th><th>When</th><th>How checked</th></tr>")
    for i, c in enumerate(rec["citations"], 1):
        how = c.get("how_checked") or ""
        if c.get("resolution") and c["resolution"] != how:
            how += f" Resolution: {c['resolution']}"
        flags = "".join(f"<br><span class=\"small\">{h(f)}</span>" for f in c["machine_flags"])
        out.append(f"<tr><td>{i}</td><td>{h(c['citation'])}{flags}</td><td>{h(c['machine_status'])}</td>"
                   f"<td>{h(c.get('attested_by') or 'NOT ATTESTED')}</td><td>{h(c.get('attested_at') or '')}</td>"
                   f"<td>{h(how)}</td></tr>")
    if not rec["citations"]:
        out.append("<tr><td colspan=\"6\">No citations listed in the citation report.</td></tr>")
    out.append("</table></div><p class=\"small\">A machine status is not attorney verification. "
               "The attestation columns are the attorney's own entries.</p>")

    out.append("<h2>Generative AI use</h2><table class=\"kv\">")
    out.append(_row("Generative AI used", _yn(ai["used"])))
    if ai["used"]:
        ov = ai.get("output_verified") or {}
        out += [_row("Tools", "; ".join(ai["tools"])), _row("Purposes", "; ".join(ai["purposes"])),
                _row("Output reviewed", f"{ov.get('by', '')}, {ov.get('on', '')}: {ov.get('how', '')}"),
                _row("Protected information entered", _yn(ai.get("protected_info_entered"))),
                _row("Disclosure decision", f"{d.get('decision')} (by {d.get('decided_by')}, {d.get('decided_on') or 'date not recorded'})")]
        if d.get("text"):
            out.append(_row(f"Disclosure text (option {d.get('option_id')}, {d.get('wording_status')})", d["text"]))
        if d.get("reason"):
            out.append(_row("Reason", d["reason"]))
    out.append("</table>")

    out.append("<h2>Judge and court AI orders (snapshot at sign-off)</h2>")
    out.append(f"<p>{h(jl['message'])}</p>")
    if jl.get("fictional_sample_data"):
        out.append("<p class=\"small\">Fictional sample data. No real court or judge.</p>")
    if jl["entries"]:
        out.append("<div class=\"tablewrap\"><table><tr><th>Entry</th><th>Order</th><th>Requirement</th><th>Last checked</th><th>Source</th></tr>")
        for e in jl["entries"]:
            stale = " (stale: recheck before relying)" if e["stale"] else ""
            req = e["requirement_type"] + (f": {e['required_text']}" if e.get("required_text") else "")
            out.append(f"<tr><td>{h(e['entry_id'])}</td><td>{h(e['order_title'])}<br><span class=\"small\">{h(e.get('judge') or 'court-wide')}</span></td>"
                       f"<td>{h(req)}</td><td>{h(e['last_checked'])} by {h(e['checked_by'])}{h(stale)}</td>"
                       f"<td class=\"mono\">{h(e['source_url'])}</td></tr>")
        out.append("</table></div>")
    resp = rec.get("judge_order_response")
    if resp:
        out.append(f"<p>Response recorded: order {h(str(resp.get('order_id')))}, {h(str(resp.get('action')))}.</p>")
    chk = rec.get("judge_order_check")
    if chk:
        out.append(f"<p>Manual check for this filing: {h(str(chk.get('checked_by')))} on {h(str(chk.get('checked_on')))}, "
                   f"result {h(str(chk.get('result')))}.</p>")

    out.append("<h2>Checklist</h2><div class=\"tablewrap\"><table><tr><th>Item</th><th>Status</th><th>Reason</th></tr>")
    for i in rec["checklist"]["items"]:
        det = "".join(f"<br><span class=\"small\">- {h(x)}</span>" for x in i["details"])
        out.append(f"<tr><td>{h(i['title'])}</td><td class=\"st {_cls(i['status'])}\">{h(i['status'])}</td>"
                   f"<td>{h(i['reason'])}{det}</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Authorities referenced</h2><div class=\"tablewrap\"><table><tr><th>Key</th><th>Section</th><th>Paraphrase</th><th>Read on</th></tr>")
    for a in rec["authorities"]:
        out.append(f"<tr><td class=\"mono\">{h(a['key'])}</td><td>{h(a['section'])}</td><td>{h(a['paraphrase'])}</td><td>{h(a['verified_on'])}</td></tr>")
    out.append("</table></div><p class=\"small\">Paraphrases from data/authorities.json. Not statutory text.</p>")

    out.append("<h2>Sign-off</h2><div class=\"sign\">")
    out.append(f"<p>{h(rec['signer']['statement'])}</p>")
    out.append(f"<p><strong>{h(rec['signer']['name'])}</strong>, {h(rec['signed_at'])}</p>")
    out.append("<p class=\"small\">Name typed at the command line. This demo has no sign-in or electronic signature.</p></div>")
    out.append("<table class=\"kv\" style=\"margin-top:8px\">")
    out.append(_row("Record SHA-256", rec["record_sha256"], mono=True))
    if ledger_entry:
        out.append(_row("Ledger entry", f"seq {ledger_entry['seq']}, hash {ledger_entry['hash']}", mono=True))
    out.append("</table></main></body></html>")
    return "\n".join(out)
