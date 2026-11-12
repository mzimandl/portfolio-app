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


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_GAIN = "background-color: rgba(46, 160, 67, 0.30)"
_LOSS = "background-color: rgba(218, 54, 51, 0.30)"


def _by_month(days) -> None:
    months = performance.monthly(days)
    if not months:
        return
    st.subheader("By month")
    frame = pd.DataFrame(
        [
            {"Year": str(year)} | {name: months[year].get(i) for i, name in enumerate(_MONTHS, 1)}
            for year in sorted(months, reverse=True)
        ]
    )
    styled = frame.style.map(
        lambda v: "" if pd.isna(v) or v == 0 else (_GAIN if v > 0 else _LOSS),
        subset=list(_MONTHS),
    )
    st.dataframe(
        styled,
        column_config={name: st.column_config.NumberColumn(format=_PERCENT) for name in _MONTHS},
        hide_index=True,
    )
    st.caption("Time-weighted return of each calendar month, dividends included, after fees.")


def _drawdown(days, start: date, today: date) -> None:
    result = performance.drawdown(days, start, today)
    if result is None:
        return
    cells = st.columns(3)
    cells[0].metric(
        "Deepest drop",
        common.percent(result.deepest),
        help="The largest fall of the time-weighted return from a high, in the period. "
        "New money does not hide it.",
    )
    cells[1].metric(
        "Now below the high",
        common.percent(result.current),
        help="How far the return is today below its highest point in the period.",
    )
    if result.trough is not None:
        after = (
            f"back at the high on {result.recovered}"
            if result.recovered
            else "not yet back at that high"
        )
        st.caption(
            f"The deepest drop ran from {result.peak} to {result.trough} "
            f"({(result.trough - result.peak).days} days); {after}."
        )


def _benchmark(data, benchmark_id: int, days, start: date, today: date) -> None:
    """The same money, paid in and taken out on the same days, held in the benchmark."""
    symbol = common.config().benchmark
    st.subheader(f"Against {symbol}")
    twin = performance.same_money(data, benchmark_id, days, start, today)
    prices = data.prices.get(benchmark_id)
    if not twin or not prices:
        st.info(f"No prices for {symbol} yet. Use Update prices.")
        return
    long_enough = (today - start).days >= _LONG_ENOUGH_DAYS
    ahead = days[-1].value - twin[-1].value
    cells = st.columns(3)
    cells[0].metric(
        f"{symbol} return",
        common.percent(performance.holding_return(data, benchmark_id, start, today)),
        help="Of holding it for the whole period, dividends reinvested.",
    )
    cells[1].metric(
        f"Yearly return of your money in {symbol}",
        common.percent(performance.money_weighted(twin) if long_enough else None),
        help="Comparable with the yearly return on your money above.",
    )
    cells[2].metric(
        "You are ahead by" if ahead >= 0 else "You are behind by",
        common.money(abs(ahead)),
        help=f"Your value today minus what the same money would be worth in {symbol}: "
        f"{common.money(twin[-1].value)}.",
    )
    note = (
        f"The same money on the same days, put into {symbol} instead: what you held at the "
        "start of the period, then every payment in and out, fees and dividends included. "
        "No fees or taxes are charged on the benchmark side."
    )
    if prices.dates[0] > twin[0].date:
        note += (
            f" {symbol} has prices only from {prices.dates[0]}; money paid before that waits "
            "as cash until then."
        )
    st.caption(note)


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
    cells = st.columns(3)
    cells[0].metric("Return (time-weighted)", common.percent(twr))
    cells[1].metric("Yearly return on your money", common.percent(yearly_rate))
    cells[2].metric("Net profit in the period", common.money(profit, signed=True))
    st.caption(
        "The time-weighted return shows how the investments did, whenever money was added. "
        "The yearly return on your money (XIRR) takes the timing of your payments into "
        "account. Both include dividends and are after fees."
    )
    _drawdown(days, start, today)
    if benchmark_id is not None:
        _benchmark(data, benchmark_id, days, start, today)

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
                "Benchmark": performance.holding_return(data, benchmark_id, year_start, year_end)
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
    _by_month(days)

    if len(ids) > 1:
        st.subheader(f"Instruments, {period.lower()}")
        instrument_rows = []
        whole = profit if profit > 0 else None
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
                        net := in_period[-1].net_profit
                        - (earlier[-1].net_profit if earlier else 0.0)
                    ),
                    "Part of the profit": net / whole if whole else None,
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
                "Part of the profit": st.column_config.NumberColumn(
                    format=_PERCENT,
                    help="This instrument's net profit as a part of the net profit of the "
                    "whole selection in the period. Empty when the selection made a loss.",
                ),
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
