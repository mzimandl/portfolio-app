import csv
import io
import sqlite3
import zipfile
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from portfolio.core import csv_io, db, repo
from portfolio.core.models import FxRate, Instrument, Price, Transaction, Valuation
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod as V


@pytest.fixture
def filled(conn, stock):
    """The AAPL stock from conftest plus one transaction of every kind and market data."""
    save = repo.add_instrument(
        conn, Instrument(ticker="SAVE", type="savings", currency="CZK", valuation=V.MANUAL)
    )
    day = date(2024, 3, 1)
    for transaction in (
        Transaction(day, stock.id, K.BUY, quantity=D("0.00000001"), price=D("150.5"),
                    currency="USD", fx_rate=D("23.1"), fee=D("25"), note='first, "quoted"'),
        Transaction(day, stock.id, K.SELL, quantity=D(1), price=D(160), currency="USD",
                    fx_rate=D("23.5")),
        Transaction(day, save.id, K.DEPOSIT, amount=D(1000), currency="CZK", fx_rate=D(1)),
        Transaction(day, save.id, K.WITHDRAWAL, amount=D(10), currency="CZK"),
        Transaction(day, stock.id, K.DIVIDEND, amount=D("8.5"), currency="USD", tax=D("1.5")),
        Transaction(day, stock.id, K.STAKING_REWARD, quantity=D("0.5")),
        Transaction(day, stock.id, K.SPLIT, split_ratio=D(10)),
        Transaction(day, save.id, K.FEE, fee=D(35)),
    ):  # fmt: skip
        repo.add_transaction(conn, transaction)
    repo.set_valuation(conn, Valuation(save.id, day, D("1010.50")))
    repo.save_prices(conn, [Price(stock.id, day, close=150.0, open=149.0, split=10.0)])
    repo.save_fx_rates(conn, [FxRate(day, "USD", "CZK", 23.1)])
    repo.dismiss_split(conn, stock.id, day)
    conn.commit()
    return conn


def table(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


# --- export ---------------------------------------------------------------------------------


def test_export_covers_every_table(filled):
    files = csv_io.export_all(filled)
    tables = {
        row[0] for row in filled.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {name.removesuffix(".csv") for name in files} == tables
    assert [r["code"] for r in table(files["currencies.csv"])] == ["CZK", "EUR", "USD"]
    assert table(files["instruments.csv"])[0] == {
        "ticker": "AAPL", "name": "", "type": "stock", "currency": "USD",
        "dividend_currency": "", "valuation": "yahoo", "yahoo_symbol": "", "active": "1",
    }  # fmt: skip
    assert table(files["valuations.csv"]) == [
        {"ticker": "SAVE", "date": "2024-03-01", "value": "1010.5"}
    ]
    assert table(files["prices.csv"])[0]["close"] == "150.0"
    assert table(files["fx_rates.csv"])[0]["from_currency"] == "USD"
    assert table(files["dismissed_splits.csv"]) == [{"ticker": "AAPL", "date": "2024-03-01"}]


def test_exported_transactions_are_exact_and_readable(filled):
    rows = table(csv_io.transactions_csv(filled))
    assert list(rows[0]) == list(csv_io.TRANSACTION_COLUMNS)
    buy = rows[0]
    assert (buy["ticker"], buy["kind"], buy["quantity"]) == ("AAPL", "buy", "0.00000001")
    assert (buy["fee"], buy["note"]) == ("25", 'first, "quoted"')
    assert (rows[1]["kind"], rows[1]["amount"]) == ("sell", "")


def test_zip_and_database_copy(filled):
    with zipfile.ZipFile(io.BytesIO(csv_io.export_zip(filled))) as archive:
        assert "transactions.csv" in archive.namelist()
        assert archive.read("currencies.csv").decode() == "code\nCZK\nEUR\nUSD\n"
    copy = sqlite3.connect(":memory:")
    copy.deserialize(csv_io.database_file(filled))
    assert copy.execute("SELECT count(*) FROM transactions").fetchone()[0] == 8
    assert copy.execute("PRAGMA user_version").fetchone()[0] == db.schema_version(filled)


# --- import ---------------------------------------------------------------------------------


def test_export_then_import_gives_the_same_transactions(filled):
    text = csv_io.transactions_csv(filled)
    original = repo.list_transactions(filled)
    rows = csv_io.parse_transactions(text, filled)
    assert all(row.ok and row.duplicate for row in rows)
    assert csv_io.import_transactions(filled, rows) == 0  # all already there

    filled.execute("DELETE FROM transactions")
    rows = csv_io.parse_transactions(text, filled)
    assert not any(row.duplicate for row in rows)
    assert csv_io.import_transactions(filled, rows) == 8
    restored = repo.list_transactions(filled)
    assert [replace(t, id=None) for t in restored] == [replace(t, id=None) for t in original]


def test_minimal_columns_and_semicolons_with_decimal_commas(conn, stock):
    text = (
        "Date;Ticker;Kind;Quantity;Price;Currency;FX_Rate;Reinvested\n"
        "15.03.2024;AAPL;BUY;1,5;1 234,56;usd;23,1;\n"
        "\n"
        "2024-03-16;AAPL;sell;0,5;200;USD;23;ano\n"
    )
    first, second = csv_io.parse_transactions(text, conn)
    assert (first.line, second.line) == (2, 4)
    assert first.transaction.date == date(2024, 3, 15)
    assert (first.transaction.quantity, first.transaction.price) == (D("1.5"), D("1234.56"))
    assert (first.transaction.currency, first.transaction.fee) == ("USD", 0)
    assert second.transaction.kind is K.SELL  # the old "reinvested" column is ignored
    assert csv_io.import_transactions(conn, [first, second]) == 2


def test_comma_file_does_not_guess_decimal_commas(conn, stock):
    text = (
        'date,ticker,kind,quantity,price,currency,fx_rate\n2024-03-15,AAPL,buy,"1,5",100,USD,23\n'
    )
    (row,) = csv_io.parse_transactions(text, conn)
    assert "quantity '1,5' is not a number" in row.error


@pytest.mark.parametrize(
    "line, message",
    [
        ("2024-03-15,NOPE,buy,1,100,USD,23", "unknown instrument 'NOPE'"),
        ("2024-03-15,AAPL,gift,1,100,USD,23", "unknown kind 'gift'"),
        ("2024-03-15,AAPL,buy,1,100,GBP,23", "unknown currency 'GBP'"),
        ("15/03/2024,AAPL,buy,1,100,USD,23", "is not YYYY-MM-DD"),
        ("2024-03-15,AAPL,buy,x,100,USD,23", "quantity 'x' is not a number"),
        ("2024-03-15,AAPL,buy,,100,USD,23", "needs 'quantity'"),
        ("2024-03-15,AAPL,buy,-1,100,USD,23", "greater than zero"),
        ("2024-03-15,AAPL,buy,1,100,USD,23,extra", "more values than columns"),
    ],
)
def test_bad_rows_are_reported_with_their_line(conn, stock, line, message):
    header = "date,ticker,kind,quantity,price,currency,fx_rate"
    text = f"{header}\n2024-03-14,AAPL,buy,1,100,USD,23\n{line}\n"
    good, bad = csv_io.parse_transactions(text, conn)
    assert good.ok and not bad.ok
    assert bad.line == 3 and message in bad.error
    with pytest.raises(csv_io.CsvError, match="lines 3"):
        csv_io.import_transactions(conn, [good, bad])
    assert repo.list_transactions(conn) == []


def test_unusable_files_are_rejected(conn, stock):
    with pytest.raises(csv_io.CsvError, match="needs the columns: ticker, kind"):
        csv_io.parse_transactions("date,amount\n2024-01-01,5\n", conn)
    with pytest.raises(csv_io.CsvError, match="Unknown columns: broker"):
        csv_io.parse_transactions("date,ticker,kind,broker\n", conn)
    with pytest.raises(csv_io.CsvError):
        csv_io.parse_transactions("", conn)
    assert csv_io.parse_transactions("date,ticker,kind\n", conn) == []


def test_duplicates_can_be_imported_on_request(conn, stock):
    text = "date,ticker,kind,quantity\n2024-03-15,AAPL,staking_reward,0.5\n"
    assert csv_io.import_transactions(conn, csv_io.parse_transactions(text, conn)) == 1
    again = csv_io.parse_transactions(text, conn)
    assert again[0].duplicate
    assert csv_io.import_transactions(conn, again) == 0
    assert csv_io.import_transactions(conn, again, skip_duplicates=False) == 1
    assert len(repo.list_transactions(conn)) == 2


def test_decode_handles_utf8_bom_and_windows_encoding():
    assert csv_io.decode("﻿date,note\n".encode()) == "date,note\n"
    assert csv_io.decode("poznámka č. 1".encode("cp1250")) == "poznámka č. 1"
