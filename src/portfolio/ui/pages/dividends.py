"""Dividends received, their yield, and what the price data says was due."""

import pandas as pd
import streamlit as st

from portfolio.core.analytics import dividends
from portfolio.core.analytics.overview import overview
from portfolio.ui import common

_PERCENT = "percent"


def _money(help: str | None = None):
    return st.column_config.NumberColumn(format="localized", help=help)


def render() -> None:
    st.title("Dividends")
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    ids = [i for i in data.instrument_ids() if not common.is_separate(data.instruments[i].type)]
    rows = dividends.by_instrument(data, ids, today)
    if not rows:
        st.info("No dividends recorded yet. Add them in Transactions.")
        return
    held = {row.ticker: row for row in overview(data, today)}
    received = sum(row.received for row in rows)
    last_year = sum(row.last_year for row in rows)
    cost = sum(held[row.ticker].cost_basis for row in rows if row.last_year)

    cells = st.columns(4)
    cells[0].metric("Received in total", common.number(received))
    cells[1].metric("In the last 12 months", common.number(last_year))
    cells[2].metric(
        "Yield on cost",
        common.percent(last_year / cost if cost > 0 else None),
        help="The last 12 months of dividends, relative to what the holdings that paid them cost.",
    )
    cells[3].metric("Tax withheld", common.number(sum(row.tax for row in rows)))
    st.caption(
        f"Net amounts as recorded, in {data.base_currency} at the exchange rate of each "
        "payment. Tax is counted only where you entered it."
    )

    years = dividends.by_year(data, ids, today)
    paid = [row for row in years if row.received]
    if paid:
        st.subheader("By year")
        frame = pd.DataFrame(
            [{"year": str(r.year), "ticker": r.ticker, "received": r.received} for r in paid]
        ).pivot_table(index="year", columns="ticker", values="received", aggfunc="sum")
        st.bar_chart(frame.fillna(0.0), y_label=data.base_currency, x_label=None)

    st.subheader("By instrument")
    table = []
    for row in rows:
        holding = held[row.ticker]
        has_cost = holding.cost_basis > 0
        table.append(
            {
                "Ticker": row.ticker,
                "Received": round(row.received),
                "Last 12 months": round(row.last_year),
                "Tax withheld": round(row.tax),
                "Payments": row.payments,
                "Cost of holding": round(holding.cost_basis),
                "Yield on cost": row.last_year / holding.cost_basis if has_cost else None,
                "Yield on value": row.last_year / holding.value if holding.value else None,
                "Possibly missing": row.missing or None,
            }
        )
    st.dataframe(
        table,
        column_config={
            "Received": _money(),
            "Last 12 months": _money(),
            "Tax withheld": _money(),
            "Cost of holding": _money("What the units you hold now cost."),
            "Yield on cost": st.column_config.NumberColumn(
                format=_PERCENT, help="The last 12 months, relative to the cost."
            ),
            "Yield on value": st.column_config.NumberColumn(
                format=_PERCENT, help="The last 12 months, relative to today's value."
            ),
            "Possibly missing": st.column_config.NumberColumn(
                help="Payments the price data reports for units you held, beyond the ones "
                "recorded. Reports from the last two months are not counted."
            ),
        },
        hide_index=True,
    )

    st.subheader("Recorded and expected")
    st.caption(
        "Expected is what the price data reports for the units you held the day before, "
        "before tax. It is dated by the day of that report; the payment comes some weeks "
        "later, so around New Year the two can fall into different years. Not every "
        "instrument has such data."
    )
    st.dataframe(
        [
            {
                "Year": str(row.year),
                "Ticker": row.ticker,
                "Received (net)": round(row.received),
                "Tax withheld": round(row.tax),
                "Payments": row.payments,
                "Expected (gross)": None if row.expected is None else round(row.expected),
                "Expected payments": None if row.expected is None else row.expected_payments,
            }
            for row in years
        ],
        column_config={
            "Received (net)": _money(),
            "Tax withheld": _money(),
            "Expected (gross)": _money(),
        },
        hide_index=True,
    )
