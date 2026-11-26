"""Mapping-driven loader.

Nothing here knows about any particular billing product. A JSON mapping file says which
file and column feeds each canonical field (see schema.py), how dates are written, how
coded values translate, and whether a number needs rescaling (for example minutes to hours).
"""

import csv
import json
import os
from collections import namedtuple
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from .money import D, parse_number
from .schema import SCHEMA, OPTIONAL_TABLES, NORMAL_CLOSE, STATUS_VALUES

Issue = namedtuple("Issue", "code table row field problem blocking")

TRUE_VALUES = {"true", "t", "yes", "y", "1"}
FALSE_VALUES = {"false", "f", "no", "n", "0"}


class MappingError(ValueError):
    pass


@dataclass
class Matter:
    matter_id: str
    matter_type: str
    status: str
    open_date: date
    close_date: Optional[date] = None
    close_reason: Optional[str] = None
    client_id: Optional[str] = None
    forum: Optional[str] = None
    num_parties: Optional[int] = None
    amount_band: Optional[str] = None
    num_units: Optional[int] = None
    hearing_occurred: Optional[bool] = None
    hearing_date: Optional[date] = None

    @property
    def is_closed(self):
        return self.status == "closed" and self.close_date is not None

    @property
    def is_abnormal_close(self):
        return self.is_closed and self.close_reason is not None and self.close_reason != NORMAL_CLOSE


@dataclass
class TimeEntry:
    entry_id: str
    matter_id: str
    timekeeper_id: str
    work_date: date
    hours_worked: Decimal
    rate: Decimal
    hours_billed: Decimal
    level: Optional[str] = None
    task_code: Optional[str] = None
    billed_assumed: bool = False

    @property
    def amount_worked(self):
        return self.hours_worked * self.rate

    @property
    def amount_billed(self):
        return self.hours_billed * self.rate


@dataclass
class Invoice:
    invoice_id: str
    matter_id: str
    invoice_date: date
    amount_billed: Decimal
    amount_collected: Decimal
    amount_written_off: Optional[Decimal] = None


@dataclass
class Dataset:
    matters: dict = dc_field(default_factory=dict)
    entries: list = dc_field(default_factory=list)
    invoices: list = dc_field(default_factory=list)
    level_history: dict = dc_field(default_factory=dict)
    issues: list = dc_field(default_factory=list)
    table_info: dict = dc_field(default_factory=dict)
    mapping_name: str = ""

    def blocking_issues(self):
        return [i for i in self.issues if i.blocking]

    def entries_by_matter(self):
        out = {}
        for e in self.entries:
            out.setdefault(e.matter_id, []).append(e)
        return out

    def invoices_by_matter(self):
        out = {}
        for inv in self.invoices:
            out.setdefault(inv.matter_id, []).append(inv)
        return out


def load_mapping(path):
    with open(path, encoding="utf-8") as fh:
        mapping = json.load(fh)
    if not isinstance(mapping, dict) or "tables" not in mapping:
        raise MappingError("mapping file needs a top-level 'tables' object: %s" % path)
    for table in mapping["tables"]:
        if table not in SCHEMA:
            raise MappingError("mapping names an unknown table %r; known tables: %s"
                               % (table, ", ".join(SCHEMA)))
        tmap = mapping["tables"][table]
        if "file" not in tmap or "columns" not in tmap:
            raise MappingError("mapping for table %r needs 'file' and 'columns'" % table)
        known = {f.name for f in SCHEMA[table]}
        for name in tmap["columns"]:
            if name not in known:
                raise MappingError("mapping for table %r names an unknown canonical field %r" % (table, name))
    return mapping


def read_raw(export_dir, tmap):
    """Return (header, rows) for one mapped file, or (None, None) when the file is absent."""
    path = os.path.join(export_dir, tmap["file"])
    if not os.path.isfile(path):
        return None, None
    with open(path, newline="", encoding=tmap.get("encoding", "utf-8-sig")) as fh:
        reader = csv.DictReader(fh, delimiter=tmap.get("delimiter", ","))
        header = [h.strip() for h in (reader.fieldnames or [])]
        rows = []
        for raw in reader:
            rows.append({(k or "").strip(): (v if v is not None else "") for k, v in raw.items()})
    return header, rows


def _convert_value(ftype, text, tmap, name):
    """Convert one cell. Returns the value or None for blank. Raises ValueError on bad input."""
    s = (text or "").strip()
    if s == "" or s.upper() in set(tmap.get("null_values", [])):
        return None
    if ftype == "str":
        vmap = tmap.get("value_maps", {}).get(name)
        if vmap is not None:
            if s in vmap:
                return vmap[s]
            lowered = {k.lower(): v for k, v in vmap.items()}
            if s.lower() in lowered:
                return lowered[s.lower()]
            raise ValueError("value %r is not in the mapping's value_maps for %s" % (s, name))
        return s
    if ftype == "date":
        fmt = tmap.get("date_format", "%Y-%m-%d")
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError as exc:
            raise ValueError("date %r does not match format %s" % (s, fmt)) from exc
    if ftype == "decimal":
        value = parse_number(s)
        scale = tmap.get("scale", {}).get(name)
        if scale:
            if "divide_by" in scale:
                value = value / D(str(scale["divide_by"]))
            if "multiply_by" in scale:
                value = value * D(str(scale["multiply_by"]))
        return value
    if ftype == "int":
        value = parse_number(s)
        if value != value.to_integral_value():
            raise ValueError("expected a whole number, got %r" % s)
        return int(value)
    if ftype == "bool":
        trues = {v.lower() for v in tmap.get("true_values", [])} or TRUE_VALUES
        falses = {v.lower() for v in tmap.get("false_values", [])} or FALSE_VALUES
        if s.lower() in trues:
            return True
        if s.lower() in falses:
            return False
        raise ValueError("cannot read %r as yes/no" % s)
    raise ValueError("unknown field type %s" % ftype)


def convert_table(table, tmap, header, rows, issues):
    """Turn raw rows into canonical dicts. Rows missing a required value are dropped with an issue."""
    columns = tmap["columns"]
    missing_required = []
    missing_optional = []
    for f in SCHEMA[table]:
        src = columns.get(f.name)
        if src is None or src not in header:
            (missing_required if f.required else missing_optional).append(f.name)
            if src is not None and src not in header:
                issues.append(Issue("missing_column", table, None, f.name,
                                    "mapped column %r is not in %s" % (src, tmap["file"]), f.required))
            elif f.required:
                issues.append(Issue("missing_column", table, None, f.name,
                                    "required field is not mapped to any column", True))
    out = []
    if missing_required:
        return out, missing_required, missing_optional
    for n, raw in enumerate(rows, start=2):  # row 1 is the header
        rec = {}
        ok = True
        for f in SCHEMA[table]:
            src = columns.get(f.name)
            if src is None or src not in header:
                rec[f.name] = None
                continue
            try:
                value = _convert_value(f.type, raw.get(src, ""), tmap, f.name)
            except ValueError as exc:
                issues.append(Issue("parse_error", table, n, f.name, str(exc), f.required))
                value = None
                if f.required:
                    ok = False
            if value is None and f.required and ok:
                issues.append(Issue("missing_value", table, n, f.name, "required value is blank", True))
                ok = False
            rec[f.name] = value
        if ok:
            rec["_row"] = n
            out.append(rec)
    return out, missing_required, missing_optional


def level_at(history, work_date):
    """Level in force on a date from a list of (effective_from or None, level)."""
    best = None
    best_date = None
    for eff, level in history:
        if eff is None:
            if best is None:
                best = level
        elif eff <= work_date and (best_date is None or eff >= best_date):
            best, best_date = level, eff
    return best


def load_dataset(export_dir, mapping):
    """Load an export through a mapping. Never raises on bad rows: problems go to dataset.issues."""
    if isinstance(mapping, str):
        mapping = load_mapping(mapping)
    ds = Dataset(mapping_name=mapping.get("name", ""))
    issues = ds.issues
    converted = {}
    for table in SCHEMA:
        tmap = mapping["tables"].get(table)
        info = {"file": None, "header": [], "rows_read": 0, "rows_loaded": 0,
                "missing_required": [], "missing_optional": [], "present": False}
        ds.table_info[table] = info
        if tmap is None:
            if table not in OPTIONAL_TABLES:
                issues.append(Issue("missing_table", table, None, None, "table is not in the mapping", True))
            converted[table] = []
            continue
        info["file"] = tmap["file"]
        header, rows = read_raw(export_dir, tmap)
        if header is None:
            issues.append(Issue("missing_table", table, None, None,
                                "file %s not found in %s" % (tmap["file"], export_dir),
                                table not in OPTIONAL_TABLES))
            converted[table] = []
            continue
        info["present"] = True
        info["header"] = header
        info["rows_read"] = len(rows)
        recs, miss_req, miss_opt = convert_table(table, tmap, header, rows, issues)
        info["missing_required"] = miss_req
        info["missing_optional"] = miss_opt
        converted[table] = recs

    # matters
    for rec in converted["matters"]:
        row = rec.pop("_row")
        mid = rec["matter_id"]
        if mid in ds.matters:
            issues.append(Issue("duplicate_id", "matters", row, "matter_id", "duplicate matter %s; first kept" % mid, True))
            continue
        if rec["status"] not in STATUS_VALUES:
            issues.append(Issue("parse_error", "matters", row, "status",
                                "status %r is not open or closed; add a value_maps entry" % rec["status"], True))
            continue
        m = Matter(**rec)
        if m.status == "closed" and m.close_date is None:
            issues.append(Issue("closed_without_close_date", "matters", row, "close_date",
                                "matter %s is closed but has no close date; it cannot be a comp" % mid, False))
        if m.close_date is not None and m.close_date < m.open_date:
            issues.append(Issue("close_before_open", "matters", row, "close_date",
                                "matter %s closes before it opens" % mid, True))
            continue
        ds.matters[mid] = m
    ds.table_info["matters"]["rows_loaded"] = len(ds.matters)

    # timekeeper level history
    for rec in converted["timekeepers"]:
        ds.level_history.setdefault(rec["timekeeper_id"], []).append((rec["effective_from"], rec["level"]))
    ds.table_info["timekeepers"]["rows_loaded"] = len(converted["timekeepers"])

    # time entries
    seen = set()
    for rec in converted["time_entries"]:
        row = rec.pop("_row")
        eid = rec["entry_id"]
        if eid in seen:
            issues.append(Issue("duplicate_id", "time_entries", row, "entry_id", "duplicate entry %s; first kept" % eid, True))
            continue
        seen.add(eid)
        if rec["matter_id"] not in ds.matters:
            issues.append(Issue("orphan_row", "time_entries", row, "matter_id",
                                "entry %s points to unknown matter %s" % (eid, rec["matter_id"]), True))
            continue
        if rec["hours_worked"] < 0 or rec["rate"] < 0:
            issues.append(Issue("negative_value", "time_entries", row, "hours_worked",
                                "entry %s has negative hours or rate; reversals must be netted before loading" % eid, True))
            continue
        assumed = False
        if rec["hours_billed"] is None:
            rec["hours_billed"] = rec["hours_worked"]
            assumed = True
        level = rec["level"]
        if level is None:
            level = level_at(ds.level_history.get(rec["timekeeper_id"], []), rec["work_date"])
            if level is None:
                issues.append(Issue("no_level", "time_entries", row, "level",
                                    "no level for timekeeper %s on %s" % (rec["timekeeper_id"], rec["work_date"]), True))
                continue
        rec["level"] = level
        ds.entries.append(TimeEntry(billed_assumed=assumed, **rec))
    ds.table_info["time_entries"]["rows_loaded"] = len(ds.entries)

    # invoices
    seen = set()
    for rec in converted["invoices"]:
        row = rec.pop("_row")
        iid = rec["invoice_id"]
        if iid in seen:
            issues.append(Issue("duplicate_id", "invoices", row, "invoice_id", "duplicate invoice %s; first kept" % iid, True))
            continue
        seen.add(iid)
        if rec["matter_id"] not in ds.matters:
            issues.append(Issue("orphan_row", "invoices", row, "matter_id",
                                "invoice %s points to unknown matter %s" % (iid, rec["matter_id"]), True))
            continue
        ds.invoices.append(Invoice(**rec))
    ds.table_info["invoices"]["rows_loaded"] = len(ds.invoices)
    return ds


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_rate_card(path):
    """Current standard rate per level, as Decimal. Values must be strings or integers in the file."""
    raw = load_json(path)
    if "current" not in raw:
        raise MappingError("rate card needs a 'current' object of level -> rate: %s" % path)
    return {level: D(str(v)) if not isinstance(v, (int, str)) else D(v) for level, v in _no_floats(raw["current"], path).items()}


def load_cost_rates(path):
    """Internal cost per hour by level. This is a user input; the demo file holds placeholders."""
    raw = load_json(path)
    if "cost_per_hour" not in raw:
        raise MappingError("cost rate file needs a 'cost_per_hour' object of level -> cost: %s" % path)
    return {level: D(v) for level, v in _no_floats(raw["cost_per_hour"], path).items()}


def _no_floats(obj, path):
    for k, v in obj.items():
        if isinstance(v, float):
            raise MappingError("%s: %s is written as a float; write money as a quoted string such as \"410.00\"" % (path, k))
    return obj
