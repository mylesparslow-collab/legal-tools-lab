from decimal import Decimal

import pytest

from feemodel.money import D, cents, display_hours, display_money, display_pct, parse_number


def test_D_rejects_floats():
    with pytest.raises(TypeError):
        D(0.1)


def test_D_accepts_strings_ints_and_decimals():
    assert D("1.10") == Decimal("1.10")
    assert D(3) == Decimal(3)
    assert D(Decimal("2.5")) is not None


def test_parse_number_handles_currency_text():
    assert parse_number("$1,234.50") == Decimal("1234.50")
    assert parse_number("(250.00)") == Decimal("-250.00")
    assert parse_number(" 42 ") == Decimal("42")


def test_parse_number_rejects_junk():
    for bad in ("", "abc", "NaN", None):
        with pytest.raises(ValueError):
            parse_number(bad)


def test_display_money_rounds_sensibly_not_falsely_precise():
    assert display_money(Decimal("65812.37")) == "$65,800"   # nearest 100 from 10,000 up
    assert display_money(Decimal("6718.49")) == "$6,720"     # nearest 10 below
    assert display_money(Decimal("-12345")) == "-$12,300"


def test_cents_rounds_half_up_and_stays_decimal():
    assert cents("1.005") == Decimal("1.01")
    assert isinstance(cents(Decimal("2")), Decimal)


def test_display_helpers():
    assert display_hours(Decimal("135.6")) == "136"
    assert display_hours(Decimal("9.96")) == "10"
    assert display_hours(Decimal("7.25")) == "7.3"
    assert display_pct(29, 43) == "67%"
    assert display_pct(1, 0) == "n/a"
