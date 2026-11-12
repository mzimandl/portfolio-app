"""Current state of every instrument."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from datetime import date

from portfolio.core.analytics.data import PortfolioData
from portfolio.core.analytics.positions import position_at, value_of
from portfolio.core.models import ValuationMethod


@dataclass(frozen=True)
class OverviewRow:
    """Money is in base currency unless noted. None means a price or rate is missing.

    Sales use up the oldest units first (FIFO). The profit has two parts: ``realised`` on
    what was sold and ``unrealised`` on what is still held; only the unrealised part is
    split into price, exchange rate and staking.
    """

    ticker: str
    name: str | None
    type: str
    currency: str
    quantity: float | None  # None for manually valued instruments
    last_price: float | None  # in the instrument's currency
    average_price: float | None  # of the bought units still held, in the instrument's currency
    invested: float  # buys and deposits
    returned: float  # sells and withdrawals
    fees: float
    dividends: float
    value: float | None
    cost_basis: float  # what the holding cost; for manual instruments, money still in
    unrealised_profit: float | None  # value - cost basis
    price_profit: float | None  # part of the unrealised profit from price movement
    fx_profit: float | None  # part of the unrealised profit from exchange-rate movement
    rewards: float | None  # part of the unrealised profit that is staking rewards held
    realised_profit: float | None  # on units sold; None for manual instruments
    total_profit: float | None  # value + returned - invested = unrealised + realised
    net_profit: float | None  # total profit + dividends - fees


def overview(
    data: PortfolioData, as_of: date | None = None, *, include_inactive: bool = False
) -> list[OverviewRow]:
    as_of = as_of or date.today()
    return [
        _row(data, instrument_id, as_of)
        for instrument_id in data.instrument_ids(include_inactive=include_inactive)
    ]


def _row(data: PortfolioData, instrument_id: int, as_of: date) -> OverviewRow:
    instrument = data.instruments[instrument_id]
    position = position_at(data, instrument_id, as_of)
    manual = instrument.valuation is ValuationMethod.MANUAL
    rate_now = data.fx_at(instrument.currency, as_of)
    prices = data.prices.get(instrument_id)
    last_price = prices.at(as_of) if prices and not manual else None
    value = value_of(position, instrument, data, as_of)

    total_profit = net_profit = None
    if value is not None:
        total_profit = value + position.returned - position.invested
        net_profit = total_profit + position.dividends - position.fees

    average_price = fx_profit = rewards = price_profit = None
    if manual:
        cost_basis = position.invested - position.returned
        unrealised = price_profit = total_profit
        realised = None
    else:
        cost_basis = position.cost_basis
        realised = position.realised
        unrealised = None if value is None else value - cost_basis
        # What the units still held would cost at today's exchange rates.
        bought = [lot for lot in position.lots if not lot.staking]
        rates = {lot.currency: data.fx_at(lot.currency, as_of) for lot in bought}
        if all(rate is not None for rate in rates.values()):
            cost_now = sum(lot.cost * rates[lot.currency] for lot in bought)
            fx_profit = cost_now - cost_basis
            if position.bought_quantity > 0 and rate_now:
                average_price = cost_now / (rate_now * position.bought_quantity)
        if position.staking_quantity == 0:
            rewards = 0.0  # needs no price
        elif last_price is not None and rate_now is not None:
            rewards = position.staking_quantity * last_price * rate_now
        if unrealised is not None and fx_profit is not None and rewards is not None:
            price_profit = unrealised - fx_profit - rewards

    return OverviewRow(
        ticker=instrument.ticker,
        name=instrument.name,
        type=instrument.type,
        currency=instrument.currency,
        quantity=None if manual else position.quantity,
        last_price=last_price,
        average_price=average_price,
        invested=position.invested,
        returned=position.returned,
        fees=position.fees,
        dividends=position.dividends,
        value=value,
        cost_basis=cost_basis,
        unrealised_profit=unrealised,
        price_profit=price_profit,
        fx_profit=fx_profit,
        rewards=rewards,
        realised_profit=realised,
        total_profit=total_profit,
        net_profit=net_profit,
    )


@dataclass(frozen=True)
class SaleRow:
    """One sale and what it realised, in base currency."""

    date: date
    ticker: str
    type: str
    quantity: float
    proceeds: float
    cost: float  # what the sold units had cost (oldest units first)
    profit: float
    held_days: float  # averaged over the units sold


def sales(
    data: PortfolioData, as_of: date | None = None, *, include_inactive: bool = False
) -> list[SaleRow]:
    """Every sale of a priced instrument, newest first. Their profits add up to the
    realised profit of the overview."""
    as_of = as_of or date.today()
    rows = []
    for instrument_id in data.instrument_ids(include_inactive=include_inactive):
        instrument = data.instruments[instrument_id]
        if instrument.valuation is ValuationMethod.MANUAL:
            continue
        for sale in position_at(data, instrument_id, as_of).sales:
            rows.append(
                SaleRow(
                    date=sale.date,
                    ticker=instrument.ticker,
                    type=instrument.type,
                    quantity=sale.quantity,
                    proceeds=sale.proceeds,
                    cost=sale.cost,
                    profit=sale.profit,
                    held_days=sale.held_days,
                )
            )
    rows.sort(key=lambda row: (row.date, row.ticker), reverse=True)
    return rows


_SUMMED = (
    "invested", "returned", "fees", "dividends", "value", "cost_basis",
    "unrealised_profit", "price_profit", "fx_profit", "rewards", "realised_profit",
    "total_profit", "net_profit",
)  # fmt: skip
assert set(_SUMMED) <= {f.name for f in fields(OverviewRow)}


def summarize(
    rows: Iterable[OverviewRow], key: Callable[[OverviewRow], str] = lambda row: "total"
) -> dict[str, dict[str, float]]:
    """Sums of the money columns per group (by default one group, "total").

    Missing numbers count as zero; ``missing`` lists the tickers whose value is unknown.
    """
    groups: dict[str, dict] = {}
    for row in rows:
        group = groups.setdefault(key(row), {name: 0.0 for name in _SUMMED} | {"missing": []})
        for name in _SUMMED:
            group[name] += getattr(row, name) or 0.0
        if row.value is None:
            group["missing"].append(row.ticker)
    return groups
