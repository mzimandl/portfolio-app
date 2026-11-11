"""Instruments, currencies and instrument types."""

import sqlite3
from dataclasses import replace

import streamlit as st

from portfolio.core import repo
from portfolio.core.models import Instrument, ValuationMethod
from portfolio.ui import common

_NEW = "New instrument"
_VALUATION_LABELS = {
    ValuationMethod.YAHOO: "Quantity × price from Yahoo",
    ValuationMethod.MANUAL: "Value entered by hand",
}


def render() -> None:
    st.title("Settings")
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)
    cfg = common.config()
    st.caption(
        f"Database: `{cfg.db_path}` · Base currency: **{cfg.base_currency}** · "
        f"Benchmark: **{cfg.benchmark or 'not set'}** (set in the config file)"
    )
    with common.connection() as conn:
        instruments_column, lists_column = st.columns([3, 1])
        with instruments_column:
            _instruments(conn)
        with lists_column:
            _simple_list(conn, "Currencies", "Code, e.g. USD", repo.list_currencies,
                         repo.add_currency, repo.delete_currency, upper=True)  # fmt: skip
            _simple_list(conn, "Instrument types", "Name, e.g. etf", repo.list_instrument_types,
                         repo.add_instrument_type, repo.delete_instrument_type)  # fmt: skip


def _done(message: str) -> None:
    st.session_state["flash"] = message
    st.rerun()


def _instruments(conn: sqlite3.Connection) -> None:
    st.subheader("Instruments")
    instruments = repo.list_instruments(conn)
    st.dataframe(
        [
            {
                "Ticker": i.ticker,
                "Name": i.name,
                "Type": i.type,
                "Currency": i.currency,
                "Dividends in": i.dividend_currency,
                "Valued by": "Yahoo" if i.valuation is ValuationMethod.YAHOO else "hand",
                "Yahoo symbol": i.yahoo_symbol,
                "Active": i.active,
            }
            for i in instruments
        ],
        hide_index=True,
        height=350,
    )

    currencies = repo.list_currencies(conn)
    types = repo.list_instrument_types(conn)
    if not currencies or not types:
        st.info("Add at least one currency and one instrument type first.")
        return
    by_ticker = {i.ticker: i for i in instruments}
    choice = st.selectbox("Add or edit", [_NEW, *by_ticker], key="settings_instrument")
    editing = by_ticker.get(choice)
    key = f"settings_{editing.id if editing else 'new'}"

    def pick(label, options, current, column, name, **kw):
        index = options.index(current) if current in options else 0
        return column.selectbox(label, options, index=index, key=f"{key}_{name}", **kw)

    a, b, c, d = st.columns(4)
    ticker = a.text_input("Ticker", value=editing.ticker if editing else "", key=f"{key}_ticker")
    name = b.text_input("Name", value=(editing.name or "") if editing else "", key=f"{key}_name")
    type_name = pick("Type", types, editing.type if editing else None, c, "type")
    currency = pick("Currency", currencies, editing.currency if editing else None, d, "currency")
    e, f, g, h = st.columns(4, vertical_alignment="bottom")
    no_dividends = "Same as instrument"
    dividend_currency = pick(
        "Dividends paid in", [no_dividends, *currencies],
        editing.dividend_currency if editing else None, e, "dividend_currency",
    )  # fmt: skip
    valuation = pick(
        "Valued by", list(ValuationMethod), editing.valuation if editing else None, f,
        "valuation", format_func=_VALUATION_LABELS.get,
    )  # fmt: skip
    yahoo_symbol = g.text_input(
        "Yahoo symbol",
        value=(editing.yahoo_symbol or "") if editing else "",
        help="Only if it differs from the ticker, e.g. BTC-EUR.",
        disabled=valuation is not ValuationMethod.YAHOO,
        key=f"{key}_yahoo",
    )
    active = h.checkbox("Active", value=editing.active if editing else True, key=f"{key}_active")

    save, delete, _ = st.columns([1, 1, 4])
    if save.button("Save changes" if editing else "Add instrument", type="primary",
                   key=f"{key}_save"):  # fmt: skip
        instrument = Instrument(
            ticker=ticker.strip(),
            name=name.strip() or None,
            type=type_name,
            currency=currency,
            dividend_currency=None if dividend_currency == no_dividends else dividend_currency,
            valuation=valuation,
            yahoo_symbol=(yahoo_symbol.strip() or None)
            if valuation is ValuationMethod.YAHOO
            else None,
            active=active,
        )
        try:
            with conn:
                if editing:
                    repo.update_instrument(conn, replace(instrument, id=editing.id))
                else:
                    repo.add_instrument(conn, instrument)
        except sqlite3.IntegrityError as error:
            st.error(_explain(error, ticker))
        else:
            _done(f"{instrument.ticker} saved.")
    if editing:
        confirmed = delete.checkbox("Really delete", key=f"{key}_confirm")
        if delete.button("Delete", disabled=not confirmed, key=f"{key}_delete"):
            try:
                with conn:
                    repo.delete_instrument(conn, editing.id)
            except sqlite3.IntegrityError:
                st.error(
                    f"{editing.ticker} still has transactions. Delete them first, or just make "
                    "the instrument inactive."
                )
            else:
                _done(f"{editing.ticker} deleted, with its stored prices and valuations.")


def _explain(error: sqlite3.IntegrityError, ticker: str) -> str:
    text = str(error)
    if "UNIQUE" in text:
        return f"An instrument with ticker '{ticker}' already exists."
    if "length(ticker)" in text or "CHECK" in text:
        return "The ticker must not be empty."
    return f"Could not save: {text}"


def _simple_list(conn, title, placeholder, list_items, add_item, delete_item, *, upper=False):
    st.subheader(title)
    items = list_items(conn)
    slug = title.lower().replace(" ", "_")
    with st.form(f"{slug}_form", clear_on_submit=True, border=False):
        new, button = st.columns([3, 1], vertical_alignment="bottom")
        value = new.text_input(title, placeholder=placeholder, label_visibility="collapsed")
        if button.form_submit_button("Add"):
            value = value.strip().upper() if upper else value.strip()
            try:
                with conn:
                    add_item(conn, value)
            except sqlite3.IntegrityError:
                st.error(f"'{value}' is not valid or already exists.")
            else:
                _done(f"{value} added.")
    for item in items:
        name, remove = st.columns([3, 1])
        name.write(item)
        if remove.button("✕", key=f"{slug}_delete_{item}", help=f"Delete {item}"):
            try:
                with conn:
                    delete_item(conn, item)
            except sqlite3.IntegrityError:
                st.error(f"{item} is in use and cannot be deleted.")
            else:
                _done(f"{item} deleted.")
