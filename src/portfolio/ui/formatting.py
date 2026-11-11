"""Turning numbers into text and back. No Streamlit here, so it is easy to test."""

from decimal import Decimal, InvalidOperation

# locale -> (thousands separator, decimal separator)
_SEPARATORS = {
    "cs": (" ", ","),
    "sk": (" ", ","),
    "de": (".", ","),
    "en": (",", "."),
}
_DEFAULT = (" ", ",")
MISSING = "–"


def number(value: float | None, locale: str, decimals: int = 0, *, signed: bool = False) -> str:
    if value is None:
        return MISSING
    thousands, decimal = _SEPARATORS.get(locale.split("_")[0].split("-")[0].lower(), _DEFAULT)
    text = f"{value:{'+' if signed else ''},.{decimals}f}"
    if float(text.replace(",", "")) == 0:
        text = text.lstrip("+-")  # no "-0"
    return text.replace(",", "\x00").replace(".", decimal).replace("\x00", thousands)


def money(
    value: float | None, currency: str, locale: str, decimals: int = 0, *, signed: bool = False
) -> str:
    if value is None:
        return MISSING
    return f"{number(value, locale, decimals, signed=signed)} {currency}"


def percent(value: float | None, locale: str, decimals: int = 1, *, signed: bool = True) -> str:
    """0.123 -> "+12,3 %"."""
    if value is None:
        return MISSING
    return f"{number(value * 100, locale, decimals, signed=signed)} %"


def parse_decimal(text: str | None, field: str = "number") -> Decimal | None:
    """Accepts "1 234,5" as well as "1234.5". Empty text gives None."""
    cleaned = (text or "").replace(" ", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"'{text}' is not a valid {field}") from None
    if not value.is_finite():
        raise ValueError(f"'{text}' is not a valid {field}")
    return value


def decimal_text(value: Decimal | None) -> str:
    """Exact text for an input box: no exponent, no trailing zeros."""
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
