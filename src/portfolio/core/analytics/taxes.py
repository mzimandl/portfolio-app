"""Figures for a tax return: sales by how long the units were held, dividends, staking.

This lists facts from the ledger and applies two simple, configurable rules. It is not tax
advice and knows nothing about anyone's other income.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from portfolio.core.analytics.data import PortfolioData, Series
from portfolio.core.analytics.positions import position_at
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod

SECURITIES = "securities"
CRYPTO = "crypto"


@dataclass(frozen=True)
class TaxRules:
    holding_years: int = 3  # held longer than this: the sale is exempt
    proceeds_limit: float = 100_000  # yearly proceeds of a group up to this: all exempt
    crypto_types: tuple[str, ...] = ("crypto",)

    def group(self, instrument_type: str) -> str:
        return CRYPTO if instrument_type in self.crypto_types else SECURITIES

    def exempt_from(self, acquired: date) -> date:
        """The first day a sale of units acquired on ``acquired`` is exempt."""
        year = acquired.year + self.holding_years
        try:
            same_day = acquired.replace(year=year)
        except ValueError:  # 29 February
            return date(year, 3, 1)
        return date.fromordinal(same_day.toordinal() + 1)


# Base currency per 1 unit of a currency for a payment on a day; None when not known.
Rates = Callable[[str, date], float | None]

_LAST_DECEMBER_DAY = 20  # a year's ČNB rates are complete once a day this late is stored


class OfficialRates:
    """Exchange rates of the Czech National Bank, as a Czech tax return uses them."""

    def __init__(self, rates: dict[str, list[tuple[date, float]]], today: date) -> None:
        self.series = {currency: Series(points) for currency, points in rates.items()}
        self.today = today

    def __bool__(self) -> bool:
        return bool(self.series)

    def daily(self, currency: str, day: date) -> float | None:
        """The rate published for that day, or the last one before it (weekends)."""
        series = self.series.get(currency)
        return series.at(day) if series else None

    def unified(self, currency: str, year: int) -> float | None:
        """The yearly unified rate: the average of the rates valid on the last day of each
        month. None until the year is over."""
        series = self.series.get(currency)
        if (
            not series
            or year >= self.today.year
            or series.dates[0] > date(year, 1, 31)
            or series.dates[-1] < date(year, 12, _LAST_DECEMBER_DAY)
        ):
            return None
        ends = [series.at(_month_end(year, month)) for month in range(1, 13)]
        return None if None in ends else sum(ends) / 12  # type: ignore[arg-type]

    def by_day(self) -> Rates:
        return self.daily

    def by_year(self) -> Rates:
        return lambda currency, day: self.unified(currency, day.year)


def _month_end(year: int, month: int) -> date:
    following = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return following - timedelta(days=1)


def _instruments(data: PortfolioData, instrument_ids: list[int]):
    for instrument_id in instrument_ids:
        instrument = data.instruments[instrument_id]
        if instrument.valuation is not ValuationMethod.MANUAL:
            yield instrument_id, instrument


@dataclass(frozen=True)
class TaxSale:
    """Units of one sale that came from one purchase. Money in base currency."""

    date: date
    ticker: str
    group: str
    acquired: date | None
    quantity: float
    proceeds: float
    cost: float
    long_held: bool  # held longer than the rules ask
    estimated: bool = False  # converted at the recorded rate: the chosen rates had none

    @property
    def profit(self) -> float:
        return self.proceeds - self.cost


def _convert(
    data: PortfolioData,
    rates: Rates | None,
    amount: float,
    currency: str | None,
    day: date,
    recorded: float,
) -> tuple[float, bool]:
    """``amount`` in ``currency`` into base currency with ``rates``. Without a rate there
    (or without ``rates``) the recorded conversion ``recorded`` is kept. Returns (value,
    whether the recorded one was used though ``rates`` were asked for)."""
    if rates is None:
        return recorded, False
    if currency is None or currency == data.base_currency:
        return amount, False
    rate = rates(currency, day)
    return (recorded, True) if rate is None else (amount * rate, False)


def sales(
    data: PortfolioData,
    instrument_ids: list[int],
    year: int,
    rules: TaxRules,
    rates: Rates | None = None,
) -> list[TaxSale]:
    """The year's sales, split by the purchases the sold units came from.

    With ``rates`` every payment is converted at those rates, the proceeds on the day of the
    sale and the cost on the day of the purchase, instead of at the rates recorded.
    """
    rows = []
    for instrument_id, instrument in _instruments(data, instrument_ids):
        for sale in position_at(data, instrument_id, date(year, 12, 31)).sales:
            if sale.date.year != year or sale.quantity <= 0:
                continue
            for part in sale.parts:
                share = part.quantity / sale.quantity
                proceeds, guessed = _convert(
                    data, rates, sale.cash * share, sale.currency, sale.date,
                    sale.proceeds * share,
                )  # fmt: skip
                cost, guessed_cost = (
                    _convert(data, rates, part.paid, part.currency, part.acquired, part.cost)
                    if part.acquired is not None and part.cost
                    else (part.cost, False)
                )
                rows.append(
                    TaxSale(
                        date=sale.date,
                        ticker=instrument.ticker,
                        group=rules.group(instrument.type),
                        acquired=part.acquired,
                        quantity=part.quantity,
                        proceeds=proceeds,
                        cost=cost,
                        long_held=part.acquired is not None
                        and sale.date >= rules.exempt_from(part.acquired),
                        estimated=guessed or guessed_cost,
                    )
                )
    rows.sort(key=lambda row: (row.date, row.ticker, row.acquired or date.min))
    return rows


@dataclass(frozen=True)
class TaxGroup:
    group: str
    proceeds: float  # of all the year's sales in the group
    profit: float
    long_proceeds: float  # of units held longer than the rules ask
    long_profit: float
    short_proceeds: float
    short_profit: float
    under_limit: bool  # the year's proceeds do not exceed the limit
    not_exempt: float  # profit left after both rules (a loss if negative)


def summary(rows: list[TaxSale], rules: TaxRules) -> list[TaxGroup]:
    groups = []
    for name in (SECURITIES, CRYPTO):
        own = [row for row in rows if row.group == name]
        if not own:
            continue
        long = [row for row in own if row.long_held]
        short = [row for row in own if not row.long_held]
        proceeds = sum(row.proceeds for row in own)
        short_profit = sum(row.profit for row in short)
        under_limit = proceeds <= rules.proceeds_limit
        groups.append(
            TaxGroup(
                group=name,
                proceeds=proceeds,
                profit=sum(row.profit for row in own),
                long_proceeds=sum(row.proceeds for row in long),
                long_profit=sum(row.profit for row in long),
                short_proceeds=sum(row.proceeds for row in short),
                short_profit=short_profit,
                under_limit=under_limit,
                not_exempt=0.0 if under_limit else short_profit,
            )
        )
    return groups


@dataclass(frozen=True)
class TaxDividend:
    ticker: str
    currency: str
    payments: int
    net: float  # received, in base currency
    tax: float  # withheld, in base currency
    estimated: bool = False  # some at the recorded rate: the chosen rates had none

    @property
    def gross(self) -> float:
        return self.net + self.tax


def dividends(
    data: PortfolioData, instrument_ids: list[int], year: int, rates: Rates | None = None
) -> list[TaxDividend]:
    rows = []
    for instrument_id in instrument_ids:
        instrument = data.instruments[instrument_id]
        paid = [
            e for e in data.events.get(instrument_id, [])
            if e.kind is K.DIVIDEND and e.date.year == year
        ]  # fmt: skip
        if paid:
            net, tax, estimated = 0.0, 0.0, False
            for e in paid:
                received, guessed = _convert(
                    data, rates, e.amount, e.currency, e.date, e.amount * e.rate
                )
                withheld, _ = _convert(data, rates, e.tax, e.currency, e.date, e.tax * e.rate)
                net, tax, estimated = net + received, tax + withheld, estimated or guessed
            rows.append(
                TaxDividend(
                    ticker=instrument.ticker,
                    currency=paid[-1].currency or instrument.currency,
                    payments=len(paid),
                    net=net,
                    tax=tax,
                    estimated=estimated,
                )
            )
    return rows


@dataclass(frozen=True)
class StakingIncome:
    ticker: str
    quantity: float  # received in the year, less what was taken back
    value: float | None  # at the price of each day received; None if a price is missing


def staking(
    data: PortfolioData, instrument_ids: list[int], year: int, rates: Rates | None = None
) -> list[StakingIncome]:
    rows = []
    for instrument_id, instrument in _instruments(data, instrument_ids):
        prices = data.prices.get(instrument_id)
        quantity, value, known = 0.0, 0.0, True
        for event in data.events.get(instrument_id, []):
            if event.date.year != year:
                continue
            sign = {K.STAKING_REWARD: 1, K.STAKING_CORRECTION: -1}.get(event.kind)
            if sign is None:
                continue
            price = prices.at(event.date) if prices else None
            rate = data.fx_at(instrument.currency, event.date)
            if rates is not None and instrument.currency != data.base_currency:
                rate = rates(instrument.currency, event.date) or rate
            quantity += sign * event.quantity
            if price is None or rate is None:
                known = False
            else:
                value += sign * event.quantity * price * rate
        if quantity:
            rows.append(StakingIncome(instrument.ticker, quantity, value if known else None))
    return rows


@dataclass(frozen=True)
class HeldRow:
    """What of one instrument could be sold exempt today, and what could not yet."""

    ticker: str
    group: str
    long_quantity: float
    long_value: float | None
    long_profit: float | None
    short_quantity: float
    short_value: float | None
    short_profit: float | None
    next_exempt: date | None  # when the oldest of the rest gets there
    next_quantity: float


def held(
    data: PortfolioData, instrument_ids: list[int], as_of: date, rules: TaxRules
) -> list[HeldRow]:
    rows = []
    for instrument_id, instrument in _instruments(data, instrument_ids):
        lots = position_at(data, instrument_id, as_of).lots
        if not lots:
            continue
        prices = data.prices.get(instrument_id)
        price = prices.at(as_of) if prices else None
        rate = data.fx_at(instrument.currency, as_of)
        worth = None if price is None or rate is None else price * rate
        long = [lot for lot in lots if as_of >= rules.exempt_from(lot.date)]
        short = [lot for lot in lots if as_of < rules.exempt_from(lot.date)]

        def totals(part, worth=worth):
            quantity = sum(lot.quantity for lot in part)
            value = None if worth is None else quantity * worth
            cost = sum(lot.cost_base for lot in part)
            return quantity, value, None if value is None else value - cost

        next_day = min((rules.exempt_from(lot.date) for lot in short), default=None)
        rows.append(
            HeldRow(
                instrument.ticker,
                rules.group(instrument.type),
                *totals(long),
                *totals(short),
                next_exempt=next_day,
                next_quantity=sum(
                    lot.quantity for lot in short if rules.exempt_from(lot.date) == next_day
                ),
            )
        )
    return rows


def years(data: PortfolioData, instrument_ids: list[int]) -> list[int]:
    """Years with a sale, a dividend or staking, newest first."""
    kinds = (K.SELL, K.DIVIDEND, K.STAKING_REWARD, K.STAKING_CORRECTION)
    found = {
        event.date.year
        for instrument_id in instrument_ids
        for event in data.events.get(instrument_id, [])
        if event.kind in kinds
    }
    return sorted(found, reverse=True)
