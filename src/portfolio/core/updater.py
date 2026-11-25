"""Downloading new prices and exchange rates into the database."""

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from portfolio.core import repo
from portfolio.core.analytics.data import PortfolioData, load_data
from portfolio.core.analytics.positions import position_at
from portfolio.core.i18n import tr
from portfolio.core.models import (
    FxRate,
    Instrument,
    Price,
    Profile,
    Snapshot,
    Statement,
    ValuationMethod,
)
from portfolio.core.providers.base import Bar, MarketDataProvider, ProviderError
from portfolio.core.providers.base import Statement as Reported
from portfolio.core.providers.official import OfficialProvider
from portfolio.core.providers.sec import SecProvider

BENCHMARK_TYPE = "benchmark"
_LEAD_IN = timedelta(days=7)  # so the first transaction day has a price even after a holiday
_NO_QUANTITY = 1e-12
# Company results are fetched again once the newest stored period is older than this.
_STATEMENTS_DUE = timedelta(days=100)
# The same for SEC filings, which come later: a 10-K up to 90 days after the year ends.
_SEC_DUE = timedelta(days=150)
# Sector and country rarely change: asked again after this long.
_PROFILE_DUE = timedelta(days=180)
# The ČNB rates of a past year are complete once a day this late in December is stored.
_LAST_DECEMBER_DAY = 20


@dataclass
class UpdateResult:
    updated: dict[str, int] = field(default_factory=dict)  # what -> number of days saved
    errors: dict[str, str] = field(default_factory=dict)  # what -> why it failed
    new_splits: list[str] = field(default_factory=list)  # tickers whose history was reloaded
    fundamentals: list[str] = field(default_factory=list)  # tickers whose ratios were saved
    sec: list[str] = field(default_factory=list)  # tickers whose SEC results were saved

    @property
    def ok(self) -> bool:
        return not self.errors


def ensure_benchmark(
    conn: sqlite3.Connection, provider: MarketDataProvider, symbol: str
) -> Instrument:
    """The instrument holding the benchmark's prices; created on first use. Commits."""
    existing = repo.get_instrument_by_ticker(conn, symbol)
    if existing:
        return existing
    currency = provider.currency(symbol)
    with conn:
        if currency not in repo.list_currencies(conn):
            repo.add_currency(conn, currency)
        if BENCHMARK_TYPE not in repo.list_instrument_types(conn):
            repo.add_instrument_type(conn, BENCHMARK_TYPE)
        return repo.add_instrument(
            conn,
            Instrument(
                ticker=symbol, type=BENCHMARK_TYPE, currency=currency,
                valuation=ValuationMethod.YAHOO, name="Benchmark",
            ),
        )  # fmt: skip


def update_market_data(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    base_currency: str,
    *,
    benchmark: str | None = None,
    full: bool = False,
    fundamentals: bool = True,
    sec: SecProvider | None = None,
    sec_tickers: dict[str, str] | None = None,
    official: OfficialProvider | None = None,
    inflation_region: str | None = None,
    today: date | None = None,
) -> UpdateResult:
    """Fetch what is new since the last update. Saves after every instrument and currency,
    so one failure does not lose the rest.

    ``full`` downloads every history again from the first transaction on. ``fundamentals``
    also saves today's valuation ratios of the shares held (once a day) and their reported
    results when new ones are due. With ``sec`` the results of US companies also come from
    SEC EDGAR, which reaches back much further; ``sec_tickers`` names their ticker there
    where it differs from the instrument's. With ``official`` the exchange rates of the
    Czech National Bank are saved too (when the base currency is CZK), and the consumer price
    index of ``inflation_region`` from Eurostat.
    """
    today = today or date.today()
    result = UpdateResult()

    benchmark_id = None
    if benchmark:
        try:
            benchmark_id = ensure_benchmark(conn, provider, benchmark).id
        except (ProviderError, sqlite3.Error) as e:
            conn.rollback()
            result.errors[tr("benchmark {symbol}", symbol=benchmark)] = str(e)

    data = load_data(conn, base_currency)
    first_dates = [events[0].date for events in data.events.values() if events]
    if not first_dates:
        return result
    portfolio_start = min(first_dates) - _LEAD_IN

    for instrument in sorted(data.instruments.values(), key=lambda i: i.ticker):
        events = data.events.get(instrument.id)
        if instrument.id == benchmark_id:
            history_start = portfolio_start
        elif _needs_prices(data, instrument, today):
            history_start = events[0].date - _LEAD_IN
        else:
            continue
        try:
            saved, reloaded = _update_prices(conn, provider, data, instrument, history_start, full)
        except (ProviderError, sqlite3.Error) as e:
            conn.rollback()
            result.errors[instrument.ticker] = str(e)
            continue
        result.updated[instrument.ticker] = saved
        if reloaded:
            result.new_splits.append(instrument.ticker)

    if fundamentals:
        for instrument in sorted(data.instruments.values(), key=lambda i: i.ticker):
            if instrument.id == benchmark_id or not _needs_prices(data, instrument, today):
                continue
            try:
                _update_profile(conn, provider, instrument, today)
            except (ProviderError, sqlite3.Error) as e:
                conn.rollback()
                result.errors[tr("sector and country {ticker}", ticker=instrument.ticker)] = str(e)
            if _asked_today(conn, instrument.id, today):
                continue
            try:
                if _update_fundamentals(conn, provider, instrument, today):
                    result.fundamentals.append(instrument.ticker)
            except (ProviderError, sqlite3.Error) as e:
                conn.rollback()
                result.errors[tr("fundamentals {ticker}", ticker=instrument.ticker)] = str(e)
                continue
            if sec is not None:
                try:
                    if _update_sec(conn, sec, instrument, sec_tickers or {}, today):
                        result.sec.append(instrument.ticker)
                except (ProviderError, sqlite3.Error) as e:
                    conn.rollback()
                    result.errors[f"SEC {instrument.ticker}"] = str(e)
            try:
                saved = _backfill_prices(conn, provider, instrument)
            except (ProviderError, sqlite3.Error) as e:
                conn.rollback()
                result.errors[tr("older prices {ticker}", ticker=instrument.ticker)] = str(e)
            else:
                if saved:
                    result.updated[instrument.ticker] = (
                        result.updated.get(instrument.ticker, 0) + saved
                    )

    for currency in sorted(
        (_currencies_in_use(data, benchmark_id) | _reporting_currencies(conn)) - {base_currency}
    ):
        label = f"{currency}/{base_currency}"
        series = data.fx.get(currency)
        start = portfolio_start if full or not series else series.dates[-1]
        try:
            bars = provider.fx_rates(currency, base_currency, start)
            with conn:
                repo.save_fx_rates(
                    conn, [FxRate(bar.date, currency, base_currency, bar.close) for bar in bars]
                )
        except (ProviderError, sqlite3.Error) as e:
            conn.rollback()
            result.errors[label] = str(e)
            continue
        result.updated[label] = len(bars)

    if official is not None:
        if base_currency == "CZK":
            _update_cnb(conn, official, min(first_dates).year, today, result)
        if inflation_region:
            _update_inflation(conn, official, inflation_region, today, result)
    return result


def _update_cnb(
    conn: sqlite3.Connection,
    official: OfficialProvider,
    first_year: int,
    today: date,
    result: UpdateResult,
) -> None:
    """The ČNB rates of every year since the first transaction. A past year is fetched once;
    the current one on every update until today's rates are stored."""
    stored = repo.official_rate_years(conn)
    for year in range(first_year, today.year + 1):
        last = stored.get(year)
        if last is not None and (
            last >= today or (year < today.year and last >= date(year, 12, _LAST_DECEMBER_DAY))
        ):
            continue
        try:
            rates = official.cnb_year(year)
            with conn:
                repo.save_official_rates(conn, rates)
        except (ProviderError, sqlite3.Error) as e:
            conn.rollback()
            result.errors[tr("ČNB rates {year}", year=year)] = str(e)
            continue
        result.updated[f"ČNB rates {year}"] = len({day for _, day, _ in rates})


def _update_inflation(
    conn: sqlite3.Connection,
    official: OfficialProvider,
    region: str,
    today: date,
    result: UpdateResult,
) -> None:
    """The whole monthly index again (it is small, and revised), until last month's is out."""
    stored = repo.list_inflation(conn, region)
    last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    if stored and stored[-1][0] >= last_month:
        return
    label = f"inflation {region}"
    try:
        months = official.hicp(region)
        with conn:
            repo.save_inflation(conn, region, months)
    except (ProviderError, sqlite3.Error) as e:
        conn.rollback()
        result.errors[tr("inflation {region}", region=region)] = str(e)
        return
    result.updated[label] = len(months) - len(stored)


def _update_profile(
    conn: sqlite3.Connection, provider: MarketDataProvider, instrument: Instrument, today: date
) -> None:
    """Sector and country from the source, unless entered by hand or asked recently."""
    existing = repo.list_profiles(conn).get(instrument.id)
    if existing is not None and (existing.manual or existing.fetched > today - _PROFILE_DUE):
        return
    company = provider.company(instrument.yahoo_symbol or instrument.ticker)
    with conn:  # also saved when empty: "asked, nothing there"
        repo.save_profile(
            conn,
            Profile(
                instrument.id,
                company.sector if company else None,
                company.country if company else None,
                today,
            ),
        )


def _update_fundamentals(
    conn: sqlite3.Connection, provider: MarketDataProvider, instrument: Instrument, today: date
) -> bool:
    """Today's ratios and the reported results when new ones are due. Returns whether there
    were ratios (False for funds and coins)."""
    symbol = instrument.yahoo_symbol or instrument.ticker
    ratios = provider.ratios(symbol)
    if ratios is None:
        with conn:  # remembered as "asked today, nothing there"
            repo.save_snapshot(conn, Snapshot(instrument.id, today))
        return False
    newest = conn.execute(
        "SELECT max(period_end) FROM statements WHERE instrument_id = ? AND source = 'yahoo'",
        (instrument.id,),
    ).fetchone()[0]
    due = newest is None or date.fromisoformat(newest) < today - _STATEMENTS_DUE
    currency, found = provider.statements(symbol) if due else (None, [])
    with conn:
        if found:
            if currency not in repo.list_currencies(conn):
                repo.add_currency(conn, currency)
            repo.save_statements(
                conn,
                [
                    Statement(instrument.id, s.period, s.period_end, currency, s.revenue,
                              s.net_income, s.eps, s.equity, s.shares)
                    for s in found
                ],
            )  # fmt: skip
        repo.save_snapshot(
            conn,
            Snapshot(instrument.id, today, ratios.trailing_pe, ratios.forward_pe,
                     ratios.price_to_book, ratios.price_to_sales, ratios.ev_to_ebitda,
                     ratios.market_cap),
        )  # fmt: skip
    return True


_BEFORE_RESULTS = timedelta(days=365)  # a year of prices before the first result: dividends
_GAP = timedelta(days=30)


def _backfill_prices(
    conn: sqlite3.Connection, provider: MarketDataProvider, instrument: Instrument
) -> int:
    """Prices from a year before the oldest stored result up to the first stored price, so
    ratios can be worked out for all of it. Returns the number of days saved."""
    oldest = conn.execute(
        "SELECT min(period_end) FROM statements WHERE instrument_id = ?", (instrument.id,)
    ).fetchone()[0]
    first = conn.execute(
        "SELECT min(date) FROM prices WHERE instrument_id = ?", (instrument.id,)
    ).fetchone()[0]
    if oldest is None or first is None:
        return 0
    start, first = date.fromisoformat(oldest) - _BEFORE_RESULTS, date.fromisoformat(first)
    if first - start <= _GAP:
        return 0
    # Asked again each day for a company listed later than its first result: one request.
    bars = [b for b in provider.prices(instrument.yahoo_symbol or instrument.ticker, start)
            if b.date < first]  # fmt: skip
    with conn:
        repo.save_prices(conn, [_price(instrument.id, bar) for bar in bars])
    return len(bars)


def _asked_today(conn: sqlite3.Connection, instrument_id: int, today: date) -> bool:
    """Company data is asked for at most once a day; a saved snapshot marks it."""
    return bool(
        conn.execute(
            "SELECT 1 FROM fundamentals WHERE instrument_id = ? AND date = ?",
            (instrument_id, today.isoformat()),
        ).fetchone()
    )


def _update_sec(
    conn: sqlite3.Connection,
    sec: SecProvider,
    instrument: Instrument,
    overrides: dict[str, str],
    today: date,
) -> bool:
    """SEC results of a US company, when new ones are due. Returns whether any were saved."""
    ticker = _sec_ticker(conn, instrument, overrides)
    if not ticker:
        return False
    newest = conn.execute(
        "SELECT max(period_end) FROM statements WHERE instrument_id = ? AND source = 'sec'",
        (instrument.id,),
    ).fetchone()[0]
    if newest is not None and date.fromisoformat(newest) >= today - _SEC_DUE:
        return False
    splits = [
        (date.fromisoformat(row[0]), row[1])
        for row in conn.execute(
            "SELECT date, split FROM prices WHERE instrument_id = ? AND split != 0",
            (instrument.id,),
        )
    ]
    found = sec.statements(ticker, splits)
    if not found:
        return False
    _check_against_yahoo(conn, instrument, ticker, found)
    with conn:
        if "USD" not in repo.list_currencies(conn):
            repo.add_currency(conn, "USD")
        repo.save_statements(
            conn,
            [
                Statement(instrument.id, s.period, s.period_end, "USD", s.revenue, s.net_income,
                          s.eps, s.equity, s.shares, source="sec")
                for s in found
            ],
        )  # fmt: skip
    return True


def _sec_ticker(
    conn: sqlite3.Connection, instrument: Instrument, overrides: dict[str, str]
) -> str | None:
    """The ticker to ask the SEC for, or None. Without a setting in the config file only
    companies Yahoo says report in USD are tried, under their symbol without the exchange
    suffix (PEP.DE -> PEP)."""
    if instrument.ticker in overrides:
        return overrides[instrument.ticker] or None
    reported_in = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT currency FROM statements WHERE instrument_id = ? AND source = 'yahoo'",
            (instrument.id,),
        )
    }
    if reported_in != {"USD"}:
        return None
    symbol = instrument.yahoo_symbol or instrument.ticker
    return symbol.split(".")[0].upper()


def _check_against_yahoo(
    conn: sqlite3.Connection, instrument: Instrument, ticker: str, found: list[Reported]
) -> None:
    """Refuse SEC results that are plainly another company's: the yearly revenue must be
    within 10 % of Yahoo's for some year both have."""
    yahoo = {
        date.fromisoformat(row[0]): row[1]
        for row in conn.execute(
            "SELECT period_end, revenue FROM statements WHERE instrument_id = ? "
            "AND source = 'yahoo' AND period = 'annual' AND revenue > 0",
            (instrument.id,),
        )
    }
    pairs = [
        (s.revenue, yahoo[s.period_end])
        for s in found
        if s.period == "annual" and s.revenue and s.period_end in yahoo
    ]
    if pairs and not any(0.9 <= ours / theirs <= 1.1 for ours, theirs in pairs):
        raise ProviderError(
            f"the SEC's results for {ticker} do not match Yahoo's for {instrument.ticker}; "
            'name the right ticker in sec_tickers, or "" to leave it out'
        )


def _reporting_currencies(conn: sqlite3.Connection) -> set[str]:
    """Currencies companies held report in: their results are converted with these rates."""
    rows = conn.execute(
        "SELECT DISTINCT s.currency FROM statements AS s "
        "JOIN instruments AS i ON i.id = s.instrument_id WHERE i.active = 1"
    )
    return {row[0] for row in rows}


def _needs_prices(data: PortfolioData, instrument: Instrument, today: date) -> bool:
    """Active, priced by Yahoo and currently held."""
    if not instrument.active or instrument.valuation is not ValuationMethod.YAHOO:
        return False
    if not data.events.get(instrument.id):
        return False
    return abs(position_at(data, instrument.id, today).quantity) > _NO_QUANTITY


def _update_prices(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    data: PortfolioData,
    instrument: Instrument,
    history_start: date,
    full: bool,
) -> tuple[int, bool]:
    """Returns (days saved, whether a new split made us reload the whole history)."""
    symbol = instrument.yahoo_symbol or instrument.ticker
    stored = data.prices.get(instrument.id)
    from_start = full or not stored
    # Prices from before the first transaction may be stored for the company data.
    earliest = min(history_start, stored.dates[0]) if stored else history_start
    # The last stored day is fetched again: it may have been saved before the market closed.
    bars = provider.prices(symbol, earliest if from_start else stored.dates[-1])

    reloaded = False
    if not from_start and _has_new_split(conn, instrument.id, bars):
        # Prices already stored are in the share units from before the split.
        bars = provider.prices(symbol, earliest)
        reloaded = True
    with conn:
        repo.save_prices(conn, [_price(instrument.id, bar) for bar in bars])
    return len(bars), reloaded


def _has_new_split(conn: sqlite3.Connection, instrument_id: int, bars: list[Bar]) -> bool:
    split_days = [bar.date.isoformat() for bar in bars if bar.split]
    if not split_days:
        return False
    known = {
        row[0]
        for row in conn.execute(
            "SELECT date FROM prices WHERE instrument_id = ? AND split != 0", (instrument_id,)
        )
    }
    return any(day not in known for day in split_days)


def _price(instrument_id: int, bar: Bar) -> Price:
    return Price(
        instrument_id=instrument_id, date=bar.date, close=bar.close, open=bar.open,
        high=bar.high, low=bar.low, dividend=bar.dividend, split=bar.split,
    )  # fmt: skip


def _currencies_in_use(data: PortfolioData, benchmark_id: int | None) -> set[str]:
    """Currencies of active instruments and of everything paid or received for them."""
    currencies: set[str] = set()
    for instrument in data.instruments.values():
        events = data.events.get(instrument.id, [])
        if instrument.id == benchmark_id or (instrument.active and events):
            currencies.add(instrument.currency)
            currencies.update(event.currency for event in events if event.currency)
    return currencies
