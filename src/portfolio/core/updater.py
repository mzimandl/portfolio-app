"""Downloading new prices and exchange rates into the database."""

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from portfolio.core import repo
from portfolio.core.analytics.data import PortfolioData, load_data
from portfolio.core.analytics.positions import position_at
from portfolio.core.models import FxRate, Instrument, Price, ValuationMethod
from portfolio.core.providers.base import Bar, MarketDataProvider, ProviderError

BENCHMARK_TYPE = "benchmark"
_LEAD_IN = timedelta(days=7)  # so the first transaction day has a price even after a holiday
_NO_QUANTITY = 1e-12


@dataclass
class UpdateResult:
    updated: dict[str, int] = field(default_factory=dict)  # what -> number of days saved
    errors: dict[str, str] = field(default_factory=dict)  # what -> why it failed
    new_splits: list[str] = field(default_factory=list)  # tickers whose history was reloaded

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
    today: date | None = None,
) -> UpdateResult:
    """Fetch what is new since the last update. Saves after every instrument and currency,
    so one failure does not lose the rest.

    ``full`` downloads every history again from the first transaction on.
    """
    today = today or date.today()
    result = UpdateResult()

    benchmark_id = None
    if benchmark:
        try:
            benchmark_id = ensure_benchmark(conn, provider, benchmark).id
        except (ProviderError, sqlite3.Error) as e:
            conn.rollback()
            result.errors[f"benchmark {benchmark}"] = str(e)

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

    for currency in sorted(_currencies_in_use(data, benchmark_id) - {base_currency}):
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
    return result


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
    # The last stored day is fetched again: it may have been saved before the market closed.
    bars = provider.prices(symbol, history_start if from_start else stored.dates[-1])

    reloaded = False
    if not from_start and _has_new_split(conn, instrument.id, bars):
        # Prices already stored are in the share units from before the split.
        bars = provider.prices(symbol, history_start)
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
