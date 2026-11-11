"""What the updater needs from a source of market data.

To add a source, write a class with these three methods; nothing else depends on it.
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
