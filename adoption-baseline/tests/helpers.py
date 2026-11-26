"""Small hand-built worlds for unit tests."""
import csv
from datetime import date

from baseline.metrics import Analysis
from baseline.roster import load_roster

TOOLS = [{"name": "Assistant A", "licence_column": "licence_assistant_a"},
         {"name": "Assistant B", "licence_column": "licence_assistant_b"}]
COLUMNS = ["person_id", "name", "email", "role", "practice", "office", "licence_assistant_a",
           "licence_assistant_b", "start_date", "end_date", "leave_periods", "effective_from"]
START, END = date(2026, 9, 7), date(2026, 10, 4)      # four ISO weeks, W37 to W40
MONDAYS = [date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28)]
CONFIG = {"suppression_threshold": 5, "lawyer_roles": ["partner", "counsel", "associate"],
          "regular_use": {"window_weeks": 4, "min_active_weeks": 3}, "unused_licence_days": 30}

MAP_LONG = {"source": "a", "tool": "Assistant A", "shape": "long",
            "user": {"column": "email", "match_on": "email"},
            "date": {"column": "ts", "formats": ["iso8601"], "timezone": "as_given"},
            "feature": {"column": "action", "map": {"chat": "chat"}, "default": "other"},
            "count": {"column": None, "default": 1}, "dedupe_key": ["id"]}
MAP_WIDE = {"source": "b", "tool": "Assistant B", "shape": "wide", "delimiter": ";",
            "user": {"column": "User", "match_on": "name"},
            "date": {"column": "Day", "formats": ["%d/%m/%Y", "%d %b %Y"]},
            "feature_columns": {"Docs": "documents", "Mail": "email"},
            "dedupe_key": ["User", "Day"]}


def person(pid, **kw):
    row = {"person_id": pid, "name": "Person %s" % pid, "email": "%s@firm.example" % pid.lower(),
           "role": "associate", "practice": "P1", "office": "O1", "licence_assistant_a": "yes",
           "licence_assistant_b": "yes", "start_date": "2020-01-06", "end_date": "", "leave_periods": "",
           "effective_from": ""}
    row.update(kw)
    return row


def make_roster(tmp_path, rows, name="roster.csv"):
    path = tmp_path / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return load_roster(str(path), TOOLS)


def write_csv(tmp_path, name, header, rows, delimiter=","):
    path = tmp_path / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


def use(pid, day, tool="Assistant A", feature="chat", n=1):
    return {"person_id": pid, "date": day, "tool": tool, "feature": feature, "interactions": n}


def make_analysis(tmp_path, rows, usage, config=None, start=START, end=END):
    cfg = dict(CONFIG)
    cfg.update(config or {})
    return Analysis(make_roster(tmp_path, rows), usage, cfg, start, end)
