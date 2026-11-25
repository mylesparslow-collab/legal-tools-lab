"""Drift check: is a statement that was already issued still true of the current registry?"""
from __future__ import annotations

from datetime import date

from . import evidence
from .build import BuildError, base_slots, build_statement, make_context, render_text
from .model import LIVE_STATUSES, InputError, sha256_json, validate_registry

STILL_TRUE = "STILL TRUE"
NO_LONGER = "NO LONGER SUPPORTED"
CANNOT_TELL_NOW = "CANNOT TELL NOW"
FIGURES_CHANGED = "FIGURES CHANGED"
NOT_CHECKED = "NOT CHECKED"
DRIFT_STATUSES = (NO_LONGER, CANNOT_TELL_NOW, FIGURES_CHANGED)


def check_statement(stmt: dict, registry: dict, as_of: date) -> dict:
    """Re-evaluate every printed sentence, using the rule stored when the statement was issued."""
    if stmt.get("schema") != "client-ai-statement/1":
        raise InputError("not a statement.json written by this tool")
    validate_registry(registry)
    ctx = make_context(registry, stmt["inputs"], stmt["client"], as_of, stmt["scopes"])
    slots = base_slots(ctx)
    rows = []
    for sec in stmt["sections"]:
        for s in sec["sentences"]:
            row = {"section": sec["label"], "claim_id": s["claim_id"], "variant_id": s["variant_id"],
                   "text": s["text"], "status": NOT_CHECKED, "detail": [], "text_now": None}
            if not s.get("rule"):
                row["detail"] = ["Policy wording or placeholder with no registry rule."]
            else:
                result = evidence.evaluate_rule(s["rule"], ctx)
                if result["status"] == evidence.NOT_SUPPORTED:
                    row["status"] = NO_LONGER
                elif result["status"] == evidence.CANNOT_TELL:
                    row["status"] = CANNOT_TELL_NOW
                else:
                    now = render_text(s["template"], slots, result)
                    row["status"] = STILL_TRUE if now == s["text"] else FIGURES_CHANGED
                    if now != s["text"]:
                        row["text_now"] = now
                        row["detail"] = [f"The registry now supports this wording instead: {now}"]
                broken = row["status"] in (NO_LONGER, CANNOT_TELL_NOW)
                for r in result["failing"] if broken else []:
                    row["detail"].append(f"{r['entry']}: {r['expected']}; found {r['actual']!r}"
                                         + (f" ({r['reason']})" if r.get("reason") else ""))
                for r in result["unknown"] if broken else []:
                    row["detail"].append(f"{r['entry']}: {r['expected']}; cannot tell"
                                         + (f" ({r['reason']})" if r.get("reason") else ""))
                if result["note"] and row["status"] != STILL_TRUE:
                    row["detail"].append(result["note"])
            rows.append(row)

    now_in_use = [t["id"] for t in registry["tools"] if t["status"] in LIVE_STATUSES]
    info = []
    added = [t for t in now_in_use if t not in stmt["tools_in_use"]]
    removed = [t for t in stmt["tools_in_use"] if t not in now_in_use]
    if added:
        info.append("Tools now in use that were not in use when the statement was issued: " + ", ".join(added) + ".")
    if removed:
        info.append("Tools in use when the statement was issued that are no longer in use: " + ", ".join(removed) + ".")
    if sha256_json(registry) == stmt["registry_sha256"]:
        info.append("The registry file is identical to the one the statement was built from; only the as-of date differs.")
    try:
        fresh = build_statement(registry, stmt["inputs"], as_of, stmt["client"])
        then = {s["claim_id"]: s["variant_id"] for sec in stmt["sections"] for s in sec["sentences"]}
        now = {s["claim_id"]: s["variant_id"] for sec in fresh["sections"] for s in sec["sentences"]}
        for cid, vid in now.items():
            if cid not in then and cid != "(none)":
                info.append(f"A rebuild would add claim '{cid}' (variant '{vid}').")
            elif cid in then and then[cid] != vid:
                info.append(f"A rebuild would print claim '{cid}' as variant '{vid}' instead of '{then[cid]}'.")
    except (BuildError, InputError) as ex:
        info.append(f"A rebuild from the current registry fails: {ex}")

    drifted = [r for r in rows if r["status"] in DRIFT_STATUSES]
    return {"statement_as_of": stmt["as_of"], "statement_version": stmt["version"], "statement_status": stmt["status"],
            "checked_as_of": as_of.isoformat(), "registry_as_of": registry["as_of"],
            "rows": rows, "info": info, "drift": bool(drifted), "drift_count": len(drifted)}


def report_md(report: dict) -> str:
    L = ["# Drift check", "",
         f"Statement dated {report['statement_as_of']} (version {report['statement_version']}, {report['statement_status']}) "
         f"checked against the registry dated {report['registry_as_of']}, as of {report['checked_as_of']}.", ""]
    if report["drift"]:
        L += [f"**RESULT: {report['drift_count']} printed sentence(s) are no longer backed by the registry. "
              "Withdraw or reissue the statement.**", ""]
    else:
        L += ["**RESULT: every printed sentence with a registry rule is still supported.**", ""]
    for status in DRIFT_STATUSES:
        hits = [r for r in report["rows"] if r["status"] == status]
        if hits:
            L += [f"## {status}", ""]
            for r in hits:
                L += [f"- \"{r['text']}\" (`{r['claim_id']} / {r['variant_id']}`, section: {r['section']})"]
                L += [f"  - {d}" for d in r["detail"]]
            L += [""]
    still = [r for r in report["rows"] if r["status"] == STILL_TRUE]
    L += [f"## {STILL_TRUE} ({len(still)})", ""] + [f"- `{r['claim_id']} / {r['variant_id']}`" for r in still] + [""]
    skipped = [r for r in report["rows"] if r["status"] == NOT_CHECKED]
    L += [f"## {NOT_CHECKED} ({len(skipped)})", "",
          "These sentences are policy wording with no registry rule. The registry cannot confirm or contradict them.", ""]
    L += [f"- `{r['claim_id']} / {r['variant_id']}`" for r in skipped] + [""]
    if report["info"]:
        L += ["## Notes", ""] + [f"- {i}" for i in report["info"]] + [""]
    return "\n".join(L)
