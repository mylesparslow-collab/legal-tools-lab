"""Invoice readers: a LEDES-1998B-style reader and a plain CSV reader.

The LEDES reader is implemented from memory and has not been checked against
the published specification. FORMAT_NOTES.md lists every assumption.
"""

import csv
import datetime as dt
import io
from decimal import Decimal

from .model import ZERO, DataError, Invoice, Line, dec, parse_iso_date


class ReaderError(DataError):
    """Raised when a file does not match the expected layout."""


LEDES_FIRST_LINE = "LEDES1998B"
LEDES_FIELDS = [
    "INVOICE_DATE",
    "INVOICE_NUMBER",
    "CLIENT_ID",
    "LAW_FIRM_MATTER_ID",
    "INVOICE_TOTAL",
    "BILLING_START_DATE",
    "BILLING_END_DATE",
    "INVOICE_DESCRIPTION",
    "LINE_ITEM_NUMBER",
    "EXP/FEE/INV_ADJ_TYPE",
    "LINE_ITEM_NUMBER_OF_UNITS",
    "LINE_ITEM_ADJUSTMENT_AMOUNT",
    "LINE_ITEM_TOTAL",
    "LINE_ITEM_DATE",
    "LINE_ITEM_TASK_CODE",
    "LINE_ITEM_EXPENSE_CODE",
    "LINE_ITEM_ACTIVITY_CODE",
    "TIMEKEEPER_ID",
    "LINE_ITEM_DESCRIPTION",
    "LAW_FIRM_ID",
    "LINE_ITEM_UNIT_COST",
    "TIMEKEEPER_NAME",
    "TIMEKEEPER_CLASSIFICATION",
    "CLIENT_MATTER_ID",
]
LEDES_KINDS = {"F": "fee", "E": "expense", "IF": "adjustment", "IE": "adjustment"}

CSV_FIELDS = [
    "invoice_id",
    "invoice_date",
    "client_id",
    "matter_id",
    "invoice_total",
    "billing_start",
    "billing_end",
    "line_no",
    "kind",
    "date",
    "timekeeper_id",
    "timekeeper_name",
    "classification",
    "units",
    "rate",
    "adjustment",
    "amount",
    "task_code",
    "activity_code",
    "expense_code",
    "narrative",
    "receipt",
    "cost",
    "ai_assisted",
]
CSV_REQUIRED = [f for f in CSV_FIELDS if f not in ("receipt", "cost", "ai_assisted", "adjustment")]


def _num(text, what, blank_ok=False):
    text = (text or "").strip()
    if not text:
        if blank_ok:
            return ZERO
        raise ReaderError("%s is blank" % what)
    try:
        return dec(text, what)
    except DataError as exc:
        raise ReaderError(str(exc))


def _ledes_date(text, what, blank_ok=False):
    text = (text or "").strip()
    if not text:
        if blank_ok:
            return None
        raise ReaderError("%s is blank" % what)
    if len(text) != 8 or not text.isdigit():
        raise ReaderError("%s: %r is not a YYYYMMDD date" % (what, text))
    try:
        return dt.date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        raise ReaderError("%s: %r is not a valid date" % (what, text))


def _yes_no(text, what):
    text = (text or "").strip().lower()
    if text in ("", "unknown"):
        return None
    if text in ("yes", "y", "true", "1"):
        return True
    if text in ("no", "n", "false", "0"):
        return False
    raise ReaderError("%s: %r is not yes, no or blank" % (what, text))


def _group(rows):
    """Group parsed rows (header dict, Line) into invoices, keeping file order."""
    invoices = {}
    for header, line, where in rows:
        key = header["invoice_id"]
        inv = invoices.get(key)
        if inv is None:
            inv = Invoice(lines=[], **header)
            invoices[key] = inv
        else:
            for name, value in header.items():
                if getattr(inv, name) != value:
                    raise ReaderError(
                        "%s: %s differs from earlier lines of invoice %s"
                        % (where, name, key)
                    )
        if any(existing.line_no == line.line_no for existing in inv.lines):
            raise ReaderError("%s: line number %s is repeated in invoice %s" % (where, line.line_no, key))
        inv.lines.append(line)
    return list(invoices.values())


def read_ledes(text):
    """Read LEDES-1998B-style text. Returns a list of Invoice."""
    text = text.lstrip("﻿")
    records = []
    for raw in text.split("[]"):
        record = raw.replace("\r", "").replace("\n", "").strip()
        if record:
            records.append(record)
    if not text.strip().endswith("[]"):
        raise ReaderError("the last record does not end with []")
    if not records or records[0].upper() != LEDES_FIRST_LINE:
        raise ReaderError("first record must be %s[]" % LEDES_FIRST_LINE)
    if len(records) < 2:
        raise ReaderError("missing header record")
    header_names = [h.strip().upper() for h in records[1].split("|")]
    if header_names != LEDES_FIELDS:
        raise ReaderError(
            "header record does not match the %d expected field names" % len(LEDES_FIELDS)
        )
    rows = []
    for index, record in enumerate(records[2:], start=3):
        where = "record %d" % index
        parts = [p.strip() for p in record.split("|")]
        if len(parts) != len(LEDES_FIELDS):
            raise ReaderError(
                "%s has %d fields, expected %d" % (where, len(parts), len(LEDES_FIELDS))
            )
        f = dict(zip(LEDES_FIELDS, parts))
        kind_code = f["EXP/FEE/INV_ADJ_TYPE"].upper()
        if kind_code not in LEDES_KINDS:
            raise ReaderError("%s: unknown line type %r" % (where, f["EXP/FEE/INV_ADJ_TYPE"]))
        kind = LEDES_KINDS[kind_code]
        try:
            line_no = int(f["LINE_ITEM_NUMBER"])
        except ValueError:
            raise ReaderError("%s: line item number %r is not an integer" % (where, f["LINE_ITEM_NUMBER"]))
        adjustment_only = kind == "adjustment"
        header = {
            "invoice_id": f["INVOICE_NUMBER"],
            "client_id": f["CLIENT_ID"],
            "matter_id": f["LAW_FIRM_MATTER_ID"],
            "invoice_date": _ledes_date(f["INVOICE_DATE"], where + " INVOICE_DATE"),
            "billing_start": _ledes_date(f["BILLING_START_DATE"], where + " BILLING_START_DATE", True),
            "billing_end": _ledes_date(f["BILLING_END_DATE"], where + " BILLING_END_DATE", True),
            "declared_total": _num(f["INVOICE_TOTAL"], where + " INVOICE_TOTAL"),
            "description": f["INVOICE_DESCRIPTION"],
            "source_format": "ledes1998b",
        }
        if not header["invoice_id"]:
            raise ReaderError("%s: INVOICE_NUMBER is blank" % where)
        line = Line(
            line_no=line_no,
            kind=kind,
            date=_ledes_date(f["LINE_ITEM_DATE"], where + " LINE_ITEM_DATE"),
            timekeeper_id=f["TIMEKEEPER_ID"],
            timekeeper_name=f["TIMEKEEPER_NAME"],
            classification=f["TIMEKEEPER_CLASSIFICATION"],
            units=_num(f["LINE_ITEM_NUMBER_OF_UNITS"], where + " LINE_ITEM_NUMBER_OF_UNITS", adjustment_only),
            rate=_num(f["LINE_ITEM_UNIT_COST"], where + " LINE_ITEM_UNIT_COST", adjustment_only),
            adjustment=_num(f["LINE_ITEM_ADJUSTMENT_AMOUNT"], where + " LINE_ITEM_ADJUSTMENT_AMOUNT", True),
            amount=_num(f["LINE_ITEM_TOTAL"], where + " LINE_ITEM_TOTAL"),
            task_code=f["LINE_ITEM_TASK_CODE"],
            activity_code=f["LINE_ITEM_ACTIVITY_CODE"],
            expense_code=f["LINE_ITEM_EXPENSE_CODE"],
            narrative=f["LINE_ITEM_DESCRIPTION"],
        )
        rows.append((header, line, where))
    if not rows:
        raise ReaderError("file has no line items")
    return _group(rows)


def read_csv(text):
    """Read the plain CSV layout described in FORMAT_NOTES.md."""
    text = text.lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ReaderError("file is empty")
    names = [n.strip().lower() for n in reader.fieldnames]
    missing = [f for f in CSV_REQUIRED if f not in names]
    if missing:
        raise ReaderError("missing column(s): %s" % ", ".join(missing))
    rows = []
    for index, raw in enumerate(reader, start=2):
        where = "row %d" % index
        f = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        kind = f["kind"].lower()
        if kind not in ("fee", "expense", "adjustment"):
            raise ReaderError("%s: kind %r is not fee, expense or adjustment" % (where, f["kind"]))
        try:
            line_no = int(f["line_no"])
        except ValueError:
            raise ReaderError("%s: line_no %r is not an integer" % (where, f["line_no"]))
        adjustment_only = kind == "adjustment"
        try:
            header = {
                "invoice_id": f["invoice_id"],
                "client_id": f["client_id"],
                "matter_id": f["matter_id"],
                "invoice_date": parse_iso_date(f["invoice_date"], where + " invoice_date"),
                "billing_start": parse_iso_date(f["billing_start"], where + " billing_start") if f["billing_start"] else None,
                "billing_end": parse_iso_date(f["billing_end"], where + " billing_end") if f["billing_end"] else None,
                "declared_total": _num(f["invoice_total"], where + " invoice_total"),
                "description": "",
                "source_format": "csv",
            }
            line_date = parse_iso_date(f["date"], where + " date")
        except ReaderError:
            raise
        except DataError as exc:
            raise ReaderError(str(exc))
        if not header["invoice_id"]:
            raise ReaderError("%s: invoice_id is blank" % where)
        cost_text = f.get("cost", "")
        line = Line(
            line_no=line_no,
            kind=kind,
            date=line_date,
            timekeeper_id=f["timekeeper_id"],
            timekeeper_name=f["timekeeper_name"],
            classification=f["classification"],
            units=_num(f["units"], where + " units", adjustment_only),
            rate=_num(f["rate"], where + " rate", adjustment_only),
            adjustment=_num(f.get("adjustment", ""), where + " adjustment", True),
            amount=_num(f["amount"], where + " amount"),
            task_code=f["task_code"],
            activity_code=f["activity_code"],
            expense_code=f["expense_code"],
            narrative=f["narrative"],
            receipt=_yes_no(f.get("receipt", ""), where + " receipt"),
            cost=_num(cost_text, where + " cost") if cost_text else None,
            ai_assisted=_yes_no(f.get("ai_assisted", ""), where + " ai_assisted"),
        )
        rows.append((header, line, where))
    if not rows:
        raise ReaderError("file has no line items")
    return _group(rows)


def detect_format(text):
    head = text.lstrip("﻿").lstrip()[:40].upper()
    if head.startswith("LEDES"):
        return "ledes"
    return "csv"


def read_invoice_text(text, fmt="auto"):
    if fmt == "auto":
        fmt = detect_format(text)
    if fmt == "ledes":
        return read_ledes(text)
    if fmt == "csv":
        return read_csv(text)
    raise ReaderError("unknown format %r" % fmt)


def read_invoice_file(path, fmt="auto"):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return read_invoice_text(handle.read(), fmt)


def validate_arithmetic(invoice):
    """Return arithmetic mismatches as plain dicts. The engine turns them into findings.

    Line rule: units x rate + adjustment must equal the line amount within one cent.
    Invoice rule: the sum of line amounts must equal the declared total within one cent.
    """
    tolerance = Decimal("0.01")
    issues = []
    for line in invoice.lines:
        if line.kind == "adjustment":
            continue
        expected = line.units * line.rate + line.adjustment
        diff = line.amount - expected
        if abs(diff) > tolerance:
            issues.append(
                {
                    "scope": "line",
                    "line_no": line.line_no,
                    "expected": expected,
                    "stated": line.amount,
                    "difference": diff,
                }
            )
    total = invoice.line_total
    diff = invoice.declared_total - total
    if abs(diff) > tolerance:
        issues.append(
            {
                "scope": "invoice",
                "line_no": None,
                "expected": total,
                "stated": invoice.declared_total,
                "difference": diff,
            }
        )
    return issues
