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


def _day_growth(previous: float, point: DayPoint) -> float:
    """Growth factor of one day, given the value at the end of the day before.

    The holding is first valued at the price of the day's first trade (``early_gain``), then
    the money put in joins it. Money taken out counts until the end of its day. So a
    purchase earns only from its own price on, and does not water down what the older units
    did before it.
    """
    factor = 1.0
    before = previous
    if point.early_gain and previous > _TINY and previous + point.early_gain > _TINY:
        before = previous + point.early_gain
        factor = before / previous
    base = before + point.put_in
    if base > _TINY:
        factor *= (point.value + point.taken_out) / base
    return factor


def twr(
    days: Sequence[DayPoint], start: date | None = None, end: date | None = None
) -> float | None:
    """Time-weighted return of the period, not annualised (0.10 means +10 %).

    It measures how the investments performed regardless of when money was added or removed.
    Money put in counts from the price it was invested at, money taken out until the end of
    its day (see ``_day_growth``).
    """
    window = _window(days, start, end)
    if not window:
        return None
    growth = 1.0
    previous = _value_before(days, window[0].date)
    for point in window:
        growth *= _day_growth(previous, point)
        previous = point.value
    return growth - 1.0


def growth(
    days: Sequence[DayPoint], start: date | None = None, end: date | None = None
) -> list[tuple[date, float]]:
    """What 1 unit of money invested before the period is worth at the end of each day,
    by the time-weighted return. New money does not move it."""
    window = _window(days, start, end)
    if not window:
        return []
    points = []
    level = 1.0
    previous = _value_before(days, window[0].date)
    for point in window:
        level *= _day_growth(previous, point)
        previous = point.value
        points.append((point.date, level))
    return points


def drops(
    days: Sequence[DayPoint], start: date | None = None, end: date | None = None
) -> list[tuple[date, float]]:
    """How far below its highest level so far the growth is each day (-0.2 means 20 % below)."""
    points = []
    peak = 1.0
    for day, level in growth(days, start, end):
        peak = max(peak, level)
        points.append((day, level / peak - 1.0 if peak > _TINY else 0.0))
    return points


@dataclass(frozen=True)
class Drawdown:
    deepest: float  # the largest drop from a peak, as a negative fraction (0 if none)
    peak: date | None  # the day of the high before that drop
    trough: date | None  # the day it was deepest
    recovered: date | None  # the first day back at that high; None if not yet
    current: float  # how far below the highest level the last day is


def drawdown(
    days: Sequence[DayPoint], start: date | None = None, end: date | None = None
) -> Drawdown | None:
    """The deepest drop of the time-weighted growth in the period, and where it stands now."""
    levels = growth(days, start, end)
    if not levels:
        return None
    deepest, peak_day, trough_day, recovered = 0.0, None, None, None
    high, high_day = 1.0, levels[0][0]
    for day, level in levels:
        if level >= high:
            high, high_day = level, day
            if trough_day is not None and recovered is None and high_day > trough_day:
                recovered = day
            continue
        drop = level / high - 1.0 if high > _TINY else 0.0
        if drop < deepest:
            deepest, peak_day, trough_day, recovered = drop, high_day, day, None
    current = levels[-1][1] / high - 1.0 if high > _TINY else 0.0
    return Drawdown(deepest, peak_day, trough_day, recovered, current)


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


def monthly(days: Sequence[DayPoint]) -> dict[int, dict[int, float]]:
    """Time-weighted return of every calendar month: ``{year: {month: return}}``."""
    spans: dict[tuple[int, int], list[date]] = {}
    for point in days:
        key = (point.date.year, point.date.month)
        if key in spans:
            spans[key][1] = point.date
        else:
            spans[key] = [point.date, point.date]
    months: dict[int, dict[int, float]] = defaultdict(dict)
    for (year, month), (first, last) in spans.items():
        months[year][month] = twr(days, first, last)
    return dict(months)


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
