"""Mapping-driven loader.

A mapping file names, for each canonical record type, the source file and how
its columns map onto the canonical field names:

    {"experience": {"file": "matters_export.csv",
                    "fields": {"client_name": "Client", "client_consent": "OK to name?"},
                    "date_format": "%m/%d/%Y", "list_separator": ";",
                    "defaults": {"practice": "general_counsel"}}}

Source files may be JSON (a list of objects) or CSV. Records that fail
validation are rejected and reported; they are not repaired.
"""
import csv
import datetime as dt
import json
import os

from .schemas import SCHEMAS, TRUE_WORDS


class LoadError(Exception):
    pass


def to_bool(value):
    """Strict: only an explicit yes counts. Anything else, including blank, is False."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value == 1
    return str(value).strip().lower() in TRUE_WORDS


def _coerce(value, ftype, date_format, sep):
    if ftype == "bool":
        return to_bool(value)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if ftype == "str":
        return str(value).strip()
    if ftype == "int":
        return int(str(value).strip())
    if ftype == "date":
        s = str(value).strip()
        if date_format:
            return dt.datetime.strptime(s, date_format).date().isoformat()
        return dt.date.fromisoformat(s).isoformat()
    if ftype == "list":
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [v.strip() for v in str(value).split(sep) if v.strip()]
    return value


def map_records(rows, schema_name, spec=None):
    """Map source rows onto a canonical schema. Returns (records, errors)."""
    spec = spec or {}
    fields = spec.get("fields", {})
    defaults = spec.get("defaults", {})
    date_format = spec.get("date_format")
    sep = spec.get("list_separator", ";")
    records, errors = [], []
    seen = set()
    for i, row in enumerate(rows):
        rec, problems = {}, []
        for name, ftype, required, default in SCHEMAS[schema_name]:
            src = fields.get(name, name)
            value = row.get(src)
            if (value is None or value == "") and name in defaults:
                value = defaults[name]
            try:
                value = _coerce(value, ftype, date_format, sep)
            except (ValueError, TypeError):
                problems.append("%s: cannot read %r as %s" % (name, row.get(src), ftype))
                continue
            if value is None:
                if required:
                    problems.append("%s: required field is missing" % name)
                    continue
                value = list(default) if isinstance(default, list) else default
            rec[name] = value
        if not problems and rec.get("id") in seen:
            problems.append("id: duplicate id %s" % rec.get("id"))
        if problems:
            errors.append({"schema": schema_name, "row": i + 1, "id": row.get(fields.get("id", "id")),
                           "problems": problems})
        else:
            seen.add(rec["id"])
            records.append(rec)
    return records, errors


def read_rows(path):
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise LoadError("%s: expected a list of records" % path)
    return data


class Data:
    """Everything the desk reads from the firm's side."""

    def __init__(self):
        self.answers, self.experience, self.bios = [], [], []
        self.rate_schedules, self.references, self.forms = [], [], []
        self.facts, self.workplan = {}, {}
        self.errors = []
        self.data_dir = ""

    def bio(self, bio_id):
        return next((b for b in self.bios if b["id"] == bio_id), None)


def load_data(data_dir, mapping_path=None):
    """Load the library from data_dir using mapping.json (or the mapping given)."""
    mapping_path = mapping_path or os.path.join(data_dir, "mapping.json")
    with open(mapping_path, encoding="utf-8") as f:
        mapping = json.load(f)
    d = Data()
    d.data_dir = data_dir
    targets = {"past_answers": "answers", "experience": "experience", "bios": "bios",
               "rate_schedules": "rate_schedules", "references": "references", "standard_forms": "forms"}
    for schema_name, attr in targets.items():
        spec = mapping.get(schema_name)
        if not spec:
            raise LoadError("mapping has no entry for %s" % schema_name)
        rows = read_rows(os.path.join(data_dir, spec["file"]))
        recs, errs = map_records(rows, schema_name, spec)
        setattr(d, attr, recs)
        d.errors += errs
    # answers filed by the harvest command are kept in canonical form next to the library
    harvested = os.path.join(data_dir, "harvested_answers.json")
    if os.path.exists(harvested):
        recs, errs = map_records(read_rows(harvested), "past_answers")
        known = {a["id"] for a in d.answers}
        d.answers += [r for r in recs if r["id"] not in known]
        d.errors += errs
    for key in ("firm_facts", "workplan"):
        spec = mapping.get(key)
        if not spec:
            raise LoadError("mapping has no entry for %s" % key)
        with open(os.path.join(data_dir, spec["file"]), encoding="utf-8") as f:
            setattr(d, "facts" if key == "firm_facts" else "workplan", json.load(f))
    for need in ("as_of", "firm_name", "founded_year", "attorney_count", "offices"):
        if need not in d.facts:
            raise LoadError("firm_facts is missing %s" % need)
    return d
