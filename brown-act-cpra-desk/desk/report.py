"""One self-contained HTML page summarising a run."""
from html import escape as e

CSS = """
:root{--bg:#f7f6f2;--ink:#1d2227;--mute:#5d6670;--line:#d9d6cc;--card:#fff;--fail:#a4262c;--review:#8a5a00;--info:#3b5b7a;--pass:#2f6b3a}
@media (prefers-color-scheme:dark){:root{--bg:#15181b;--ink:#e6e3da;--mute:#9aa3ab;--line:#30363c;--card:#1c2024;--fail:#f08a8f;--review:#e2b25c;--info:#8fb4d6;--pass:#86c592}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:28px 16px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:34px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:15px;margin:18px 0 6px}.sub{color:var(--mute);margin:0 0 6px}.note{border:1px solid var(--line);background:var(--card);padding:10px 14px;border-radius:6px;margin:14px 0}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);font-size:14px}th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{font-weight:600;white-space:nowrap}.lv{font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:.04em;white-space:nowrap}
.fail{color:var(--fail)}.review{color:var(--review)}.info{color:var(--info)}.pass{color:var(--pass)}.cite{color:var(--mute);white-space:nowrap}a{color:inherit}
.counts span{display:inline-block;margin-right:14px}
"""


def _cite(f):
    c = f.get("cite") or ""
    if f.get("source_url"):
        c = f'<a href="{e(f["source_url"])}">{e(c)}</a>'
    else:
        c = e(c)
    st = f.get("source_status")
    return c + (f" <small>({e(st)})</small>" if st and st != "verified" else "")


def _findings(fs):
    order = {"fail": 0, "review": 1, "info": 2, "pass": 3}
    rows = "".join(f'<tr><td class="lv {f["level"]}">{f["level"]}</td><td>{e(f["message"])}</td><td class="cite">{_cite(f)}</td></tr>'
                   for f in sorted(fs, key=lambda f: order[f["level"]]))
    return f'<div class="wrap"><table><tr><th>Result</th><th>Finding</th><th>Source</th></tr>{rows}</table></div>'


def render(agendas: list, cpra_rows: list, legacy: list, log: list, production: dict, asof: str) -> str:
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Agenda and Records Desk</title><style>{CSS}</style></head><body><main>",
         "<h1>Brown Act agenda check and CPRA records desk</h1>",
         f"<p class='sub'>Demo run as of {e(asof)}. All agencies, people and records are fictional.</p>",
         "<div class='note'>This is a personal portfolio demo, not legal advice and not built or reviewed by an attorney. "
         "A 'pass' means the input met a coded rule. A 'review' is a question for a person. Each row links to the code section it relies on; "
         "rows marked 'assumption' or 'not_modeled' do not come from statute text.</div>"]
    for a in agendas:
        m, c = a["meeting"], a["counts"]
        h.append(f"<h2>{e(a['body'] or '')}, {e(m['type'])} meeting, {e(m['start'].replace('T', ' '))}</h2><p class='sub'>{e(a['agency'] or '')}</p>")
        h.append("<p class='counts'>" + "".join(f"<span class='{k}'><b>{c[k]}</b> {k}</span>" for k in c) + "</p>")
        for key, title in (("clocks", "Posting and notice clocks"), ("quorum", "Quorum and remote participation"), ("items", "Agenda items")):
            if a["sections"][key]:
                h.append(f"<h3>{title}</h3>" + _findings(a["sections"][key]))
    if cpra_rows:
        h.append("<h2>Records requests</h2><div class='wrap'><table><tr><th>Request</th><th>Received</th><th>Day-10 date</th><th>Latest with extension</th><th>Status</th><th>Notes</th></tr>")
        for r in cpra_rows:
            notes = "<br>".join(f"<span class='lv {f['level']}'>{f['level']}</span> {e(f['message'])}" for f in r["findings"] if f["code"] != "determination")
            lvl = next(f["level"] for f in r["findings"] if f["code"] == "determination")
            h.append(f"<tr><td>{e(r['id'])}</td><td>{r['received']}</td><td>{r['determination_due']}</td><td>{r['extension_latest']}</td><td class='{lvl}'>{e(r['status'])}</td><td>{notes}</td></tr>")
        h.append("</table></div>")
    if legacy:
        h.append("<h2>Former CPRA citations found in the draft letter</h2><div class='wrap'><table><tr><th>Found</th><th>Current section</th><th>Topic</th><th>Status</th></tr>")
        for x in legacy:
            h.append(f"<tr><td>{e(x['found'])}</td><td>{e(x['new'] or 'not in table')}</td><td>{e(x['topic'] or '')}</td><td>{e(x['status'])}</td></tr>")
        h.append("</table></div>")
    if log:
        h.append("<h2>Withholding log (approved entries only)</h2><div class='wrap'><table><tr>" + "".join(f"<th>{e(k.replace('_', ' '))}</th>" for k in log[0]) + "</tr>")
        for r in log:
            h.append("<tr>" + "".join(f"<td>{e(str(v))}</td>" for v in r.values()) + "</tr>")
        h.append("</table></div>")
    if production:
        h.append("<h2>Redacted production set</h2><div class='wrap'><table><tr><th>Document</th><th>Redactions applied</th><th>Leak check after save</th></tr>")
        for d, r in production.items():
            if r.get("withheld"):
                h.append(f"<tr><td>{e(d)}</td><td colspan='2'>Withheld in full; no file produced</td></tr>")
            else:
                h.append(f"<tr><td>{e(d)}</td><td>{sum(r['hits'].values())}</td><td class='{'fail' if r['leaks'] else 'pass'}'>{'LEAK' if r['leaks'] else 'no redacted text found'}</td></tr>")
        h.append("</table></div>")
    h.append("</main></body></html>")
    return "".join(h)
