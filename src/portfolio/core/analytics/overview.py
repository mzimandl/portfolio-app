"""Current state of every instrument."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from datetime import date

from portfolio.core.analytics.data import PortfolioData
from portfolio.core.analytics.positions import position_at, value_of
from portfolio.core.models import ValuationMethod


@dataclass(frozen=True)
class OverviewRow:
    """Money is in base currency unless noted. None means a price or rate is missing."""

    ticker: str
    name: str | None
    type: str
    currency: str
    quantity: float | None  # None for manually valued instruments
    last_price: float | None  # in the instrument's currency
    average_price: float | None  # average buy price, in the instrument's currency
    invested: float  # buys and deposits
    returned: float  # sells and withdrawals
    reinvested: float
    fees: float
    dividends: float
    value: float | None
    total_profit: float | None  # value + returned - invested
    price_profit: float | None  # part of total profit from price movement
    fx_profit: float | None  # part of total profit from exchange-rate movement
    rewards: float | None  # part of total profit that is staking rewards
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

    # What the buys would cost at today's exchange rates, against what they did cost.
    buy_rates = {currency: data.fx_at(currency, as_of) for currency in position.buy_cost}
    average_price = fx_profit = rewards = None
    if not manual and all(rate is not None for rate in buy_rates.values()):
        cost_now = sum(cash * buy_rates[c] for c, cash in position.buy_cost.items())
        fx_profit = cost_now - position.bought
        if position.buy_quantity > 0 and rate_now:
            average_price = cost_now / (rate_now * position.buy_quantity)
    if not manual and last_price is not None and rate_now is not None:
        rewards = position.staking_quantity * last_price * rate_now

    total_profit = price_profit = net_profit = None
    if value is not None:
        total_profit = value + position.returned - position.invested
        net_profit = total_profit + position.dividends - position.fees
        if manual:
            price_profit = total_profit
        elif fx_profit is not None and rewards is not None:
            price_profit = total_profit - fx_profit - rewards

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
        reinvested=position.reinvested,
        fees=position.fees,
        dividends=position.dividends,
        value=value,
        total_profit=total_profit,
        price_profit=price_profit,
        fx_profit=fx_profit,
        rewards=rewards,
        net_profit=net_profit,
    )


_SUMMED = (
    "invested", "returned", "reinvested", "fees", "dividends", "value", "total_profit",
    "price_profit", "fx_profit", "rewards", "net_profit",
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
