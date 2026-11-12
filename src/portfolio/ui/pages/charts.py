"""Value, invested money and profit over time."""

import pandas as pd
import streamlit as st

from portfolio.core.analytics import performance
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
    history = common.history(loaded, ids)
    start = common.period_start(period, loaded.today)
    days = [p for p in history if p.date >= start] if start else history
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
    drops, _ = thin(performance.drops(history, start), MAX_POINTS)
    st.subheader("Drop from the high")
    st.area_chart(
        pd.DataFrame(
            {"Below the high (%)": [drop * 100 for _, drop in drops]},
            index=pd.to_datetime([day for day, _ in drops]),
        ),
        y_label="%",
    )
    st.caption(
        "How far the time-weighted return is below its highest point so far in the period. "
        "New money does not move it."
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
