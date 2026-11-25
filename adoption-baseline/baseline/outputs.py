"""Write baseline.json, the HTML report and flat CSV files."""
import csv
import json
import os

from .report import render_report

CELL_COLUMNS = ["numerator", "denominator", "people", "rate", "suppressed"]


def _cell(c):
    if c is None:
        return ["", "", "", "", ""]
    rate = "" if c.get("rate") is None else "%.4f" % c["rate"]
    return ["" if c.get("n") is None else c["n"], "" if c.get("d") is None else c["d"],
            "" if c.get("people") is None else c["people"], rate, c.get("suppressed") or ""]


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_outputs(baseline, out_dir, prefix="baseline"):
    os.makedirs(out_dir, exist_ok=True)
    written = []

    def path(name):
        p = os.path.join(out_dir, name)
        written.append(p)
        return p

    with open(path(prefix + ".json"), "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)
        f.write("\n")
    with open(path(prefix + "_report.html"), "w", encoding="utf-8") as f:
        f.write(render_report(baseline))
    _write(path(prefix + "_weekly_trend.csv"),
           ["week", "week_start", "active_lawyers", "eligible_lawyers", "rate", "excluded_not_started",
            "excluded_on_leave", "excluded_left"],
           [[w["week"], w["week_start"], w["n"], w["d"], "" if w["rate"] is None else "%.4f" % w["rate"],
             w["excluded"]["not_started"], w["excluded"]["on_leave"], w["excluded"]["left"]]
            for w in baseline["weekly_trend"]])
    for dim, tb in baseline["breakdowns"].items():
        rows = []
        for r in tb["rows"] + [tb["total"]]:
            for measure, c in r["cells"].items():
                rows.append([tb["population"], r["group"], measure] + _cell(c))
        _write(path("%s_by_%s.csv" % (prefix, dim)), ["population", dim, "measure"] + CELL_COLUMNS, rows)
    rows = []
    for t in baseline["tools"]:
        for measure, c in t["cells"].items():
            rows.append([t["tool"], "" if t["licensed"] is None else t["licensed"], measure] + _cell(c))
    _write(path(prefix + "_tools.csv"), ["tool", "licensed", "measure"] + CELL_COLUMNS, rows)
    tg = baseline["targets"]
    _write(path(prefix + "_targets.csv"),
           ["id", "label", "basis", "threshold", "numerator", "denominator", "people", "rate", "status", "reason"],
           [[t["id"], t["label"], t["basis"], t["threshold"], "" if t["n"] is None else t["n"],
             "" if t["d"] is None else t["d"], "" if t["people"] is None else t["people"],
             "" if t["rate"] is None else "%.4f" % t["rate"], t["status"], t["reason"]]
            for t in tg["targets"] + tg["gates"]])
    rows = []
    for q in baseline["data_quality"]["ingestion"]["sources"]:
        rows.append([q["source"], "rows", "read", q["rows_read"]])
        rows.append([q["source"], "rows", "kept", q["rows_kept"]])
        for group in ("dropped", "repaired", "flagged_but_kept"):
            rows += [[q["source"], group, k, v] for k, v in q[group].items()]
    _write(path(prefix + "_data_quality.csv"), ["source", "kind", "item", "rows"], rows)
    s = baseline.get("survey")
    if s:
        rows = []
        for scope, items in (("practice", s["by_practice"]), ("role", s["by_role"]), ("all lawyers", [s["overall"]])):
            for r in items:
                rows.append([scope, r["group"]] + _cell(r["claimed"])[:2] + _cell(r["logged"])[:2]
                            + ["" if r["gap_points"] is None else r["gap_points"], r["claimed"].get("suppressed") or ""])
        _write(path(prefix + "_survey_vs_log.csv"),
               ["scope", "group", "survey_claimed", "survey_respondents", "logged_active", "logged_eligible",
                "gap_points", "suppressed"], rows)
        rows = []
        for qid, t in s["tallies"].items():
            for k, v in t["counts"].items():
                rows.append([qid, k, t["labels"][k], "" if v is None else v, t["answered"], "" if v is not None else "small_group"])
        _write(path(prefix + "_survey_tallies.csv"), ["question", "option", "label", "responses", "answered", "suppressed"], rows)
    return written


def write_individuals(analysis, out_dir, prefix="baseline"):
    """Per-person file. Only called when the user asks for it explicitly."""
    rows = analysis.individual_rows()
    p = os.path.join(out_dir, prefix + "_individual_activity.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["person_id"])
        w.writeheader()
        w.writerows(rows)
    return p
