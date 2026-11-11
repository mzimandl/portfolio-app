"""Returns: time-weighted, money-weighted, per year, against a benchmark."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from portfolio.core.analytics.data import PortfolioData
from portfolio.core.analytics.timeseries import DayPoint
from portfolio.core.models import TransactionKind as K

_TINY = 1e-9


def _window(days: Sequence[DayPoint], start: date | None, end: date | None) -> Sequence[DayPoint]:
    return [
        p for p in days if (start is None or p.date >= start) and (end is None or p.date <= end)
    ]


def _value_before(days: Sequence[DayPoint], start: date | None) -> float:
    """Value at the end of the day before ``start`` (zero before the history begins)."""
    if start is None:
        return 0.0
    previous = [p for p in days if p.date < start]
    return previous[-1].value if previous else 0.0


def twr(
    days: Sequence[DayPoint], start: date | None = None, end: date | None = None
) -> float | None:
    """Time-weighted return of the period, not annualised (0.10 means +10 %).

    It measures how the investments performed regardless of when money was added or removed.
    Money put in counts from the start of its day, money taken out until the end of its day.
    """
    window = _window(days, start, end)
    if not window:
        return None
    growth = 1.0
    previous = _value_before(days, window[0].date)
    for point in window:
        base = previous + point.put_in
        if base > _TINY:
            growth *= (point.value + point.taken_out) / base
        previous = point.value
    return growth - 1.0


def xirr(flows: Sequence[tuple[date, float]]) -> float | None:
    """Yearly rate at which the dated cash flows balance out (0.10 means 10 % a year).

    Money paid is negative, money received positive. None if there is no such rate.
    """
    flows = [(day, amount) for day, amount in flows if amount]
    if not flows or all(a > 0 for _, a in flows) or all(a < 0 for _, a in flows):
        return None
    first = min(day for day, _ in flows)
    timed = [((day - first).days / 365.0, amount) for day, amount in flows]

    def present_value(rate: float) -> float:
        return sum(amount / (1.0 + rate) ** years for years, amount in timed)

    low, high = -0.999999, 1.0
    value_low = present_value(low)
    value_high = present_value(high)
    while value_low * value_high > 0 and high < 1e15:
        high *= 4
        value_high = present_value(high)
    if value_low * value_high > 0:
        return None
    for _ in range(200):
        middle = (low + high) / 2
        value_middle = present_value(middle)
        if value_low * value_middle <= 0:
            high = middle
        else:
            low, value_low = middle, value_middle
        if high - low < 1e-10 * max(1.0, abs(high)):
            break
    return (low + high) / 2


def money_weighted(
    days: Sequence[DayPoint], start: date | None = None, end: date | None = None
) -> float | None:
    """Yearly return actually earned on the money, taking the timing of payments into account.

    Unlike ``twr`` it is annualised, so it is only meaningful for periods of months or more.
    """
    window = _window(days, start, end)
    if not window:
        return None
    flows = [(window[0].date, -_value_before(days, window[0].date))]
    flows += [(p.date, p.taken_out - p.put_in) for p in window]
    flows.append((window[-1].date, window[-1].value))
    return xirr(flows)


@dataclass(frozen=True)
class YearRow:
    year: int
    start_value: float
    end_value: float
    put_in: float
    taken_out: float
    profit: float  # end - start - put in + taken out; includes dividends, after fees
    twr: float | None


def yearly(days: Sequence[DayPoint]) -> list[YearRow]:
    by_year: dict[int, list[DayPoint]] = defaultdict(list)
    for point in days:
        by_year[point.date.year].append(point)
    rows = []
    previous_value = 0.0
    for year in sorted(by_year):
        points = by_year[year]
        put_in = sum(p.put_in for p in points)
        taken_out = sum(p.taken_out for p in points)
        end_value = points[-1].value
        rows.append(
            YearRow(
                year=year,
                start_value=previous_value,
                end_value=end_value,
                put_in=put_in,
                taken_out=taken_out,
                profit=end_value - previous_value - put_in + taken_out,
                twr=twr(days, points[0].date, points[-1].date),
            )
        )
        previous_value = end_value
    return rows


def price_return(data: PortfolioData, instrument_id: int, start: date, end: date) -> float | None:
    """Return of simply holding one instrument from ``start`` to ``end``, in base currency.

    Used for the benchmark. None if a price or exchange rate is missing at either end.
    """
    instrument = data.instruments[instrument_id]
    prices = data.prices.get(instrument_id)
    if not prices:
        return None
    worth = []
    for day in (start, end):
        price, rate = prices.at(day), data.fx_at(instrument.currency, day)
        if price is None or rate is None:
            return None
        worth.append(price * rate)
    return worth[1] / worth[0] - 1.0 if worth[0] else None


_MONEY_IN = {K.BUY: 1, K.DEPOSIT: 1, K.SELL: -1, K.WITHDRAWAL: -1}


def invested_by_period(
    data: PortfolioData, span: str = "year", *, include_inactive: bool = False
) -> list[dict]:
    """New money per year or month: buys and deposits minus sells and withdrawals.

    Each row is ``{"period": "2024" or "2024-03", "total": ..., <instrument type>: ...}``.
    """
    if span not in ("year", "month"):
        raise ValueError("span must be 'year' or 'month'")
    periods: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for instrument_id in data.instrument_ids(include_inactive=include_inactive):
        instrument_type = data.instruments[instrument_id].type
        for event in data.events[instrument_id]:
            sign = _MONEY_IN.get(event.kind)
            if sign is None:
                continue
            cash = event.amount if event.kind in (K.DEPOSIT, K.WITHDRAWAL) else (
                event.quantity * event.price)  # fmt: skip
            period = event.date.strftime("%Y" if span == "year" else "%Y-%m")
            periods[period][instrument_type] += sign * cash * event.rate
    return [
        {"period": period, "total": sum(by_type.values()), **dict(sorted(by_type.items()))}
        for period, by_type in sorted(periods.items())
    ]
