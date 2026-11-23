"""What the updater needs from a source of market data.

To add a source, write a class with these methods; nothing else depends on it. A source
without company data can return None from ``ratios`` and ``(None, [])`` from ``statements``.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ProviderError(Exception):
    """The source could not deliver the data (network, unknown symbol, changed format)."""


@dataclass(frozen=True, slots=True)
class Bar:
    """One trading day. Prices are real closing prices in today's share units:
    adjusted for later splits, not for dividends."""

    date: date
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    dividend: float = 0.0
    split: float = 0.0  # ratio of a split that took effect this day, else 0


@dataclass(frozen=True, slots=True)
class Ratios:
    """Valuation ratios as the source reports them today. Any of them may be missing."""

    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    price_to_sales: float | None = None
    ev_to_ebitda: float | None = None
    market_cap: float | None = None  # in the currency the symbol is quoted in


@dataclass(frozen=True, slots=True)
class Statement:
    """One reported period. Money is in the company's reporting currency; per-share numbers
    are in today's share units."""

    period: str  # "annual" or "quarterly"
    period_end: date
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None
    equity: float | None = None
    shares: float | None = None


class MarketDataProvider(Protocol):
    def prices(self, symbol: str, start: date) -> list[Bar]:
        """Daily bars from ``start`` to today, oldest first. Empty if there are none yet."""
        ...

    def fx_rates(self, from_currency: str, to_currency: str, start: date) -> list[Bar]:
        """Daily rates (``to`` per 1 ``from``) from ``start`` to today, oldest first."""
        ...

    def currency(self, symbol: str) -> str:
        """ISO code of the currency the symbol is quoted in."""
        ...

    def ratios(self, symbol: str) -> Ratios | None:
        """Today's valuation ratios; None when the symbol is not a company (a fund, a coin)."""
        ...

    def statements(self, symbol: str) -> tuple[str | None, list[Statement]]:
        """The reporting currency and the reported periods, oldest first."""
        ...
