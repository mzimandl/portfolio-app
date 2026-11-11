"""One-off import from the database of the old Sanic/React app.

Old layout: separate ``trades``, ``crypto``, ``deposits``, ``dividends`` and ``staking`` tables
with signed numbers stored as floats. Everything becomes rows of the new ``transactions`` ledger.
After copying, totals per ticker are recomputed from both databases and compared.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

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

_VALUATION_BY_LEGACY_EVALUATION = {
    "yfinance": ValuationMethod.YAHOO,
    "manual": ValuationMethod.MANUAL,
}
_TOLERANCE = 1e-9


class LegacyImportError(Exception):
    pass


@dataclass(frozen=True)
class Check:
    """One total computed from the old and the new database."""

    ticker: str
    what: str
    old: float
    new: float

    @property
    def ok(self) -> bool:
        return abs(self.old - self.new) <= _TOLERANCE * max(1.0, abs(self.old))


@dataclass
class ImportReport:
    imported: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    skipped: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    notes: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)

    @property
    def failed_checks(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    @property
    def ok(self) -> bool:
        return not self.failed_checks


def _dec(value: float) -> Decimal:
    """Float to decimal, dropping binary noise such as 51.129000000000005."""
    return Decimal(format(value, ".15g"))


def _fx_rate(base_rate: float | None) -> Decimal:
    """Old ``base_rate`` divides (trade currency per 1 base); the new rate multiplies."""
    if not base_rate:
        raise LegacyImportError("A trade has an empty or zero base_rate")
    if base_rate == 1:
        return Decimal(1)
    return Decimal(format(1 / base_rate, ".15g"))


def import_legacy(
    source: sqlite3.Connection, target: sqlite3.Connection, base_currency: str
) -> ImportReport:
    """Copy everything from ``source`` into the empty ``target``. Does not commit."""
    source.row_factory = sqlite3.Row
    if repo.list_instruments(target) or repo.list_currencies(target):
        raise LegacyImportError("The target database already contains data")

    report = ImportReport()

    for row in source.execute("SELECT name FROM currencies"):
        repo.add_currency(target, row["name"])
        report.imported["currencies"] += 1
    for row in source.execute("SELECT name FROM types"):
        repo.add_instrument_type(target, row["name"])
        report.imported["instrument types"] += 1

    instruments = _import_instruments(source, target, report)
    transactions = _collect_transactions(source, instruments, base_currency, report)
    # Chronological ids: same-day rows keep the order of the old tables.
    transactions.sort(key=lambda item: item[0])
    for _, transaction in transactions:
        repo.add_transaction(target, transaction)
        report.imported[f"transactions: {transaction.kind}"] += 1

    _import_market_data(source, target, instruments, report)
    _verify(source, target, instruments, report)
    return report


def _import_instruments(
    source: sqlite3.Connection, target: sqlite3.Connection, report: ImportReport
) -> dict[str, Instrument]:
    instruments: dict[str, Instrument] = {}
    for row in source.execute("SELECT * FROM instruments ORDER BY rowid"):
        valuation = _VALUATION_BY_LEGACY_EVALUATION.get(row["evaluation"])
        if valuation is None:
            report.skipped["instruments"] += 1
            report.notes.append(
                f"{row['ticker']}: not imported, price source '{row['evaluation']}' was dropped"
            )
            continue
        instruments[row["ticker"]] = repo.add_instrument(
            target,
            Instrument(
                ticker=row["ticker"],
                name=row["name"],
                type=row["type"],
                currency=row["currency"],
                dividend_currency=row["dividend_currency"],
                valuation=valuation,
                yahoo_symbol=row["eval_param"] if valuation is ValuationMethod.YAHOO else None,
                active=bool(row["active"]),
            ),
        )
        report.imported["instruments"] += 1
    return instruments


def _collect_transactions(
    source: sqlite3.Connection,
    instruments: dict[str, Instrument],
    base_currency: str,
    report: ImportReport,
) -> list[tuple[tuple, Transaction]]:
    """Returns (sort key, transaction) pairs."""
    result: list[tuple[tuple, Transaction]] = []

    def rows(table_number: int, table: str):
        for row in source.execute(f"SELECT * FROM {table} ORDER BY id"):
            instrument = instruments.get(row["ticker"])
            if instrument is None:
                report.skipped[f"{table} rows"] += 1
                continue
            day = date.fromisoformat(row["date"])

            def add(kind: K, instrument=instrument, day=day, row=row, **fields) -> None:
                transaction = Transaction(day, instrument.id, kind, **fields)
                result.append(((row["date"], table_number, row["id"]), transaction))

            yield row, instrument, add

    def cash_rate(currency: str) -> Decimal | None:
        # Empty means "use the market rate of that day"; the base currency needs no rate.
        return Decimal(1) if currency == base_currency else None

    def trade(row, currency: str, add) -> None:
        if row["volume"] == 0:
            raise LegacyImportError(f"{row['ticker']} {row['date']}: trade with zero volume")
        selling = row["volume"] < 0
        fx_rate = _fx_rate(row["base_rate"])
        if fx_rate == 1 and currency != base_currency and row["price"] != 0:
            report.notes.append(
                f"{row['ticker']} {row['date']}: {currency} trade recorded with exchange rate 1 "
                "(imported as it is, probably a typing slip)"
            )
        add(
            K.SELL if selling else K.BUY,
            quantity=_dec(abs(row["volume"])),
            price=_dec(row["price"]),
            currency=currency,
            fx_rate=fx_rate,
            fee=_dec(row["fee"] or 0),
            reinvested=bool(row["reinvested"]) and selling,
        )

    for row, instrument, add in rows(0, "trades"):
        trade(row, instrument.currency, add)

    for row, _instrument, add in rows(1, "crypto"):
        trade(row, row["currency"], add)

    for row, instrument, add in rows(2, "deposits"):
        amount, fee = row["amount"] or 0, _dec(row["fee"] or 0)
        if amount == 0:
            if fee == 0:
                report.skipped["deposits rows (empty)"] += 1
            else:
                add(K.FEE, fee=fee)
            continue
        add(
            K.DEPOSIT if amount > 0 else K.WITHDRAWAL,
            amount=_dec(abs(amount)),
            currency=instrument.currency,
            fx_rate=cash_rate(instrument.currency),
            fee=fee,
            reinvested=bool(row["reinvested"]) and amount < 0,
        )

    for row, instrument, add in rows(3, "dividends"):
        currency = instrument.dividend_currency or instrument.currency
        add(K.DIVIDEND, amount=_dec(row["dividend"]), currency=currency,
            fx_rate=cash_rate(currency))  # fmt: skip

    negative_staking = 0
    for row, instrument, add in rows(4, "staking"):
        if row["volume"] > 0:
            add(K.STAKING_REWARD, quantity=_dec(row["volume"]))
        elif row["volume"] < 0:
            # Coins taken back. Same convention the old data uses for coins lost to
            # network fees: a sell at price zero.
            negative_staking += 1
            add(
                K.SELL,
                quantity=_dec(-row["volume"]),
                price=Decimal(0),
                currency=instrument.currency,
                fx_rate=Decimal(1),
                note="Negative staking in the old app",
            )
        else:
            report.skipped["staking rows (empty)"] += 1
    if negative_staking:
        report.notes.append(
            f"{negative_staking} negative staking rows were imported as sells at price 0"
        )
    return result


def _import_market_data(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    instruments: dict[str, Instrument],
    report: ImportReport,
) -> None:
    valuations = 0
    for row in source.execute('SELECT * FROM "values"'):
        instrument = instruments.get(row["ticker"])
        if instrument is None:
            report.skipped["values rows"] += 1
            continue
        repo.set_valuation(
            target,
            Valuation(instrument.id, date.fromisoformat(row["date"]), _dec(row["value"])),
        )
        valuations += 1
    report.imported["valuations"] = valuations

    prices = []
    for row in source.execute("SELECT * FROM historical"):
        instrument = instruments.get(row["ticker"])
        if instrument is None or row["close"] is None:
            report.skipped["historical rows"] += 1
            continue
        prices.append(
            Price(
                instrument_id=instrument.id,
                date=date.fromisoformat(row["date"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                dividend=row["dividends"] or 0.0,
                split=row["splits"] or 0.0,
            )
        )
    repo.save_prices(target, prices)
    # The old ledger was adjusted by hand after splits, so none of them needs a transaction.
    for price in prices:
        if price.split:
            repo.dismiss_split(target, price.instrument_id, price.date)
    report.imported["prices"] = len(prices)

    rates = [
        FxRate(date.fromisoformat(row["date"]), row["from_curr"], row["to_curr"], row["close"])
        for row in source.execute("SELECT * FROM fx WHERE close IS NOT NULL")
    ]
    repo.save_fx_rates(target, rates)
    report.imported["fx rates"] = len(rates)


# --- verification ---------------------------------------------------------------------------

# Totals per ticker straight from the old tables. Money is in base currency.
_OLD_TOTALS = {
    "quantity": """
        SELECT ticker, sum(volume) FROM (
            SELECT ticker, volume FROM trades UNION ALL
            SELECT ticker, volume FROM crypto UNION ALL
            SELECT ticker, volume FROM staking
        ) GROUP BY ticker""",
    "bought": """
        SELECT ticker, sum(volume * price / base_rate) FROM (
            SELECT ticker, volume, price, base_rate FROM trades UNION ALL
            SELECT ticker, volume, price, base_rate FROM crypto
        ) WHERE volume > 0 GROUP BY ticker""",
    "sold": """
        SELECT ticker, -sum(volume * price / base_rate) FROM (
            SELECT ticker, volume, price, base_rate FROM trades UNION ALL
            SELECT ticker, volume, price, base_rate FROM crypto
        ) WHERE volume < 0 GROUP BY ticker""",
    "deposited": "SELECT ticker, sum(amount) FROM deposits WHERE amount > 0 GROUP BY ticker",
    "withdrawn": "SELECT ticker, -sum(amount) FROM deposits WHERE amount < 0 GROUP BY ticker",
    "reinvested": """
        SELECT ticker, sum(x) FROM (
            SELECT ticker, -volume * price / base_rate AS x FROM trades
                WHERE volume < 0 AND reinvested = 1 UNION ALL
            SELECT ticker, -volume * price / base_rate FROM crypto
                WHERE volume < 0 AND reinvested = 1 UNION ALL
            SELECT ticker, -amount FROM deposits WHERE amount < 0 AND reinvested = 1
        ) GROUP BY ticker""",
    "fees": """
        SELECT ticker, sum(fee) FROM (
            SELECT ticker, fee FROM trades UNION ALL
            SELECT ticker, fee FROM crypto UNION ALL
            SELECT ticker, fee FROM deposits
        ) GROUP BY ticker""",
    "dividends": "SELECT ticker, sum(dividend) FROM dividends GROUP BY ticker",
    "valuations": 'SELECT ticker, sum(value) FROM "values" GROUP BY ticker',
    "price rows": "SELECT ticker, count(*) FROM historical WHERE close IS NOT NULL GROUP BY ticker",
    "last close": """
        SELECT ticker, close FROM historical AS h
        WHERE date = (SELECT max(date) FROM historical WHERE ticker = h.ticker)""",
}


def _new_totals(target: sqlite3.Connection) -> dict[str, dict[int, float]]:
    totals: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    zero = Decimal(0)
    exact: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(lambda: zero))
    for t in repo.list_transactions(target):
        i = t.instrument_id
        exact["fees"][i] += t.fee
        if t.kind in (K.BUY, K.SELL):
            sign = 1 if t.kind is K.BUY else -1
            cash = t.quantity * t.price * t.fx_rate
            exact["quantity"][i] += sign * t.quantity
            exact["bought" if t.kind is K.BUY else "sold"][i] += cash
            if t.reinvested:
                exact["reinvested"][i] += cash
        elif t.kind is K.STAKING_REWARD:
            exact["quantity"][i] += t.quantity
        elif t.kind is K.DEPOSIT:
            exact["deposited"][i] += t.amount
        elif t.kind is K.WITHDRAWAL:
            exact["withdrawn"][i] += t.amount
            if t.reinvested:
                exact["reinvested"][i] += t.amount
        elif t.kind is K.DIVIDEND:
            exact["dividends"][i] += t.amount
    for what, per_instrument in exact.items():
        for i, value in per_instrument.items():
            totals[what][i] = float(value)
    for valuation in repo.list_valuations(target):
        totals["valuations"][valuation.instrument_id] += float(valuation.value)
    for price in repo.list_prices(target):  # ordered by date within an instrument
        totals["price rows"][price.instrument_id] += 1
        totals["last close"][price.instrument_id] = price.close
    return totals


def _verify(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    instruments: dict[str, Instrument],
    report: ImportReport,
) -> None:
    new = _new_totals(target)
    for what, sql in _OLD_TOTALS.items():
        old = {row[0]: row[1] or 0.0 for row in source.execute(sql)}
        for ticker, instrument in instruments.items():
            old_value = float(old.get(ticker, 0.0))
            new_value = new[what].get(instrument.id, 0.0)
            if old_value or new_value:
                report.checks.append(Check(ticker, what, old_value, new_value))

    old_fx = source.execute("SELECT count(*) FROM fx WHERE close IS NOT NULL").fetchone()[0]
    new_fx = target.execute("SELECT count(*) FROM fx_rates").fetchone()[0]
    report.checks.append(Check("(all)", "fx rate rows", old_fx, new_fx))
