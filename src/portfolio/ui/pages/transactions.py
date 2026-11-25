"""The ledger: list, add, edit and delete transactions and manual valuations."""

import sqlite3
from datetime import date

import streamlit as st

from portfolio.core import repo
from portfolio.core.i18n import N_, tr
from portfolio.core.models import (
    Instrument,
    Transaction,
    TransactionKind,
    ValidationError,
    Valuation,
    ValuationMethod,
    fields_for,
)
from portfolio.ui import common
from portfolio.ui.formatting import decimal_text, parse_decimal

_KIND_LABELS = common.KIND_LABELS
_FIELD_LABELS = {
    "quantity": N_("Quantity"),
    "price": N_("Price per unit"),
    "amount": N_("Amount"),
    "tax": N_("Tax withheld"),
    "split_ratio": N_("New units per old unit"),
}
_ALL = "*"  # the filter's value for no filter


def render() -> None:
    st.title(tr("Transactions"))
    ledger, valuations = st.tabs([tr("Ledger"), tr("Manual valuations")])
    with common.connection() as conn:
        instruments = repo.list_instruments(conn)
        if not instruments:
            st.info(tr("Add an instrument in Settings first."))
            return
        with ledger:
            _ledger(conn, instruments)
        with valuations:
            _valuations(conn, instruments)


def _flash() -> None:
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


def _changed(message: str) -> None:
    """After a saved change: show the message and drop the table selection."""
    st.session_state["flash"] = message
    st.session_state["tx_version"] = st.session_state.get("tx_version", 0) + 1
    st.rerun()


# --- ledger ---------------------------------------------------------------------------------


def _ledger(conn: sqlite3.Connection, instruments: list[Instrument]) -> None:
    _flash()
    by_id = {i.id: i for i in instruments}
    by_ticker = {i.ticker: i for i in instruments}

    f1, f2, f3, f4 = st.columns(4)
    ticker = f1.selectbox(
        tr("Instrument"), [_ALL, *by_ticker], format_func=lambda t: tr("All") if t == _ALL else t,
        key="tx_filter_instrument",
    )  # fmt: skip
    kind = f2.selectbox(
        tr("Kind"), [_ALL, *_KIND_LABELS],
        format_func=lambda k: tr("All") if k == _ALL else common.kind_label(k),
        key="tx_filter_kind",
    )  # fmt: skip
    date_from = f3.date_input(tr("From"), value=None, key="tx_filter_from")
    date_to = f4.date_input(tr("To"), value=None, key="tx_filter_to")
    rows = repo.list_transactions(
        conn,
        instrument_id=None if ticker == _ALL else by_ticker[ticker].id,
        kinds=None if kind == _ALL else [kind],
        date_from=date_from,
        date_to=date_to,
    )
    rows.reverse()  # newest first

    def number(value):
        return None if value is None else float(value)

    table = [
        {
            "date": t.date,
            "instrument": by_id[t.instrument_id].ticker,
            "kind": common.kind_label(t.kind),
            "quantity": number(t.quantity),
            "price": number(t.price),
            "amount": number(t.amount),
            "currency": t.currency,
            "rate": number(t.fx_rate),
            "fee": number(t.fee),
            "tax": number(t.tax),
            "split": number(t.split_ratio),
            "note": t.note,
        }
        for t in rows
    ]
    st.caption(tr("Transactions: {count}. Select a row to edit or delete it.", count=len(rows)))
    version = st.session_state.get("tx_version", 0)
    table_key = f"tx_table_{version}_{ticker}_{kind}_{date_from}_{date_to}"
    event = st.dataframe(
        table,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        # A new key clears the selection: after every change and whenever the filters
        # change, because the selection is a row position, not a transaction.
        key=table_key,
        column_config={
            "date": tr("Date"),
            "instrument": tr("Instrument"),
            "kind": tr("Kind"),
            "quantity": st.column_config.NumberColumn(tr("Quantity"), format="%.8g"),
            "price": st.column_config.NumberColumn(tr("Price"), format="%.8g"),
            "amount": tr("Amount"),
            "currency": tr("Currency"),
            "rate": st.column_config.NumberColumn(tr("Rate"), format="%.6g"),
            "fee": tr("Fee"),
            "tax": tr("Tax"),
            "split": tr("Split"),
            "note": tr("Note"),
        },
    )
    selected_rows = event.selection.rows if event else []
    selected = rows[selected_rows[0]] if selected_rows and selected_rows[0] < len(rows) else None
    default_instrument = by_ticker.get(ticker) if ticker != _ALL else None
    _transaction_form(conn, instruments, selected, default_instrument)


def _transaction_form(
    conn: sqlite3.Connection,
    instruments: list[Instrument],
    editing: Transaction | None,
    default_instrument: Instrument | None,
) -> None:
    base = common.config().base_currency
    by_id = {i.id: i for i in instruments}
    # Widget keys include the edited row, so choosing another row refills the form.
    key = f"tx_form_{editing.id if editing else 'new'}"
    st.subheader(tr("Edit transaction") if editing else tr("Add transaction"))

    choices = instruments if editing else [i for i in instruments if i.active] or instruments
    preset = by_id[editing.instrument_id] if editing else default_instrument
    top = st.columns(3)
    instrument = top[0].selectbox(
        tr("Instrument"),
        choices,
        index=choices.index(preset) if preset in choices else 0,
        format_func=lambda i: i.ticker,
        key=f"{key}_instrument",
    )
    kinds = list(_KIND_LABELS)
    kind = top[1].selectbox(
        tr("Kind"),
        kinds,
        index=kinds.index(editing.kind) if editing else 0,
        format_func=common.kind_label,
        key=f"{key}_kind",
    )
    day = top[2].date_input(
        tr("Date"), value=editing.date if editing else date.today(), key=f"{key}_date"
    )

    required, optional = fields_for(kind)
    shown = [f for f in (*required, *optional) if f not in ("currency", "fx_rate")]
    values: dict[str, str] = {}
    cells = st.columns(4)
    position = 0
    for field in shown:
        suffix = "" if field in required else " " + tr("(optional)")
        values[field] = cells[position % 4].text_input(
            tr(_FIELD_LABELS[field]) + suffix,
            value=decimal_text(getattr(editing, field)) if editing else "",
            key=f"{key}_{kind}_{field}",
        )
        position += 1

    currency = None
    if "currency" in required:
        currencies = repo.list_currencies(conn)
        if editing and editing.currency:
            suggested = editing.currency
        elif kind is TransactionKind.DIVIDEND and instrument.dividend_currency:
            suggested = instrument.dividend_currency
        else:
            suggested = _last_trade_currency(conn, instrument) or instrument.currency
        currency = cells[position % 4].selectbox(
            tr("Currency"),
            currencies,
            index=currencies.index(suggested) if suggested in currencies else 0,
            key=f"{key}_{kind}_{instrument.id}_currency",
        )
        position += 1
        rate_required = "fx_rate" in required
        if currency == base:
            values["fx_rate"] = "1"
        else:
            values["fx_rate"] = cells[position % 4].text_input(
                tr("{base} per 1 {currency}", base=base, currency=currency)
                + ("" if rate_required else " " + tr("(optional)")),
                value=decimal_text(editing.fx_rate) if editing else "",
                help=None if rate_required else tr("Empty: the market rate of that day is used."),
                key=f"{key}_{kind}_{currency}_rate",
            )
            position += 1

    bottom = st.columns([1, 3])
    fee_text = bottom[0].text_input(
        tr("Fee ({currency})", currency=base),
        value=decimal_text(editing.fee) if editing else "0",
        key=f"{key}_fee",
    )
    note = bottom[1].text_input(
        tr("Note"), value=(editing.note or "") if editing else "", key=f"{key}_note"
    )

    save, delete, _ = st.columns([1, 1, 4])
    if save.button(tr("Save changes") if editing else tr("Add"), type="primary", key=f"{key}_save"):
        try:
            numbers = {f: parse_decimal(text, tr(_FIELD_LABELS.get(f, N_("rate"))).lower())
                       for f, text in values.items()}  # fmt: skip
            transaction = Transaction(
                id=editing.id if editing else None,
                date=day,
                instrument_id=instrument.id,
                kind=kind,
                currency=currency,
                fee=parse_decimal(fee_text, tr("fee")) or parse_decimal("0"),
                note=note.strip() or None,
                **numbers,
            )
            with conn:
                if editing:
                    repo.update_transaction(conn, transaction)
                else:
                    repo.add_transaction(conn, transaction)
        except (ValueError, ValidationError, sqlite3.Error, repo.NotFoundError) as e:
            st.error(str(e))
        else:
            _changed(
                tr("{kind} of {ticker} on {day} changed.", kind=common.kind_label(kind),
                   ticker=instrument.ticker, day=day)
                if editing
                else tr("{kind} of {ticker} on {day} added.", kind=common.kind_label(kind),
                        ticker=instrument.ticker, day=day)
            )  # fmt: skip

    if editing:
        confirmed = delete.checkbox(tr("Really delete"), key=f"{key}_confirm")
        if delete.button(tr("Delete"), disabled=not confirmed, key=f"{key}_delete"):
            with conn:
                repo.delete_transaction(conn, editing.id)
            _changed(tr("Transaction deleted."))


def _last_trade_currency(conn: sqlite3.Connection, instrument: Instrument) -> str | None:
    """What this instrument was last bought or sold in, offered again for the next trade."""
    trades = repo.list_transactions(
        conn, instrument_id=instrument.id, kinds=[TransactionKind.BUY, TransactionKind.SELL]
    )
    return trades[-1].currency if trades else None


# --- manual valuations ----------------------------------------------------------------------


def _cash_by_day(conn: sqlite3.Connection, instrument_id: int) -> dict[date, float]:
    """Deposits minus withdrawals per day, in the currency they were recorded in."""
    kinds = [TransactionKind.DEPOSIT, TransactionKind.WITHDRAWAL]
    totals: dict[date, float] = {}
    for t in repo.list_transactions(conn, instrument_id=instrument_id, kinds=kinds):
        sign = 1 if t.kind is TransactionKind.DEPOSIT else -1
        totals[t.date] = totals.get(t.date, 0.0) + sign * float(t.amount)
    return totals


def _valuations(conn: sqlite3.Connection, instruments: list[Instrument]) -> None:
    manual = [i for i in instruments if i.valuation is ValuationMethod.MANUAL]
    if not manual:
        st.info(tr("No instrument is valued by hand. Set that in Settings."))
        return
    active = [i for i in manual if i.active] or manual
    st.caption(
        tr(
            "The total value of an instrument on a day, in its own currency. Deposits and "
            "withdrawals made on that day or later are added on top automatically."
        )
    )
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
    instrument = c1.selectbox(
        tr("Instrument"),
        active,
        format_func=lambda i: f"{i.ticker} ({i.currency})",
        key="val_instrument",
    )
    day = c2.date_input(tr("Date"), value=date.today(), key="val_date")
    value_text = c3.text_input(tr("Value"), key="val_value")
    if c4.button(tr("Save"), type="primary", key="val_save"):
        try:
            value = parse_decimal(value_text, tr("value"))
            if value is None:
                raise ValueError(tr("Enter a value."))
            with conn:
                repo.set_valuation(conn, Valuation(instrument.id, day, value))
        except (ValueError, sqlite3.Error) as e:
            st.error(str(e))
        else:
            _changed(tr("Value of {ticker} on {day} saved.", ticker=instrument.ticker, day=day))

    rows = repo.list_valuations(conn, instrument.id)
    rows.reverse()
    same_day = _cash_by_day(conn, instrument.id)
    if any(v.date in same_day for v in rows):
        st.warning(
            tr(
                "Some values share their day with a deposit or withdrawal, which is added on "
                "top of the value. If the value you entered already contained it, it is "
                "counted twice until the next value: lower the value by that amount, or move "
                "the value one day later."
            )
        )
    event = st.dataframe(
        [{"date": v.date, "value": float(v.value), "on_top": same_day.get(v.date)} for v in rows],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"val_table_{instrument.id}_{st.session_state.get('tx_version', 0)}",
        column_config={
            "date": tr("Date"),
            "value": st.column_config.NumberColumn(tr("Value"), format="localized"),
            "on_top": st.column_config.NumberColumn(
                tr("Added on top"),
                format="localized",
                help=tr("Deposits minus withdrawals recorded on the same day."),
            ),
        },
        width="content",
    )
    chosen = event.selection.rows if event else []
    if chosen and chosen[0] < len(rows):
        target = rows[chosen[0]]
        if st.button(tr("Delete the value from {day}", day=target.date), key="val_delete"):
            with conn:
                repo.delete_valuation(conn, instrument.id, target.date)
            _changed(tr("Valuation deleted."))
