"""CSV export of everything, and CSV import of transactions.

The export is for keeping a copy readable without this app. Instruments are identified by
ticker, not by database id, so the files make sense on their own.
"""

import csv
import io
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from portfolio.core import repo
from portfolio.core.models import Transaction, TransactionKind, ValidationError

TRANSACTION_COLUMNS = (
    "date", "ticker", "kind", "quantity", "price", "amount", "currency", "fx_rate", "fee", "tax",
    "split_ratio", "note",
)  # fmt: skip
_REQUIRED_COLUMNS = ("date", "ticker", "kind")
_DECIMAL_COLUMNS = ("quantity", "price", "amount", "fx_rate", "fee", "tax", "split_ratio")
# Columns of files exported by earlier versions; read without complaint and not used.
_IGNORED_COLUMNS = ("reinvested",)


class CsvError(Exception):
    """The file as a whole cannot be read (as opposed to a problem in one row)."""


# --- export ---------------------------------------------------------------------------------


def _csv(header: tuple[str, ...] | list[str], rows) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows([["" if cell is None else cell for cell in row] for row in rows])
    return buffer.getvalue()


def transactions_csv(conn: sqlite3.Connection) -> str:
    tickers = {i.id: i.ticker for i in repo.list_instruments(conn)}
    text = repo.decimal_text
    return _csv(
        TRANSACTION_COLUMNS,
        (
            (
                t.date.isoformat(), tickers[t.instrument_id], t.kind.value, text(t.quantity),
                text(t.price), text(t.amount), t.currency, text(t.fx_rate), text(t.fee),
                text(t.tax), text(t.split_ratio), t.note,
            )
            for t in repo.list_transactions(conn)
        ),
    )  # fmt: skip


def export_all(conn: sqlite3.Connection) -> dict[str, str]:
    """Every table as CSV text, keyed by file name."""
    instruments = repo.list_instruments(conn)
    tickers = {i.id: i.ticker for i in instruments}
    return {
        "currencies.csv": _csv(["code"], ([code] for code in repo.list_currencies(conn))),
        "instrument_types.csv": _csv(
            ["name"], ([name] for name in repo.list_instrument_types(conn))
        ),
        "instruments.csv": _csv(
            ["ticker", "name", "type", "currency", "dividend_currency", "valuation",
             "yahoo_symbol", "active"],
            (
                (i.ticker, i.name, i.type, i.currency, i.dividend_currency, i.valuation.value,
                 i.yahoo_symbol, int(i.active))
                for i in instruments
            ),
        ),
        "transactions.csv": transactions_csv(conn),
        "valuations.csv": _csv(
            ["ticker", "date", "value"],
            (
                (tickers[v.instrument_id], v.date.isoformat(), repo.decimal_text(v.value))
                for v in repo.list_valuations(conn)
            ),
        ),
        "prices.csv": _csv(
            ["ticker", "date", "open", "high", "low", "close", "dividend", "split"],
            (
                (tickers[p.instrument_id], p.date.isoformat(), p.open, p.high, p.low, p.close,
                 p.dividend, p.split)
                for p in repo.list_prices(conn)
            ),
        ),
        "fx_rates.csv": _csv(
            ["date", "from_currency", "to_currency", "close"],
            (
                (r.date.isoformat(), r.from_currency, r.to_currency, r.close)
                for r in repo.list_fx_rates(conn)
            ),
        ),
        "dismissed_splits.csv": _csv(
            ["ticker", "date"],
            (
                (tickers[row[0]], row[1])
                for row in conn.execute(
                    "SELECT instrument_id, date FROM dismissed_splits ORDER BY date, instrument_id"
                )
            ),
        ),
        "reviewed_findings.csv": _csv(
            ["check", "ticker", "date", "key", "reviewed_on"],
            (
                (row[0], tickers[row[1]], row[2], row[3], row[4])
                for row in conn.execute(
                    "SELECT check_name, instrument_id, date, key, reviewed_on "
                    "FROM reviewed_findings ORDER BY check_name, instrument_id, date, key"
                )
            ),
        ),
    }  # fmt: skip


def export_zip(conn: sqlite3.Connection) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in export_all(conn).items():
            archive.writestr(name, text)
    return buffer.getvalue()


def database_file(conn: sqlite3.Connection) -> bytes:
    """A complete copy of the database as one SQLite file."""
    return conn.serialize()


# --- import of transactions -----------------------------------------------------------------


@dataclass(frozen=True)
class ParsedRow:
    line: int  # line number in the file, the header being line 1
    transaction: Transaction | None  # None if the row has an error
    ticker: str
    error: str | None = None
    duplicate: bool = False  # an identical transaction is already in the database

    @property
    def ok(self) -> bool:
        return self.error is None


def decode(raw: bytes) -> str:
    """Text of an uploaded file: UTF-8, or the Windows encoding Czech Excel uses."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1250")


def _parse_date(text: str) -> date:
    for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"date '{text}' is not YYYY-MM-DD or DD.MM.YYYY")


def _parse_decimal(text: str, column: str, decimal_comma: bool) -> Decimal | None:
    cleaned = text.replace(" ", "").replace(" ", "")
    if decimal_comma:
        cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"{column} '{text}' is not a number") from None


def _duplicate_key(t: Transaction) -> tuple:
    return (t.date, t.instrument_id, t.kind, t.quantity, t.price, t.amount, t.split_ratio, t.fee)


def parse_transactions(text: str, conn: sqlite3.Connection) -> list[ParsedRow]:
    """Read a CSV with the columns of ``TRANSACTION_COLUMNS`` (only date, ticker and kind
    are mandatory). Comma or semicolon separated; with semicolons, decimal commas are accepted.

    Nothing is written. Rows that cannot be used carry an ``error`` instead of a transaction.
    """
    first_line = text.lstrip().split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    columns = [(name or "").strip().lower() for name in reader.fieldnames or []]
    missing = [name for name in _REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise CsvError(f"The file needs the columns: {', '.join(missing)}")
    unknown = [name for name in columns if name not in (*TRANSACTION_COLUMNS, *_IGNORED_COLUMNS)]
    if unknown:
        raise CsvError(
            f"Unknown columns: {', '.join(unknown)}. Allowed: {', '.join(TRANSACTION_COLUMNS)}"
        )
    reader.fieldnames = columns

    instruments = {i.ticker: i for i in repo.list_instruments(conn)}
    currencies = set(repo.list_currencies(conn))
    existing = {_duplicate_key(t) for t in repo.list_transactions(conn)}
    rows: list[ParsedRow] = []
    for record in reader:
        line = reader.line_num  # the real line in the file, blank lines included
        if None in record:
            rows.append(ParsedRow(line, None, "", "more values than columns"))
            continue
        cells = {name: (value or "").strip() for name, value in record.items()}
        if not any(cells.values()):
            continue
        ticker = cells["ticker"]
        try:
            instrument = instruments.get(ticker)
            if instrument is None:
                raise ValueError(f"unknown instrument '{ticker}'")
            try:
                kind = TransactionKind(cells["kind"].lower())
            except ValueError:
                raise ValueError(f"unknown kind '{cells['kind']}'") from None
            currency = cells.get("currency", "").upper() or None
            if currency and currency not in currencies:
                raise ValueError(f"unknown currency '{currency}'")
            numbers = {
                column: _parse_decimal(cells.get(column, ""), column, delimiter == ";")
                for column in _DECIMAL_COLUMNS
            }
            numbers["fee"] = numbers["fee"] or Decimal(0)
            transaction = Transaction(
                date=_parse_date(cells["date"]),
                instrument_id=instrument.id,
                kind=kind,
                currency=currency,
                note=cells.get("note") or None,
                **numbers,
            )
        except (ValueError, ValidationError) as e:
            rows.append(ParsedRow(line, None, ticker, str(e)))
            continue
        rows.append(
            ParsedRow(line, transaction, ticker, duplicate=_duplicate_key(transaction) in existing)
        )
    return rows


def import_transactions(
    conn: sqlite3.Connection, rows: list[ParsedRow], *, skip_duplicates: bool = True
) -> int:
    """Add the parsed rows. Refuses if any row has an error. Does not commit."""
    bad = [row.line for row in rows if not row.ok]
    if bad:
        raise CsvError(f"Fix the errors first (lines {', '.join(map(str, bad))}).")
    added = 0
    for row in rows:
        if row.duplicate and skip_duplicates:
            continue
        repo.add_transaction(conn, row.transaction)
        added += 1
    return added
