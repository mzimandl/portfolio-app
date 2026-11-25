"""Dividends received, their yield, and what the price data says was due."""

import pandas as pd
import streamlit as st

from portfolio.core.analytics import dividends
from portfolio.core.analytics.overview import overview
from portfolio.core.i18n import tr
from portfolio.ui import common

_PERCENT = "percent"


def _money(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format="localized", help=help)


def render() -> None:
    st.title(tr("Dividends"))
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    ids = [i for i in data.instrument_ids() if not common.is_separate(data.instruments[i].type)]
    rows = dividends.by_instrument(data, ids, today)
    if not rows:
        st.info(tr("No dividends recorded yet. Add them in Transactions."))
        return
    held = {row.ticker: row for row in overview(data, today)}
    received = sum(row.received for row in rows)
    last_year = sum(row.last_year for row in rows)
    cost = sum(held[row.ticker].cost_basis for row in rows if row.last_year)

    cells = st.columns(4)
    cells[0].metric(tr("Received in total"), common.number(received))
    cells[1].metric(tr("In the last 12 months"), common.number(last_year))
    cells[2].metric(
        tr("Yield on cost"),
        common.percent(last_year / cost if cost > 0 else None),
        help=tr(
            "The last 12 months of dividends, relative to what the holdings that paid them cost."
        ),
    )
    cells[3].metric(tr("Tax withheld"), common.number(sum(row.tax for row in rows)))
    st.caption(
        tr(
            "Net amounts as recorded, in {currency} at the exchange rate of each payment. "
            "Tax is counted only where you entered it.",
            currency=data.base_currency,
        )
    )

    years = dividends.by_year(data, ids, today)
    paid = [row for row in years if row.received]
    if paid:
        st.subheader(tr("By year"))
        frame = pd.DataFrame(
            [{"year": str(r.year), "ticker": r.ticker, "received": r.received} for r in paid]
        ).pivot_table(index="year", columns="ticker", values="received", aggfunc="sum")
        st.bar_chart(frame.fillna(0.0), y_label=data.base_currency, x_label=None)

    st.subheader(tr("By instrument"))
    table = []
    for row in rows:
        holding = held[row.ticker]
        has_cost = holding.cost_basis > 0
        table.append(
            {
                "ticker": row.ticker,
                "received": round(row.received),
                "last_year": round(row.last_year),
                "tax": round(row.tax),
                "payments": row.payments,
                "cost": round(holding.cost_basis),
                "yield_cost": row.last_year / holding.cost_basis if has_cost else None,
                "yield_value": row.last_year / holding.value if holding.value else None,
                "missing": row.missing or None,
            }
        )
    st.dataframe(
        table,
        column_config={
            "ticker": tr("Ticker"),
            "received": _money(tr("Received")),
            "last_year": _money(tr("Last 12 months")),
            "tax": _money(tr("Tax withheld")),
            "payments": tr("Payments"),
            "cost": _money(tr("Cost of holding"), tr("What the units you hold now cost.")),
            "yield_cost": st.column_config.NumberColumn(
                tr("Yield on cost"),
                format=_PERCENT,
                help=tr("The last 12 months, relative to the cost."),
            ),
            "yield_value": st.column_config.NumberColumn(
                tr("Yield on value"),
                format=_PERCENT,
                help=tr("The last 12 months, relative to today's value."),
            ),
            "missing": st.column_config.NumberColumn(
                tr("Possibly missing"),
                help=tr(
                    "Payments the price data reports for units you held, beyond the ones "
                    "recorded. Reports from the last two months are not counted."
                ),
            ),
        },
        hide_index=True,
    )

    st.subheader(tr("Recorded and expected"))
    st.caption(
        tr(
            "Expected is what the price data reports for the units you held the day before, "
            "before tax. It is dated by the day of that report; the payment comes some weeks "
            "later, so around New Year the two can fall into different years. Not every "
            "instrument has such data."
        )
    )
    st.dataframe(
        [
            {
                "year": str(row.year),
                "ticker": row.ticker,
                "received": round(row.received),
                "tax": round(row.tax),
                "payments": row.payments,
                "expected": None if row.expected is None else round(row.expected),
                "expected_payments": None if row.expected is None else row.expected_payments,
            }
            for row in years
        ],
        column_config={
            "year": tr("Year"),
            "ticker": tr("Ticker"),
            "received": _money(tr("Received (net)")),
            "tax": _money(tr("Tax withheld")),
            "payments": tr("Payments"),
            "expected": _money(tr("Expected (gross)")),
            "expected_payments": tr("Expected payments"),
        },
        hide_index=True,
    )
