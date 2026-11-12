"""Dividends: what was received, and what the downloaded data says should have been."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from portfolio.core.analytics.data import PortfolioData
from portfolio.core.analytics.positions import Position, apply
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod

# A dividend is paid some weeks after the day the price data reports it.
PAYMENT_DELAY = timedelta(days=60)


@dataclass(frozen=True)
class Expected:
    """A dividend the price data reports for units held the day before."""

    date: date
    quantity: float  # units held, in today's units
    gross: float  # before tax, in base currency at that day's exchange rate


def expected(data: PortfolioData, instrument_id: int, as_of: date) -> list[Expected]:
    instrument = data.instruments[instrument_id]
    reported = data.dividends.get(instrument_id)
    if not reported or instrument.valuation is ValuationMethod.MANUAL:
        return []
    events = data.events.get(instrument_id, [])
    position = Position()
    index = 0
    found = []
    for day in sorted(reported):
        if day > as_of:
            break
        while index < len(events) and events[index].date < day:
            apply(position, events[index], instrument, data)
            index += 1
        # Reported dividends are per unit as units are counted today.
        later_splits = 1.0
        for event in events[index:]:
            if event.kind is K.SPLIT:
                later_splits *= event.split_ratio
        quantity = position.quantity * later_splits
        rate = data.fx_at(instrument.currency, day)
        if quantity > 1e-9 and rate is not None:
            found.append(Expected(day, quantity, quantity * reported[day] * rate))
    return found


@dataclass(frozen=True)
class DividendYear:
    """One instrument in one year, in base currency."""

    year: int
    ticker: str
    received: float  # net, as recorded
    tax: float  # withheld, as recorded
    payments: int
    expected: float | None  # gross, by the day the price data reports; None if it has none
    expected_payments: int


def by_year(data: PortfolioData, instrument_ids: list[int], as_of: date) -> list[DividendYear]:
    """Recorded and expected dividends per instrument and year, newest year first.

    The two can fall into different years around New Year: the expected ones are dated by
    the day the price data reports them, the recorded ones by the day you entered.
    """
    rows = []
    for instrument_id in instrument_ids:
        instrument = data.instruments[instrument_id]
        years: dict[int, list] = defaultdict(lambda: [0.0, 0.0, 0, 0.0, 0])
        for event in data.events.get(instrument_id, []):
            if event.kind is K.DIVIDEND and event.date <= as_of:
                year = years[event.date.year]
                year[0] += event.amount * event.rate
                year[1] += event.tax * event.rate
                year[2] += 1
        has_data = instrument_id in data.dividends
        for item in expected(data, instrument_id, as_of):
            year = years[item.date.year]
            year[3] += item.gross
            year[4] += 1
        for number, (received, tax, payments, gross, count) in years.items():
            rows.append(
                DividendYear(
                    number, instrument.ticker, received, tax, payments,
                    gross if has_data else None, count,
                )
            )  # fmt: skip
    rows.sort(key=lambda row: (-row.year, row.ticker))
    return rows


@dataclass(frozen=True)
class DividendRow:
    """One instrument's dividends, in base currency."""

    ticker: str
    type: str
    received: float  # net, all time
    last_year: float  # net, in the 365 days up to today
    tax: float  # withheld, all time
    payments: int
    missing: int  # payments the price data expects beyond the recorded ones


def by_instrument(data: PortfolioData, instrument_ids: list[int], as_of: date) -> list[DividendRow]:
    """Instruments that paid or should have paid a dividend."""
    since = as_of - timedelta(days=365)
    rows = []
    for instrument_id in instrument_ids:
        instrument = data.instruments[instrument_id]
        paid = [
            e for e in data.events.get(instrument_id, [])
            if e.kind is K.DIVIDEND and e.date <= as_of
        ]  # fmt: skip
        # The newest expected ones may simply not have been paid out yet.
        due = [e for e in expected(data, instrument_id, as_of) if e.date <= as_of - PAYMENT_DELAY]
        if not paid and not due:
            continue
        rows.append(
            DividendRow(
                ticker=instrument.ticker,
                type=instrument.type,
                received=sum(e.amount * e.rate for e in paid),
                last_year=sum(e.amount * e.rate for e in paid if e.date > since),
                tax=sum(e.tax * e.rate for e in paid),
                payments=len(paid),
                missing=max(len(due) - len(paid), 0),
            )
        )
    return rows
