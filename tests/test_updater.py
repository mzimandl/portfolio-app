from datetime import date
from decimal import Decimal as D

import pandas as pd
import pytest

from portfolio.core import repo
from portfolio.core.analytics.data import load_data
from portfolio.core.models import FxRate, Instrument, Price, Transaction
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod as V
from portfolio.core.providers.base import Bar, ProviderError, Ratios, Statement
from portfolio.core.providers.yahoo import (
    bars_from_frame,
    cross_rates,
    fx_symbol,
    ratios_from_info,
    statements_from_frames,
)
from portfolio.core.updater import ensure_benchmark, update_market_data

TODAY = date(2024, 3, 10)


def day(n: int, month: int = 3) -> date:
    return date(2024, month, n)


class FakeProvider:
    """Serves prepared bars and records what was asked for."""

    def __init__(self):
        self.bars: dict[str, list[Bar]] = {}
        self.failing: set[str] = set()
        self.currencies: dict[str, str] = {}
        self.calls: list[tuple[str, date]] = []
        self.ratio_data: dict[str, Ratios] = {}
        self.statement_data: dict[str, tuple[str, list[Statement]]] = {}

    def _serve(self, key: str, start: date) -> list[Bar]:
        self.calls.append((key, start))
        if key in self.failing:
            raise ProviderError(f"{key} is unavailable")
        return [bar for bar in self.bars.get(key, []) if bar.date >= start]

    def prices(self, symbol, start):
        return self._serve(symbol, start)

    def fx_rates(self, from_currency, to_currency, start):
        return self._serve(f"{from_currency}/{to_currency}", start)

    def currency(self, symbol):
        if symbol not in self.currencies:
            raise ProviderError(f"unknown symbol {symbol}")
        return self.currencies[symbol]

    def ratios(self, symbol):
        self.calls.append((f"ratios {symbol}", None))
        if f"ratios {symbol}" in self.failing:
            raise ProviderError(f"no ratios for {symbol}")
        return self.ratio_data.get(symbol)

    def statements(self, symbol):
        self.calls.append((f"statements {symbol}", None))
        return self.statement_data.get(symbol, (None, []))

    def asked(self, key: str) -> list[date]:
        return [start for asked_key, start in self.calls if asked_key == key]


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def portfolio(conn):
    """AAPL (USD) bought on 1 March, plus instruments the updater must leave alone."""
    for code in ("CZK", "USD", "EUR"):
        repo.add_currency(conn, code)
    for name in ("stock", "savings"):
        repo.add_instrument_type(conn, name)

    def add(ticker, currency="USD", valuation=V.YAHOO, **more):
        return repo.add_instrument(
            conn,
            Instrument(ticker=ticker, type="stock", currency=currency, valuation=valuation, **more),
        ).id

    def buy(instrument_id, on, currency="USD"):
        repo.add_transaction(
            conn,
            Transaction(on, instrument_id, K.BUY, quantity=D(1), price=D(100), currency=currency,
                        fx_rate=D(23)),
        )  # fmt: skip

    ids = {
        "AAPL": add("AAPL"),
        "BTC": add("BTC", "EUR", yahoo_symbol="BTC-EUR"),
        "INACTIVE": add("INACTIVE", active=False),
        "MANUAL": add("MANUAL", "CZK", V.MANUAL),
        "SOLD": add("SOLD"),
        "EMPTY": add("EMPTY"),
    }
    buy(ids["AAPL"], day(1))
    buy(ids["BTC"], day(5), currency="USD")  # EUR coin paid for in USD
    buy(ids["INACTIVE"], day(1))
    buy(ids["SOLD"], day(1))
    repo.add_transaction(
        conn,
        Transaction(day(2), ids["SOLD"], K.SELL, quantity=D(1), price=D(1), currency="USD",
                    fx_rate=D(23)),
    )  # fmt: skip
    repo.add_transaction(
        conn, Transaction(day(1), ids["MANUAL"], K.DEPOSIT, amount=D(5), currency="CZK")
    )
    conn.commit()
    return ids


def run(conn, provider, **options):
    return update_market_data(conn, provider, "CZK", today=TODAY, **options)


def test_first_update_downloads_from_a_week_before_the_first_transaction(conn, provider, portfolio):
    provider.bars = {
        "AAPL": [Bar(day(1), 100.0, open=99.0, high=101.0, low=98.0), Bar(day(4), 104.0)],
        "BTC-EUR": [Bar(day(5), 60000.0)],
        "USD/CZK": [Bar(day(1), 23.0), Bar(day(4), 23.2)],
        "EUR/CZK": [Bar(day(5), 25.0)],
    }
    result = run(conn, provider)

    assert result.ok and not result.new_splits
    assert result.updated == {"AAPL": 2, "BTC": 1, "EUR/CZK": 1, "USD/CZK": 2}
    assert provider.asked("AAPL") == [date(2024, 2, 23)]
    assert provider.asked("BTC-EUR") == [date(2024, 2, 27)]  # uses the Yahoo symbol
    assert provider.asked("USD/CZK") == [date(2024, 2, 23)]  # from the portfolio's first day
    asked_for = {key for key, _ in provider.calls}
    # Nothing for the others; ratios only for what is held and priced by Yahoo.
    assert asked_for == {"AAPL", "BTC-EUR", "USD/CZK", "EUR/CZK", "ratios AAPL", "ratios BTC-EUR"}
    first, second = repo.list_prices(conn, portfolio["AAPL"])
    assert (first.close, first.open, first.high, first.low) == (100.0, 99.0, 101.0, 98.0)
    assert second.close == 104.0
    assert [r.close for r in repo.list_fx_rates(conn, "USD", "CZK")] == [23.0, 23.2]


def test_later_update_continues_from_the_last_stored_day(conn, provider, portfolio):
    repo.save_prices(
        conn, [Price(portfolio["AAPL"], day(1), 100.0), Price(portfolio["AAPL"], day(4), 103.0)]
    )
    repo.save_fx_rates(conn, [FxRate(day(4), "USD", "CZK", 23.0)])
    conn.commit()
    provider.bars = {
        "AAPL": [Bar(day(1), 1.0), Bar(day(4), 104.0), Bar(day(5), 105.0)],
        "USD/CZK": [Bar(day(4), 23.2), Bar(day(5), 23.3)],
    }
    result = run(conn, provider)

    assert provider.asked("AAPL") == [day(4)]
    assert provider.asked("USD/CZK") == [day(4)]
    assert result.updated["AAPL"] == 2
    # The last stored day is corrected, older days are untouched.
    assert [p.close for p in repo.list_prices(conn, portfolio["AAPL"])] == [100.0, 104.0, 105.0]
    assert [r.close for r in repo.list_fx_rates(conn, "USD", "CZK")] == [23.2, 23.3]


def test_full_update_downloads_everything_again(conn, provider, portfolio):
    repo.save_prices(conn, [Price(portfolio["AAPL"], day(1), 90.0)])
    repo.save_fx_rates(conn, [FxRate(day(1), "USD", "CZK", 20.0)])
    conn.commit()
    provider.bars = {"AAPL": [Bar(day(1), 100.0)], "USD/CZK": [Bar(day(1), 23.0)]}
    run(conn, provider, full=True)

    assert provider.asked("AAPL") == [date(2024, 2, 23)]
    assert provider.asked("USD/CZK") == [date(2024, 2, 23)]
    assert repo.list_prices(conn, portfolio["AAPL"])[0].close == 100.0


def test_one_failure_does_not_stop_the_rest(conn, provider, portfolio):
    provider.bars = {"BTC-EUR": [Bar(day(5), 60000.0)], "EUR/CZK": [Bar(day(5), 25.0)]}
    provider.failing = {"AAPL", "USD/CZK"}
    result = run(conn, provider)

    assert not result.ok
    assert set(result.errors) == {"AAPL", "USD/CZK"}
    assert "unavailable" in result.errors["AAPL"]
    assert result.updated == {"BTC": 1, "EUR/CZK": 1}
    conn.rollback()  # everything that succeeded is already saved
    assert len(repo.list_prices(conn, portfolio["BTC"])) == 1
    assert len(repo.list_fx_rates(conn, "EUR", "CZK")) == 1


def test_new_split_reloads_history_and_waits_for_a_decision(conn, provider, portfolio):
    aapl = portfolio["AAPL"]
    repo.save_prices(conn, [Price(aapl, day(1), 1000.0), Price(aapl, day(4), 1040.0)])
    conn.commit()
    # After a 10:1 split on the 6th the source reports the whole history in new units.
    provider.bars["AAPL"] = [
        Bar(day(1), 100.0), Bar(day(4), 104.0), Bar(day(6), 105.0, split=10.0), Bar(day(7), 106.0),
    ]  # fmt: skip
    result = run(conn, provider)

    assert result.new_splits == ["AAPL"]
    assert provider.asked("AAPL") == [day(4), date(2024, 2, 23)]
    assert [p.close for p in repo.list_prices(conn, aapl)] == [100.0, 104.0, 105.0, 106.0]
    assert repo.pending_splits(conn) == [(aapl, day(6), 10.0)]

    # Seeing the same split again changes nothing.
    provider.calls.clear()
    assert run(conn, provider).new_splits == []
    assert provider.asked("AAPL") == [day(7)]

    # Adding the split to the ledger settles it.
    with conn:
        repo.add_transaction(conn, Transaction(day(6), aapl, K.SPLIT, split_ratio=D(10)))
    assert repo.pending_splits(conn) == []
    assert load_data(conn, "CZK").events[aapl][-1].kind is K.SPLIT


def test_split_can_be_dismissed_and_is_ignored_without_earlier_transactions(conn, portfolio):
    aapl, btc = portfolio["AAPL"], portfolio["BTC"]
    repo.save_prices(
        conn,
        [
            Price(aapl, day(6), 105.0, split=10.0),
            Price(btc, day(2), 1.0, split=2.0),  # before the first BTC transaction
        ],
    )
    assert repo.pending_splits(conn) == [(aapl, day(6), 10.0)]
    repo.dismiss_split(conn, aapl, day(6))
    repo.dismiss_split(conn, aapl, day(6))  # twice is harmless
    assert repo.pending_splits(conn) == []


def test_benchmark_is_created_once_and_updated(conn, provider, portfolio):
    provider.currencies = {"SPY": "USD", "CSPX.L": "GBP"}
    provider.bars = {
        "SPY": [Bar(day(1), 500.0), Bar(day(4), 510.0)],
        "GBP/CZK": [Bar(day(1), 29.0)],
    }
    result = run(conn, provider, benchmark="SPY")

    benchmark = repo.get_instrument_by_ticker(conn, "SPY")
    assert (benchmark.type, benchmark.currency, benchmark.valuation) == (
        "benchmark",
        "USD",
        V.YAHOO,
    )
    assert result.updated["SPY"] == 2
    assert provider.asked("SPY") == [date(2024, 2, 23)]
    assert benchmark.id not in load_data(conn, "CZK").instrument_ids()
    assert ensure_benchmark(conn, provider, "SPY") == benchmark

    # A benchmark in a currency not used before brings its exchange rate along.
    result = run(conn, provider, benchmark="CSPX.L")
    assert "GBP" in repo.list_currencies(conn)
    assert result.updated["GBP/CZK"] == 1


def test_unknown_benchmark_is_reported_and_the_rest_still_updates(conn, provider, portfolio):
    provider.bars = {"AAPL": [Bar(day(1), 100.0)]}
    result = run(conn, provider, benchmark="NOPE")
    assert "benchmark NOPE" in result.errors
    assert result.updated["AAPL"] == 1
    assert repo.get_instrument_by_ticker(conn, "NOPE") is None


def test_empty_portfolio_asks_for_nothing(conn, provider):
    result = run(conn, provider)
    assert result.ok and result.updated == {} and provider.calls == []


# --- Yahoo specifics --------------------------------------------------------------------------


def test_fx_symbols():
    assert fx_symbol("USD", "CZK") == "CZK=X"
    assert fx_symbol("EUR", "CZK") == "EURCZK=X"


def test_bars_from_a_yfinance_table():
    index = pd.to_datetime(["2024-03-05", "2024-03-04", "2024-03-06"]).tz_localize(
        "America/New_York"
    )
    frame = pd.DataFrame(
        {
            "Open": [10.0, 9.0, float("nan")],
            "High": [11.0, 9.5, float("nan")],
            "Low": [9.5, 8.5, float("nan")],
            "Close": [10.5, 9.2, float("nan")],
            "Adj Close": [10.4, 9.1, float("nan")],
            "Dividends": [0.0, 0.25, 0.0],
            "Stock Splits": [10.0, 0.0, 0.0],
        },
        index=index,
    )
    assert bars_from_frame(frame) == [
        Bar(date(2024, 3, 4), 9.2, open=9.0, high=9.5, low=8.5, dividend=0.25, split=0.0),
        Bar(date(2024, 3, 5), 10.5, open=10.0, high=11.0, low=9.5, dividend=0.0, split=10.0),
    ]
    # Exchange rates come without dividend and split columns.
    rates = pd.DataFrame({"Close": [23.1]}, index=pd.to_datetime(["2024-03-04"]))
    assert bars_from_frame(rates) == [Bar(date(2024, 3, 4), 23.1)]
    assert bars_from_frame(pd.DataFrame()) == []


def test_company_data_once_a_day_and_results_when_due(conn, provider, portfolio):
    provider.ratio_data["AAPL"] = Ratios(trailing_pe=30.0, price_to_book=40.0, market_cap=3e12)
    provider.statement_data["AAPL"] = (
        "USD",
        [
            Statement("annual", date(2023, 9, 30), revenue=383e9, eps=6.13, shares=15.5e9),
            Statement("quarterly", date(2023, 12, 30), revenue=120e9, eps=2.18),
        ],
    )
    result = run(conn, provider)
    assert result.ok and result.fundamentals == ["AAPL"]
    (snapshot,) = repo.list_snapshots(conn, portfolio["AAPL"])
    assert (snapshot.date, snapshot.trailing_pe, snapshot.market_cap) == (TODAY, 30.0, 3e12)
    annual, quarter = repo.list_statements(conn, portfolio["AAPL"])
    assert (annual.period, annual.currency, annual.eps, annual.shares) == (
        "annual", "USD", 6.13, 15.5e9,
    )  # fmt: skip
    assert (quarter.period, quarter.eps, quarter.equity) == ("quarterly", 2.18, None)
    # BTC is a coin: asked once, remembered as empty.
    (coin,) = repo.list_snapshots(conn, portfolio["BTC"])
    assert coin.empty

    run(conn, provider)  # the same day again: nothing asked
    assert len(provider.asked("ratios AAPL")) == 1
    assert len(provider.asked("ratios BTC-EUR")) == 1

    # Next day: new ratios, but the newest result is recent, so no results are fetched.
    update_market_data(conn, provider, "CZK", today=date(2024, 3, 11))
    assert len(provider.asked("ratios AAPL")) == 2
    assert len(provider.asked("statements AAPL")) == 1
    assert len(repo.list_snapshots(conn, portfolio["AAPL"])) == 2
    # Once the newest result is more than 100 days old, results are fetched again.
    update_market_data(conn, provider, "CZK", today=date(2024, 4, 9))
    assert len(provider.asked("statements AAPL")) == 2

    assert not run(conn, provider, fundamentals=False).fundamentals


def test_reporting_currency_is_added_and_its_rates_downloaded(conn, provider, portfolio):
    provider.ratio_data["AAPL"] = Ratios(trailing_pe=30.0)
    provider.statement_data["AAPL"] = ("DKK", [Statement("annual", date(2023, 12, 31), eps=9.0)])
    provider.bars["DKK/CZK"] = [Bar(day(1), 3.3)]
    result = run(conn, provider)
    assert result.ok
    assert "DKK" in repo.list_currencies(conn)
    assert result.updated["DKK/CZK"] == 1
    assert repo.list_statements(conn)[0].currency == "DKK"


def test_failing_company_data_is_reported_and_the_rest_still_updates(conn, provider, portfolio):
    provider.failing.add("ratios AAPL")
    provider.bars["AAPL"] = [Bar(day(4), 104.0)]
    result = run(conn, provider)
    assert "no ratios for AAPL" in result.errors["fundamentals AAPL"]
    assert result.updated["AAPL"] == 1
    assert repo.list_snapshots(conn, portfolio["AAPL"]) == []  # asked again next time


def test_ratios_and_statements_from_yfinance_tables():
    assert ratios_from_info({"quoteType": "ETF", "trailingPE": 20}) is None
    ratios = ratios_from_info({"quoteType": "EQUITY", "trailingPE": 20.5, "forwardPE": "x"})
    assert (ratios.trailing_pe, ratios.forward_pe, ratios.market_cap) == (20.5, None, None)

    ends = pd.to_datetime(["2025-12-31", "2024-12-31", "2023-12-31"])
    income = pd.DataFrame(
        [[100.0, 90.0, float("nan")], [2.5, 2.0, float("nan")], [10.0, 9.0, float("nan")]],
        index=["Total Revenue", "Diluted EPS", "Net Income"],
        columns=ends,
    )
    balance = pd.DataFrame(
        [[50.0, 45.0, 40.0], [4.0, 4.0, 4.1]],
        index=["Common Stock Equity", "Ordinary Shares Number"],
        columns=ends,
    )
    found = statements_from_frames("annual", income, balance)
    assert [s.period_end.year for s in found] == [2023, 2024, 2025]
    oldest, _, newest = found
    assert (oldest.revenue, oldest.eps, oldest.equity, oldest.shares) == (None, None, 40.0, 4.1)
    assert (newest.revenue, newest.net_income, newest.eps) == (100.0, 10.0, 2.5)
    assert (newest.equity, newest.period) == (50.0, "annual")
    assert statements_from_frames("annual", pd.DataFrame(), None) == []


def test_cross_rates_through_a_third_currency():
    krw_eur = [Bar(day(1), 0.0007), Bar(day(4), 0.0008), Bar(day(5), 0.0009)]
    eur_czk = [Bar(day(2), 25.0), Bar(day(5), 24.0)]
    assert cross_rates(krw_eur, eur_czk) == [
        Bar(day(4), pytest.approx(0.0008 * 25)),  # day 1 has no EUR rate yet
        Bar(day(5), pytest.approx(0.0009 * 24)),
    ]
