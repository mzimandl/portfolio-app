"""How much prices in the shops rose, and what is left of a return after that.

The index has one value per month, its average price level. It is taken as the level at the
end of that month, so a calendar year runs from last December's value to this December's,
which is how yearly inflation is usually reported.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from portfolio.core.analytics.data import Series


def _month_before(day: date) -> date:
    """The first day of the month before the one ``day`` is in."""
    first = day.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


def _level(index: Series, day: date) -> tuple[float, bool] | None:
    """The price level at the end of ``day``: the value of the last month that has ended by
    then. Returns (value, whether that month is published) or None before the first one."""
    month = _month_before(day + timedelta(days=1))
    found = index.at_with_date(month)
    if found is None or index.dates[0] > month:
        return None
    published_month, value = found
    return value, published_month == month


@dataclass(frozen=True)
class Inflation:
    change: float  # 0.05: prices rose by 5 %
    complete: bool  # False: the index for the end of the period is not published yet
    known_until: date  # the first day of the last month published


def inflation(index: Series, start: date, end: date) -> Inflation | None:
    """From the start of ``start`` to the end of ``end``; None when the index does not reach
    back that far. Days after the last published month use that month's value."""
    if not index:
        return None
    before = _level(index, start - timedelta(days=1))
    after = _level(index, end)
    if before is None or after is None:
        return None
    return Inflation(after[0] / before[0] - 1, after[1] and before[1], index.dates[-1])


def real(nominal: float | None, change: float | None) -> float | None:
    """What a return is worth in today's prices: 10 % with 4 % inflation is 1.10 / 1.04 − 1."""
    if nominal is None or change is None:
        return None
    return (1 + nominal) / (1 + change) - 1


def yearly(change: float, start: date, end: date) -> float:
    """The inflation over a period as a rate per year."""
    years = ((end - start).days + 1) / 365.25
    return (1 + change) ** (1 / years) - 1 if years > 0 else change
