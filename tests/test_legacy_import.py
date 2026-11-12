import sqlite3
from datetime import date
from decimal import Decimal as D

import pytest

from portfolio.core import repo
from portfolio.core.legacy_import import Check, LegacyImportError, _dec, _fx_rate, import_legacy
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod

# The old app's tables as they exist in the real database.
OLD_SCHEMA = """
CREATE TABLE currencies (name TEXT NOT NULL UNIQUE);
CREATE TABLE types (name TEXT NOT NULL UNIQUE);
CREATE TABLE instruments (ticker TEXT NOT NULL UNIQUE, currency TEXT NOT NULL, type TEXT NOT NULL,
    evaluation TEXT NOT NULL, eval_param TEXT, dividend_currency TEXT, name TEXT,
    active INTEGER DEFAULT 1);
CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT, volume REAL,
    price REAL, fee REAL DEFAULT 0, base_rate REAL DEFAULT 1, reinvested INTEGER DEFAULT 0);
CREATE TABLE crypto (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT, volume REAL,
    price REAL, currency TEXT, fee REAL DEFAULT 0, base_rate REAL DEFAULT 1,
    reinvested INTEGER DEFAULT 0);
CREATE TABLE staking (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT, volume REAL);
CREATE TABLE deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT,
    amount REAL DEFAULT 0, fee REAL DEFAULT 0, reinvested INTEGER DEFAULT 0);
CREATE TABLE dividends (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ticker TEXT,
    dividend REAL, dividend_currency TEXT);
CREATE TABLE historical (date TEXT, ticker TEXT, open REAL, high REAL, low REAL, close REAL,
    dividends REAL, splits REAL);
CREATE TABLE fx (date TEXT, from_curr TEXT, to_curr TEXT, open REAL, high REAL, low REAL,
    close REAL);
CREATE TABLE "values" (date TEXT, ticker TEXT, value REAL);

INSERT INTO currencies VALUES ('CZK'), ('USD'), ('EUR');
INSERT INTO types VALUES ('stock'), ('crypto'), ('savings'), ('fund');
INSERT INTO instruments (ticker, currency, type, evaluation, eval_param, dividend_currency, name,
    active) VALUES
    ('AAPL', 'USD', 'stock', 'yfinance', NULL, 'CZK', 'Apple', 1),
    ('BTC', 'EUR', 'crypto', 'yfinance', 'BTC-EUR', NULL, NULL, 1),
    ('SAVE', 'CZK', 'savings', 'manual', NULL, NULL, NULL, 0),
    ('WEBFUND', 'CZK', 'fund', 'http', '{"url": "x"}', NULL, NULL, 0);

INSERT INTO trades (date, ticker, volume, price, fee, base_rate, reinvested) VALUES
    ('2024-01-10', 'AAPL', 2.0, 51.129000000000005, 25.0, 0.04, 0),
    ('2024-03-01', 'AAPL', -0.5, 200.0, 10.0, 0.05, 1),
    ('2024-01-05', 'WEBFUND', 100.0, 1.5, 0, 1, 0);
INSERT INTO crypto (date, ticker, volume, price, currency, fee, base_rate, reinvested) VALUES
    ('2024-01-10', 'BTC', 0.01, 40000.0, 'USD', 5.0, 0.04, 0),
    ('2024-02-01', 'BTC', -0.0002, 0.0, 'EUR', 0.0, 1.0, 0);
INSERT INTO staking (date, ticker, volume) VALUES
    ('2024-02-02', 'BTC', 0.00000123),
    ('2024-02-03', 'BTC', -0.0000005),
    ('2024-02-04', 'GONE', 1.0);
INSERT INTO deposits (date, ticker, amount, fee, reinvested) VALUES
    ('2024-01-01', 'SAVE', 1000.0, 0, 0),
    ('2024-01-15', 'SAVE', 0, 35.0, 0),
    ('2024-01-20', 'SAVE', 0, 0, 0),
    ('2024-06-01', 'SAVE', -400.0, 2.0, 1);
INSERT INTO dividends (date, ticker, dividend) VALUES ('2024-05-01', 'AAPL', 12.34);
INSERT INTO "values" VALUES ('2024-03-31', 'SAVE', 1010.5), ('2024-03-31', 'WEBFUND', 150.0);
INSERT INTO historical VALUES
    ('2024-01-10', 'AAPL', 50.0, 52.0, 49.0, 51.0, 0.0, 0.0),
    ('2024-01-11', 'AAPL', 51.0, 53.0, 50.0, 52.5, 0.24, 10.0),
    ('2024-01-11', 'GONE', 1.0, 1.0, 1.0, 1.0, 0.0, 0.0),
    ('2024-01-11', 'WEBFUND', NULL, NULL, NULL, 1.5, NULL, NULL);
INSERT INTO fx VALUES ('2024-01-10', 'USD', 'CZK', 22.0, 23.0, 21.0, 22.5);
"""


@pytest.fixture
def old():
    connection = sqlite3.connect(":memory:")
    connection.executescript(OLD_SCHEMA)
    yield connection
    connection.close()


@pytest.fixture
def imported(old, conn):
    report = import_legacy(old, conn, "CZK")
    by_ticker = {i.ticker: i for i in repo.list_instruments(conn)}
    return report, by_ticker


def transactions(conn, instrument):
    return repo.list_transactions(conn, instrument_id=instrument.id)


def test_reference_data_and_instruments(imported, conn):
    _, by_ticker = imported
    assert repo.list_currencies(conn) == ["CZK", "EUR", "USD"]
    assert repo.list_instrument_types(conn) == ["crypto", "fund", "savings", "stock"]
    assert set(by_ticker) == {"AAPL", "BTC", "SAVE"}
    aapl, btc, save = by_ticker["AAPL"], by_ticker["BTC"], by_ticker["SAVE"]
    assert (aapl.name, aapl.currency, aapl.dividend_currency) == ("Apple", "USD", "CZK")
    assert (aapl.valuation, aapl.yahoo_symbol, aapl.active) == (ValuationMethod.YAHOO, None, True)
    assert btc.yahoo_symbol == "BTC-EUR"
    assert (save.valuation, save.active) == (ValuationMethod.MANUAL, False)


def test_trades_become_buys_and_sells(imported, conn):
    _, by_ticker = imported
    buy, sell, dividend = transactions(conn, by_ticker["AAPL"])
    assert (buy.kind, buy.date) == (K.BUY, date(2024, 1, 10))
    assert (buy.quantity, buy.price, buy.currency) == (D("2"), D("51.129"), "USD")
    assert (buy.fx_rate, buy.fee) == (D("25"), D("25"))
    assert (sell.kind, sell.quantity, sell.price) == (K.SELL, D("0.5"), D("200"))
    assert (sell.fx_rate, sell.fee) == (D("20"), D("10"))
    assert (dividend.kind, dividend.amount) == (K.DIVIDEND, D("12.34"))
    assert (dividend.currency, dividend.fx_rate) == ("CZK", D("1"))


def test_crypto_keeps_its_own_currency_and_staking(imported, conn):
    _, by_ticker = imported
    buy, lost, reward, taken_back = transactions(conn, by_ticker["BTC"])
    assert (buy.kind, buy.quantity, buy.price, buy.currency) == (
        K.BUY,
        D("0.01"),
        D("40000"),
        "USD",
    )
    assert (lost.kind, lost.quantity, lost.price, lost.currency) == (K.SELL, D("0.0002"), 0, "EUR")
    assert (reward.kind, reward.quantity) == (K.STAKING_REWARD, D("0.00000123"))
    assert (taken_back.kind, taken_back.quantity) == (K.STAKING_CORRECTION, D("0.0000005"))
    assert taken_back.price is None


def test_deposits_withdrawals_and_fee_only_rows(imported, conn):
    report, by_ticker = imported
    deposit, fee, withdrawal = transactions(conn, by_ticker["SAVE"])
    assert (deposit.kind, deposit.amount, deposit.currency) == (K.DEPOSIT, D("1000"), "CZK")
    assert deposit.fx_rate == 1
    assert (fee.kind, fee.fee, fee.amount) == (K.FEE, D("35"), None)
    assert (withdrawal.kind, withdrawal.amount, withdrawal.fee) == (K.WITHDRAWAL, D("400"), D("2"))
    assert report.skipped["deposits rows (empty)"] == 1


def test_ids_follow_dates_across_old_tables(imported, conn):
    rows = repo.list_transactions(conn)
    assert [row.id for row in rows] == sorted(row.id for row in rows)
    assert [row.date for row in rows] == sorted(row.date for row in rows)


def test_market_data(imported, conn):
    _, by_ticker = imported
    prices = repo.list_prices(conn)
    assert [(p.instrument_id, p.close) for p in prices] == [
        (by_ticker["AAPL"].id, 51.0),
        (by_ticker["AAPL"].id, 52.5),
    ]
    assert (prices[1].dividend, prices[1].split) == (0.24, 10.0)
    assert len(repo.list_fx_rates(conn, "USD", "CZK")) == 1
    (valuation,) = repo.list_valuations(conn)
    assert (valuation.instrument_id, valuation.value) == (by_ticker["SAVE"].id, D("1010.5"))


def test_report(imported):
    report, _ = imported
    assert report.ok and report.checks
    assert report.imported["instruments"] == 3
    assert report.skipped == {
        "instruments": 1,
        "trades rows": 1,
        "staking rows": 1,
        "deposits rows (empty)": 1,
        "values rows": 1,
        "historical rows": 2,
    }
    assert any("WEBFUND" in note for note in report.notes)
    assert any("negative staking" in note for note in report.notes)
    checked = {(c.ticker, c.what): c.old for c in report.checks}
    assert checked[("AAPL", "quantity")] == 1.5
    assert checked[("AAPL", "bought")] == pytest.approx(2 * 51.129 / 0.04)
    assert checked[("SAVE", "fees")] == 37.0
    assert checked[("SAVE", "withdrawn")] == 400.0
    assert ("WEBFUND", "quantity") not in checked


def test_foreign_trade_with_rate_one_is_noted(old, conn):
    old.execute(
        "INSERT INTO trades (date, ticker, volume, price) VALUES ('2024-04-01', 'AAPL', 1, 100)"
    )
    report = import_legacy(old, conn, "CZK")
    assert any("AAPL 2024-04-01" in note and "rate 1" in note for note in report.notes)


def test_target_must_be_empty(old, conn, stock):
    with pytest.raises(LegacyImportError, match="already contains data"):
        import_legacy(old, conn, "CZK")


def test_zero_base_rate_stops_the_import(old, conn):
    old.execute("UPDATE trades SET base_rate = 0 WHERE ticker = 'AAPL' AND volume > 0")
    with pytest.raises(LegacyImportError, match="base_rate"):
        import_legacy(old, conn, "CZK")


def test_number_conversion():
    assert _dec(51.129000000000005) == D("51.129")
    assert _dec(0.1 + 0.2) == D("0.3")
    assert _dec(9.47446e-05) == D("0.0000947446")
    assert _fx_rate(1.0) == 1
    assert _fx_rate(0.04) == 25
    assert float(_fx_rate(0.04079)) == pytest.approx(1 / 0.04079, rel=1e-14)


def test_check_tolerance():
    assert Check("X", "bought", 1000.0, 1000.0000000001).ok
    assert not Check("X", "bought", 1000.0, 1000.01).ok
    assert not Check("X", "quantity", 0.0, 0.001).ok
