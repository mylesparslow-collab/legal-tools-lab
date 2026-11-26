"""Builds the static demo page (index.html) from the demo outputs. Data is written into the page; nothing is fetched."""
from __future__ import annotations

from html import escape as h

CSS = """
:root{--bg:#f6f5f1;--card:#fff;--ink:#1c1d1f;--muted:#5b5f66;--line:#d9d6cd;--accent:#1f4e79;
--pass:#17693a;--fail:#a61b1b;--att:#8a5a00;--na:#5b5f66;--code:#efede6}
@media (prefers-color-scheme:dark){:root{--bg:#15171a;--card:#1d2024;--ink:#e8e6e1;--muted:#a3a7ad;--line:#33373d;
--accent:#8fb8e0;--pass:#6fcf97;--fail:#ff8a80;--att:#f2c26b;--na:#a3a7ad;--code:#24282d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif}
main{max-width:940px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:18px;margin:0 0 8px}
h3{font-size:15px;margin:14px 0 6px}
p{margin:6px 0}
.lede{color:var(--muted);max-width:68ch}
.banner{border:1px solid var(--line);border-left:4px solid var(--att);background:var(--card);padding:10px 12px;margin:16px 0;font-size:14px}
section{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:16px 18px;margin:16px 0}
.step{display:inline-block;font-size:12px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.08em;margin-bottom:2px}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em}
.wrap table{min-width:560px}.wrap table.kv{min-width:0}
code,.mono{font-family:ui-monospace,Consolas,Menlo,monospace;font-size:12.5px}
.mono{word-break:break-all}
pre{background:var(--code);padding:10px 12px;border-radius:4px;overflow-x:auto;font-size:12.5px;margin:8px 0;white-space:pre-wrap}
.st{font-weight:700;white-space:nowrap;font-size:12.5px}
.PASS{color:var(--pass)}.FAIL{color:var(--fail)}.ATT{color:var(--att)}.NA{color:var(--na)}
.pill{display:inline-block;border:1px solid currentColor;border-radius:99px;padding:1px 9px;font-size:12px;font-weight:700}
.small{font-size:13px;color:var(--muted)}
details{border:1px solid var(--line);border-radius:6px;margin:8px 0;background:var(--card)}
summary{cursor:pointer;padding:10px 12px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
summary b{flex:1;min-width:200px}
details>div{padding:0 12px 12px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
button{font:inherit;font-size:13px;padding:5px 12px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--bg)}
button:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
a{color:var(--accent)}
ul{margin:6px 0;padding-left:20px}
"""

JS = """
document.querySelectorAll('.filters button').forEach(function(b){b.addEventListener('click',function(){
var f=b.getAttribute('data-f');
document.querySelectorAll('.filters button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});
document.querySelectorAll('details[data-result]').forEach(function(d){d.hidden=!(f==='all'||d.getAttribute('data-result')===f)});
})});
"""


def _cls(s):
    return {"PASS": "PASS", "FAIL": "FAIL", "NEEDS ATTENTION": "ATT", "NOT APPLICABLE": "NA"}.get(s, "NA")


def _checklist_table(result, auth_sections):
    rows = ["<div class=\"wrap\"><table><tr><th>Item</th><th>Status</th><th>Reason</th></tr>"]
    for i in result["items"]:
        det = "".join(f"<li>{h(d)}</li>" for d in i["details"])
        keys = ", ".join(h(auth_sections.get(k, k)) for k in i["authority_keys"])
        rows.append(f"<tr><td>{h(i['title'])}{' <span class=\"small\">(blocks)</span>' if i['blocking'] else ''}</td>"
                    f"<td class=\"st {_cls(i['status'])}\">{h(i['status'])}</td>"
                    f"<td>{h(i['reason'])}{'<ul>' + det + '</ul>' if det else ''}"
                    f"{'<div class=\"small\">See: ' + keys + '</div>' if keys else ''}</td></tr>")
    rows.append("</table></div>")
    return "".join(rows)


def _result_pill(result):
    ok = result["clear_to_file"]
    return f"<span class=\"pill {'PASS' if ok else 'FAIL'}\">{h(result['result'])}</span>"


def build_page(d: dict) -> str:
    """d holds: walk (descriptor, document_text, checklist, record, ledger_entries), scenarios, edited, tamper,
    ledger_check, judge_examples, authorities, auth_sections."""
    w = d["walk"]
    desc, chk, rec = w["descriptor"], w["checklist"], w["record"]
    sec = d["auth_sections"]
    o = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
         "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
         f"<title>Filing verification kit demo</title><style>{CSS}</style></head><body><main>",
         "<h1>Filing verification kit</h1>",
         "<p class=\"lede\">A walk through one fictional court filing: what is checked before filing, what the "
         "attorney attests, and what record is kept. Built from the files in <code>output/</code>.</p>",
         "<div class=\"banner\">Personal portfolio demo. All parties, attorneys, judges, courts, cases and orders "
         "shown here are fictional. Not legal advice. Not reviewed by an attorney.</div>"]

    m = desc["matter"]
    o.append("<section><span class=\"step\">Step 1</span><h2>The filing</h2>"
             "<p>A filing descriptor says what is being filed, where, and who is responsible for it.</p>"
             "<div class=\"wrap\"><table class=\"kv\">"
             f"<tr><th>Filing</th><td>{h(desc['filing_id'])}: {h(desc['document']['title'])} ({h(desc['document']['type'])})</td></tr>"
             f"<tr><th>Matter</th><td>{h(m['caption'])}, case no. {h(m['case_number'])}</td></tr>"
             f"<tr><th>Court</th><td>{h(desc['court'])}; judge id <code>{h(desc['judge_id'])}</code></td></tr>"
             f"<tr><th>Responsible attorney</th><td>{h(desc['responsible_attorney']['name'])}</td></tr>"
             f"<tr><th>Generative AI used</th><td>{'yes: ' + h('; '.join(desc['genai'].get('purposes', []))) if desc['genai'].get('used') else 'no'}</td></tr>"
             f"<tr><th>Document SHA-256</th><td class=\"mono\">{h(chk['document']['sha256'])}</td></tr>"
             "</table></div>"
             f"<details><summary><b>Document text</b></summary><div><pre>{h(w['document_text'])}</pre></div></details></section>")

    o.append("<section><span class=\"step\">Step 2</span><h2>Citation check and attorney attestation</h2>"
             "<p>The existing citation checker produces a machine report. The kit reads that report and then asks a "
             "separate question for each citation: did the responsible attorney verify it, when, and how? "
             "A machine result of PASS does not answer that question.</p>"
             "<div class=\"wrap\"><table><tr><th>Citation</th><th>Machine</th><th>Verified by</th><th>How checked</th></tr>")
    for c in chk["citations"]:
        a = c["attestation"] or {}
        o.append(f"<tr><td>{h(c['label'])}</td><td>{h(c['machine_status'])}</td>"
                 f"<td>{h(a.get('attorney') or 'not attested')}<div class=\"small\">{h(a.get('attested_at') or '')}</div></td>"
                 f"<td>{h(a.get('how_checked') or '')}</td></tr>")
    o.append("</table></div></section>")

    jl = chk["judge_lookup"]
    o.append("<section><span class=\"step\">Step 3</span><h2>Judge and court orders on AI</h2>"
             f"<p>{h(jl['message'])}</p>"
             "<p class=\"small\">The lookup has three answers: current, recheck before relying, and not checked. "
             "It never answers that no order exists.</p>")
    for ex in d["judge_examples"]:
        label = {"not_checked": "NOT CHECKED", "stale": "RECHECK BEFORE RELYING", "current": "CURRENT"}[ex["status"]]
        cls = {"not_checked": "ATT", "stale": "ATT", "current": "PASS"}[ex["status"]]
        o.append(f"<details><summary><b>{h(ex['title'])}</b><span class=\"pill {cls}\">{label}</span></summary><div>"
                 f"<p>{h(ex['message'])}</p>")
        if ex["entries"]:
            o.append("<div class=\"wrap\"><table><tr><th>Entry</th><th>Order</th><th>Requirement</th><th>Last checked</th></tr>")
            for e in ex["entries"]:
                o.append(f"<tr><td>{h(e['entry_id'])}</td><td>{h(e['order_title'])}<div class=\"small\">{h(e.get('judge') or 'court-wide')}</div></td>"
                         f"<td>{h(e['requirement_type'])}<div class=\"small\">{h(e.get('required_text') or '')}</div></td>"
                         f"<td>{h(e['last_checked'])}{' (stale)' if e['stale'] else ''}<div class=\"small\">{h(e['checked_by'])}</div></td></tr>")
            o.append("</table></div>")
        o.append("</div></details>")
    o.append("</section>")

    o.append(f"<section><span class=\"step\">Step 4</span><h2>Pre-filing checklist {_result_pill(chk)}</h2>"
             "<p>Each item is PASS, FAIL, NEEDS ATTENTION or NOT APPLICABLE, with a reason. "
             "The filing is clear only when no blocking item remains.</p>"
             + _checklist_table(chk, sec) + "</section>")

    o.append("<section><span class=\"step\">Step 5</span><h2>Sign-off and record</h2>"
             f"<p>{h(rec['signer']['name'])} signed at {h(rec['signed_at'])}. The record ties the sign-off to the "
             "document hash and is written to an append-only ledger.</p>"
             f"<pre>{h(rec['signer']['statement'])}</pre>"
             "<div class=\"wrap\"><table class=\"kv\">"
             f"<tr><th>Record SHA-256</th><td class=\"mono\">{h(rec['record_sha256'])}</td></tr>"
             f"<tr><th>Disclosure text chosen</th><td>{h(rec['disclosure'].get('text') or 'none')}"
             f"<div class=\"small\">{h(rec['disclosure'].get('wording_status') or '')}</div></td></tr>"
             "</table></div>"
             f"<p><a href=\"{h(w['record_html'])}\">Open the printable record</a> "
             f"(<a href=\"{h(w['record_json'])}\">JSON</a>)</p>"
             "<h3>Ledger entries</h3><div class=\"wrap\"><table><tr><th>Seq</th><th>Event</th><th>Filing</th><th>Hash</th></tr>")
    for e in d["ledger_entries"]:
        o.append(f"<tr><td>{e['seq']}</td><td>{h(e['event'])}</td><td>{h(e.get('filing_id', ''))}</td>"
                 f"<td class=\"mono\">{h(e['hash'][:24])}...</td></tr>")
    lc = d["ledger_check"]
    o.append("</table></div>"
             f"<p>Ledger check: <span class=\"st {'PASS' if lc['ok'] else 'FAIL'}\">{'chain intact' if lc['ok'] else 'broken'}</span>, "
             f"{lc['entries']} entries.</p></section>")

    ed, tp = d["edited"], d["tamper"]
    o.append("<section><span class=\"step\">Step 6</span><h2>What happens after an edit</h2>"
             f"<p>Filing {h(ed['filing_id'])} was signed, and then one sentence was added to the document.</p>"
             "<div class=\"wrap\"><table><tr><th>Check</th><th>Result</th></tr>"
             f"<tr><td>Record against the signed document</td><td class=\"st PASS\">{h(ed['before']['status'])}</td></tr>"
             f"<tr><td>Record against the edited document</td><td class=\"st FAIL\">{h(ed['after']['status'])}</td></tr>"
             f"<tr><td>Checklist on the edited document</td><td class=\"st FAIL\">{h(ed['recheck']['result'])}</td></tr>"
             "</table></div>"
             "<ul>" + "".join(f"<li>{h(p)}</li>" for p in ed["after"]["problems"]) + "</ul>"
             "<h3>Tampering with the ledger</h3>"
             f"<p>{h(tp['what'])}</p><ul>"
             + "".join(f"<li>line {p['line']}: {h(p['problem'])}</li>" for p in tp["check"]["problems"]) + "</ul></section>")

    o.append("<section><span class=\"step\">All sample filings</span><h2>Eight fictional filings</h2>"
             "<div class=\"filters\" role=\"group\" aria-label=\"Filter filings\">"
             "<button data-f=\"all\" aria-pressed=\"true\">All</button>"
             "<button data-f=\"clear\" aria-pressed=\"false\">Clear to file</button>"
             "<button data-f=\"blocked\" aria-pressed=\"false\">Blocked</button></div>")
    for s in d["scenarios"]:
        r = s["checklist"]
        o.append(f"<details data-result=\"{'clear' if r['clear_to_file'] else 'blocked'}\"><summary>"
                 f"<b>{h(r['filing_id'])}: {h(s['scenario'])}</b>{_result_pill(r)}</summary><div>"
                 f"<p class=\"small\">{h(s['title'])} ({h(r['document']['type'])}). {h(s['note'])}</p>"
                 + _checklist_table(r, sec) + "</div></details>")
    o.append("</section>")

    o.append("<section><h2>Authorities referenced</h2><p class=\"small\">Paraphrases from "
             "<code>data/authorities.json</code>, read against the chaptered bill text on the date shown. "
             "Not statutory text. Anything not listed here is firm policy or an open question for an attorney.</p>"
             "<div class=\"wrap\"><table><tr><th>Section</th><th>Paraphrase</th><th>Read on</th></tr>")
    for a in d["authorities"]:
        o.append(f"<tr><td>{h(a['section'])}</td><td>{h(a['paraphrase'])}</td><td>{h(a['verified_on'])}</td></tr>")
    o.append(f"</table></div></section><script>{JS}</script></main></body></html>")
    return "\n".join(o)
