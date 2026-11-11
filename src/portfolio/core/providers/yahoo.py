"""Yahoo Finance through the ``yfinance`` package.

Yahoo has no official API and ``yfinance`` breaks from time to time. Everything that touches
it is in this file, so that is the only place to fix or replace.
"""

import math
import re
from datetime import date

from portfolio.core.providers.base import Bar, ProviderError

# Pairs Yahoo lists under a different symbol than the usual "EURCZK=X".
_FX_SYMBOLS = {("USD", "CZK"): "CZK=X"}
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def fx_symbol(from_currency: str, to_currency: str) -> str:
    return _FX_SYMBOLS.get((from_currency, to_currency), f"{from_currency}{to_currency}=X")


def _number(value, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(number) else number


def bars_from_frame(frame) -> list[Bar]:
    """Convert the table ``yfinance`` returns. Days without a closing price are dropped."""
    bars = []
    for timestamp, row in frame.iterrows():
        close = _number(row.get("Close"))
        if close is None:
            continue
        bars.append(
            Bar(
                date=timestamp.date(),
                close=close,
                open=_number(row.get("Open")),
                high=_number(row.get("High")),
                low=_number(row.get("Low")),
                dividend=_number(row.get("Dividends"), 0.0),
                split=_number(row.get("Stock Splits"), 0.0),
            )
        )
    bars.sort(key=lambda bar: bar.date)
    return bars


class YahooProvider:
    def _history(self, symbol: str, start: date) -> list[Bar]:
        import yfinance  # noqa: PLC0415  (slow import, only needed when updating)

        try:
            # auto_adjust=False gives real closing prices. The adjusted ones are rewritten
            # backwards after every dividend, which would count dividends twice.
            frame = yfinance.Ticker(symbol).history(
                start=start.isoformat(), auto_adjust=False, actions=True, raise_errors=True
            )
        except Exception as e:  # yfinance raises many unrelated types
            raise ProviderError(f"Yahoo: {symbol}: {e}") from e
        return bars_from_frame(frame)

    def prices(self, symbol: str, start: date) -> list[Bar]:
        return self._history(symbol, start)

    def fx_rates(self, from_currency: str, to_currency: str, start: date) -> list[Bar]:
        return self._history(fx_symbol(from_currency, to_currency), start)

    def currency(self, symbol: str) -> str:
        import yfinance  # noqa: PLC0415

        try:
            currency = yfinance.Ticker(symbol).fast_info["currency"]
        except Exception as e:
            raise ProviderError(f"Yahoo: {symbol}: {e}") from e
        if not isinstance(currency, str) or not _CURRENCY_RE.match(currency):
            # For example London shares quoted in pence ("GBp").
            raise ProviderError(
                f"Yahoo: {symbol} is quoted in '{currency}', which is not supported"
            )
        return currency
