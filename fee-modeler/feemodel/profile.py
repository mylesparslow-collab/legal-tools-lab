"""Profile an export against the canonical schema before any modeling.

Run this first on any new export. It reports what is missing, what failed to parse, and what
would make the model's output wrong or low confidence. It does not model anything.
"""

import csv
import os
from decimal import Decimal

from .comps import DEFAULT_MIN_COMPS
from .loader import load_dataset, load_mapping
from .money import ZERO
from .schema import SCHEMA, OPTIONAL_TABLES

OPTIONAL_CONSEQUENCES = {
    ("matters", "close_date"): "Closed matters cannot be used as comps and nothing can be back-tested.",
    ("matters", "close_reason"): "Matters settled early or transferred cannot be flagged; they will pull the figures down.",
    ("matters", "forum"): "Comps cannot be narrowed by forum.",
    ("matters", "num_parties"): "Comps cannot be narrowed by number of parties.",
    ("matters", "amount_band"): "Comps cannot be narrowed by amount band.",
    ("matters", "num_units"): "Comps cannot be narrowed by number of units; cost per unit cannot be shown.",
    ("matters", "hearing_occurred"): "Comps cannot be narrowed by whether a hearing occurred.",
    ("matters", "hearing_date"): "The date-window fallback cannot place hearing work; uncoded hearing time lands in other phases.",
    ("matters", "client_id"): "No effect on modeling.",
    ("timekeepers", "effective_from"): "Level changes over time cannot be seen; hours are valued at one level per timekeeper.",
    ("time_entries", "hours_billed"): "Write-downs cannot be shown; billed is assumed equal to worked.",
    ("time_entries", "level"): "Levels come from the timekeepers table instead.",
    ("time_entries", "task_code"): "Every phase figure falls back to date windows (low confidence).",
    ("invoices", "amount_written_off"): "Write-offs cannot be told apart from unpaid balances.",
}


def _check(name, status, detail, **extra):
    out = {"name": name, "status": status, "detail": detail}
    out.update(extra)
    return out


def describe_files(export_dir):
    """Headers of every CSV in a folder, for writing a mapping."""
    out = []
    for name in sorted(os.listdir(export_dir)):
        path = os.path.join(export_dir, name)
        if not os.path.isfile(path) or not name.lower().endswith((".csv", ".txt", ".tsv")):
            continue
        with open(path, newline="", encoding="utf-8-sig") as fh:
            first = fh.readline()
        try:
            delim = csv.Sniffer().sniff(first, delimiters=",;\t|").delimiter
        except csv.Error:
            delim = ","
        out.append({"file": name, "delimiter": delim, "columns": [c.strip().strip('"') for c in first.strip().split(delim)]})
    return out


def profile_export(export_dir, mapping, code_map=None, rate_card=None, cost_rates=None, min_comps=DEFAULT_MIN_COMPS):
    """Return a report dict. report['ready'] is False when anything would block modeling."""
    if isinstance(mapping, str):
        mapping = load_mapping(mapping)
    ds = load_dataset(export_dir, mapping)
    checks = []

    # Tables and columns.
    for table in SCHEMA:
        info = ds.table_info[table]
        if not info["present"]:
            if table in OPTIONAL_TABLES:
                level_mapped = "level" in mapping["tables"].get("time_entries", {}).get("columns", {})
                checks.append(_check("table %s" % table, "ok" if level_mapped else "fail",
                                     "Not provided. Levels are read from each time entry." if level_mapped else
                                     "Not provided and time entries carry no level. One of the two is required."))
            else:
                checks.append(_check("table %s" % table, "fail", "Missing. Map a file to this table."))
            continue
        if info["missing_required"]:
            checks.append(_check("table %s" % table, "fail",
                                 "Required fields missing: %s." % ", ".join(info["missing_required"]),
                                 missing=info["missing_required"]))
        else:
            checks.append(_check("table %s" % table, "ok", "%d rows read, %d loaded."
                                 % (info["rows_read"], info["rows_loaded"])))
        for name in info["missing_optional"]:
            if (table, name) == ("time_entries", "level") and ds.table_info["timekeepers"]["present"]:
                continue
            checks.append(_check("optional field %s.%s" % (table, name), "warn",
                                 "Not provided. %s" % OPTIONAL_CONSEQUENCES.get((table, name), "")))

    # Row-level issues from the loader.
    by_code = {}
    for issue in ds.issues:
        if issue.code in ("missing_table", "missing_column"):
            continue
        slot = by_code.setdefault(issue.code, {"count": 0, "blocking": 0, "examples": []})
        slot["count"] += 1
        slot["blocking"] += 1 if issue.blocking else 0
        if len(slot["examples"]) < 3:
            slot["examples"].append("%s row %s %s: %s" % (issue.table, issue.row, issue.field, issue.problem))
    for code, slot in sorted(by_code.items()):
        read = max(1, sum(i["rows_read"] for i in ds.table_info.values()))
        status = "fail" if slot["blocking"] * 100 > read else "warn"
        checks.append(_check("rows: %s" % code, status,
                             "%d rows affected (%d dropped). More than 1%% of all rows dropped is treated as blocking."
                             % (slot["count"], slot["blocking"]), examples=slot["examples"]))

    matters = ds.matters
    entries_by = ds.entries_by_matter()
    invoices_by = ds.invoices_by_matter()
    closed = [m for m in matters.values() if m.is_closed]

    # History span.
    dates = [e.work_date for e in ds.entries]
    span = {"first_work_date": min(dates) if dates else None, "last_work_date": max(dates) if dates else None}
    if dates:
        years = Decimal((max(dates) - min(dates)).days) / Decimal("365.25")
        checks.append(_check("history span", "ok" if years >= 3 else "warn",
                             "Time entries run from %s to %s (%s years). A walk-forward back-test needs several "
                             "years so that later matters have earlier closed matters to be modeled from."
                             % (min(dates), max(dates), years.quantize(Decimal("0.1")))))

    # Closed matters with no time.
    no_time = [m.matter_id for m in closed if not entries_by.get(m.matter_id)]
    checks.append(_check("closed matters with no time entries", "warn" if no_time else "ok",
                         "%d of %d closed matters have no time. They would look free." % (len(no_time), len(closed)),
                         examples=no_time[:5]))

    # Entries outside the matter's life.
    before = after = 0
    late_matters = set()
    for e in ds.entries:
        m = matters[e.matter_id]
        if e.work_date < m.open_date:
            before += 1
        elif m.close_date is not None and e.work_date > m.close_date:
            after += 1
            late_matters.add(m.matter_id)
    checks.append(_check("time dated outside the matter's open-to-close dates", "warn" if before or after else "ok",
                         "%d entries before open, %d after close (on %d matters). Late time is included in a matter's "
                         "cost but hidden from the back-test until its date has passed."
                         % (before, after, len(late_matters)), examples=sorted(late_matters)[:5]))

    # Billed above worked, zero rates.
    over = sum(1 for e in ds.entries if e.hours_billed > e.hours_worked)
    zero = sum(1 for e in ds.entries if e.rate == 0)
    checks.append(_check("billed hours above worked hours", "warn" if over else "ok",
                         "%d entries. Check for write-ups or swapped columns." % over))
    checks.append(_check("zero-rate entries", "warn" if zero else "ok",
                         "%d entries. Hours still count toward normalized value; raw value will look low." % zero))

    # Task codes.
    if code_map is not None and ds.entries:
        total_h = sum((e.hours_worked for e in ds.entries), ZERO)
        blank_h = sum((e.hours_worked for e in ds.entries if not e.task_code), ZERO)
        unmapped = {}
        unmapped_h = ZERO
        for e in ds.entries:
            if e.task_code and code_map.phase_for(e.task_code) is None:
                unmapped[e.task_code] = unmapped.get(e.task_code, 0) + 1
                unmapped_h += e.hours_worked
        coded_pct = ((total_h - blank_h - unmapped_h) * 100 / total_h).quantize(Decimal("1")) if total_h else ZERO
        checks.append(_check("task code coverage", "ok" if coded_pct >= 80 else "warn",
                             "%s%% of hours carry a task code that maps to a phase. The rest use the date-window "
                             "fallback." % coded_pct, coded_hours_pct=coded_pct,
                             unmapped_codes=dict(sorted(unmapped.items()))))
        if unmapped:
            checks.append(_check("task codes not in the phase map", "warn",
                                 "%d distinct codes on %d entries: %s. Add them to the task code map."
                                 % (len(unmapped), sum(unmapped.values()), ", ".join(sorted(unmapped)[:10]))))

    # Levels against the rate files.
    levels = sorted({e.level for e in ds.entries})
    for label, table in (("rate card", rate_card), ("cost rates", cost_rates)):
        if table is None:
            continue
        missing = [lv for lv in levels if lv not in table]
        checks.append(_check("levels covered by %s" % label, "fail" if missing else "ok",
                             ("Levels with no rate: %s." % ", ".join(missing)) if missing else
                             "All %d levels found in the data have a rate." % len(levels)))
    held = {}
    for e in ds.entries:
        held.setdefault(e.timekeeper_id, set()).add(e.level)
    changed = sorted(tk for tk, lv in held.items() if len(lv) > 1)
    checks.append(_check("timekeepers who changed level", "ok",
                         "%d timekeepers have time at more than one level: %s. Each entry is valued at the level held "
                         "on its work date." % (len(changed), ", ".join(changed[:10]) or "none"),
                         timekeepers=changed))

    # Close reasons.
    if closed:
        no_reason = sum(1 for m in closed if m.close_reason is None)
        abnormal = sum(1 for m in closed if m.is_abnormal_close)
        checks.append(_check("close reasons", "warn" if no_reason else "ok",
                             "%d of %d closed matters have no close reason; %d closed abnormally and are excluded "
                             "from comps by default." % (no_reason, len(closed), abnormal)))

    # Invoices against time, and unpaid balances on closed matters.
    unpaid, unreconciled = [], []
    for m in closed:
        invs = invoices_by.get(m.matter_id, [])
        billed_time = sum((e.amount_billed for e in entries_by.get(m.matter_id, [])), ZERO)
        invoiced = sum((i.amount_billed for i in invs), ZERO)
        collected = sum((i.amount_collected for i in invs), ZERO)
        written = sum((i.amount_written_off or ZERO for i in invs), ZERO)
        if invoiced - collected - written > Decimal("0.01"):
            unpaid.append(m.matter_id)
        if billed_time > 0 and abs(invoiced - billed_time) * 100 > billed_time:
            unreconciled.append(m.matter_id)
    checks.append(_check("closed matters with an unpaid balance", "warn" if unpaid else "ok",
                         "%d closed matters have fees neither collected nor written off. Collected figures for them "
                         "are not final." % len(unpaid), examples=unpaid[:5]))
    checks.append(_check("invoices reconcile to billed time", "warn" if unreconciled else "ok",
                         "%d closed matters where invoiced fees differ from billed time by more than 1%%. Ask whether "
                         "invoices include costs, flat fees or discounts." % len(unreconciled),
                         examples=unreconciled[:5]))

    # Matter types: is there enough clean history?
    types = []
    for mtype in sorted({m.matter_type for m in matters.values()}):
        ms = [m for m in matters.values() if m.matter_type == mtype]
        clean = [m for m in ms if m.is_closed and not m.is_abnormal_close]
        types.append({"matter_type": mtype, "n_matters": len(ms), "n_open": sum(1 for m in ms if m.status != "closed"),
                      "n_abnormal": sum(1 for m in ms if m.is_abnormal_close), "n_clean_closed": len(clean),
                      "enough_to_model": len(clean) >= min_comps})
    thin = [t["matter_type"] for t in types if not t["enough_to_model"]]
    if types:
        checks.append(_check("matter types with enough clean closed history", "warn" if thin else "ok",
                             "%d of %d matter types have at least %d clean closed matters.%s"
                             % (len(types) - len(thin), len(types), min_comps,
                                (" Too few: %s." % ", ".join(thin)) if thin else "")))

    fails = [c for c in checks if c["status"] == "fail"]
    return {
        "export_dir": export_dir, "mapping": mapping.get("name", ""), "ready": not fails,
        "summary": {"matters": len(matters), "closed_matters": len(closed), "time_entries": len(ds.entries),
                    "invoices": len(ds.invoices), **span},
        "tables": {t: {k: v for k, v in info.items() if k != "header"} for t, info in ds.table_info.items()},
        "checks": checks, "matter_types": types,
        "next_step": ("Run the back-test next: python -m feemodel backtest" if not fails else
                      "Fix the failed checks before modeling. Nothing downstream should be trusted until they pass."),
    }


def format_report(report):
    mark = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL"}
    lines = ["Export profile: %s" % report["export_dir"], "Mapping: %s" % report["mapping"], ""]
    s = report["summary"]
    lines.append("Loaded %d matters (%d closed), %d time entries, %d invoices."
                 % (s["matters"], s["closed_matters"], s["time_entries"], s["invoices"]))
    lines.append("")
    for c in report["checks"]:
        lines.append("[%s] %s: %s" % (mark[c["status"]], c["name"], c["detail"]))
        for ex in c.get("examples", [])[:3]:
            lines.append("         e.g. %s" % ex)
    lines.append("")
    lines.append("Matter types (clean closed = closed normally, usable as comps):")
    for t in report["matter_types"]:
        lines.append("  %-40s clean closed %4d  abnormal %3d  open %3d  %s"
                     % (t["matter_type"], t["n_clean_closed"], t["n_abnormal"], t["n_open"],
                        "enough" if t["enough_to_model"] else "TOO FEW"))
    lines.append("")
    n_fail = sum(1 for c in report["checks"] if c["status"] == "fail")
    n_warn = sum(1 for c in report["checks"] if c["status"] == "warn")
    lines.append("Result: %s (%d failed, %d warnings)." % ("ready to back-test" if report["ready"] else "NOT READY", n_fail, n_warn))
    lines.append(report["next_step"])
    return "\n".join(lines)


def format_unmapped(export_dir):
    lines = ["No mapping given. Files found in %s:" % export_dir, ""]
    for f in describe_files(export_dir):
        lines.append("  %s (delimiter %r)" % (f["file"], f["delimiter"]))
        lines.append("    columns: %s" % ", ".join(f["columns"]))
    lines.append("")
    lines.append("Write a mapping file that points these columns at the canonical fields below,")
    lines.append("then run: python -m feemodel profile <export> --mapping <mapping.json>")
    lines.append("")
    for table, fields in SCHEMA.items():
        lines.append("%s%s" % (table, " (optional if time entries carry a level)" if table in OPTIONAL_TABLES else ""))
        for f in fields:
            lines.append("  %-20s %-8s %s  %s" % (f.name, f.type, "required" if f.required else "optional", f.description))
    return "\n".join(lines)
