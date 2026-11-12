"""Checks of the data: things that look wrong or out of date. Nothing is changed."""

from dataclasses import dataclass, replace
from datetime import date, timedelta

from portfolio.core.analytics import dividends
from portfolio.core.analytics.data import PortfolioData
from portfolio.core.analytics.positions import position_at, value_of
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod

STALE_PRICE = "Prices out of date"
STALE_VALUATION = "Manual values out of date"
PRICE_OFF = "Trade price far from the market"
RATE_OFF = "Exchange rate far from the market"
LEFTOVER = "Tiny leftovers"
OVERSOLD = "More sold than held"
DIVIDENDS = "Dividends possibly not recorded"
SAME_DAY = "Manual value on the day of a deposit"

EXPLANATIONS = {
    STALE_PRICE: "Instruments you hold whose newest price or exchange rate is more than a "
    "week old. Their value is counted with that old number.",
    STALE_VALUATION: "Instruments valued by hand whose newest value is more than three months old.",
    PRICE_OFF: "Buys and sells whose price differs from that day's closing price by more "
    "than 15 %. Often a typing mistake, or a price entered in another currency.",
    RATE_OFF: "Trades whose exchange rate differs from that day's market rate by more than 3 %.",
    LEFTOVER: "Positions with less than a thousandth of what was ever acquired left. "
    "Usually a rounding remainder of a sale.",
    OVERSOLD: "Instruments whose sales add up to more than was bought.",
    DIVIDENDS: "The price data reports more dividends for the units you held than you "
    "recorded. Reports from the last two months are not counted.",
    SAME_DAY: "A deposit or withdrawal on the day of a manual value is added on top of it. "
    "If the value already contained it, it is counted twice until the next value.",
}

_PRICE_AGE = timedelta(days=7)
_VALUATION_AGE = timedelta(days=92)
_NEAR = timedelta(days=5)  # how old a market price may be to compare a trade with it
_PRICE_TOLERANCE = 0.15
_RATE_TOLERANCE = 0.03
_LEFTOVER_SHARE = 0.001
_TINY = 1e-9


@dataclass(frozen=True)
class Finding:
    check: str
    ticker: str
    date: date | None
    detail: str
    instrument_id: int = 0
    # What makes this "the same finding" when it was marked as looked at. By default the
    # detail: once the record changes, the finding counts as new and shows up again.
    key: str = ""

    @property
    def identity(self) -> tuple[str, int, date | None, str]:
        return (self.check, self.instrument_id, self.date, self.key or self.detail)


def run_checks(data: PortfolioData, as_of: date | None = None) -> list[Finding]:
    """Every finding for the active instruments, grouped by check in a fixed order."""
    as_of = as_of or date.today()
    found: list[Finding] = []
    ids = data.instrument_ids()
    for instrument_id in ids:
        found += [
            replace(finding, instrument_id=instrument_id)
            for finding in _instrument(data, instrument_id, as_of)
        ]
    by_ticker = {data.instruments[i].ticker: i for i in ids}
    for row in dividends.by_instrument(data, ids, as_of):
        if row.missing:
            found.append(
                Finding(
                    DIVIDENDS,
                    row.ticker,
                    None,
                    f"{row.payments} recorded, {row.payments + row.missing} expected",
                    by_ticker[row.ticker],
                )
            )
    order = list(EXPLANATIONS)
    found.sort(key=lambda f: (order.index(f.check), f.ticker, f.date or date.min))
    return found


def _instrument(data: PortfolioData, instrument_id: int, as_of: date) -> list[Finding]:
    instrument = data.instruments[instrument_id]
    ticker = instrument.ticker
    events = [e for e in data.events[instrument_id] if e.date <= as_of]
    position = position_at(data, instrument_id, as_of)
    found = []

    if instrument.valuation is ValuationMethod.MANUAL:
        valuations = data.valuations.get(instrument_id)
        value = value_of(position, instrument, data, as_of)
        if valuations and value and valuations.dates[-1] < as_of - _VALUATION_AGE:
            newest = valuations.dates[-1]
            found.append(Finding(STALE_VALUATION, ticker, newest, f"newest value is from {newest}"))
        valued = set(valuations.dates) if valuations else set()
        for event in events:
            if event.kind in (K.DEPOSIT, K.WITHDRAWAL) and event.date in valued:
                found.append(
                    Finding(
                        SAME_DAY, ticker, event.date,
                        f"{event.kind} of {event.amount:g} {event.currency}",
                    )
                )  # fmt: skip
        return found

    prices = data.prices.get(instrument_id)
    if position.quantity < -_TINY:
        found.append(Finding(OVERSOLD, ticker, None, f"quantity is {position.quantity:g}"))
    if position.quantity > _TINY:
        if not prices:
            found.append(Finding(STALE_PRICE, ticker, None, "no price at all"))
        elif prices.dates[-1] < as_of - _PRICE_AGE:
            newest = prices.dates[-1]
            found.append(Finding(STALE_PRICE, ticker, newest, f"newest price is from {newest}"))
        rates = data.fx.get(instrument.currency)
        if instrument.currency != data.base_currency and (
            not rates or rates.dates[-1] < as_of - _PRICE_AGE
        ):
            newest = rates.dates[-1] if rates else None
            found.append(
                Finding(
                    STALE_PRICE, ticker, newest,
                    f"newest {instrument.currency} rate is from {newest}"
                    if newest else f"no {instrument.currency} rate at all",
                )
            )  # fmt: skip
        acquired = sum(
            e.quantity for e in events if e.kind in (K.BUY, K.STAKING_REWARD)
        )  # fmt: skip
        if acquired > _TINY and position.quantity / acquired < _LEFTOVER_SHARE:
            value = value_of(position, instrument, data, as_of)
            worth = "" if value is None else f", worth {value:.2f} {data.base_currency}"
            left = f"{position.quantity:g} left"
            # The worth changes with the price every day; the quantity is what was looked at.
            found.append(Finding(LEFTOVER, ticker, None, left + worth, key=left))

    # Downloaded prices are in today's units; a trade before a split is not.
    later_splits = 1.0
    for event in reversed(events):
        if event.kind is K.SPLIT:
            later_splits *= event.split_ratio
            continue
        if event.kind not in (K.BUY, K.SELL) or event.price <= 0:
            continue
        market = prices.at_with_date(event.date) if prices else None
        market_rate = data.fx_at(instrument.currency, event.date)
        if market and market_rate and event.date - market[0] <= _NEAR:
            paid = event.price * event.rate / later_splits
            close = market[1] * market_rate
            if close > 0 and abs(paid / close - 1) > _PRICE_TOLERANCE:
                found.append(
                    Finding(
                        PRICE_OFF, ticker, event.date,
                        f"{event.kind} at {paid / close - 1:+.0%} against the close "
                        f"({event.price / later_splits:g} {event.currency})",
                    )
                )  # fmt: skip
        series = data.fx.get(event.currency) if event.currency else None
        day_rate = series.at_with_date(event.date) if series else None
        if day_rate and event.date - day_rate[0] <= _NEAR and day_rate[1] > 0:
            off = event.rate / day_rate[1] - 1
            if abs(off) > _RATE_TOLERANCE:
                found.append(
                    Finding(
                        RATE_OFF, ticker, event.date,
                        f"{event.kind} at {event.rate:g}, market {day_rate[1]:g} ({off:+.1%})",
                    )
                )  # fmt: skip
    return found
