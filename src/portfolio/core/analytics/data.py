"""Everything the calculations need, loaded from the database once."""

import sqlite3
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from portfolio.core import repo
from portfolio.core.models import Instrument, Transaction, TransactionKind


class Series:
    """Dated values in ascending order, looked up as "the latest value on or before a day"."""

    __slots__ = ("dates", "values")

    def __init__(self, points: list[tuple[date, float]] | None = None) -> None:
        points = sorted(points or [])
        self.dates = [day for day, _ in points]
        self.values = [value for _, value in points]

    def __bool__(self) -> bool:
        return bool(self.dates)

    def at_with_date(self, day: date) -> tuple[date, float] | None:
        index = bisect_right(self.dates, day) - 1
        return None if index < 0 else (self.dates[index], self.values[index])

    def at(self, day: date) -> float | None:
        found = self.at_with_date(day)
        return None if found is None else found[1]


@dataclass(frozen=True, slots=True)
class Event:
    """A transaction with float numbers and its exchange rate already resolved."""

    date: date
    kind: TransactionKind
    quantity: float
    price: float
    amount: float
    currency: str | None
    rate: float  # base currency per 1 unit of `currency`
    fee: float
    split_ratio: float
    reinvested: bool


@dataclass
class PortfolioData:
    base_currency: str
    instruments: dict[int, Instrument] = field(default_factory=dict)
    events: dict[int, list[Event]] = field(default_factory=dict)  # per instrument, oldest first
    prices: dict[int, Series] = field(default_factory=dict)
    valuations: dict[int, Series] = field(default_factory=dict)
    fx: dict[str, Series] = field(default_factory=dict)  # currency -> rate to base
    warnings: list[str] = field(default_factory=list)

    def fx_at(self, currency: str, day: date) -> float | None:
        """Base currency per 1 unit of ``currency`` on that day; None if no rate is known yet."""
        if currency == self.base_currency:
            return 1.0
        series = self.fx.get(currency)
        return series.at(day) if series else None

    def instrument_ids(self, *, include_inactive: bool = False) -> list[int]:
        """Instruments that have transactions, in ticker order."""
        chosen = [
            i for i in self.instruments.values()
            if self.events.get(i.id) and (i.active or include_inactive)
        ]  # fmt: skip
        return [i.id for i in sorted(chosen, key=lambda i: i.ticker)]

    @property
    def last_date(self) -> date | None:
        """The most recent day anything is known about."""
        candidates = [s.dates[-1] for group in (self.prices, self.valuations) for s in
                      group.values() if s]  # fmt: skip
        candidates += [events[-1].date for events in self.events.values() if events]
        return max(candidates, default=None)


def _points(rows, key, value) -> dict:
    grouped: dict = defaultdict(list)
    for row in rows:
        grouped[key(row)].append((row.date, float(value(row))))
    return {k: Series(points) for k, points in grouped.items()}


def load_data(conn: sqlite3.Connection, base_currency: str) -> PortfolioData:
    data = PortfolioData(base_currency=base_currency)
    data.instruments = {i.id: i for i in repo.list_instruments(conn)}
    data.prices = _points(repo.list_prices(conn), lambda p: p.instrument_id, lambda p: p.close)
    data.valuations = _points(
        repo.list_valuations(conn), lambda v: v.instrument_id, lambda v: v.value
    )
    data.fx = _points(
        repo.list_fx_rates(conn, to_currency=base_currency),
        lambda r: r.from_currency,
        lambda r: r.close,
    )
    for transaction in repo.list_transactions(conn):  # ordered by date, then id
        event = _to_event(transaction, data)
        data.events.setdefault(transaction.instrument_id, []).append(event)
    return data


def _to_event(t: Transaction, data: PortfolioData) -> Event:
    if t.fx_rate is not None:
        rate = float(t.fx_rate)
    elif t.currency is None:
        rate = 1.0
    else:
        rate = data.fx_at(t.currency, t.date)
        if rate is None:
            ticker = data.instruments[t.instrument_id].ticker
            data.warnings.append(
                f"{ticker} {t.date}: no {t.currency} exchange rate known for this {t.kind}; "
                "counted with rate 1"
            )
            rate = 1.0
    return Event(
        date=t.date,
        kind=t.kind,
        quantity=float(t.quantity or 0),
        price=float(t.price or 0),
        amount=float(t.amount or 0),
        currency=t.currency,
        rate=rate,
        fee=float(t.fee),
        split_ratio=float(t.split_ratio or 1),
        reinvested=t.reinvested,
    )
