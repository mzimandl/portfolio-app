"""Instruments, currencies and instrument types."""

import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal

import streamlit as st

from portfolio.core import repo
from portfolio.core.i18n import N_, tr
from portfolio.core.models import Instrument, Profile, ValuationMethod
from portfolio.core.updater import BENCHMARK_TYPE
from portfolio.ui import common

_NEW = ""  # the choice of a new instrument; no ticker is empty
_VALUATION_LABELS = {
    ValuationMethod.YAHOO: N_("Quantity × price from Yahoo"),
    ValuationMethod.MANUAL: N_("Value entered by hand"),
}


def render() -> None:
    st.title(tr("Settings"))
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)
    cfg = common.config()
    st.caption(
        tr(
            "Database: `{path}` · Base currency: **{currency}** · Benchmark: **{benchmark}** "
            "(set in the config file)",
            path=cfg.db_path, currency=cfg.base_currency,
            benchmark=cfg.benchmark or tr("not set"),
        )
    )  # fmt: skip
    with common.connection() as conn:
        instruments_column, lists_column = st.columns([3, 1])
        with instruments_column:
            _instruments(conn)
        with lists_column:
            _simple_list(conn, "currencies", tr("Currencies"), tr("Code, e.g. USD"),
                         repo.list_currencies, repo.add_currency, repo.delete_currency,
                         upper=True)  # fmt: skip
            _simple_list(conn, "instrument_types", tr("Instrument types"), tr("Name, e.g. etf"),
                         repo.list_instrument_types, repo.add_instrument_type,
                         repo.delete_instrument_type)  # fmt: skip
        _targets(conn)
        _profiles(conn)


def _profiles(conn: sqlite3.Connection) -> None:
    instruments = [
        i
        for i in repo.list_instruments(conn)
        if i.active
        and i.valuation is ValuationMethod.YAHOO
        and i.type != BENCHMARK_TYPE
        and not common.is_separate(i.type)
    ]
    if not instruments:
        return
    st.subheader(tr("Sector and country"))
    st.caption(
        tr(
            "Used for the spread on the Overview. Update prices fills them in from Yahoo for "
            "shares; funds and coins have none, so give them your own (e.g. World, Crypto). "
            "What you enter here is kept; clear both cells to let Yahoo fill them again."
        )
    )
    stored = repo.list_profiles(conn)
    rows = [
        {
            "ticker": i.ticker,
            "sector": stored[i.id].sector if i.id in stored else None,
            "country": stored[i.id].country if i.id in stored else None,
            "entered_by": (
                (tr("hand") if stored[i.id].manual else "Yahoo") if i.id in stored else None
            ),
        }
        for i in instruments
    ]
    edited = st.data_editor(
        rows,
        column_config={
            "ticker": st.column_config.TextColumn(tr("Ticker"), disabled=True),
            "sector": st.column_config.TextColumn(tr("Sector")),
            "country": st.column_config.TextColumn(tr("Country")),
            "entered_by": st.column_config.TextColumn(tr("Entered by"), disabled=True),
        },
        hide_index=True,
        key="settings_profiles",
        height=min(38 * (len(rows) + 1) + 2, 420),
    )
    if not st.button(tr("Save sector and country"), key="settings_profiles_save"):
        return
    changed = 0
    with conn:
        for instrument, before, after in zip(instruments, rows, edited, strict=True):
            sector = (after["sector"] or "").strip() or None
            country = (after["country"] or "").strip() or None
            if (sector, country) == (before["sector"], before["country"]):
                continue
            changed += 1
            if sector is None and country is None:
                repo.delete_profile(conn, instrument.id)
            else:
                repo.save_profile(
                    conn, Profile(instrument.id, sector, country, date.today(), manual=True)
                )
    _done(
        tr("Sector and country saved for instruments: {count}.", count=changed)
        if changed
        else tr("No changes.")
    )


def _targets(conn: sqlite3.Connection) -> None:
    types = [
        name
        for name in repo.list_instrument_types(conn)
        if name != BENCHMARK_TYPE and not common.is_separate(name)
    ]
    if not types:
        return
    st.subheader(tr("Target allocation"))
    st.caption(
        tr(
            "The share of your investments each type should have, in percent. The Overview "
            "then shows how far you are from it and where new money should go. Leave "
            "everything at 0 for no target."
        )
    )
    current = repo.list_targets(conn)
    cells = st.columns(max(len(types), 4))
    shares = {
        name: Decimal(
            cells[i].number_input(
                name,
                min_value=0,
                max_value=100,
                value=int(current.get(name, 0)),
                step=5,
                key=f"settings_target_{name}",
            )
        )
        for i, name in enumerate(types)
    }
    total = sum(shares.values())
    valid = total in (0, 100)
    save, note = st.columns([1, 5], vertical_alignment="center")
    note.caption(
        tr("Together {total} %.", total=total)
        + ("" if valid else " " + tr("They have to add up to 100."))
    )
    if save.button(tr("Save targets"), disabled=not valid, key="settings_targets_save"):
        with conn:
            repo.set_targets(conn, shares)
        _done(tr("Target allocation saved.") if total else tr("Target allocation removed."))


def _done(message: str) -> None:
    st.session_state["flash"] = message
    st.rerun()


def _instruments(conn: sqlite3.Connection) -> None:
    st.subheader(tr("Instruments"))
    instruments = repo.list_instruments(conn)
    st.dataframe(
        [
            {
                tr("Ticker"): i.ticker,
                tr("Name"): i.name,
                tr("Type"): i.type,
                tr("Currency"): i.currency,
                tr("Dividends in"): i.dividend_currency,
                tr("Valued by"): "Yahoo" if i.valuation is ValuationMethod.YAHOO else tr("hand"),
                tr("Yahoo symbol"): i.yahoo_symbol,
                tr("Active"): i.active,
            }
            for i in instruments
        ],
        hide_index=True,
        height=350,
    )

    currencies = repo.list_currencies(conn)
    types = repo.list_instrument_types(conn)
    if not currencies or not types:
        st.info(tr("Add at least one currency and one instrument type first."))
        return
    by_ticker = {i.ticker: i for i in instruments}
    choice = st.selectbox(
        tr("Add or edit"), [_NEW, *by_ticker],
        format_func=lambda c: tr("New instrument") if c == _NEW else c,
        key="settings_instrument",
    )  # fmt: skip
    editing = by_ticker.get(choice)
    key = f"settings_{editing.id if editing else 'new'}"

    def pick(label, options, current, column, name, **kw):
        index = options.index(current) if current in options else 0
        return column.selectbox(label, options, index=index, key=f"{key}_{name}", **kw)

    a, b, c, d = st.columns(4)
    ticker = a.text_input(
        tr("Ticker"), value=editing.ticker if editing else "", key=f"{key}_ticker"
    )
    name = b.text_input(
        tr("Name"), value=(editing.name or "") if editing else "", key=f"{key}_name"
    )
    type_name = pick(tr("Type"), types, editing.type if editing else None, c, "type")
    currency = pick(
        tr("Currency"), currencies, editing.currency if editing else None, d, "currency"
    )
    e, f, g, h = st.columns(4, vertical_alignment="bottom")
    no_dividends = ""  # no currency code is empty
    dividend_currency = pick(
        tr("Dividends paid in"), [no_dividends, *currencies],
        editing.dividend_currency if editing else None, e, "dividend_currency",
        format_func=lambda c: tr("Same as instrument") if c == no_dividends else c,
    )  # fmt: skip
    valuation = pick(
        tr("Valued by"), list(ValuationMethod), editing.valuation if editing else None, f,
        "valuation", format_func=lambda v: tr(_VALUATION_LABELS[v]),
    )  # fmt: skip
    yahoo_symbol = g.text_input(
        tr("Yahoo symbol"),
        value=(editing.yahoo_symbol or "") if editing else "",
        help=tr("Only if it differs from the ticker, e.g. BTC-EUR."),
        disabled=valuation is not ValuationMethod.YAHOO,
        key=f"{key}_yahoo",
    )
    active = h.checkbox(
        tr("Active"), value=editing.active if editing else True, key=f"{key}_active"
    )

    save, delete, _ = st.columns([1, 1, 4])
    if save.button(tr("Save changes") if editing else tr("Add instrument"), type="primary",
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
            _done(tr("{ticker} saved.", ticker=instrument.ticker))
    if editing:
        confirmed = delete.checkbox(tr("Really delete"), key=f"{key}_confirm")
        if delete.button(tr("Delete"), disabled=not confirmed, key=f"{key}_delete"):
            try:
                with conn:
                    repo.delete_instrument(conn, editing.id)
            except sqlite3.IntegrityError:
                st.error(
                    tr(
                        "{ticker} still has transactions. Delete them first, or just make the "
                        "instrument inactive.",
                        ticker=editing.ticker,
                    )
                )
            else:
                _done(
                    tr("{ticker} deleted, with its stored prices and valuations.",
                       ticker=editing.ticker)
                )  # fmt: skip


def _explain(error: sqlite3.IntegrityError, ticker: str) -> str:
    text = str(error)
    if "UNIQUE" in text:
        return tr("An instrument with ticker '{ticker}' already exists.", ticker=ticker)
    if "length(ticker)" in text or "CHECK" in text:
        return tr("The ticker must not be empty.")
    return tr("Could not save: {error}", error=text)


def _simple_list(conn, slug, title, placeholder, list_items, add_item, delete_item, *, upper=False):
    st.subheader(title)
    items = list_items(conn)
    with st.form(f"{slug}_form", clear_on_submit=True, border=False):
        new, button = st.columns([3, 1], vertical_alignment="bottom")
        value = new.text_input(title, placeholder=placeholder, label_visibility="collapsed")
        if button.form_submit_button(tr("Add")):
            value = value.strip().upper() if upper else value.strip()
            try:
                with conn:
                    add_item(conn, value)
            except sqlite3.IntegrityError:
                st.error(tr("'{value}' is not valid or already exists.", value=value))
            else:
                _done(tr("{value} added.", value=value))
    for item in items:
        name, remove = st.columns([3, 1])
        name.write(item)
        if remove.button("✕", key=f"{slug}_delete_{item}", help=tr("Delete {item}", item=item)):
            try:
                with conn:
                    delete_item(conn, item)
            except sqlite3.IntegrityError:
                st.error(tr("{item} is in use and cannot be deleted.", item=item))
            else:
                _done(tr("{item} deleted.", item=item))
