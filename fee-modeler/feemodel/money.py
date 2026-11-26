"""Decimal helpers. Money and hours never pass through float."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def D(value):
    """Convert to Decimal. Floats are rejected on purpose."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a number here")
    if isinstance(value, float):
        raise TypeError("floats are not accepted in money or hours paths; pass a string or Decimal")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError("not a decimal number: %r" % value) from exc
    raise TypeError("cannot convert %r to Decimal" % type(value).__name__)


def parse_number(text):
    """Parse a number from export text. Accepts $ signs, thousands commas and (negatives)."""
    if text is None:
        raise ValueError("empty number")
    s = str(text).strip()
    if s == "":
        raise ValueError("empty number")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    if s.startswith("-"):
        negative = not negative
        s = s[1:]
    try:
        value = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("not a number: %r" % text) from exc
    if not value.is_finite():
        raise ValueError("not a finite number: %r" % text)
    return -value if negative else value


def cents(value):
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def tenths(value):
    return D(value).quantize(TENTH, rounding=ROUND_HALF_UP)


def round_to(value, step):
    step = D(step)
    return (D(value) / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


def display_money(value):
    """Rounded for reading: nearest 100 from 10,000 up, nearest 10 below. Exact cents stay in JSON."""
    if value is None:
        return "n/a"
    value = D(value)
    step = Decimal("100") if abs(value) >= Decimal("10000") else Decimal("10")
    rounded = round_to(value, step)
    sign = "-" if rounded < 0 else ""
    return "%s$%s" % (sign, format(int(abs(rounded)), ","))


def display_hours(value):
    if value is None:
        return "n/a"
    value = tenths(value)
    if abs(value) >= 10 or value == 0:
        return format(int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), ",")
    return str(value)


def display_pct(numerator, denominator):
    """Whole percent from a count over a count, with the counts kept visible by the caller."""
    if not denominator:
        return "n/a"
    value = (D(numerator) * HUNDRED / D(denominator)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return "%s%%" % value


def ratio(numerator, denominator, places="0.01"):
    if not denominator:
        return None
    return (D(numerator) / D(denominator)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
