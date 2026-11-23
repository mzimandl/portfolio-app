"""Valuation ratios for every past day, worked out from reported results and prices.

A result counts from the end of its period on (in reality it is published some weeks later).
Earnings and revenue are taken over the last twelve months: the sum of the last four quarters
when they are all there, otherwise the last year, whichever ends later. Equity and the number
of shares are those of the newest period. Results in another currency than the share's price
are converted at the exchange rate of the day.

A traded unit is not always one reported share: a depositary receipt can stand for a quarter
of a share, a class B share for 1/1500 of a class A one. ``share_units`` estimates how many
traded units one reported share is from the market value the source reports; when that is
clearly not 1, per-share figures are worked out from the totals divided by that many units.
"""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from portfolio.core.analytics.data import PortfolioData
from portfolio.core.models import Snapshot, Statement

_QUARTERS_SPAN = timedelta(days=300)  # four quarter ends lie about 273 days apart
_TOO_OLD = timedelta(days=550)  # a result older than this is not used any more
_YEAR = timedelta(days=365)
_SAME_UNITS = (0.8, 1.25)  # a units estimate within this band means one unit is one share


@dataclass(frozen=True, slots=True)
class RatioPoint:
    """One trading day. None where the inputs are missing or the ratio means nothing (a loss
    gives no P/E)."""

    date: date
    price: float  # in the instrument's currency
    pe: float | None
    pb: float | None
    ps: float | None
    dividend_yield: float | None  # dividends of the last 12 months / price


def preferred(statements: Sequence[Statement]) -> list[Statement]:
    """One source per company: the SEC's when they are usable (they reach back much further
    and are what the company filed), otherwise Yahoo's.

    Usable means the newest SEC period with any per-share basis (EPS or shares) is no older
    than Yahoo's newest. Companies with several share classes, like Berkshire Hathaway, tag
    no share count, and then Yahoo's numbers are the better ones.
    """
    sec = [s for s in statements if s.source == "sec"]
    yahoo = [s for s in statements if s.source != "sec"]
    usable = [s.period_end for s in sec if s.eps is not None or s.shares is not None]
    if not usable:
        return yahoo or sec
    if yahoo and max(usable) < max(s.period_end for s in yahoo) - _QUARTERS_SPAN / 2:
        return yahoo
    return sec


def _value(s: Statement, field: str, shares: float | None) -> float | None:
    """A field of one period; EPS missing is net income / shares where both are known."""
    value = getattr(s, field)
    if value is None and field == "eps":
        count = s.shares or shares
        if s.net_income is not None and count:
            value = s.net_income / count
    return value


def _twelve_months(
    field: str, quarters: Sequence[Statement], years: Sequence[Statement], day, shares=None
):
    """Value over the last twelve months known on ``day``, or None."""
    best = None
    known_q = [(s, v) for s in quarters if (v := _value(s, field, shares)) is not None]
    if len(known_q) >= 4:
        last = known_q[-4:]
        if last[-1][0].period_end - last[0][0].period_end <= _QUARTERS_SPAN:
            best = (sum(v for _, v in last), last[-1][0].period_end)
    for s in reversed(years):
        value = _value(s, field, shares)
        if value is not None:
            if best is None or s.period_end > best[1]:
                best = (value, s.period_end)
            break
    if best is None or day - best[1] > _TOO_OLD:
        return None
    return best[0]


def _newest(field: str, known: Sequence[Statement], day):
    for s in reversed(known):
        value = getattr(s, field)
        if value is not None:
            return value if day - s.period_end <= _TOO_OLD else None
    return None


def daily_ratios(
    data: PortfolioData,
    instrument_id: int,
    statements: Sequence[Statement],
    start: date | None = None,
    end: date | None = None,
    units: float = 1.0,
) -> list[RatioPoint]:
    """Every day with a stored price, from ``start`` to ``end``.

    ``units`` is how many traded units one reported share is (see ``share_units``).
    """
    instrument = data.instruments[instrument_id]
    prices = data.prices.get(instrument_id)
    if not prices:
        return []
    ordered = sorted(statements, key=lambda s: s.period_end)
    ends = [s.period_end for s in ordered]
    dividend_days = sorted(data.dividends.get(instrument_id, {}).items())
    first_price = prices.dates[0]
    points = []
    for day, price in zip(prices.dates, prices.values, strict=True):
        if (start and day < start) or (end and day > end) or price <= 0:
            continue
        known = ordered[: bisect_right(ends, day)]
        quarters = [s for s in known if s.period == "quarterly"]
        years = [s for s in known if s.period == "annual"]
        pe = pb = ps = None
        factor = _conversion(data, known[-1].currency, instrument.currency, day) if known else None
        if factor:
            shares = _newest("shares", known, day)
            if units == 1.0:
                eps = _twelve_months("eps", quarters, years, day, shares)
            else:
                # Reported EPS may be per share of another class: use the totals.
                income = _twelve_months("net_income", quarters, years, day)
                eps = income / shares if income is not None and shares else None
            if shares:
                shares *= units
                eps = eps / units if eps is not None else None
            if eps and eps > 0:
                pe = price / (eps * factor)
            equity = _newest("equity", known, day)
            if equity and equity > 0 and shares:
                pb = price / (equity / shares * factor)
            revenue = _twelve_months("revenue", quarters, years, day)
            if revenue and revenue > 0 and shares:
                ps = price / (revenue / shares * factor)
        dividend_yield = None
        if day - first_price >= _YEAR:
            paid = sum(amount for paid_on, amount in dividend_days if day - _YEAR < paid_on <= day)
            dividend_yield = paid / price
        points.append(RatioPoint(day, price, pe, pb, ps, dividend_yield))
    return points


def share_units(
    data: PortfolioData,
    instrument_id: int,
    statements: Sequence[Statement],
    snapshots: Sequence[Snapshot],
) -> float:
    """How many traded units one reported share is: market value / (price × shares) on the
    newest day the source reported a market value. 1 when that is about 1 or unknown."""
    prices = data.prices.get(instrument_id)
    for snapshot in reversed(snapshots):
        if not snapshot.market_cap or not prices:
            continue
        price = prices.at(snapshot.date)
        known = [s for s in statements if s.period_end <= snapshot.date and s.shares]
        if not price or not known:
            return 1.0
        units = snapshot.market_cap / (price * known[-1].shares)
        low, high = _SAME_UNITS
        return 1.0 if low <= units <= high else units
    return 1.0


def _conversion(data: PortfolioData, reported_in: str, quoted_in: str, day: date) -> float | None:
    """Units of the quote currency per unit of the reporting currency on ``day``."""
    if reported_in == quoted_in:
        return 1.0
    reported, quoted = data.fx_at(reported_in, day), data.fx_at(quoted_in, day)
    return reported / quoted if reported and quoted else None


@dataclass(frozen=True)
class RatioSummary:
    """The newest day and the typical level over the whole history worked out."""

    pe: float | None
    pe_median: float | None
    pb: float | None
    pb_median: float | None
    ps: float | None
    ps_median: float | None
    dividend_yield: float | None
    since: date | None  # first day with a P/E


def summarize_ratios(points: Sequence[RatioPoint]) -> RatioSummary:
    def typical(name: str) -> float | None:
        values = [getattr(p, name) for p in points if getattr(p, name) is not None]
        return median(values) if values else None

    last = points[-1] if points else None
    first_pe = next((p.date for p in points if p.pe is not None), None)
    return RatioSummary(
        pe=last.pe if last else None,
        pe_median=typical("pe"),
        pb=last.pb if last else None,
        pb_median=typical("pb"),
        ps=last.ps if last else None,
        ps_median=typical("ps"),
        dividend_yield=last.dividend_yield if last else None,
        since=first_pe,
    )
