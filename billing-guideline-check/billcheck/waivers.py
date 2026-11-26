"""Waivers: a record that the client approved an exception to one rule.

A waiver names the client, matter and rule, who approved it, when, and a
reference (for example an email). It can be narrowed to one timekeeper, one
invoice or one line. It applies to work dated from effective_from (optional)
through expires_on. For findings that are not tied to one entry the invoice
date is used. A waiver past its expiry does not suppress anything; the finding
stays open and says the waiver has expired.
"""

from dataclasses import dataclass
from typing import Optional
import datetime as dt

from .guidelines import loads
from .model import DataError, parse_iso_date

REQUIRED = ("waiver_id", "client_id", "matter_id", "rule_id", "approved_by", "approved_on", "reference", "expires_on")


@dataclass
class Waiver:
    waiver_id: str
    client_id: str
    matter_id: str
    rule_id: str
    approved_by: str
    approved_on: dt.date
    reference: str
    expires_on: dt.date
    effective_from: Optional[dt.date] = None
    timekeeper_id: str = ""
    invoice_id: str = ""
    line_no: Optional[int] = None
    note: str = ""

    def to_dict(self):
        return {
            "waiver_id": self.waiver_id,
            "client_id": self.client_id,
            "matter_id": self.matter_id,
            "rule_id": self.rule_id,
            "approved_by": self.approved_by,
            "approved_on": self.approved_on.isoformat(),
            "reference": self.reference,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "expires_on": self.expires_on.isoformat(),
            "timekeeper_id": self.timekeeper_id,
            "invoice_id": self.invoice_id,
            "line_no": self.line_no,
            "note": self.note,
        }


def waiver_from_dict(data):
    for name in REQUIRED:
        if not str(data.get(name, "")).strip():
            raise DataError("waiver %s: missing %s" % (data.get("waiver_id", "?"), name))
    return Waiver(
        waiver_id=data["waiver_id"],
        client_id=data["client_id"],
        matter_id=data["matter_id"],
        rule_id=data["rule_id"],
        approved_by=data["approved_by"],
        approved_on=parse_iso_date(data["approved_on"], "approved_on"),
        reference=data["reference"],
        expires_on=parse_iso_date(data["expires_on"], "expires_on"),
        effective_from=parse_iso_date(data["effective_from"], "effective_from") if data.get("effective_from") else None,
        timekeeper_id=data.get("timekeeper_id") or "",
        invoice_id=data.get("invoice_id") or "",
        line_no=data.get("line_no"),
        note=data.get("note") or "",
    )


def load_waivers(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = loads(handle.read())
    return [waiver_from_dict(w) for w in data.get("waivers", [])]


def waiver_state(waiver, finding, invoice):
    """Return "applies", "expired" or None (does not match this finding)."""
    if waiver.client_id != invoice.client_id or waiver.matter_id != invoice.matter_id:
        return None
    if waiver.rule_id != finding.rule_id:
        return None
    if waiver.timekeeper_id and waiver.timekeeper_id != finding.timekeeper_id:
        return None
    if waiver.invoice_id and waiver.invoice_id != invoice.invoice_id:
        return None
    if waiver.line_no is not None and waiver.line_no != finding.line_no:
        return None
    work_date = finding.entry_date or invoice.invoice_date
    if waiver.effective_from and work_date < waiver.effective_from:
        return None
    if work_date > waiver.expires_on:
        return "expired"
    return "applies"
