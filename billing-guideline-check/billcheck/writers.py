"""Writers for the two invoice layouts. Used by the synthetic data generator and round-trip tests."""

import csv
import io

from .readers import CSV_FIELDS, LEDES_FIELDS, LEDES_FIRST_LINE


def _plain(value):
    return format(value, "f")


def _ymd(value):
    return value.strftime("%Y%m%d") if value else ""


def _yes_no(value):
    if value is None:
        return ""
    return "yes" if value else "no"


def write_ledes(invoices, law_firm_id="FIRM-0001"):
    out = [LEDES_FIRST_LINE + "[]", "|".join(LEDES_FIELDS) + "[]"]
    for inv in invoices:
        for ln in inv.lines:
            kind = {"fee": "F", "expense": "E", "adjustment": "IF"}[ln.kind]
            for text in (ln.narrative, inv.description, ln.timekeeper_name):
                if "|" in text or "[]" in text:
                    raise ValueError("text fields may not contain | or []: %r" % text)
            fields = [
                _ymd(inv.invoice_date),
                inv.invoice_id,
                inv.client_id,
                inv.matter_id,
                _plain(inv.declared_total),
                _ymd(inv.billing_start),
                _ymd(inv.billing_end),
                inv.description,
                str(ln.line_no),
                kind,
                _plain(ln.units),
                _plain(ln.adjustment),
                _plain(ln.amount),
                _ymd(ln.date),
                ln.task_code,
                ln.expense_code,
                ln.activity_code,
                ln.timekeeper_id,
                ln.narrative,
                law_firm_id,
                _plain(ln.rate),
                ln.timekeeper_name,
                ln.classification,
                inv.matter_id,
            ]
            out.append("|".join(fields) + "[]")
    return "\r\n".join(out) + "\r\n"


def write_csv(invoices):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for inv in invoices:
        for ln in inv.lines:
            writer.writerow(
                [
                    inv.invoice_id,
                    inv.invoice_date.isoformat(),
                    inv.client_id,
                    inv.matter_id,
                    _plain(inv.declared_total),
                    inv.billing_start.isoformat() if inv.billing_start else "",
                    inv.billing_end.isoformat() if inv.billing_end else "",
                    ln.line_no,
                    ln.kind,
                    ln.date.isoformat(),
                    ln.timekeeper_id,
                    ln.timekeeper_name,
                    ln.classification,
                    _plain(ln.units),
                    _plain(ln.rate),
                    _plain(ln.adjustment),
                    _plain(ln.amount),
                    ln.task_code,
                    ln.activity_code,
                    ln.expense_code,
                    ln.narrative,
                    _yes_no(ln.receipt),
                    _plain(ln.cost) if ln.cost is not None else "",
                    _yes_no(ln.ai_assisted),
                ]
            )
    return buf.getvalue()
