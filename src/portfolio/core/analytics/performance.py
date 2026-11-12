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


def _worth(data: PortfolioData, instrument_id: int, day: date) -> float | None:
    """One unit of the instrument in base currency on ``day``."""
    prices = data.prices.get(instrument_id)
    price = prices.at(day) if prices else None
    rate = data.fx_at(data.instruments[instrument_id].currency, day)
    return None if price is None or rate is None else price * rate


def _dividend_growth(data: PortfolioData, instrument_id: int, day: date) -> float:
    """How many units one unit becomes when that day's dividend is reinvested."""
    dividend = data.dividends.get(instrument_id, {}).get(day)
    price = data.prices[instrument_id].at(day) if dividend else None
    return 1.0 + dividend / price if dividend and price else 1.0


def holding_return(data: PortfolioData, instrument_id: int, start: date, end: date) -> float | None:
    """Return of simply holding one instrument from ``start`` to ``end``, in base currency,
    with its dividends reinvested.

    Used for the benchmark. None if a price or exchange rate is missing at either end.
    """
    first, last = _worth(data, instrument_id, start), _worth(data, instrument_id, end)
    if not first or last is None:
        return None
    units = 1.0
    for day in data.dividends.get(instrument_id, {}):
        if start < day <= end:
            units *= _dividend_growth(data, instrument_id, day)
    return units * last / first - 1.0


def same_money(
    data: PortfolioData,
    instrument_id: int,
    days: Sequence[DayPoint],
    start: date | None = None,
    end: date | None = None,
) -> list[DayPoint]:
    """What the same payments would have done in another instrument (the benchmark).

    Whatever ``days`` were worth before ``start`` is put in on the first day; after that the
    same money goes in and comes out on the same days. Dividends are reinvested. Money that
    arrives before the instrument has a price waits as cash. The value can turn negative:
    more was taken out than the instrument would have made.
    """
    window = _window(days, start, end)
    if not window:
        return []
    opening = _value_before(days, window[0].date)
    units = cash = invested = 0.0
    points = []
    for index, point in enumerate(window):
        put_in = point.put_in + (opening if index == 0 else 0.0)
        cash += put_in - point.taken_out
        invested += put_in - point.taken_out
        worth = _worth(data, instrument_id, point.date)
        if worth:
            units *= _dividend_growth(data, instrument_id, point.date)
            units += cash / worth
            cash = 0.0
        value = cash + (units * worth if worth else 0.0)
        points.append(DayPoint(point.date, value, put_in, point.taken_out, invested, 0.0))
    return points


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
