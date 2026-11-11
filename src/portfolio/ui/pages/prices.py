"""Stored prices and exchange rates."""

import pandas as pd
import streamlit as st

from portfolio.core import repo
from portfolio.ui import common


def render() -> None:
    st.title("Prices")
    base = common.config().base_currency
    price_tab, rate_tab = st.tabs(["Instruments", "Exchange rates"])
    with common.connection() as conn:
        with price_tab:
            with_prices = set(repo.last_price_dates(conn))
            instruments = [i for i in repo.list_instruments(conn) if i.id in with_prices]
            if not instruments:
                st.info("No prices stored yet. Use Update prices in the sidebar.")
            else:
                instrument = st.selectbox(
                    "Instrument",
                    instruments,
                    format_func=lambda i: f"{i.ticker} ({i.currency})",
                    key="prices_instrument",
                )
                prices = repo.list_prices(conn, instrument.id)
                _chart_and_table(
                    [(p.date, p.close) for p in prices],
                    instrument.currency,
                    extra={
                        "Dividend": [p.dividend or None for p in prices],
                        "Split": [p.split or None for p in prices],
                    },
                )
        with rate_tab:
            pairs = sorted(repo.last_fx_dates(conn))
            if not pairs:
                st.info("No exchange rates stored yet.")
            else:
                pair = st.selectbox(
                    "Currency", pairs, format_func=lambda p: f"{p[0]} in {p[1]}", key="prices_pair"
                )
                rates = repo.list_fx_rates(conn, *pair)
                _chart_and_table([(r.date, r.close) for r in rates], base)


def _chart_and_table(points: list[tuple], unit: str, extra: dict | None = None) -> None:
    frame = pd.DataFrame({"Close": [value for _, value in points]},
                         index=pd.to_datetime([day for day, _ in points]))  # fmt: skip
    st.line_chart(frame, y_label=unit)
    table = {"Date": [day for day, _ in points], "Close": frame["Close"].tolist()} | (extra or {})
    newest_first = pd.DataFrame(table).iloc[::-1]
    st.caption(f"{len(points)} days, from {points[0][0]} to {points[-1][0]}.")
    st.dataframe(newest_first, hide_index=True, height=400, width="content")
