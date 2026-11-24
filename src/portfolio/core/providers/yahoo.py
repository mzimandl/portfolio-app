"""Yahoo Finance through the ``yfinance`` package.

Yahoo has no official API and ``yfinance`` breaks from time to time. Everything that touches
it is in this file, so that is the only place to fix or replace.
"""

import logging
import math
import re
from datetime import date

from portfolio.core.providers.base import Bar, Company, ProviderError, Ratios, Statement

# yfinance logs every failed lookup itself (for example "HTTP Error 404 ... KRWCZK=X" when a
# pair is not listed and the rate is then worked out through EUR). Failures that matter are
# raised as ProviderError and reported by the app, so its own messages are only noise.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Pairs Yahoo lists under a different symbol than the usual "EURCZK=X".
_FX_SYMBOLS = {("USD", "CZK"): "CZK=X"}
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def fx_symbol(from_currency: str, to_currency: str) -> str:
    return _FX_SYMBOLS.get((from_currency, to_currency), f"{from_currency}{to_currency}=X")


def cross_rates(first: list[Bar], second: list[Bar]) -> list[Bar]:
    """A rate through a third currency: A->B on each day of ``first`` times the latest B->C.

    Days before the first B->C rate are dropped.
    """
    rates = sorted((bar.date, bar.close) for bar in second)
    combined = []
    index = -1
    for bar in sorted(first, key=lambda b: b.date):
        while index + 1 < len(rates) and rates[index + 1][0] <= bar.date:
            index += 1
        if index >= 0:
            combined.append(Bar(bar.date, bar.close * rates[index][1]))
    return combined


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


# Rows of yfinance's statement tables, first choice first.
_INCOME_ROWS = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "net_income": ("Net Income Common Stockholders", "Net Income"),
    "eps": ("Diluted EPS", "Basic EPS"),
}
_BALANCE_ROWS = {
    "equity": ("Stockholders Equity", "Common Stock Equity"),
    "shares": ("Ordinary Shares Number", "Share Issued"),
}
_RATIO_KEYS = {
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "price_to_book": "priceToBook",
    "price_to_sales": "priceToSalesTrailing12Months",
    "ev_to_ebitda": "enterpriseToEbitda",
    "market_cap": "marketCap",
}


def _rows(frame, wanted: dict[str, tuple[str, ...]]) -> dict:
    """Period end -> {field: number} from one statement table (columns are period ends)."""
    found: dict = {}
    if frame is None or getattr(frame, "empty", True):
        return found
    for column in frame.columns:
        values = {}
        for name, candidates in wanted.items():
            for row in candidates:
                if row in frame.index:
                    value = _number(frame.at[row, column])
                    if value is not None:
                        values[name] = value
                        break
        if values:
            found[column.date()] = values
    return found


def statements_from_frames(period: str, income, balance) -> list[Statement]:
    """Merge yfinance's income statement and balance sheet tables of one period kind."""
    by_end = _rows(income, _INCOME_ROWS)
    for end, values in _rows(balance, _BALANCE_ROWS).items():
        by_end.setdefault(end, {}).update(values)
    return [Statement(period, end, **values) for end, values in sorted(by_end.items())]


def ratios_from_info(info: dict) -> Ratios | None:
    """None for anything that is not a company: funds, coins, currencies."""
    if info.get("quoteType") != "EQUITY":
        return None
    return Ratios(**{name: _number(info.get(key)) for name, key in _RATIO_KEYS.items()})


def company_from_info(info: dict) -> Company | None:
    """None for anything that is not a company, or a company Yahoo knows nothing about."""
    if info.get("quoteType") != "EQUITY":
        return None
    sector, country = info.get("sector"), info.get("country")
    if not sector and not country:
        return None
    return Company(sector or None, country or None)


class YahooProvider:
    def __init__(self) -> None:
        self._infos: dict[str, dict] = {}  # one request per symbol for ratios and company

    def _info(self, symbol: str) -> dict:
        import yfinance  # noqa: PLC0415

        if symbol not in self._infos:
            try:
                self._infos[symbol] = yfinance.Ticker(symbol).info or {}
            except Exception as e:
                raise ProviderError(f"Yahoo: {symbol}: {e}") from e
        return self._infos[symbol]

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
        try:
            direct = self._history(fx_symbol(from_currency, to_currency), start)
        except ProviderError as error:
            direct, failure = [], error
        else:
            failure = None
        if direct:
            return direct
        # Yahoo lists no rate for some pairs (KRW/CZK): go through EUR or USD instead.
        for via in ("EUR", "USD"):
            if via in (from_currency, to_currency):
                continue
            try:
                first = self._history(fx_symbol(from_currency, via), start)
                second = self._history(fx_symbol(via, to_currency), start)
            except ProviderError:
                continue
            if first and second:
                return cross_rates(first, second)
        if failure:
            raise failure
        return []

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

    def ratios(self, symbol: str) -> Ratios | None:
        return ratios_from_info(self._info(symbol))

    def company(self, symbol: str) -> Company | None:
        return company_from_info(self._info(symbol))

    def statements(self, symbol: str) -> tuple[str | None, list[Statement]]:
        import yfinance  # noqa: PLC0415

        try:
            ticker = yfinance.Ticker(symbol)
            info = self._info(symbol)
            currency = info.get("financialCurrency") or info.get("currency")
            found = statements_from_frames(
                "annual", ticker.income_stmt, ticker.balance_sheet
            ) + statements_from_frames(
                "quarterly", ticker.quarterly_income_stmt, ticker.quarterly_balance_sheet
            )
        except Exception as e:
            raise ProviderError(f"Yahoo: {symbol}: {e}") from e
        if not isinstance(currency, str) or not _CURRENCY_RE.match(currency):
            return None, []
        found.sort(key=lambda s: (s.period_end, s.period))
        return currency, found
