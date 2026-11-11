"""Returns over time."""

from datetime import date

import pandas as pd
import streamlit as st

from portfolio.core.analytics import performance
from portfolio.ui import common

_PERCENT = "percent"
_LONG_ENOUGH_DAYS = 90  # a yearly rate from a shorter period is mostly noise


def _benchmark_id(loaded: common.Loaded) -> int | None:
    symbol = common.config().benchmark
    if not symbol:
        return None
    return next((i.id for i in loaded.data.instruments.values() if i.ticker == symbol), None)


def render() -> None:
    st.title("Performance")
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    left, right = st.columns(2)
    with left:
        label, ids = common.scope_picker(loaded, "performance_scope")
    period = right.selectbox("Period", common.PERIODS, key="performance_period")
    days = common.history(loaded, ids)
    if not days:
        st.info("Nothing to show for this selection.")
        return
    start = max(common.period_start(period, today) or days[0].date, days[0].date)
    benchmark_id = _benchmark_id(loaded)

    twr = performance.twr(days, start, today)
    yearly_rate = (
        performance.money_weighted(days, start, today)
        if (today - start).days >= _LONG_ENOUGH_DAYS
        else None
    )
    window = [p for p in days if p.date >= start]
    before = [p for p in days if p.date < start]
    profit = window[-1].net_profit - (before[-1].net_profit if before else 0.0)
    cells = st.columns(4)
    cells[0].metric("Return (time-weighted)", common.percent(twr))
    cells[1].metric("Yearly return on your money", common.percent(yearly_rate))
    cells[2].metric("Net profit in the period", common.money(profit, signed=True))
    if benchmark_id is not None:
        benchmark = performance.price_return(data, benchmark_id, start, today)
        cells[3].metric(f"Benchmark {common.config().benchmark}", common.percent(benchmark))
    st.caption(
        "The time-weighted return shows how the investments did, whenever money was added. "
        "The yearly return on your money (XIRR) takes the timing of your payments into "
        "account. Both include dividends and are after fees."
    )

    st.subheader("By year")
    year_rows = []
    for row in performance.yearly(days):
        year_start = max(date(row.year, 1, 1), days[0].date)
        year_end = min(date(row.year, 12, 31), today)
        year_rows.append(
            {
                "Year": str(row.year),
                "Start value": round(row.start_value),
                "Put in": round(row.put_in),
                "Taken out": round(row.taken_out),
                "End value": round(row.end_value),
                "Net profit": round(row.profit),
                "Return": row.twr,
                "Benchmark": performance.price_return(data, benchmark_id, year_start, year_end)
                if benchmark_id is not None
                else None,
            }
        )
    year_config = {
        name: st.column_config.NumberColumn(format="localized")
        for name in ("Start value", "Put in", "Taken out", "End value", "Net profit")
    } | {name: st.column_config.NumberColumn(format=_PERCENT) for name in ("Return", "Benchmark")}
    if benchmark_id is None:
        year_config["Benchmark"] = None
    st.dataframe(year_rows, column_config=year_config, hide_index=True)

    if len(ids) > 1:
        st.subheader(f"Instruments, {period.lower()}")
        instrument_rows = []
        for instrument_id in ids:
            history = loaded.daily.get(instrument_id) or []
            in_period = [p for p in history if p.date >= start]
            if not in_period:
                continue
            earlier = [p for p in history if p.date < start]
            first_day = in_period[0].date
            instrument = data.instruments[instrument_id]
            instrument_rows.append(
                {
                    "Ticker": instrument.ticker,
                    "Type": instrument.type,
                    "Value": round(in_period[-1].value),
                    "Net profit": round(
                        in_period[-1].net_profit - (earlier[-1].net_profit if earlier else 0.0)
                    ),
                    "Return": performance.twr(history, start, today),
                    "Yearly return": performance.money_weighted(history, start, today)
                    if (today - first_day).days >= _LONG_ENOUGH_DAYS
                    else None,
                }
            )
        st.dataframe(
            instrument_rows,
            column_config={
                "Value": st.column_config.NumberColumn(format="localized"),
                "Net profit": st.column_config.NumberColumn(format="localized"),
                "Return": st.column_config.NumberColumn(format=_PERCENT),
                "Yearly return": st.column_config.NumberColumn(format=_PERCENT),
            },
            hide_index=True,
        )

    st.subheader("New money")
    span = st.radio("Per", ["year", "month"], horizontal=True, key="performance_span")
    include_inactive = label == common.EVERYTHING
    periods = performance.invested_by_period(data, span, include_inactive=include_inactive)
    if periods:
        frame = pd.DataFrame(periods).set_index("period").drop(columns="total").fillna(0.0)
        st.bar_chart(frame, y_label=data.base_currency, x_label=None)
        st.caption(
            "Buys and deposits minus sells and withdrawals, by instrument type, for "
            + ("all instruments." if include_inactive else "active instruments.")
        )
