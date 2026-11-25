"""Mapping-driven ingestion of usage exports into one canonical table.

Canonical day table, one row per person, day, tool and feature:

    person_id, date (YYYY-MM-DD), tool, feature, interactions

Nothing here knows any vendor's export layout. A JSON mapping file says which
column holds the user, the date and the counts. Every row that is dropped or
repaired is counted, and rows read always equals rows kept plus rows dropped.
"""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from .roster import normalise_identifier

DROP_REASONS = ("blank_row", "missing_user", "bad_date", "bad_count", "zero_count", "duplicate",
                "conflicting_duplicate", "unknown_user", "ambiguous_user", "outside_period")
REPAIR_KINDS = ("identifier_repaired", "unmapped_feature")
FLAG_KINDS = ("usage_without_licence", "usage_before_start_date", "usage_after_end_date")
CANONICAL_COLUMNS = ("person_id", "date", "tool", "feature", "interactions")


class MappingError(ValueError):
    pass


def load_mapping(path):
    with open(path, encoding="utf-8") as f:
        mapping = json.load(f)
    validate_mapping(mapping)
    return mapping


def validate_mapping(m):
    for key in ("source", "tool", "shape", "user", "date"):
        if key not in m:
            raise MappingError("mapping is missing %r" % key)
    if m["shape"] not in ("long", "wide"):
        raise MappingError("shape must be 'long' or 'wide'")
    if m["user"].get("match_on") not in ("email", "name", "person_id"):
        raise MappingError("user.match_on must be email, name or person_id")
    if not m["date"].get("formats"):
        raise MappingError("date.formats must list at least one format")
    tz = m["date"].get("timezone", "as_given")
    if tz not in ("as_given", "convert"):
        raise MappingError("date.timezone must be 'as_given' or 'convert'")
    if tz == "convert" and "target_utc_offset_minutes" not in m["date"]:
        raise MappingError("date.timezone 'convert' needs target_utc_offset_minutes")
    if m["shape"] == "wide" and not m.get("feature_columns"):
        raise MappingError("a wide mapping needs feature_columns")
    if m["shape"] == "long" and "feature" not in m:
        raise MappingError("a long mapping needs feature")


def required_columns(m):
    cols = [m["user"]["column"], m["date"]["column"]]
    if m["shape"] == "wide":
        cols += list(m["feature_columns"])
    else:
        if m["feature"].get("column"):
            cols.append(m["feature"]["column"])
        if (m.get("count") or {}).get("column"):
            cols.append(m["count"]["column"])
    cols += [c for c in m.get("dedupe_key", []) if c not in cols]
    return cols


def parse_date(text, spec):
    """Parse a date or timestamp using only the formats listed in the mapping.

    Returns (date, format used). Raises ValueError if no format fits.
    With timezone 'as_given' the calendar date is taken as written, whatever
    offset the timestamp carries. With 'convert' a timestamp that carries an
    offset is first moved to target_utc_offset_minutes.
    """
    text = text.strip()
    if not text:
        raise ValueError("blank date")
    for fmt in spec["formats"]:
        try:
            if fmt == "iso8601":
                dt = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
            else:
                dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if spec.get("timezone", "as_given") == "convert" and dt.tzinfo is not None:
            dt = dt.astimezone(timezone(timedelta(minutes=spec["target_utc_offset_minutes"])))
        return dt.date(), fmt
    raise ValueError("no listed format fits %r" % text)


def parse_count(text):
    """Blank means zero. Anything else must be a whole number, zero or more."""
    text = str(text).strip()
    if text == "":
        return 0
    value = float(text)          # raises ValueError for text
    if value < 0 or value != int(value):
        raise ValueError("count must be a whole number, zero or more")
    return int(value)


def new_quality(mapping, path):
    return {
        "source": mapping["source"],
        "tool": mapping["tool"],
        "file": str(path),
        "rows_read": 0,
        "rows_kept": 0,
        "interactions_kept": 0,
        "dropped": {k: 0 for k in DROP_REASONS},
        "repaired": {k: 0 for k in REPAIR_KINDS},
        "flagged_but_kept": {k: 0 for k in FLAG_KINDS},
        "unknown_user_distinct_identifiers": 0,
        "unknown_user_interactions": 0,
        "unmapped_feature_values": [],
        "date_formats_used": {},
        "first_date_kept": None,
        "last_date_kept": None,
    }


def ingest_file(path, mapping, roster, period=None):
    """Read one export. Returns (events, quality, unknown identifiers).

    events are canonical rows before daily aggregation. Checks run in a fixed
    order and the first failing check decides the drop reason:
    blank row, missing user, bad date, bad count, zero count, duplicate,
    unknown or ambiguous user, outside period.
    """
    validate_mapping(mapping)
    q = new_quality(mapping, path)
    user_col, date_col = mapping["user"]["column"], mapping["date"]["column"]
    match_on = mapping["user"]["match_on"]
    tool = mapping["tool"]
    dedupe_cols = mapping.get("dedupe_key", [])
    events, unknown = [], Counter()
    seen = {}
    unmapped, formats = Counter(), Counter()
    with open(path, newline="", encoding=mapping.get("encoding", "utf-8-sig")) as f:
        reader = csv.DictReader(f, delimiter=mapping.get("delimiter", ","))
        missing = [c for c in required_columns(mapping) if c not in (reader.fieldnames or [])]
        if missing:
            raise MappingError("%s: mapping %r names columns that are not in the file: %s. Columns found: %s"
                               % (path, mapping["source"], ", ".join(missing),
                                  ", ".join(reader.fieldnames or [])))
        for row in reader:
            q["rows_read"] += 1
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                q["dropped"]["blank_row"] += 1
                continue
            raw_user = row[user_col] or ""
            if not raw_user.strip():
                q["dropped"]["missing_user"] += 1
                continue
            try:
                day, fmt = parse_date(row[date_col] or "", mapping["date"])
            except ValueError:
                q["dropped"]["bad_date"] += 1
                continue
            try:
                pairs, row_unmapped = _row_counts(row, mapping)
            except ValueError:
                q["dropped"]["bad_count"] += 1
                continue
            total = sum(c for _, c in pairs)
            if total == 0:
                q["dropped"]["zero_count"] += 1
                continue
            if dedupe_cols:
                key = tuple(normalise_identifier(raw_user) if c == user_col else
                            day.isoformat() if c == date_col else (row[c] or "").strip()
                            for c in dedupe_cols)
                content = (normalise_identifier(raw_user), day, tuple(sorted(pairs)))
                if key in seen:
                    q["dropped"]["duplicate" if seen[key] == content else "conflicting_duplicate"] += 1
                    continue
                seen[key] = content
            person, outcome = roster.lookup(raw_user, match_on)
            if person is None:
                if outcome == "ambiguous":
                    q["dropped"]["ambiguous_user"] += 1
                else:
                    q["dropped"]["unknown_user"] += 1
                    unknown[normalise_identifier(raw_user)] += 1
                    q["unknown_user_interactions"] += total
                continue
            if period and not (period[0] <= day <= period[1]):
                q["dropped"]["outside_period"] += 1
                continue
            q["rows_kept"] += 1
            q["interactions_kept"] += total
            formats[fmt] += 1
            if outcome == "repaired":
                q["repaired"]["identifier_repaired"] += 1
            if row_unmapped:
                q["repaired"]["unmapped_feature"] += 1
                unmapped.update(row_unmapped)
            if not person.licences.get(tool, False):
                q["flagged_but_kept"]["usage_without_licence"] += 1
            if day < person.start_date:
                q["flagged_but_kept"]["usage_before_start_date"] += 1
            if person.end_date is not None and day > person.end_date:
                q["flagged_but_kept"]["usage_after_end_date"] += 1
            iso = day.isoformat()
            q["first_date_kept"] = min(q["first_date_kept"] or iso, iso)
            q["last_date_kept"] = max(q["last_date_kept"] or iso, iso)
            for feature, count in pairs:
                if count:
                    events.append({"person_id": person.person_id, "date": iso, "tool": tool,
                                   "feature": feature, "interactions": count})
    q["unknown_user_distinct_identifiers"] = len(unknown)
    q["unmapped_feature_values"] = sorted(unmapped)
    q["date_formats_used"] = dict(sorted(formats.items()))
    q["rows_dropped"] = sum(q["dropped"].values())
    return events, q, unknown


def _row_counts(row, mapping):
    """Return ([(feature, count)], [raw feature values that were not in the map])."""
    if mapping["shape"] == "wide":
        return [(feature, parse_count(row[col] or "")) for col, feature in
                mapping["feature_columns"].items()], []
    spec = mapping["feature"]
    count_spec = mapping.get("count") or {}
    count = parse_count(row[count_spec["column"]]) if count_spec.get("column") else int(
        count_spec.get("default", 1))
    default = spec.get("default", "other")
    if not spec.get("column"):
        return [(default, count)], []
    raw = (row[spec["column"]] or "").strip()
    fmap = spec.get("map")
    if fmap is None:
        return [(raw or default, count)], []
    if raw in fmap:
        return [(fmap[raw], count)], []
    return [(default, count)], [raw or "(blank)"]


def to_day_table(events):
    """Sum events to one row per person, date, tool and feature."""
    totals = defaultdict(int)
    for e in events:
        totals[(e["person_id"], e["date"], e["tool"], e["feature"])] += e["interactions"]
    return [dict(zip(CANONICAL_COLUMNS, key + (n,))) for key, n in sorted(totals.items())]


def ingest_all(sources, roster, period=None):
    """sources is a list of (csv path, mapping dict). Returns (day table, quality, unknown)."""
    events, per_source, unknown = [], [], {}
    for path, mapping in sources:
        ev, q, unk = ingest_file(path, mapping, roster, period)
        events += ev
        per_source.append(q)
        unknown[mapping["source"]] = dict(unk)
    table = to_day_table(events)
    read = sum(q["rows_read"] for q in per_source)
    dropped = sum(q["rows_dropped"] for q in per_source)
    unknown_rows = sum(q["dropped"]["unknown_user"] for q in per_source)
    quality = {
        "sources": per_source,
        "totals": {
            "rows_read": read,
            "rows_kept": sum(q["rows_kept"] for q in per_source),
            "rows_dropped": dropped,
            "rows_repaired": sum(sum(q["repaired"].values()) for q in per_source),
            "unknown_user_rows": unknown_rows,
            "unknown_user_row_share": (unknown_rows / read) if read else None,
            "interactions_kept": sum(q["interactions_kept"] for q in per_source),
            "canonical_rows": len(table),
        },
        "tools_with_no_rows": sorted(set(roster.tools) - {q["tool"] for q in per_source if q["rows_kept"]}),
    }
    return table, quality, unknown


def write_day_table(table, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_COLUMNS)
        w.writeheader()
        w.writerows(table)
