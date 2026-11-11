import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from portfolio.core import repo
from portfolio.core.models import (
    FxRate,
    Instrument,
    Price,
    Transaction,
    Valuation,
    ValuationMethod,
)
from portfolio.core.models import TransactionKind as K


def buy(stock, day=date(2024, 3, 1), **changes):
    fields = dict(quantity=D("2"), price=D("150.5"), currency="USD", fx_rate=D("23.1"))
    return Transaction(date=day, instrument_id=stock.id, kind=K.BUY, **{**fields, **changes})


# --- reference data ---


def test_currencies_and_types(conn):
    repo.add_currency(conn, "USD")
    repo.add_currency(conn, "CZK")
    repo.add_instrument_type(conn, "etf")
    assert repo.list_currencies(conn) == ["CZK", "USD"]
    assert repo.list_instrument_types(conn) == ["etf"]
    repo.delete_currency(conn, "USD")
    repo.delete_instrument_type(conn, "etf")
    assert repo.list_currencies(conn) == ["CZK"]
    assert repo.list_instrument_types(conn) == []


@pytest.mark.parametrize("code", ["usd", "US", "DOLLAR", ""])
def test_bad_currency_code_rejected(conn, code):
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_currency(conn, code)


def test_currency_in_use_cannot_be_deleted(conn, stock):
    with pytest.raises(sqlite3.IntegrityError):
        repo.delete_currency(conn, "USD")


# --- instruments ---


def test_instrument_round_trip(conn, stock):
    assert stock.id is not None
    assert repo.get_instrument(conn, stock.id) == stock
    assert repo.get_instrument_by_ticker(conn, "AAPL") == stock
    assert repo.get_instrument(conn, 999) is None
    assert repo.get_instrument_by_ticker(conn, "NOPE") is None


def test_instrument_update_and_active_filter(conn, stock):
    changed = replace(stock, name="Apple", yahoo_symbol="AAPL.US", active=False)
    repo.update_instrument(conn, changed)
    assert repo.get_instrument(conn, stock.id) == changed
    assert repo.list_instruments(conn) == [changed]
    assert repo.list_instruments(conn, active_only=True) == []


def test_instrument_needs_known_type_and_currency_and_unique_ticker(conn, stock):
    base = Instrument(ticker="X", type="stock", currency="USD", valuation=ValuationMethod.MANUAL)
    for bad in (
        replace(base, type="unknown"),
        replace(base, currency="GBP"),
        replace(base, dividend_currency="GBP"),
        replace(base, ticker="AAPL"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            repo.add_instrument(conn, bad)
        conn.rollback()


def test_update_or_delete_of_missing_instrument(conn, stock):
    with pytest.raises(repo.NotFoundError):
        repo.update_instrument(conn, replace(stock, id=999))
    with pytest.raises(repo.NotFoundError):
        repo.delete_instrument(conn, 999)
    with pytest.raises(ValueError):
        repo.update_instrument(conn, replace(stock, id=None))


def test_instrument_with_transactions_cannot_be_deleted(conn, stock):
    repo.add_transaction(conn, buy(stock))
    with pytest.raises(sqlite3.IntegrityError):
        repo.delete_instrument(conn, stock.id)


def test_deleting_instrument_removes_its_prices_and_valuations(conn, stock):
    repo.save_prices(conn, [Price(stock.id, date(2024, 1, 2), close=10.0)])
    repo.set_valuation(conn, Valuation(stock.id, date(2024, 1, 2), D("5")))
    repo.delete_instrument(conn, stock.id)
    assert repo.list_prices(conn) == []
    assert repo.list_valuations(conn) == []


# --- transactions ---


def test_transaction_round_trip_for_each_kind(conn, stock):
    day = date(2024, 3, 1)
    rows = [
        buy(stock, fee=D("25"), note="first"),
        Transaction(day, stock.id, K.SELL, quantity=D("1"), price=D("160"), currency="USD",
                    fx_rate=D("23.5"), reinvested=True),
        Transaction(day, stock.id, K.DEPOSIT, amount=D("1000"), currency="CZK"),
        Transaction(day, stock.id, K.WITHDRAWAL, amount=D("10"), currency="CZK", fx_rate=D("1")),
        Transaction(day, stock.id, K.DIVIDEND, amount=D("8.5"), currency="USD", tax=D("1.5")),
        Transaction(day, stock.id, K.STAKING_REWARD, quantity=D("0.00000123")),
        Transaction(day, stock.id, K.SPLIT, split_ratio=D("10")),
    ]  # fmt: skip
    saved = [repo.add_transaction(conn, row) for row in rows]
    assert all(row.id is not None for row in saved)
    assert repo.list_transactions(conn) == saved
    assert repo.get_transaction(conn, saved[0].id) == saved[0]
    assert repo.get_transaction(conn, 999) is None


@pytest.mark.parametrize(
    "text",
    ["0.1", "0.30000000000000004", "0.00000001", "123456789012345678.123456789012345678", "1E+3",
     "1E-10", "100", "100.00"],
)  # fmt: skip
def test_decimals_are_stored_exactly(conn, stock, text):
    saved = repo.add_transaction(conn, buy(stock, quantity=D(text)))
    loaded = repo.get_transaction(conn, saved.id)
    assert loaded.quantity == D(text)
    stored = conn.execute("SELECT quantity FROM transactions").fetchone()[0]
    assert isinstance(stored, str) and "E" not in stored.upper()


def test_transaction_filters_and_order(conn, stock):
    other = repo.add_instrument(
        conn,
        Instrument(ticker="MSFT", type="stock", currency="USD", valuation=ValuationMethod.YAHOO),
    )
    late = repo.add_transaction(conn, buy(stock, date(2024, 5, 1)))
    early = repo.add_transaction(conn, buy(stock, date(2024, 1, 1)))
    same_day = repo.add_transaction(conn, buy(stock, date(2024, 1, 1), quantity=D("9")))
    split = repo.add_transaction(
        conn, Transaction(date(2024, 3, 1), other.id, K.SPLIT, split_ratio=D("2"))
    )
    assert repo.list_transactions(conn) == [early, same_day, split, late]
    assert repo.list_transactions(conn, instrument_id=other.id) == [split]
    assert repo.list_transactions(conn, kinds=[K.SPLIT, K.SELL]) == [split]
    assert repo.list_transactions(conn, date_from=date(2024, 3, 1)) == [split, late]
    assert repo.list_transactions(conn, date_to=date(2024, 3, 1)) == [early, same_day, split]
    assert repo.list_transactions(
        conn, instrument_id=stock.id, date_from=date(2024, 2, 1), date_to=date(2024, 12, 31)
    ) == [late]


def test_transaction_update_and_delete(conn, stock):
    saved = repo.add_transaction(conn, buy(stock))
    changed = replace(saved, quantity=D("3.5"), note="fixed")
    repo.update_transaction(conn, changed)
    assert repo.get_transaction(conn, saved.id) == changed
    repo.delete_transaction(conn, saved.id)
    assert repo.list_transactions(conn) == []
    with pytest.raises(repo.NotFoundError):
        repo.delete_transaction(conn, saved.id)
    with pytest.raises(repo.NotFoundError):
        repo.update_transaction(conn, changed)


def test_transaction_needs_existing_instrument_and_currency(conn, stock):
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_transaction(conn, replace(buy(stock), instrument_id=999))
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        repo.add_transaction(conn, buy(stock, currency="GBP"))


# --- valuations ---


def test_valuations(conn, stock):
    repo.set_valuation(conn, Valuation(stock.id, date(2024, 2, 1), D("100.10")))
    repo.set_valuation(conn, Valuation(stock.id, date(2024, 1, 1), D("90")))
    repo.set_valuation(conn, Valuation(stock.id, date(2024, 2, 1), D("101.25")))  # replaces
    assert repo.list_valuations(conn, stock.id) == [
        Valuation(stock.id, date(2024, 1, 1), D("90")),
        Valuation(stock.id, date(2024, 2, 1), D("101.25")),
    ]
    repo.delete_valuation(conn, stock.id, date(2024, 1, 1))
    assert len(repo.list_valuations(conn)) == 1
    with pytest.raises(repo.NotFoundError):
        repo.delete_valuation(conn, stock.id, date(2024, 1, 1))
    with pytest.raises(ValueError):
        repo.set_valuation(conn, Valuation(stock.id, date(2024, 1, 1), D("-1")))


# --- prices and FX ---


def test_prices(conn, stock):
    first = Price(stock.id, date(2024, 1, 2), close=10.0, open=9.0, high=11.0, low=8.5)
    second = Price(stock.id, date(2024, 1, 3), close=12.0, dividend=0.25, split=10.0)
    repo.save_prices(conn, [second, first])
    assert repo.list_prices(conn, stock.id) == [first, second]
    corrected = replace(first, close=10.5)
    repo.save_prices(conn, [corrected])
    assert repo.list_prices(conn, stock.id, date_to=date(2024, 1, 2)) == [corrected]
    assert repo.list_prices(conn, stock.id, date_from=date(2024, 1, 3)) == [second]
    assert repo.last_price_dates(conn) == {stock.id: date(2024, 1, 3)}


def test_fx_rates(conn, stock):
    usd1 = FxRate(date(2024, 1, 2), "USD", "CZK", 22.5)
    usd2 = FxRate(date(2024, 1, 3), "USD", "CZK", 22.7)
    eur = FxRate(date(2024, 1, 2), "EUR", "CZK", 24.6)
    repo.save_fx_rates(conn, [usd2, eur, usd1])
    assert repo.list_fx_rates(conn, "USD", "CZK") == [usd1, usd2]
    assert repo.list_fx_rates(conn) == [eur, usd1, usd2]
    repo.save_fx_rates(conn, [replace(usd1, close=22.6)])
    assert repo.list_fx_rates(conn, "USD", date_to=date(2024, 1, 2))[0].close == 22.6
    assert repo.last_fx_dates(conn) == {
        ("USD", "CZK"): date(2024, 1, 3),
        ("EUR", "CZK"): date(2024, 1, 2),
    }
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_fx_rates(conn, [FxRate(date(2024, 1, 2), "GBP", "CZK", 29.0)])
