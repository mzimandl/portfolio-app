"""Replaying the ledger of one instrument into a position."""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from portfolio.core.analytics.data import Event, PortfolioData
from portfolio.core.models import Instrument, ValuationMethod
from portfolio.core.models import TransactionKind as K

_NO_QUANTITY = 1e-12


@dataclass
class Position:
    """State of one instrument after some of its events. Money is in base currency."""

    quantity: float = 0.0
    staking_quantity: float = 0.0  # part of `quantity` that came from staking rewards
    buy_quantity: float = 0.0
    buy_cost: dict[str, float] = field(default_factory=lambda: defaultdict(float))  # per currency
    bought: float = 0.0  # what the buys cost, at the exchange rates of the time
    invested: float = 0.0  # buys and deposits
    returned: float = 0.0  # sells and withdrawals
    reinvested: float = 0.0  # part of `returned` that was put back into other investments
    fees: float = 0.0
    dividends: float = 0.0
    # Cash put in minus cash taken out, in the instrument's currency, as a running total.
    # A manual valuation is topped up with the cash that moved since it was entered.
    cash_dates: list[date] = field(default_factory=list)
    cash_running: list[float] = field(default_factory=list)

    def _add_cash(self, day: date, amount: float) -> None:
        self.cash_dates.append(day)
        self.cash_running.append((self.cash_running[-1] if self.cash_running else 0.0) + amount)

    def cash_since(self, day: date | None) -> float:
        """Net cash put in on ``day`` or later (everything if ``day`` is None)."""
        if not self.cash_running:
            return 0.0
        total = self.cash_running[-1]
        if day is None:
            return total
        index = bisect_left(self.cash_dates, day)
        return total - (self.cash_running[index - 1] if index else 0.0)


def apply(
    position: Position, event: Event, instrument: Instrument, data: PortfolioData
) -> tuple[float, float]:
    """Update the position. Returns (money put in, money taken out) in base currency.

    Those two are what the investor paid and received on that day, used to measure returns:
    fees count as money put in, dividends as money taken out.
    """
    kind = event.kind
    position.fees += event.fee
    if kind in (K.BUY, K.SELL):
        cash = event.quantity * event.price
        base = cash * event.rate
        local = _to_instrument_currency(cash, base, event, instrument, data)
        if kind is K.BUY:
            position.quantity += event.quantity
            position.buy_quantity += event.quantity
            position.buy_cost[event.currency] += cash
            position.bought += base
            position.invested += base
            position._add_cash(event.date, local)
            return base + event.fee, 0.0
        position.quantity -= event.quantity
        position.returned += base
        if event.reinvested:
            position.reinvested += base
        position._add_cash(event.date, -local)
        return event.fee, base
    if kind in (K.DEPOSIT, K.WITHDRAWAL):
        base = event.amount * event.rate
        local = _to_instrument_currency(event.amount, base, event, instrument, data)
        if kind is K.DEPOSIT:
            position.invested += base
            position._add_cash(event.date, local)
            return base + event.fee, 0.0
        position.returned += base
        if event.reinvested:
            position.reinvested += base
        position._add_cash(event.date, -local)
        return event.fee, base
    if kind is K.DIVIDEND:
        base = event.amount * event.rate
        position.dividends += base
        return event.fee, base
    if kind is K.STAKING_REWARD:
        position.quantity += event.quantity
        position.staking_quantity += event.quantity
    elif kind is K.SPLIT:
        position.quantity *= event.split_ratio
        position.staking_quantity *= event.split_ratio
        position.buy_quantity *= event.split_ratio
    return event.fee, 0.0


def _to_instrument_currency(
    cash: float, base: float, event: Event, instrument: Instrument, data: PortfolioData
) -> float:
    if event.currency == instrument.currency:
        return cash
    rate = data.fx_at(instrument.currency, event.date)
    return base / rate if rate else cash


def value_of(
    position: Position,
    instrument: Instrument,
    data: PortfolioData,
    day: date,
    *,
    later_splits: float = 1.0,
) -> float | None:
    """Value in base currency on ``day``; None when a price or exchange rate is missing.

    ``later_splits`` is the product of split ratios after ``day``. Downloaded prices are
    expressed in today's units, so an older quantity has to be scaled the same way.
    """
    if instrument.valuation is ValuationMethod.MANUAL:
        valuations = data.valuations.get(instrument.id)
        found = valuations.at_with_date(day) if valuations else None
        if found is None:
            local = position.cash_since(None)
        else:
            valued_on, valuation = found
            local = valuation + position.cash_since(valued_on)
    else:
        if abs(position.quantity) < _NO_QUANTITY:
            return 0.0
        prices = data.prices.get(instrument.id)
        price = prices.at(day) if prices else None
        if price is None:
            return None
        local = position.quantity * later_splits * price
    rate = data.fx_at(instrument.currency, day)
    return None if rate is None else local * rate


def position_at(data: PortfolioData, instrument_id: int, as_of: date) -> Position:
    instrument = data.instruments[instrument_id]
    position = Position()
    for event in data.events.get(instrument_id, []):
        if event.date > as_of:
            break
        apply(position, event, instrument, data)
    return position
