#!/usr/bin/env python3
"""AI Tool Registry: validate a registry file, flag gaps, render a one-page view.

Usage:
  python3 registry.py check  REGISTRY.json            validate and list flags (exit 1 on errors)
  python3 registry.py render REGISTRY.json --out DIR  write registry.html, registry.md, registry.csv

A registry file follows registry.schema.json. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "registry.schema.json"
_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
          "boolean": bool, "null": type(None)}


# ---------- validation (the subset of JSON Schema that registry.schema.json uses) ----------

def _is_type(value, name: str) -> bool:
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def validate(value, schema: dict, path: str = "$") -> list[str]:
    errors: list[str] = []
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        if not any(_is_type(value, t) for t in types):
            return [f"{path}: expected {' or '.join(types)}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: '{value}' is not one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: '{value}' does not match {schema['pattern']}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: '{value}' is not a date (YYYY-MM-DD)")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        for i, item in enumerate(value):
            errors += validate(item, schema.get("items", {}), f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing '{req}'")
        for k, v in value.items():
            if k in props:
                errors += validate(v, props[k], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unknown field '{k}'")
    return errors


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------- flags ----------

LIVE = {"pilot", "production"}


def tool_flags(tool: dict, reg: dict) -> list[str]:
    """Plain-language gaps for one tool. Empty list means nothing to chase."""
    flags: list[str] = []
    as_of = date.fromisoformat(reg["as_of"])
    live = tool["status"] in LIVE
    if tool["business_owner"].strip().lower() in ("to be assigned", "tbd", "none", "unassigned"):
        flags.append("No business owner.")
    db = tool["data_boundary"]
    if db["used_for_training"] != "no":
        flags.append("Training use of inputs is not ruled out.")
    sensitive = {"client_confidential", "personal_data", "health_information"} & set(db["data_allowed"])
    ocg = tool["ocg_check"]
    if sensitive and ocg["method"] in ("none", "not_applicable"):
        flags.append("Client or personal data is allowed but there is no outside counsel guideline check.")
    if ocg["method"] in ("automated_gate", "manual_lookup"):
        if not ocg.get("last_checked"):
            flags.append("Outside counsel guideline check has no date.")
        else:
            age = (as_of - date.fromisoformat(ocg["last_checked"])).days
            limit = reg.get("ocg_check_max_age_days", 90)
            if age > limit:
                flags.append(f"Outside counsel guideline check is {age} days old (limit {limit}).")
    if "health_information" in db["data_allowed"] and not any(
            "business associate" in a.lower() or "baa" in a.lower() for a in db.get("agreements", [])):
        flags.append("Health information is allowed but no business associate agreement is listed.")
    gs = tool["golden_set"]
    if gs["status"] == "not_run" and live:
        flags.append("In use without a golden-set score.")
    if gs["status"] == "scored":
        if gs.get("passes") is False:
            flags.append("Golden-set score is below the pass mark.")
        if gs.get("passes") is None or gs.get("high_severity_recall") is None or gs.get("quote_grounding") is None:
            flags.append("Golden-set score is incomplete.")
    sb = tool["sb574_log"]
    if sb["court_filing_use"] in ("yes", "possible") and sb["mechanism"].strip().lower().startswith("none"):
        flags.append("May be used for court filings but has no citation verification log.")
    if sb["court_filing_use"] == "yes" and not sb.get("disclosure_step"):
        flags.append("Used for court filings but no court disclosure step is recorded.")
    review_age = (as_of - date.fromisoformat(tool["last_review"])).days
    limit = reg.get("review_interval_days", 180)
    if review_age > limit:
        flags.append(f"Last review was {review_age} days ago (interval {limit}).")
    if live and not tool.get("human_review"):
        flags.append("No human review step recorded.")
    return flags


def check(reg: dict) -> tuple[list[str], dict[str, list[str]]]:
    errors = validate(reg, load_schema())
    if errors:
        return errors, {}
    ids = [t["id"] for t in reg["tools"]]
    errors += [f"duplicate tool id '{i}'" for i in sorted({i for i in ids if ids.count(i) > 1})]
    return errors, {t["id"]: tool_flags(t, reg) for t in reg["tools"]}


# ---------- rendering ----------

def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _golden(gs: dict) -> str:
    if gs["status"] == "not_run":
        return "Not run"
    if gs["status"] == "not_applicable":
        return "Not applicable" + (f". {gs['notes']}" if gs.get("notes") else "")
    result = {True: "pass", False: "below pass mark", None: "result not recorded"}[gs.get("passes")]
    out = (f"High-severity recall {_pct(gs.get('high_severity_recall'))}, quote grounding "
           f"{_pct(gs.get('quote_grounding'))}: {result}")
    if gs.get("net_minutes_saved_per_document") is not None:
        out += f". Net {gs['net_minutes_saved_per_document']:+g} min per document (modeled)"
    if gs.get("run_date"):
        out += f". Run {gs['run_date']}"
    if gs.get("notes"):
        out += f". {gs['notes']}"
    return out


def _boundary(db: dict) -> str:
    data = ", ".join(d.replace("_", " ") for d in db["data_allowed"])
    out = (f"Runs in: {db['runs_in']}. Model: {db['model_provider']}. Data allowed: {data}. "
           f"Retention: {db['retention']}. Used for training: {db['used_for_training']}.")
    if db.get("agreements"):
        out += " Agreements: " + "; ".join(db["agreements"]) + "."
    return out


def _ocg(o: dict) -> str:
    label = {"automated_gate": "Automated gate", "manual_lookup": "Manual lookup",
             "not_applicable": "Not applicable", "none": "None"}[o["method"]]
    out = label
    if o.get("description"):
        out += f": {o['description']}"
    if o.get("last_checked"):
        out += f" Last checked {o['last_checked']}."
    if o.get("matters_blocked") is not None:
        out += f" Matters blocked: {o['matters_blocked']}."
    return out


def _sb574(s: dict) -> str:
    out = f"Court filing use: {s['court_filing_use']}. {s['mechanism']}"
    if s.get("log_location"):
        out += f" Log: {s['log_location']}."
    if s.get("disclosure_step"):
        out += f" Disclosure: {s['disclosure_step']}"
    return out


COLUMNS = ["Tool", "Status", "Owner", "Data boundary", "OCG check", "Golden-set score", "SB 574 log", "Last review", "Open flags"]


def rows(reg: dict, flags: dict[str, list[str]]) -> list[list[str]]:
    out = []
    for t in reg["tools"]:
        fl = flags.get(t["id"], []) + [f"Open issue: {i}" for i in t.get("open_issues", [])]
        out.append([f"{t['name']}. {t['purpose']}", t["status"], t["business_owner"], _boundary(t["data_boundary"]),
                    _ocg(t["ocg_check"]), _golden(t["golden_set"]), _sb574(t["sb574_log"]), t["last_review"],
                    " ".join(fl) if fl else "None"])
    return out


def to_markdown(reg: dict, flags: dict[str, list[str]]) -> str:
    L = [f"# AI Tool Registry: {reg['organization']}", "",
         f"Owner: {reg['registry_owner']}. As of {reg['as_of']}. {len(reg['tools'])} tools.", ""]
    if reg.get("notes"):
        L += [reg["notes"], ""]
    L += ["| " + " | ".join(COLUMNS) + " |", "|" + " --- |" * len(COLUMNS)]
    for r in rows(reg, flags):
        L.append("| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in r) + " |")
    return "\n".join(L) + "\n"


def to_csv(reg: dict, flags: dict[str, list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    w.writerows(rows(reg, flags))
    return buf.getvalue()


_CSS = """
:root{--ink:#1c2329;--muted:#55616b;--line:#cfd6db;--bg:#fff;--head:#eef2f4;--flag:#8a3b12}
*{box-sizing:border-box}body{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);
font:13px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:1400px;margin:0 auto}h1{font-size:20px;margin:0 0 4px}p.meta{margin:0 0 4px;color:var(--muted)}
p.note{margin:8px 0 14px;color:var(--muted);max-width:90ch}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:1000px;table-layout:fixed}
th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left;overflow-wrap:anywhere}
th{background:var(--head);font-weight:600}td.flags{color:var(--flag)}td.ok{color:var(--muted)}
col.tool{width:15%}col.s{width:6%}col.o{width:9%}col.d{width:18%}col.c{width:13%}col.g{width:13%}col.l{width:13%}col.r{width:6%}col.f{width:13%}
footer{margin-top:10px;color:var(--muted);font-size:11px}
@media print{@page{size:landscape;margin:10mm}body{padding:0;font-size:8.5pt}table{min-width:0}.wrap{overflow:visible}}
"""


def to_html(reg: dict, flags: dict[str, list[str]]) -> str:
    e = html.escape
    body = []
    for r in rows(reg, flags):
        cells = "".join(f"<td>{e(c)}</td>" for c in r[:-1])
        cls = "ok" if r[-1] == "None" else "flags"
        body.append(f"<tr>{cells}<td class=\"{cls}\">{e(r[-1])}</td></tr>")
    cols = "".join(f'<col class="{c}">' for c in ["tool", "s", "o", "d", "c", "g", "l", "r", "f"])
    head = "".join(f"<th scope=\"col\">{e(c)}</th>" for c in COLUMNS)
    note = f'<p class="note">{e(reg["notes"])}</p>' if reg.get("notes") else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Tool Registry</title><style>{_CSS}</style></head><body><main>
<h1>AI Tool Registry: {e(reg['organization'])}</h1>
<p class="meta">Owner: {e(reg['registry_owner'])}. As of {e(reg['as_of'])}. {len(reg['tools'])} tools.</p>{note}
<div class="wrap"><table><colgroup>{cols}</colgroup><thead><tr>{head}</tr></thead><tbody>
{chr(10).join(body)}
</tbody></table></div>
<footer>Flags are generated by registry.py from the entries above. OCG means a client's outside counsel guidelines.
SB 574 log means the record of attorney verification of AI output and citations (Bus. &amp; Prof. Code § 6068.1; Code Civ. Proc. § 128.7), operative January 1, 2027.</footer>
</main></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate and render an AI Tool Registry file.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("registry")
    r = sub.add_parser("render")
    r.add_argument("registry")
    r.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    reg = json.loads(Path(a.registry).read_text(encoding="utf-8"))
    errors, flags = check(reg)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if a.cmd == "check":
        for t in reg["tools"]:
            fl = flags[t["id"]]
            print(f"{t['id']} [{t['status']}]: " + ("no flags" if not fl else ""))
            for f in fl:
                print(f"  - {f}")
        return 0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "registry.html").write_text(to_html(reg, flags), encoding="utf-8")
    (out / "registry.md").write_text(to_markdown(reg, flags), encoding="utf-8")
    (out / "registry.csv").write_text(to_csv(reg, flags), encoding="utf-8")
    print(f"wrote {out}/registry.html, registry.md, registry.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
