"""Returns over time."""

from datetime import date

import pandas as pd
import streamlit as st

from portfolio.core.analytics import performance
from portfolio.core.analytics.inflation import inflation, real
from portfolio.core.analytics.inflation import yearly as yearly_inflation
from portfolio.core.i18n import N_, tr
from portfolio.ui import common

_PERCENT = "percent"
_LONG_ENOUGH_DAYS = 90  # a yearly rate from a shorter period is mostly noise


def _benchmark_id(loaded: common.Loaded) -> int | None:
    symbol = common.config().benchmark
    if not symbol:
        return None
    return next((i.id for i in loaded.data.instruments.values() if i.ticker == symbol), None)


_MONTHS = (N_("Jan"), N_("Feb"), N_("Mar"), N_("Apr"), N_("May"), N_("Jun"), N_("Jul"),
           N_("Aug"), N_("Sep"), N_("Oct"), N_("Nov"), N_("Dec"))  # fmt: skip
_SPANS = {"year": N_("year"), "month": N_("month")}
_GAIN = "background-color: rgba(46, 160, 67, 0.30)"
_LOSS = "background-color: rgba(218, 54, 51, 0.30)"


def _by_month(days) -> None:
    months = performance.monthly(days)
    if not months:
        return
    st.subheader(tr("By month"))
    names = [tr(name) for name in _MONTHS]
    frame = pd.DataFrame(
        [
            {tr("Year"): str(year)} | {name: months[year].get(i) for i, name in enumerate(names, 1)}
            for year in sorted(months, reverse=True)
        ]
    )
    styled = frame.style.map(
        lambda v: "" if pd.isna(v) or v == 0 else (_GAIN if v > 0 else _LOSS),
        subset=names,
    )
    st.dataframe(
        styled,
        column_config={name: st.column_config.NumberColumn(format=_PERCENT) for name in names},
        hide_index=True,
    )
    st.caption(tr("Time-weighted return of each calendar month, dividends included, after fees."))


def _drawdown(days, start: date, today: date) -> None:
    result = performance.drawdown(days, start, today)
    if result is None:
        return
    cells = st.columns(3)
    cells[0].metric(
        tr("Deepest drop"),
        common.percent(result.deepest),
        help=tr(
            "The largest fall of the time-weighted return from a high, in the period. "
            "New money does not hide it."
        ),
    )
    cells[1].metric(
        tr("Now below the high"),
        common.percent(result.current),
        help=tr("How far the return is today below its highest point in the period."),
    )
    if result.trough is not None:
        after = (
            tr("back at the high on {day}", day=result.recovered)
            if result.recovered
            else tr("not yet back at that high")
        )
        st.caption(
            tr(
                "The deepest drop ran from {peak} to {trough} ({days} days); {after}.",
                peak=result.peak, trough=result.trough,
                days=(result.trough - result.peak).days, after=after,
            )
        )  # fmt: skip


def _after_inflation(
    loaded: common.Loaded, twr: float | None, yearly_rate: float | None, start: date
) -> None:
    region = common.config().inflation_region
    if not region:
        return
    found = inflation(loaded.inflation, start, loaded.today)
    if found is None:
        if not loaded.inflation:
            st.caption(tr("No inflation figures for {region} yet. Use Update prices.",
                          region=region))  # fmt: skip
        return
    cells = st.columns(3)
    cells[0].metric(
        tr("Return after inflation"),
        common.percent(real(twr, found.change)),
        help=tr(
            "The time-weighted return in today's prices: what it bought more than at the start."
        ),
    )
    cells[1].metric(
        tr("Yearly return after inflation"),
        common.percent(
            real(yearly_rate, yearly_inflation(found.change, start, loaded.today))
            if yearly_rate is not None
            else None
        ),
        help=tr("The yearly return on your money minus the yearly inflation of the period."),
    )
    cells[2].metric(
        tr("Inflation ({region})", region=region),
        common.percent(found.change),
        help=tr("How much consumer prices rose in the period (Eurostat's harmonised index)."),
    )
    if not found.complete:
        st.caption(
            tr(
                "Inflation is published up to {month}; prices are taken as unchanged since then.",
                month=f"{found.known_until:%m/%Y}",
            )
        )


def _benchmark(data, benchmark_id: int, days, start: date, today: date) -> None:
    """The same money, paid in and taken out on the same days, held in the benchmark."""
    symbol = common.config().benchmark
    st.subheader(tr("Against {symbol}", symbol=symbol))
    twin = performance.same_money(data, benchmark_id, days, start, today)
    prices = data.prices.get(benchmark_id)
    if not twin or not prices:
        st.info(tr("No prices for {symbol} yet. Use Update prices.", symbol=symbol))
        return
    long_enough = (today - start).days >= _LONG_ENOUGH_DAYS
    ahead = days[-1].value - twin[-1].value
    cells = st.columns(3)
    cells[0].metric(
        tr("{symbol} return", symbol=symbol),
        common.percent(performance.holding_return(data, benchmark_id, start, today)),
        help=tr("Of holding it for the whole period, dividends reinvested."),
    )
    cells[1].metric(
        tr("Yearly return of your money in {symbol}", symbol=symbol),
        common.percent(performance.money_weighted(twin) if long_enough else None),
        help=tr("Comparable with the yearly return on your money above."),
    )
    cells[2].metric(
        tr("You are ahead by") if ahead >= 0 else tr("You are behind by"),
        common.money(abs(ahead)),
        help=tr(
            "Your value today minus what the same money would be worth in {symbol}: {value}.",
            symbol=symbol, value=common.money(twin[-1].value),
        ),
    )  # fmt: skip
    note = tr(
        "The same money on the same days, put into {symbol} instead: what you held at the "
        "start of the period, then every payment in and out, fees and dividends included. "
        "No fees or taxes are charged on the benchmark side.",
        symbol=symbol,
    )
    if prices.dates[0] > twin[0].date:
        note += " " + tr(
            "{symbol} has prices only from {day}; money paid before that waits as cash until "
            "then.",
            symbol=symbol, day=prices.dates[0],
        )  # fmt: skip
    st.caption(note)


def render() -> None:
    st.title(tr("Performance"))
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    left, right = st.columns(2)
    with left:
        scope, ids = common.scope_picker(loaded, "performance_scope")
    period = common.period_picker(right, "performance_period")
    days = common.history(loaded, ids)
    if not days:
        st.info(tr("Nothing to show for this selection."))
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
    cells[0].metric(tr("Return (time-weighted)"), common.percent(twr))
    cells[1].metric(tr("Yearly return on your money"), common.percent(yearly_rate))
    cells[2].metric(tr("Net profit in the period"), common.money(profit, signed=True))
    st.caption(
        tr(
            "The time-weighted return shows how the investments did, whenever money was "
            "added. The yearly return on your money (XIRR) takes the timing of your payments "
            "into account. Both include dividends and are after fees."
        )
    )
    _after_inflation(loaded, twr, yearly_rate, start)
    _drawdown(days, start, today)
    if benchmark_id is not None:
        _benchmark(data, benchmark_id, days, start, today)

    st.subheader(tr("By year"))
    year_rows = []
    for row in performance.yearly(days):
        year_start = max(date(row.year, 1, 1), days[0].date)
        year_end = min(date(row.year, 12, 31), today)
        prices_rose = inflation(loaded.inflation, year_start, year_end)
        year_rows.append(
            {
                "year": str(row.year),
                "start_value": round(row.start_value),
                "put_in": round(row.put_in),
                "taken_out": round(row.taken_out),
                "end_value": round(row.end_value),
                "net_profit": round(row.profit),
                "return": row.twr,
                "inflation": prices_rose.change if prices_rose else None,
                "after_inflation": real(row.twr, prices_rose.change if prices_rose else None),
                "benchmark": performance.holding_return(data, benchmark_id, year_start, year_end)
                if benchmark_id is not None
                else None,
            }
        )
    year_config = (
        {"year": tr("Year")}
        | {
            name: st.column_config.NumberColumn(label, format="localized")
            for name, label in (
                ("start_value", tr("Start value")), ("put_in", tr("Put in")),
                ("taken_out", tr("Taken out")), ("end_value", tr("End value")),
                ("net_profit", tr("Net profit")),
            )
        }
        | {
            name: st.column_config.NumberColumn(label, format=_PERCENT)
            for name, label in (
                ("return", tr("Return")), ("inflation", tr("Inflation")),
                ("after_inflation", tr("After inflation")), ("benchmark", tr("Benchmark")),
            )
        }
    )  # fmt: skip
    if benchmark_id is None:
        year_config["benchmark"] = None
    if not loaded.inflation:
        year_config["inflation"] = year_config["after_inflation"] = None
    st.dataframe(year_rows, column_config=year_config, hide_index=True)
    _by_month(days)

    if len(ids) > 1:
        st.subheader(tr("Instruments, {period}", period=common.period_label(period).lower()))
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
                    "ticker": instrument.ticker,
                    "type": instrument.type,
                    "value": round(in_period[-1].value),
                    "net_profit": round(
                        net := in_period[-1].net_profit
                        - (earlier[-1].net_profit if earlier else 0.0)
                    ),
                    "part": net / whole if whole else None,
                    "return": performance.twr(history, start, today),
                    "yearly": performance.money_weighted(history, start, today)
                    if (today - first_day).days >= _LONG_ENOUGH_DAYS
                    else None,
                }
            )
        st.dataframe(
            instrument_rows,
            column_config={
                "ticker": tr("Ticker"),
                "type": tr("Type"),
                "value": st.column_config.NumberColumn(tr("Value"), format="localized"),
                "net_profit": st.column_config.NumberColumn(tr("Net profit"), format="localized"),
                "part": st.column_config.NumberColumn(
                    tr("Part of the profit"),
                    format=_PERCENT,
                    help=tr(
                        "This instrument's net profit as a part of the net profit of the "
                        "whole selection in the period. Empty when the selection made a loss."
                    ),
                ),
                "return": st.column_config.NumberColumn(tr("Return"), format=_PERCENT),
                "yearly": st.column_config.NumberColumn(tr("Yearly return"), format=_PERCENT),
            },
            hide_index=True,
        )

    st.subheader(tr("New money"))
    span = st.radio(
        tr("Per"), ["year", "month"], format_func=lambda s: tr(_SPANS[s]), horizontal=True,
        key="performance_span",
    )  # fmt: skip
    include_inactive = scope == common.EVERYTHING
    periods = performance.invested_by_period(data, span, include_inactive=include_inactive)
    if periods:
        frame = pd.DataFrame(periods).set_index("period").drop(columns="total").fillna(0.0)
        st.bar_chart(frame, y_label=data.base_currency, x_label=None)
        st.caption(
            tr("Buys and deposits minus sells and withdrawals, by instrument type, for all "
               "instruments.")
            if include_inactive
            else tr("Buys and deposits minus sells and withdrawals, by instrument type, for "
                    "active instruments.")
        )  # fmt: skip
