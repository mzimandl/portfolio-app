"""Valuation ratios of the shares held: today and over the past years."""

from datetime import date

import pandas as pd
import streamlit as st

from portfolio.core import repo
from portfolio.core.analytics.fundamentals import (
    RatioPoint,
    daily_ratios,
    share_units,
    summarize_ratios,
)
from portfolio.core.analytics.positions import position_at
from portfolio.core.analytics.timeseries import thin
from portfolio.core.models import Snapshot, Statement, ValuationMethod
from portfolio.ui import common
from portfolio.ui.pages.charts import MAX_POINTS

_RATIO = st.column_config.NumberColumn(format="%.1f")
_PERCENT = st.column_config.NumberColumn(format="percent")
_DIFFERS = 0.3  # worked-out P/E this far from Yahoo's is pointed out


def _held(loaded: common.Loaded) -> list[int]:
    data = loaded.data
    return [
        i
        for i in data.instrument_ids()
        if data.instruments[i].valuation is ValuationMethod.YAHOO
        and position_at(data, i, loaded.today).quantity > 1e-12
    ]


def _latest(snapshots: list[Snapshot]) -> Snapshot | None:
    filled = [s for s in snapshots if not s.empty]
    return filled[-1] if filled else None


def render() -> None:
    st.title("Fundamentals")
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    with common.connection() as conn:
        statements = repo.list_statements(conn)
        snapshots = repo.list_snapshots(conn)
    by_id_statements: dict[int, list[Statement]] = {}
    for s in statements:
        by_id_statements.setdefault(s.instrument_id, []).append(s)
    by_id_snapshots: dict[int, list[Snapshot]] = {}
    for s in snapshots:
        by_id_snapshots.setdefault(s.instrument_id, []).append(s)

    companies = [
        i for i in _held(loaded) if by_id_statements.get(i) or _latest(by_id_snapshots.get(i, []))
    ]
    if not companies:
        st.info(
            "No company data yet. Update prices downloads it for the shares you hold; funds "
            "and coins have none."
        )
        return
    st.caption(
        "Ratios worked out for every day from the reported results and the price of that "
        "day, and the ones Yahoo reports, saved on every day you update prices. Results count "
        "from the end of their period; earnings and revenue are those of the last twelve "
        "months. Yahoo keeps results of about the last five years."
    )

    histories = {}
    units = {}
    for i in companies:
        rows_i, snaps_i = by_id_statements.get(i, []), by_id_snapshots.get(i, [])
        units[i] = share_units(data, i, rows_i, snaps_i)
        histories[i] = daily_ratios(data, i, rows_i, units=units[i])
    st.subheader("Your shares")
    rows = []
    differing = []
    for i in companies:
        summary = summarize_ratios(histories[i])
        latest = _latest(by_id_snapshots.get(i, []))
        yahoo_pe = latest.trailing_pe if latest else None
        if summary.pe and yahoo_pe and yahoo_pe > 0 and abs(summary.pe / yahoo_pe - 1) > _DIFFERS:
            differing.append(data.instruments[i].ticker)
        rows.append(
            {
                "Ticker": data.instruments[i].ticker,
                "P/E": summary.pe,
                "Typical P/E": summary.pe_median,
                "P/B": summary.pb,
                "P/S": summary.ps,
                "Dividend yield": summary.dividend_yield,
                "Forward P/E": latest.forward_pe if latest else None,
                "EV/EBITDA": latest.ev_to_ebitda if latest else None,
                "P/E by Yahoo": latest.trailing_pe if latest else None,
                "Since": summary.since,
            }
        )
    st.dataframe(
        rows,
        column_config={
            "P/E": st.column_config.NumberColumn(
                format="%.1f", help="Price / earnings per share of the last twelve months."
            ),
            "Typical P/E": st.column_config.NumberColumn(
                format="%.1f", help="The median P/E over the days it could be worked out."
            ),
            "P/B": st.column_config.NumberColumn(format="%.1f", help="Price / equity per share."),
            "P/S": st.column_config.NumberColumn(
                format="%.1f", help="Price / revenue per share of the last twelve months."
            ),
            "Dividend yield": st.column_config.NumberColumn(
                format="percent", help="Dividends of the last twelve months / price."
            ),
            "Forward P/E": st.column_config.NumberColumn(
                format="%.1f", help="By Yahoo: price / expected earnings of the next year."
            ),
            "EV/EBITDA": st.column_config.NumberColumn(format="%.1f", help="By Yahoo."),
            "P/E by Yahoo": st.column_config.NumberColumn(
                format="%.1f", help="For comparison; Yahoo may count earnings differently."
            ),
            "Since": st.column_config.DateColumn(help="First day with a P/E worked out."),
        },
        hide_index=True,
    )
    st.caption("Empty where a company made a loss, or where results are missing or too old.")
    if differing:
        st.warning(
            "The P/E worked out differs from Yahoo's by more than 30 % for "
            + ", ".join(differing)
            + ". Usually a quarter missing in Yahoo's results, a one-off gain or loss, or "
            "results reported in other units: look at the reported results below before "
            "relying on it."
        )
    adjusted = [data.instruments[i].ticker for i in companies if units[i] != 1.0]
    if adjusted:
        st.caption(
            "Traded units that are not one reported share each (depositary receipts, other "
            "share classes) are counted with the ratio Yahoo's market value implies: "
            + ", ".join(f"{data.instruments[i].ticker} {units[i]:.4g} per share"
                        for i in companies if units[i] != 1.0)
            + "."
        )  # fmt: skip

    left, right = st.columns(2)
    chosen = left.selectbox(
        "Instrument",
        companies,
        format_func=lambda i: data.instruments[i].ticker,
        key="fundamentals_instrument",
    )
    period = right.selectbox("Period", common.PERIODS, key="fundamentals_period")
    start = common.period_start(period, today)
    points = [p for p in histories[chosen] if start is None or p.date >= start]
    _charts(points)
    _reported(by_id_snapshots.get(chosen, []), start)
    _results(by_id_statements.get(chosen, []), data.instruments[chosen].currency)


def _frame(points: list[RatioPoint], columns: dict[str, str]) -> pd.DataFrame | None:
    drawn, _ = thin(points, MAX_POINTS)
    frame = pd.DataFrame(
        {label: [getattr(p, name) for p in drawn] for name, label in columns.items()},
        index=pd.to_datetime([p.date for p in drawn]),
    )
    frame = frame.dropna(how="all")
    return None if frame.empty else frame


def _charts(points: list[RatioPoint]) -> None:
    pe = _frame(points, {"pe": "P/E"})
    if pe is not None:
        st.subheader("Price / earnings")
        st.line_chart(pe)
    others = _frame(points, {"pb": "P/B", "ps": "P/S"})
    if others is not None:
        st.subheader("Price / book and price / sales")
        st.line_chart(others)
    dividends = _frame(points, {"dividend_yield": "Dividend yield"})
    if dividends is not None and (dividends["Dividend yield"] > 0).any():
        st.subheader("Dividend yield")
        st.line_chart(dividends * 100, y_label="%")
    if pe is None and others is None:
        st.info("No results to work ratios out from in this period.")


def _reported(snapshots: list[Snapshot], start: date | None) -> None:
    filled = [s for s in snapshots if not s.empty and (start is None or s.date >= start)]
    if not filled:
        return
    st.subheader("As reported by Yahoo")
    table = pd.DataFrame(
        {
            "Date": [s.date for s in filled],
            "P/E": [s.trailing_pe for s in filled],
            "Forward P/E": [s.forward_pe for s in filled],
            "P/B": [s.price_to_book for s in filled],
            "P/S": [s.price_to_sales for s in filled],
            "EV/EBITDA": [s.ev_to_ebitda for s in filled],
            "Market cap": [s.market_cap for s in filled],
        }
    )
    if len(filled) > 1:
        st.line_chart(table.set_index(pd.to_datetime(table["Date"]))[["P/E", "Forward P/E"]])
    st.dataframe(
        table.iloc[::-1],
        column_config={name: _RATIO for name in ("P/E", "Forward P/E", "P/B", "P/S", "EV/EBITDA")}
        | {"Market cap": st.column_config.NumberColumn(format="compact")},
        hide_index=True,
    )
    st.caption("Saved on every day you update prices, so this grows from the first update on.")


def _results(statements: list[Statement], quoted_in: str) -> None:
    if not statements:
        return
    currency = statements[-1].currency
    st.subheader("Reported results")
    note = f"In {currency}, as the company reports them."
    if currency != quoted_in:
        note += f" The share is priced in {quoted_in}; ratios convert at the day's rate."
    st.caption(note)
    for period, label in (("annual", "By year"), ("quarterly", "By quarter")):
        rows = [s for s in statements if s.period == period]
        if not rows:
            continue
        with st.expander(label, expanded=period == "annual"):
            st.dataframe(
                [
                    {
                        "Period end": s.period_end,
                        "Revenue": s.revenue,
                        "Net income": s.net_income,
                        "Margin": s.net_income / s.revenue
                        if s.net_income is not None and s.revenue
                        else None,
                        "EPS": s.eps,
                        "Equity": s.equity,
                        "Shares": s.shares,
                    }
                    for s in reversed(rows)
                ],
                column_config={
                    "Revenue": st.column_config.NumberColumn(format="compact"),
                    "Net income": st.column_config.NumberColumn(format="compact"),
                    "Margin": _PERCENT,
                    "EPS": st.column_config.NumberColumn(format="%.2f"),
                    "Equity": st.column_config.NumberColumn(format="compact"),
                    "Shares": st.column_config.NumberColumn(format="compact"),
                },
                hide_index=True,
            )
