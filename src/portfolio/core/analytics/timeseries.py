"""Day-by-day history of instruments and of groups of them."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from portfolio.core.analytics.data import PortfolioData
from portfolio.core.analytics.positions import Position, apply, value_of
from portfolio.core.models import TransactionKind


@dataclass(frozen=True, slots=True)
class DayPoint:
    """One day, in base currency. ``put_in`` and ``taken_out`` are that day's movements;
    the other numbers are the state at the end of the day."""

    date: date
    value: float
    put_in: float  # buys, deposits and fees paid that day
    taken_out: float  # sells, withdrawals and dividends received that day
    invested: float  # buys and deposits minus sells and withdrawals, so far
    income: float  # dividends minus fees, so far

    @property
    def profit(self) -> float:
        """Value minus the money still invested (same definition as the overview)."""
        return self.value - self.invested

    @property
    def net_profit(self) -> float:
        return self.profit + self.income


def instrument_daily(data: PortfolioData, instrument_id: int, end: date) -> list[DayPoint]:
    """Every calendar day from the first transaction to ``end``.

    While a price is still missing the value is carried at cost, so no gain or loss
    is shown for those days.
    """
    instrument = data.instruments[instrument_id]
    events = data.events.get(instrument_id, [])
    if not events or events[0].date > end:
        return []
    # Product of the split ratios still to come, used to scale older quantities.
    later_splits = 1.0
    for event in events:
        if event.kind is TransactionKind.SPLIT and event.date <= end:
            later_splits *= event.split_ratio

    position = Position()
    points: list[DayPoint] = []
    previous_value = 0.0
    index = 0
    day = events[0].date
    one_day = timedelta(days=1)
    while day <= end:
        put_in = taken_out = 0.0
        while index < len(events) and events[index].date == day:
            event = events[index]
            if event.kind is TransactionKind.SPLIT:
                later_splits /= event.split_ratio
            added, removed = apply(position, event, instrument, data)
            put_in += added
            taken_out += removed
            index += 1
        value = value_of(position, instrument, data, day, later_splits=later_splits)
        if value is None:
            value = previous_value + put_in - taken_out
        points.append(
            DayPoint(
                date=day,
                value=value,
                put_in=put_in,
                taken_out=taken_out,
                invested=position.invested - position.returned,
                income=position.dividends - position.fees,
            )
        )
        previous_value = value
        day += one_day
    return points


def combine(series: Iterable[list[DayPoint]]) -> list[DayPoint]:
    """Sum several instruments' histories into one, from the earliest first day on."""
    series = [points for points in series if points]
    if not series:
        return []
    start = min(points[0].date for points in series)
    end = max(points[-1].date for points in series)
    length = (end - start).days + 1
    totals = [[0.0] * length for _ in range(5)]
    value, put_in, taken_out, invested, income = totals
    for points in series:
        offset = (points[0].date - start).days
        for i, point in enumerate(points, offset):
            value[i] += point.value
            put_in[i] += point.put_in
            taken_out[i] += point.taken_out
            invested[i] += point.invested
            income[i] += point.income
        # An instrument whose history ends early keeps its last state.
        last = points[-1]
        for i in range(offset + len(points), length):
            value[i] += last.value
            invested[i] += last.invested
            income[i] += last.income
    return [
        DayPoint(start + timedelta(days=i), value[i], put_in[i], taken_out[i], invested[i],
                 income[i])
        for i in range(length)
    ]  # fmt: skip


def all_daily(
    data: PortfolioData, end: date | None = None, *, include_inactive: bool = False
) -> dict[int, list[DayPoint]]:
    """History of every instrument, keyed by instrument id. The expensive step; cache it."""
    end = end or date.today()
    return {
        instrument_id: instrument_daily(data, instrument_id, end)
        for instrument_id in data.instrument_ids(include_inactive=include_inactive)
    }


def thin[T](points: list[T], max_points: int) -> tuple[list[T], int]:
    """At most about ``max_points`` evenly spaced points for drawing, and the spacing used.

    The last point is always kept, so a chart ends on the current state. With spacing 1
    the list is returned as it is.
    """
    if max_points < 2 or len(points) <= max_points:
        return points, 1
    step = -(-len(points) // max_points)  # rounded up
    # Counted back from the end; the very first point is added so the range stays complete.
    kept = points[::-1][::step][::-1]
    if kept[0] is not points[0]:
        kept.insert(0, points[0])
    return kept, step
