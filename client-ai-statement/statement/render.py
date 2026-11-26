"""Render a built statement, its proposal paragraph and the internal evidence appendix."""
from __future__ import annotations

import html
import json

e = html.escape

_SERIF = 'Charter,"Bitstream Charter","Iowan Old Style","Palatino Linotype",Georgia,"Times New Roman",serif'
_SANS = 'system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'

STATEMENT_CSS = f"""
:root{{--ink:#111;--muted:#4d4d4d;--rule:#b5b5b5;--paper:#fff;--desk:#e8e8e4}}
*{{box-sizing:border-box}}
html{{background:var(--desk)}}
body{{margin:0;color:var(--ink);font:9.7pt/1.38 {_SERIF};-webkit-text-size-adjust:100%}}
.sheet{{position:relative;width:8.5in;max-width:100%;min-height:11in;margin:24px auto;padding:0.7in 0.85in 0.6in;
background:var(--paper);box-shadow:0 1px 5px rgba(0,0,0,.22)}}
header{{border-bottom:1.25pt solid var(--ink);padding-bottom:9pt}}
h1{{margin:0;font:600 20pt/1.15 {_SERIF};letter-spacing:-.01em}}
.sub{{margin:4pt 0 0;color:var(--muted);font-size:9.5pt}}
.tag{{position:absolute;top:0.7in;right:0.85in;border:1pt solid var(--ink);padding:2pt 7pt;
font:600 7.5pt/1.5 {_SANS};letter-spacing:.09em;text-transform:uppercase}}
section{{display:grid;grid-template-columns:1.4in 1fr;column-gap:.22in;padding:6pt 0;border-bottom:.5pt solid var(--rule)}}
h2{{margin:1.6pt 0 0;font:600 7.6pt/1.4 {_SANS};letter-spacing:.07em;text-transform:uppercase}}
section p{{margin:0;hyphens:manual}}
footer{{display:flex;justify-content:space-between;gap:1em;margin-top:7pt;color:var(--muted);font-size:8.3pt}}
.watermark{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden;pointer-events:none}}
.watermark span{{font:700 120pt/1 {_SANS};letter-spacing:.12em;color:rgba(0,0,0,.055);transform:rotate(-38deg)}}
@media (max-width:7in){{.sheet{{padding:20px 16px;margin:0}}section{{grid-template-columns:1fr}}h2{{margin-bottom:2pt}}
.tag{{position:static;display:inline-block;margin-bottom:8px}}footer{{display:block}}}}
@media print{{
@page{{size:letter;margin:0.7in 0.85in 0.6in}}
html{{background:#fff}}
.sheet{{width:auto;min-height:0;margin:0;padding:0;box-shadow:none}}
.tag{{top:0;right:0}}
.watermark{{position:fixed}}
section{{break-inside:avoid}}
}}
"""


def statement_html(stmt: dict) -> str:
    draft = stmt["status"] != "APPROVED"
    secs = []
    for sec in stmt["sections"]:
        text = " ".join(e(s["text"]) for s in sec["sentences"])
        secs.append(f'<section><h2>{e(sec["label"])}</h2><p>{text}</p></section>')
    mark = '<div class="watermark" aria-hidden="true"><span>DRAFT</span></div><div class="tag">Draft, not approved</div>' if draft else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(stmt['title'])}</title><style>{STATEMENT_CSS}</style></head>
<body><main class="sheet">{mark}
<header><h1>{e(stmt['title'])}</h1><p class="sub">{e(stmt['subtitle'])}</p></header>
{chr(10).join(secs)}
<footer><span>{e(stmt['footer'])}</span><span>{e(stmt['status_line'])}</span></footer>
</main></body></html>
"""


def statement_md(stmt: dict) -> str:
    L = [f"# {stmt['title']}", "", stmt["subtitle"], ""]
    if stmt["status"] != "APPROVED":
        L += [f"> {stmt['status_line']}", ""]
    for sec in stmt["sections"]:
        L += [f"## {sec['label']}", "", " ".join(s["text"] for s in sec["sentences"]), ""]
    L += ["---", "", f"{stmt['footer']} {stmt['status_line']}", ""]
    return "\n".join(L)


def proposal_md(stmt: dict) -> str:
    p = stmt["proposal"]
    L = ["# Proposal paragraph: AI use", ""]
    if p["status"] != "APPROVED":
        L += ["> DRAFT. Not approved for release.", ""]
    L += [p["text"], "", "---", "",
          f"{p['words']} words (target about {p['target']}, ceiling {p['max']}). Built from the same supported claims as the "
          f"statement dated {stmt['as_of']}, version {stmt['version']}. Each sentence is listed in the evidence appendix.", ""]
    return "\n".join(L)


# ---------- evidence appendix (internal) ----------

def _val(v) -> str:
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else repr(v)


def _basis(s: dict) -> str:
    ev = s.get("evidence")
    if s["kind"] == "placeholder":
        return "Placeholder. No claim in this section is supported by the registry."
    if s["kind"] == "draft_option" and not ev:
        return (f"DRAFT option {s['variant_id']}. Policy wording chosen in the statement inputs. No registry evidence. "
                "Needs General Counsel approval.")
    by_entry: dict = {}
    for c in ev["checked"]:
        by_entry.setdefault(c["entry"], []).append(f"{c['field']} = {_val(c['actual'])}")
    lines = [f"{k}: " + ", ".join(v) for k, v in by_entry.items()]
    if s["kind"] == "record":
        head = "Not registry evidence. Taken from the statement inputs or the client-terms record; confirm by hand."
    else:
        head = f"Registry: {len(ev['passing'])} of {len(ev['scope'])} entries in scope meet the rule."
        if ev["scope"] and not by_entry:
            lines = ["In scope: " + ", ".join(ev["scope"])]
    if s["kind"] == "draft_option":
        head = f"DRAFT option {s['variant_id']}. Needs General Counsel approval. " + head
    return head + (" " + " | ".join(lines) if lines else "")


def _why(result: dict) -> str:
    rows = [f"{r['entry']}: {r['expected']}; found {_val(r['actual'])}" + (f" ({r['reason']})" if r.get("reason") else "")
            for r in result["failing"]]
    rows += [f"{r['entry']}: {r['expected']}; cannot tell" + (f" ({r['reason']})" if r.get("reason") else "")
             for r in result["unknown"]]
    if result["note"]:
        rows.append(result["note"])
    return f"{result['status']}. " + " | ".join(rows)


def appendix_model(stmt: dict) -> dict:
    printed = [{"section": sec["label"], "claim": f"{s['claim_id']} / {s['variant_id']}", "text": s["text"],
                "basis": _basis(s)} for sec in stmt["sections"] for s in sec["sentences"]]
    downgraded = [{"claim": d["claim_id"], "printed": d["printed_text"],
                   "not_used": [{"variant": v["variant_id"], "wording": v["template"], "why": _why(v["result"])}
                                for v in d["stronger"]]} for d in stmt["downgraded"]]
    omitted = [{"claim": o["claim_id"], "section": o["section"],
                "variants": [{"variant": v["variant_id"], "wording": v["template"], "why": _why(v["result"])}
                             for v in o["variants"]]} for o in stmt["omitted"]]
    return {"printed": printed, "downgraded": downgraded, "omitted": omitted,
            "not_applicable": stmt["not_applicable"], "draft_options": stmt["draft_options"],
            "warnings": stmt["warnings"], "category_check": stmt["category_check"], "proposal": stmt["proposal"]}


def _approval_block(stmt: dict) -> list[str]:
    if stmt["status"] == "APPROVED":
        a = stmt["approval"]
        return [f"Status: APPROVED by {a['approved_by']} on {a['approved_on']}.",
                f"Approved content hash: {a['content_hash']}"]
    return ["Status: DRAFT. The statement and proposal paragraph are watermarked DRAFT.",
            "To approve this exact text, set approval.approved_by, approval.approved_on and approval.content_hash "
            "in the statement inputs, then rebuild. Any change to the printed text changes the hash and returns the statement to DRAFT.",
            f"Content hash of this text: {stmt['content_hash']}"]


def appendix_md(stmt: dict) -> str:
    m = appendix_model(stmt)
    L = ["# Evidence appendix", "",
         "**INTERNAL. Not for clients. For General Counsel review before the statement is approved.**", "",
         f"Statement: {stmt['subtitle']} As of {stmt['as_of']}, version {stmt['version']}. "
         f"Registry dated {stmt['registry_as_of']} (sha256 {stmt['registry_sha256'][:12]}). "
         f"{stmt['word_count']} of {stmt['word_limit']} words.", ""]
    L += _approval_block(stmt) + [""]
    L += ["## Warnings", ""] + ([f"- {w}" for w in m["warnings"]] or ["None."]) + [""]
    L += ["## 1. Printed sentences and the evidence behind each", ""]
    for i, p in enumerate(m["printed"], 1):
        L += [f"{i}. **{p['text']}**", f"   - Section: {p['section']}. Claim: `{p['claim']}`.", f"   - {p['basis']}"]
    L += ["", "## 2. Downgraded claims (a weaker wording was printed)", ""]
    for d in m["downgraded"]:
        L += [f"- `{d['claim']}` printed as: **{d['printed']}**"]
        L += [f"  - Not used (`{v['variant']}`): \"{v['wording']}\" {v['why']}" for v in d["not_used"]]
    if not m["downgraded"]:
        L += ["None."]
    L += ["", "## 3. Omitted claims (no wording is supported)", ""]
    for o in m["omitted"]:
        L += [f"- `{o['claim']}`"]
        L += [f"  - `{v['variant']}`: \"{v['wording']}\" {v['why']}" for v in o["variants"]]
    if not m["omitted"]:
        L += ["None."]
    L += ["", "## 4. Claims that do not apply or were excluded", ""]
    L += [f"- `{n['claim_id']}`: {n['reason']}" for n in m["not_applicable"]] or ["None."]
    L += ["", "## 5. DRAFT options chosen (lawyer decisions)", ""]
    L += [f"- {o['topic']}: option {o['option_id']} ({o['name']})" + ("" if o["printed"] else ". Prints nothing.")
          for o in m["draft_options"]]
    L += ["", "## 6. Tool categories and uses to confirm against the registry", "",
          "The registry schema has no category field. These labels come from the statement inputs.", "",
          "| Tool id | Status | Category printed | Use printed | Registry purpose |", "| --- | --- | --- | --- | --- |"]
    L += [f"| {c['id']} | {c['status']} | {c['category'] or 'MISSING'} | {c['use'] or 'MISSING'} | {c['registry_purpose']} |"
          for c in m["category_check"]]
    L += ["", "## 7. Proposal paragraph", "", m["proposal"]["text"], "",
          f"{m['proposal']['words']} words. Sentences: " + ", ".join(f"`{s['claim_id']}`" for s in m["proposal"]["sentences"]) + ".", ""]
    return "\n".join(L)


APPENDIX_CSS = f"""
:root{{--ink:#15191c;--muted:#56606a;--line:#c9cfd4;--head:#eef1f3;--warn:#7a2e0e}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px 16px;background:#fff;color:var(--ink);font:13px/1.45 {_SANS}}}
main{{max-width:1040px;margin:0 auto}}
.banner{{border:2px solid var(--ink);padding:8px 12px;font-weight:700;letter-spacing:.04em;margin-bottom:14px}}
h1{{font-size:20px;margin:0 0 6px}}h2{{font-size:15px;margin:22px 0 8px}}
p{{margin:0 0 6px}}.meta{{color:var(--muted)}}
.wrap{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}
th{{background:var(--head);font-weight:600}}
td.s{{width:30%}}td.c{{width:22%;color:var(--muted)}}
code{{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
ul{{margin:0;padding-left:18px}}li{{margin-bottom:4px}}
.warn{{color:var(--warn)}}.hash{{font-family:ui-monospace,Menlo,Consolas,monospace;overflow-wrap:anywhere}}
@media print{{@page{{size:letter;margin:14mm}}body{{padding:0;font-size:9pt}}tr{{break-inside:avoid}}}}
"""


def appendix_html(stmt: dict) -> str:
    m = appendix_model(stmt)
    out = [f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evidence appendix (internal)</title><style>{APPENDIX_CSS}</style></head><body><main>
<div class="banner">INTERNAL. NOT FOR CLIENTS. For General Counsel review before the statement is approved.</div>
<h1>Evidence appendix</h1>
<p class="meta">Statement: {e(stmt['subtitle'])} As of {e(stmt['as_of'])}, version {e(stmt['version'])}.
Registry dated {e(stmt['registry_as_of'])} (sha256 {e(stmt['registry_sha256'][:12])}).
{stmt['word_count']} of {stmt['word_limit']} words.</p>"""]
    out += [f'<p class="hash">{e(line)}</p>' for line in _approval_block(stmt)]
    out.append("<h2>Warnings</h2>")
    out.append("<ul class=\"warn\">" + "".join(f"<li>{e(w)}</li>" for w in m["warnings"]) + "</ul>" if m["warnings"] else "<p>None.</p>")

    out.append('<h2>1. Printed sentences and the evidence behind each</h2><div class="wrap"><table>'
               '<thead><tr><th>Printed sentence</th><th>Section and claim</th><th>Evidence</th></tr></thead><tbody>')
    for p in m["printed"]:
        out.append(f'<tr><td class="s">{e(p["text"])}</td><td class="c">{e(p["section"])}<br><code>{e(p["claim"])}</code></td>'
                   f'<td>{e(p["basis"])}</td></tr>')
    out.append("</tbody></table></div>")

    def variants_table(title: str, rows: list, key: str, first: str) -> None:
        out.append(f"<h2>{e(title)}</h2>")
        if not rows:
            out.append("<p>None.</p>")
            return
        out.append(f'<div class="wrap"><table><thead><tr><th>{e(first)}</th><th>Wording not used</th>'
                   "<th>Why the registry does not support it</th></tr></thead><tbody>")
        for r in rows:
            vs = r[key]
            for i, v in enumerate(vs):
                lead = ""
                if i == 0:
                    label = f'<code>{e(r["claim"])}</code>' + (f'<br>Printed: {e(r["printed"])}' if "printed" in r else "")
                    lead = f'<td class="s" rowspan="{len(vs)}">{label}</td>'
                out.append(f'<tr>{lead}<td><code>{e(v["variant"])}</code><br>{e(v["wording"])}</td><td>{e(v["why"])}</td></tr>')
        out.append("</tbody></table></div>")

    variants_table("2. Downgraded claims (a weaker wording was printed)", m["downgraded"], "not_used", "Claim and printed wording")
    variants_table("3. Omitted claims (no wording is supported)", m["omitted"], "variants", "Claim")

    out.append("<h2>4. Claims that do not apply or were excluded</h2>")
    out.append("<ul>" + "".join(f'<li><code>{e(n["claim_id"])}</code>: {e(n["reason"])}</li>' for n in m["not_applicable"]) + "</ul>"
               if m["not_applicable"] else "<p>None.</p>")
    out.append("<h2>5. DRAFT options chosen (lawyer decisions)</h2><ul>")
    out += [f'<li>{e(o["topic"])}: option <code>{e(o["option_id"])}</code> ({e(o["name"])})'
            + ("" if o["printed"] else ". Prints nothing.") + "</li>" for o in m["draft_options"]]
    out.append("</ul>")
    out.append('<h2>6. Tool categories and uses to confirm against the registry</h2>'
               "<p>The registry schema has no category field. These labels come from the statement inputs.</p>"
               '<div class="wrap"><table><thead><tr><th>Tool id</th><th>Status</th><th>Category printed</th><th>Use printed</th>'
               "<th>Registry purpose</th></tr></thead><tbody>")
    out += [f'<tr><td><code>{e(c["id"])}</code></td><td>{e(c["status"])}</td><td>{e(c["category"] or "MISSING")}</td>'
            f'<td>{e(c["use"] or "MISSING")}</td><td>{e(c["registry_purpose"])}</td></tr>' for c in m["category_check"]]
    out.append("</tbody></table></div>")
    out.append(f'<h2>7. Proposal paragraph</h2><p>{e(m["proposal"]["text"])}</p>'
               f'<p class="meta">{m["proposal"]["words"]} words. Sentences: '
               + ", ".join(f'<code>{e(s["claim_id"])}</code>' for s in m["proposal"]["sentences"]) + ".</p>")
    out.append("</main></body></html>\n")
    return "\n".join(out)
