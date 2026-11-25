"""Stored prices and exchange rates."""

import pandas as pd
import streamlit as st

from portfolio.core import repo
from portfolio.core.analytics.timeseries import thin
from portfolio.core.i18n import tr
from portfolio.ui import common
from portfolio.ui.pages.charts import MAX_POINTS


def render() -> None:
    st.title(tr("Prices"))
    base = common.config().base_currency
    price_tab, rate_tab = st.tabs([tr("Instruments"), tr("Exchange rates")])
    with common.connection() as conn:
        with price_tab:
            with_prices = set(repo.last_price_dates(conn))
            instruments = [i for i in repo.list_instruments(conn) if i.id in with_prices]
            if not instruments:
                st.info(tr("No prices stored yet. Use Update prices in the sidebar."))
            else:
                instrument = st.selectbox(
                    tr("Instrument"),
                    instruments,
                    format_func=lambda i: f"{i.ticker} ({i.currency})",
                    key="prices_instrument",
                )
                prices = repo.list_prices(conn, instrument.id)
                _chart_and_table(
                    [(p.date, p.close) for p in prices],
                    instrument.currency,
                    extra={
                        tr("Dividend"): [p.dividend or None for p in prices],
                        tr("Split"): [p.split or None for p in prices],
                    },
                )
        with rate_tab:
            pairs = sorted(repo.last_fx_dates(conn))
            if not pairs:
                st.info(tr("No exchange rates stored yet."))
            else:
                pair = st.selectbox(
                    tr("Currency"),
                    pairs,
                    format_func=lambda p: tr("{currency} in {base}", currency=p[0], base=p[1]),
                    key="prices_pair",
                )
                rates = repo.list_fx_rates(conn, *pair)
                _chart_and_table([(r.date, r.close) for r in rates], base)


def _chart_and_table(points: list[tuple], unit: str, extra: dict | None = None) -> None:
    drawn, spacing = thin(points, MAX_POINTS)
    close = tr("Close")
    frame = pd.DataFrame({close: [value for _, value in drawn]},
                         index=pd.to_datetime([day for day, _ in drawn]))  # fmt: skip
    st.line_chart(frame, y_label=unit)
    if spacing > 1:
        st.caption(
            tr("The chart draws one point for every {days} stored days; the table has all of "
               "them.", days=spacing)
        )  # fmt: skip
    table = {tr("Date"): [day for day, _ in points], close: [v for _, v in points]} | (extra or {})
    newest_first = pd.DataFrame(table).iloc[::-1]
    st.caption(
        tr("Days: {count}, from {first} to {last}.", count=len(points), first=points[0][0],
           last=points[-1][0])
    )  # fmt: skip
    st.dataframe(newest_first, hide_index=True, height=400, width="content")
