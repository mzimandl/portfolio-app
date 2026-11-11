"""Reading and writing records.

Functions never commit. Wrap writes in ``with conn:`` so they are saved together or not at all.
"""

import sqlite3
from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from decimal import Decimal

from portfolio.core.models import (
    FxRate,
    Instrument,
    Price,
    Transaction,
    TransactionKind,
    Valuation,
    ValuationMethod,
)

# --- value conversion -----------------------------------------------------------------------


def _dec_to_db(value: Decimal | None) -> str | None:
    """Plain decimal text without exponent, so the stored value is exact and readable."""
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def decimal_text(value: Decimal | None) -> str | None:
    """The exact text a decimal is stored and exported as."""
    return _dec_to_db(value)


def _dec_from_db(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _date_range_clause(
    date_from: date | None, date_to: date | None, clauses: list[str], params: list
) -> None:
    if date_from is not None:
        clauses.append("date >= ?")
        params.append(date_from.isoformat())
    if date_to is not None:
        clauses.append("date <= ?")
        params.append(date_to.isoformat())


def _where(clauses: list[str]) -> str:
    return f" WHERE {' AND '.join(clauses)}" if clauses else ""


# --- currencies and instrument types --------------------------------------------------------


def list_currencies(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT code FROM currencies ORDER BY code")]


def add_currency(conn: sqlite3.Connection, code: str) -> None:
    conn.execute("INSERT INTO currencies (code) VALUES (?)", (code,))


def delete_currency(conn: sqlite3.Connection, code: str) -> None:
    conn.execute("DELETE FROM currencies WHERE code = ?", (code,))


def list_instrument_types(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT name FROM instrument_types ORDER BY name")]


def add_instrument_type(conn: sqlite3.Connection, name: str) -> None:
    conn.execute("INSERT INTO instrument_types (name) VALUES (?)", (name,))


def delete_instrument_type(conn: sqlite3.Connection, name: str) -> None:
    conn.execute("DELETE FROM instrument_types WHERE name = ?", (name,))


# --- instruments ----------------------------------------------------------------------------

_INSTRUMENT_COLUMNS = (
    "ticker, name, type, currency, dividend_currency, valuation, yahoo_symbol, active"
)


def _instrument_from_row(row: sqlite3.Row) -> Instrument:
    return Instrument(
        id=row["id"],
        ticker=row["ticker"],
        name=row["name"],
        type=row["type"],
        currency=row["currency"],
        dividend_currency=row["dividend_currency"],
        valuation=ValuationMethod(row["valuation"]),
        yahoo_symbol=row["yahoo_symbol"],
        active=bool(row["active"]),
    )


def _instrument_params(i: Instrument) -> tuple:
    return (
        i.ticker,
        i.name,
        i.type,
        i.currency,
        i.dividend_currency,
        i.valuation.value,
        i.yahoo_symbol,
        int(i.active),
    )


def list_instruments(conn: sqlite3.Connection, *, active_only: bool = False) -> list[Instrument]:
    where = " WHERE active = 1" if active_only else ""
    rows = conn.execute(f"SELECT id, {_INSTRUMENT_COLUMNS} FROM instruments{where} ORDER BY ticker")
    return [_instrument_from_row(row) for row in rows]


def get_instrument(conn: sqlite3.Connection, instrument_id: int) -> Instrument | None:
    row = conn.execute(
        f"SELECT id, {_INSTRUMENT_COLUMNS} FROM instruments WHERE id = ?", (instrument_id,)
    ).fetchone()
    return _instrument_from_row(row) if row else None


def get_instrument_by_ticker(conn: sqlite3.Connection, ticker: str) -> Instrument | None:
    row = conn.execute(
        f"SELECT id, {_INSTRUMENT_COLUMNS} FROM instruments WHERE ticker = ?", (ticker,)
    ).fetchone()
    return _instrument_from_row(row) if row else None


def add_instrument(conn: sqlite3.Connection, instrument: Instrument) -> Instrument:
    cursor = conn.execute(
        f"INSERT INTO instruments ({_INSTRUMENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        _instrument_params(instrument),
    )
    return replace(instrument, id=cursor.lastrowid)


def update_instrument(conn: sqlite3.Connection, instrument: Instrument) -> None:
    _require_id(instrument.id, "instrument")
    assignments = ", ".join(f"{c.strip()} = ?" for c in _INSTRUMENT_COLUMNS.split(","))
    cursor = conn.execute(
        f"UPDATE instruments SET {assignments} WHERE id = ?",
        (*_instrument_params(instrument), instrument.id),
    )
    _require_found(cursor, "instrument", instrument.id)


def delete_instrument(conn: sqlite3.Connection, instrument_id: int) -> None:
    """Fails if the instrument still has transactions; its prices and valuations go with it."""
    cursor = conn.execute("DELETE FROM instruments WHERE id = ?", (instrument_id,))
    _require_found(cursor, "instrument", instrument_id)


# --- transactions ---------------------------------------------------------------------------

_TRANSACTION_COLUMNS = (
    "date, instrument_id, kind, quantity, price, amount, currency, fx_rate, fee, tax, "
    "split_ratio, note"
)


def _transaction_from_row(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        instrument_id=row["instrument_id"],
        kind=TransactionKind(row["kind"]),
        quantity=_dec_from_db(row["quantity"]),
        price=_dec_from_db(row["price"]),
        amount=_dec_from_db(row["amount"]),
        currency=row["currency"],
        fx_rate=_dec_from_db(row["fx_rate"]),
        fee=_dec_from_db(row["fee"]),
        tax=_dec_from_db(row["tax"]),
        split_ratio=_dec_from_db(row["split_ratio"]),
        note=row["note"],
    )


def _transaction_params(t: Transaction) -> tuple:
    return (
        t.date.isoformat(),
        t.instrument_id,
        t.kind.value,
        _dec_to_db(t.quantity),
        _dec_to_db(t.price),
        _dec_to_db(t.amount),
        t.currency,
        _dec_to_db(t.fx_rate),
        _dec_to_db(t.fee),
        _dec_to_db(t.tax),
        _dec_to_db(t.split_ratio),
        t.note,
    )


def list_transactions(
    conn: sqlite3.Connection,
    *,
    instrument_id: int | None = None,
    kinds: Iterable[TransactionKind] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Transaction]:
    """Oldest first; rows on the same day keep the order they were entered in."""
    clauses: list[str] = []
    params: list = []
    if instrument_id is not None:
        clauses.append("instrument_id = ?")
        params.append(instrument_id)
    if kinds is not None:
        kind_values = [kind.value for kind in kinds]
        clauses.append(f"kind IN ({', '.join('?' * len(kind_values))})")
        params.extend(kind_values)
    _date_range_clause(date_from, date_to, clauses, params)
    rows = conn.execute(
        f"SELECT id, {_TRANSACTION_COLUMNS} FROM transactions{_where(clauses)} ORDER BY date, id",
        params,
    )
    return [_transaction_from_row(row) for row in rows]


def get_transaction(conn: sqlite3.Connection, transaction_id: int) -> Transaction | None:
    row = conn.execute(
        f"SELECT id, {_TRANSACTION_COLUMNS} FROM transactions WHERE id = ?", (transaction_id,)
    ).fetchone()
    return _transaction_from_row(row) if row else None


def add_transaction(conn: sqlite3.Connection, transaction: Transaction) -> Transaction:
    placeholders = ", ".join("?" * 12)
    cursor = conn.execute(
        f"INSERT INTO transactions ({_TRANSACTION_COLUMNS}) VALUES ({placeholders})",
        _transaction_params(transaction),
    )
    return replace(transaction, id=cursor.lastrowid)


def update_transaction(conn: sqlite3.Connection, transaction: Transaction) -> None:
    _require_id(transaction.id, "transaction")
    assignments = ", ".join(f"{c.strip()} = ?" for c in _TRANSACTION_COLUMNS.split(","))
    cursor = conn.execute(
        f"UPDATE transactions SET {assignments} WHERE id = ?",
        (*_transaction_params(transaction), transaction.id),
    )
    _require_found(cursor, "transaction", transaction.id)


def delete_transaction(conn: sqlite3.Connection, transaction_id: int) -> None:
    cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    _require_found(cursor, "transaction", transaction_id)


# --- manual valuations ----------------------------------------------------------------------


def list_valuations(conn: sqlite3.Connection, instrument_id: int | None = None) -> list[Valuation]:
    where, params = (
        (" WHERE instrument_id = ?", [instrument_id]) if instrument_id is not None else ("", [])
    )
    rows = conn.execute(
        f"SELECT instrument_id, date, value FROM valuations{where} ORDER BY instrument_id, date",
        params,
    )
    return [
        Valuation(row["instrument_id"], date.fromisoformat(row["date"]), Decimal(row["value"]))
        for row in rows
    ]


def set_valuation(conn: sqlite3.Connection, valuation: Valuation) -> None:
    """Add the valuation, or replace the one already entered for that day."""
    if not valuation.value.is_finite() or valuation.value < 0:
        raise ValueError("A valuation must be a finite number, zero or more")
    conn.execute(
        "INSERT INTO valuations (instrument_id, date, value) VALUES (?, ?, ?) "
        "ON CONFLICT (instrument_id, date) DO UPDATE SET value = excluded.value",
        (valuation.instrument_id, valuation.date.isoformat(), _dec_to_db(valuation.value)),
    )


def delete_valuation(conn: sqlite3.Connection, instrument_id: int, on: date) -> None:
    cursor = conn.execute(
        "DELETE FROM valuations WHERE instrument_id = ? AND date = ?",
        (instrument_id, on.isoformat()),
    )
    _require_found(cursor, "valuation", f"{instrument_id} on {on}")


# --- prices ---------------------------------------------------------------------------------


def save_prices(conn: sqlite3.Connection, prices: Iterable[Price]) -> None:
    """Add prices; a day that already has a price is overwritten with the newer data."""
    conn.executemany(
        "INSERT INTO prices (instrument_id, date, open, high, low, close, dividend, split) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (instrument_id, date) DO UPDATE SET open = excluded.open, "
        "high = excluded.high, low = excluded.low, close = excluded.close, "
        "dividend = excluded.dividend, split = excluded.split",
        [
            (
                p.instrument_id,
                p.date.isoformat(),
                p.open,
                p.high,
                p.low,
                p.close,
                p.dividend,
                p.split,
            )
            for p in prices
        ],
    )


def list_prices(
    conn: sqlite3.Connection,
    instrument_id: int | None = None,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Price]:
    clauses: list[str] = []
    params: list = []
    if instrument_id is not None:
        clauses.append("instrument_id = ?")
        params.append(instrument_id)
    _date_range_clause(date_from, date_to, clauses, params)
    rows = conn.execute(
        "SELECT instrument_id, date, open, high, low, close, dividend, split FROM prices"
        f"{_where(clauses)} ORDER BY instrument_id, date",
        params,
    )
    return [
        Price(
            instrument_id=row["instrument_id"],
            date=date.fromisoformat(row["date"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            dividend=row["dividend"],
            split=row["split"],
        )
        for row in rows
    ]


def last_price_dates(conn: sqlite3.Connection) -> dict[int, date]:
    """The most recent day with a stored price, per instrument."""
    rows = conn.execute("SELECT instrument_id, max(date) FROM prices GROUP BY instrument_id")
    return {row[0]: date.fromisoformat(row[1]) for row in rows}


# --- splits reported by the price source ----------------------------------------------------


def pending_splits(conn: sqlite3.Connection) -> list[tuple[int, date, float]]:
    """Reported splits not yet in the ledger and not dismissed: (instrument id, day, ratio).

    Only for instruments that had transactions before the split; otherwise nothing changes.
    """
    rows = conn.execute(
        """
        SELECT p.instrument_id, p.date, p.split FROM prices AS p
        WHERE p.split != 0
          AND NOT EXISTS (SELECT 1 FROM dismissed_splits AS d
                          WHERE d.instrument_id = p.instrument_id AND d.date = p.date)
          AND NOT EXISTS (SELECT 1 FROM transactions AS t
                          WHERE t.instrument_id = p.instrument_id AND t.date = p.date
                            AND t.kind = 'split')
          AND EXISTS (SELECT 1 FROM transactions AS t
                      WHERE t.instrument_id = p.instrument_id AND t.date < p.date)
        ORDER BY p.date, p.instrument_id
        """
    )
    return [(row[0], date.fromisoformat(row[1]), row[2]) for row in rows]


def dismiss_split(conn: sqlite3.Connection, instrument_id: int, on: date) -> None:
    """Remember that this reported split needs no transaction."""
    conn.execute(
        "INSERT OR IGNORE INTO dismissed_splits (instrument_id, date) VALUES (?, ?)",
        (instrument_id, on.isoformat()),
    )


# --- FX rates -------------------------------------------------------------------------------


def save_fx_rates(conn: sqlite3.Connection, rates: Iterable[FxRate]) -> None:
    """Add rates; a day that already has a rate is overwritten with the newer data."""
    conn.executemany(
        "INSERT INTO fx_rates (date, from_currency, to_currency, close) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (from_currency, to_currency, date) DO UPDATE SET close = excluded.close",
        [(r.date.isoformat(), r.from_currency, r.to_currency, r.close) for r in rates],
    )


def list_fx_rates(
    conn: sqlite3.Connection,
    from_currency: str | None = None,
    to_currency: str | None = None,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[FxRate]:
    clauses: list[str] = []
    params: list = []
    if from_currency is not None:
        clauses.append("from_currency = ?")
        params.append(from_currency)
    if to_currency is not None:
        clauses.append("to_currency = ?")
        params.append(to_currency)
    _date_range_clause(date_from, date_to, clauses, params)
    rows = conn.execute(
        f"SELECT date, from_currency, to_currency, close FROM fx_rates{_where(clauses)} "
        "ORDER BY from_currency, to_currency, date",
        params,
    )
    return [
        FxRate(
            date.fromisoformat(row["date"]), row["from_currency"], row["to_currency"], row["close"]
        )
        for row in rows
    ]


def last_fx_dates(conn: sqlite3.Connection) -> dict[tuple[str, str], date]:
    """The most recent day with a stored rate, per (from, to) currency pair."""
    rows = conn.execute(
        "SELECT from_currency, to_currency, max(date) FROM fx_rates "
        "GROUP BY from_currency, to_currency"
    )
    return {(row[0], row[1]): date.fromisoformat(row[2]) for row in rows}


# --- helpers --------------------------------------------------------------------------------


class NotFoundError(LookupError):
    """The record to change or delete does not exist."""


def _require_id(record_id: int | None, what: str) -> None:
    if record_id is None:
        raise ValueError(f"Cannot update a {what} that has no id")


def _require_found(cursor: sqlite3.Cursor, what: str, key: object) -> None:
    if cursor.rowcount == 0:
        raise NotFoundError(f"No {what} with id {key}")
