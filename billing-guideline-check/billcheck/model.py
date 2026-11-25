"""Internal invoice model. All money and hours are decimal.Decimal."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import List, Optional

CENT = Decimal("0.01")
ZERO = Decimal("0")


class DataError(ValueError):
    """Raised when input data cannot be read into the model."""


def dec(value, what="value"):
    """Convert a str, int or Decimal to Decimal. Binary floats are refused."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise DataError("%s: expected a number, got a boolean" % what)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            result = Decimal(text)
        except InvalidOperation:
            raise DataError("%s: %r is not a number" % (what, value))
        if not result.is_finite():
            raise DataError("%s: %r is not a finite number" % (what, value))
        return result
    raise DataError(
        "%s: %r has type %s; money and hours must be Decimal, int or str"
        % (what, value, type(value).__name__)
    )


def money(value):
    """Round to cents, half up."""
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_money(value):
    return "${:,.2f}".format(money(value))


def fmt_num(value):
    """Plain decimal text without exponent or trailing zeros (2.50 -> 2.5)."""
    value = dec(value)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_iso_date(text, what="date"):
    try:
        return dt.date.fromisoformat(str(text).strip())
    except ValueError:
        raise DataError("%s: %r is not a YYYY-MM-DD date" % (what, text))


@dataclass
class Line:
    line_no: int
    kind: str  # "fee", "expense" or "adjustment"
    date: dt.date
    timekeeper_id: str
    timekeeper_name: str
    classification: str
    units: Decimal  # hours for fees, quantity for expenses
    rate: Decimal  # hourly rate for fees, unit cost for expenses
    adjustment: Decimal
    amount: Decimal
    task_code: str
    activity_code: str
    expense_code: str
    narrative: str
    receipt: Optional[bool] = None  # None means the file does not say
    cost: Optional[Decimal] = None  # what the firm paid, when the file says
    ai_assisted: Optional[bool] = None  # None means the file does not say

    @property
    def hours(self):
        return self.units


@dataclass
class Invoice:
    invoice_id: str
    client_id: str
    matter_id: str
    invoice_date: dt.date
    billing_start: Optional[dt.date]
    billing_end: Optional[dt.date]
    declared_total: Decimal
    description: str = ""
    source_format: str = ""
    lines: List[Line] = field(default_factory=list)

    @property
    def fee_lines(self):
        return [ln for ln in self.lines if ln.kind == "fee"]

    @property
    def expense_lines(self):
        return [ln for ln in self.lines if ln.kind == "expense"]

    @property
    def line_total(self):
        return sum((ln.amount for ln in self.lines), ZERO)
