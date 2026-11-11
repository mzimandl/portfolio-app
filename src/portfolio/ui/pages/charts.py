"""Value, invested money and profit over time."""

import pandas as pd
import streamlit as st

from portfolio.core.analytics.timeseries import thin
from portfolio.ui import common

# A chart is at most about this many pixels wide; more points only make it slow.
MAX_POINTS = 400


def render() -> None:
    st.title("Charts")
    loaded = common.portfolio()
    left, right = st.columns(2)
    with left:
        _, ids = common.scope_picker(loaded, "charts_scope")
    period = right.selectbox("Period", common.PERIODS, key="charts_period")
    days = common.history(loaded, ids)
    start = common.period_start(period, loaded.today)
    if start:
        days = [p for p in days if p.date >= start]
    if not days:
        st.info("Nothing to show for this selection.")
        return

    base = loaded.data.base_currency
    days, spacing = thin(days, MAX_POINTS)
    index = pd.to_datetime([p.date for p in days])
    st.subheader("Value and money invested")
    st.line_chart(
        pd.DataFrame(
            {"Value": [p.value for p in days], "Still invested": [p.invested for p in days]},
            index=index,
        ),
        y_label=base,
    )
    st.subheader("Profit")
    st.line_chart(
        pd.DataFrame(
            {
                "Profit": [p.profit for p in days],
                "Net profit (with dividends, after fees)": [p.net_profit for p in days],
            },
            index=index,
        ),
        y_label=base,
    )
    st.caption(
        "Each day uses the prices and exchange rates of that day. "
        "Profit = value − money still invested."
        + (
            f" Drawn with one point every {spacing} days; pick a shorter period for more detail."
            if spacing > 1
            else ""
        )
    )
