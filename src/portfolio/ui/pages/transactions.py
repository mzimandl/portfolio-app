"""The ledger: list, add, edit and delete transactions and manual valuations."""

import sqlite3
from datetime import date

import streamlit as st

from portfolio.core import repo
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

_KIND_LABELS = {
    TransactionKind.BUY: "Buy",
    TransactionKind.SELL: "Sell",
    TransactionKind.DEPOSIT: "Deposit",
    TransactionKind.WITHDRAWAL: "Withdrawal",
    TransactionKind.DIVIDEND: "Dividend",
    TransactionKind.STAKING_REWARD: "Staking reward",
    TransactionKind.STAKING_CORRECTION: "Staking correction",
    TransactionKind.SPLIT: "Split",
    TransactionKind.FEE: "Fee only",
}
_FIELD_LABELS = {
    "quantity": "Quantity",
    "price": "Price per unit",
    "amount": "Amount",
    "tax": "Tax withheld",
    "split_ratio": "New units per old unit",
}
_ALL = "All"


def render() -> None:
    st.title("Transactions")
    ledger, valuations = st.tabs(["Ledger", "Manual valuations"])
    with common.connection() as conn:
        instruments = repo.list_instruments(conn)
        if not instruments:
            st.info("Add an instrument in Settings first.")
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
    ticker = f1.selectbox("Instrument", [_ALL, *by_ticker], key="tx_filter_instrument")
    kind = f2.selectbox(
        "Kind", [_ALL, *_KIND_LABELS], format_func=lambda k: _KIND_LABELS.get(k, k),
        key="tx_filter_kind",
    )  # fmt: skip
    date_from = f3.date_input("From", value=None, key="tx_filter_from")
    date_to = f4.date_input("To", value=None, key="tx_filter_to")
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
            "Date": t.date,
            "Instrument": by_id[t.instrument_id].ticker,
            "Kind": _KIND_LABELS[t.kind],
            "Quantity": number(t.quantity),
            "Price": number(t.price),
            "Amount": number(t.amount),
            "Currency": t.currency,
            "Rate": number(t.fx_rate),
            "Fee": number(t.fee),
            "Tax": number(t.tax),
            "Split": number(t.split_ratio),
            "Note": t.note,
        }
        for t in rows
    ]
    st.caption(f"{len(rows)} transactions. Select a row to edit or delete it.")
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
            "Quantity": st.column_config.NumberColumn(format="%.8g"),
            "Price": st.column_config.NumberColumn(format="%.8g"),
            "Rate": st.column_config.NumberColumn(format="%.6g"),
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
    st.subheader("Edit transaction" if editing else "Add transaction")

    choices = instruments if editing else [i for i in instruments if i.active] or instruments
    preset = by_id[editing.instrument_id] if editing else default_instrument
    top = st.columns(3)
    instrument = top[0].selectbox(
        "Instrument",
        choices,
        index=choices.index(preset) if preset in choices else 0,
        format_func=lambda i: i.ticker,
        key=f"{key}_instrument",
    )
    kinds = list(_KIND_LABELS)
    kind = top[1].selectbox(
        "Kind",
        kinds,
        index=kinds.index(editing.kind) if editing else 0,
        format_func=_KIND_LABELS.get,
        key=f"{key}_kind",
    )
    day = top[2].date_input(
        "Date", value=editing.date if editing else date.today(), key=f"{key}_date"
    )

    required, optional = fields_for(kind)
    shown = [f for f in (*required, *optional) if f not in ("currency", "fx_rate")]
    values: dict[str, str] = {}
    cells = st.columns(4)
    position = 0
    for field in shown:
        suffix = "" if field in required else " (optional)"
        values[field] = cells[position % 4].text_input(
            _FIELD_LABELS[field] + suffix,
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
            suggested = instrument.currency
        currency = cells[position % 4].selectbox(
            "Currency",
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
                f"{base} per 1 {currency}" + ("" if rate_required else " (optional)"),
                value=decimal_text(editing.fx_rate) if editing else "",
                help=None if rate_required else "Empty: the market rate of that day is used.",
                key=f"{key}_{kind}_{currency}_rate",
            )
            position += 1

    bottom = st.columns([1, 3])
    fee_text = bottom[0].text_input(
        f"Fee ({base})",
        value=decimal_text(editing.fee) if editing else "0",
        key=f"{key}_fee",
    )
    note = bottom[1].text_input(
        "Note", value=(editing.note or "") if editing else "", key=f"{key}_note"
    )

    save, delete, _ = st.columns([1, 1, 4])
    if save.button("Save changes" if editing else "Add", type="primary", key=f"{key}_save"):
        try:
            numbers = {f: parse_decimal(text, _FIELD_LABELS.get(f, "rate")) for f, text in
                       values.items()}  # fmt: skip
            transaction = Transaction(
                id=editing.id if editing else None,
                date=day,
                instrument_id=instrument.id,
                kind=kind,
                currency=currency,
                fee=parse_decimal(fee_text, "fee") or parse_decimal("0"),
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
                f"{_KIND_LABELS[kind]} of {instrument.ticker} on {day} "
                + ("changed." if editing else "added.")
            )

    if editing:
        confirmed = delete.checkbox("Really delete", key=f"{key}_confirm")
        if delete.button("Delete", disabled=not confirmed, key=f"{key}_delete"):
            with conn:
                repo.delete_transaction(conn, editing.id)
            _changed("Transaction deleted.")


# --- manual valuations ----------------------------------------------------------------------


def _valuations(conn: sqlite3.Connection, instruments: list[Instrument]) -> None:
    manual = [i for i in instruments if i.valuation is ValuationMethod.MANUAL]
    if not manual:
        st.info("No instrument is valued by hand. Set that in Settings.")
        return
    active = [i for i in manual if i.active] or manual
    st.caption(
        "The total value of an instrument on a day, in its own currency. Deposits and "
        "withdrawals made on that day or later are added on top automatically."
    )
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
    instrument = c1.selectbox(
        "Instrument",
        active,
        format_func=lambda i: f"{i.ticker} ({i.currency})",
        key="val_instrument",
    )
    day = c2.date_input("Date", value=date.today(), key="val_date")
    value_text = c3.text_input("Value", key="val_value")
    if c4.button("Save", type="primary", key="val_save"):
        try:
            value = parse_decimal(value_text, "value")
            if value is None:
                raise ValueError("Enter a value.")
            with conn:
                repo.set_valuation(conn, Valuation(instrument.id, day, value))
        except (ValueError, sqlite3.Error) as e:
            st.error(str(e))
        else:
            _changed(f"Value of {instrument.ticker} on {day} saved.")

    rows = repo.list_valuations(conn, instrument.id)
    rows.reverse()
    event = st.dataframe(
        [{"Date": v.date, "Value": float(v.value)} for v in rows],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"val_table_{instrument.id}_{st.session_state.get('tx_version', 0)}",
        column_config={"Value": st.column_config.NumberColumn(format="localized")},
        width="content",
    )
    chosen = event.selection.rows if event else []
    if chosen and chosen[0] < len(rows):
        target = rows[chosen[0]]
        if st.button(f"Delete the value from {target.date}", key="val_delete"):
            with conn:
                repo.delete_valuation(conn, instrument.id, target.date)
            _changed("Valuation deleted.")
