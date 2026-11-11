from decimal import Decimal as D

import pytest

from portfolio.ui.formatting import MISSING, decimal_text, money, number, parse_decimal, percent

NBSP = " "


def test_number_uses_the_separators_of_the_locale():
    assert number(1234567.891, "cs", 2) == f"1{NBSP}234{NBSP}567,89"
    assert number(1234567.891, "en", 2) == "1,234,567.89"
    assert number(1234567.891, "de", 1) == "1.234.567,9"
    assert number(1234.5, "cs_CZ") == f"1{NBSP}234"
    assert number(1234.5, "xx", 1) == f"1{NBSP}234,5"
    assert number(None, "cs") == MISSING


def test_signs():
    assert number(12.3, "cs", 1, signed=True) == "+12,3"
    assert number(-12.3, "cs", 1, signed=True) == "-12,3"
    assert number(-0.001, "cs", 1) == "0,0"
    assert number(0.0, "cs", signed=True) == "0"


def test_money_and_percent():
    assert money(-1500.4, "CZK", "cs") == f"-1{NBSP}500{NBSP}CZK"
    assert money(12.345, "USD", "en", 2, signed=True) == f"+12.35{NBSP}USD"
    assert money(None, "CZK", "cs") == MISSING
    assert percent(0.1234, "cs") == f"+12,3{NBSP}%"
    assert percent(-0.05, "en", 2) == f"-5.00{NBSP}%"
    assert percent(None, "cs") == MISSING


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1234.5", "1234.5"),
        ("1 234,5", "1234.5"),
        (f"1{NBSP}234,50", "1234.50"),
        (" 0,00000001 ", "1E-8"),
        ("-3", "-3"),
    ],
)
def test_parse_decimal(text, expected):
    assert parse_decimal(text) == D(expected)


def test_parse_decimal_empty_and_invalid():
    assert parse_decimal("") is None
    assert parse_decimal(None) is None
    assert parse_decimal("   ") is None
    for bad in ("abc", "1.2.3", "NaN", "Infinity", "1,234.5"):
        with pytest.raises(ValueError, match="not a valid price"):
            parse_decimal(bad, "price")


def test_decimal_text_round_trips():
    assert decimal_text(None) == ""
    assert decimal_text(D("1E-8")) == "0.00000001"
    assert decimal_text(D("100.00")) == "100"
    assert decimal_text(D("0.0")) == "0"
    assert parse_decimal(decimal_text(D("51.129"))) == D("51.129")
