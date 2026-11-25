"""Value, invested money and profit over time."""

import pandas as pd
import streamlit as st

from portfolio.core.analytics import performance
from portfolio.core.analytics.timeseries import thin
from portfolio.core.i18n import tr
from portfolio.ui import common

# A chart is at most about this many pixels wide; more points only make it slow.
MAX_POINTS = 400


def render() -> None:
    st.title(tr("Charts"))
    loaded = common.portfolio()
    left, right = st.columns(2)
    with left:
        _, ids = common.scope_picker(loaded, "charts_scope")
    period = common.period_picker(right, "charts_period")
    history = common.history(loaded, ids)
    start = common.period_start(period, loaded.today)
    days = [p for p in history if p.date >= start] if start else history
    if not days:
        st.info(tr("Nothing to show for this selection."))
        return

    base = loaded.data.base_currency
    days, spacing = thin(days, MAX_POINTS)
    index = pd.to_datetime([p.date for p in days])
    st.subheader(tr("Value and money invested"))
    st.line_chart(
        pd.DataFrame(
            {
                tr("Value"): [p.value for p in days],
                tr("Still invested"): [p.invested for p in days],
            },
            index=index,
        ),
        y_label=base,
    )
    st.subheader(tr("Profit"))
    st.line_chart(
        pd.DataFrame(
            {
                tr("Profit"): [p.profit for p in days],
                tr("Net profit (with dividends, after fees)"): [p.net_profit for p in days],
            },
            index=index,
        ),
        y_label=base,
    )
    drops, _ = thin(performance.drops(history, start), MAX_POINTS)
    st.subheader(tr("Drop from the high"))
    st.area_chart(
        pd.DataFrame(
            {tr("Below the high (%)"): [drop * 100 for _, drop in drops]},
            index=pd.to_datetime([day for day, _ in drops]),
        ),
        y_label="%",
    )
    st.caption(
        tr(
            "How far the time-weighted return is below its highest point so far in the "
            "period. New money does not move it."
        )
    )
    st.caption(
        tr(
            "Each day uses the prices and exchange rates of that day. "
            "Profit = value − money still invested."
        )
        + (
            " "
            + tr(
                "Drawn with one point every {days} days; pick a shorter period for more detail.",
                days=spacing,
            )
            if spacing > 1
            else ""
        )
    )
