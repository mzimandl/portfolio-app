"""Valuation ratios of the shares held: today and over the past years."""

from datetime import date

import pandas as pd
import streamlit as st

from portfolio.core import repo
from portfolio.core.analytics.fundamentals import (
    RatioPoint,
    daily_ratios,
    preferred,
    share_units,
    summarize_ratios,
)
from portfolio.core.analytics.positions import position_at
from portfolio.core.analytics.timeseries import thin
from portfolio.core.i18n import tr
from portfolio.core.models import Snapshot, Statement, ValuationMethod
from portfolio.ui import common
from portfolio.ui.pages.charts import MAX_POINTS

_RATIO = st.column_config.NumberColumn(format="%.1f")
_DIFFERS = 0.3  # worked-out P/E this far from Yahoo's is pointed out


def _held(loaded: common.Loaded) -> list[int]:
    data = loaded.data
    return [
        i
        for i in data.instrument_ids()
        if data.instruments[i].valuation is ValuationMethod.YAHOO
        and position_at(data, i, loaded.today).quantity > 1e-12
    ]


def _source(statements: list[Statement]) -> str | None:
    if not statements:
        return None
    return "SEC" if statements[0].source == "sec" else "Yahoo"


def _latest(snapshots: list[Snapshot]) -> Snapshot | None:
    filled = [s for s in snapshots if not s.empty]
    return filled[-1] if filled else None


def render() -> None:
    st.title(tr("Fundamentals"))
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    with common.connection() as conn:
        statements = repo.list_statements(conn)
        snapshots = repo.list_snapshots(conn)
    by_id_statements: dict[int, list[Statement]] = {}
    for s in statements:
        by_id_statements.setdefault(s.instrument_id, []).append(s)
    by_id_statements = {i: preferred(rows) for i, rows in by_id_statements.items()}
    by_id_snapshots: dict[int, list[Snapshot]] = {}
    for s in snapshots:
        by_id_snapshots.setdefault(s.instrument_id, []).append(s)

    companies = [
        i for i in _held(loaded) if by_id_statements.get(i) or _latest(by_id_snapshots.get(i, []))
    ]
    if not companies:
        st.info(
            tr(
                "No company data yet. Update prices downloads it for the shares you hold; "
                "funds and coins have none."
            )
        )
        return
    st.caption(
        tr(
            "Ratios worked out for every day from the reported results and the price of that "
            "day, and the ones Yahoo reports, saved on every day you update prices. Results "
            "count from the end of their period; earnings and revenue are those of the last "
            "twelve months. Yahoo keeps results of about the last five years; with SEC EDGAR "
            "set up in the config file, US companies reach back to about 2009."
        )
    )

    histories = {}
    units = {}
    for i in companies:
        rows_i, snaps_i = by_id_statements.get(i, []), by_id_snapshots.get(i, [])
        units[i] = share_units(data, i, rows_i, snaps_i)
        histories[i] = daily_ratios(data, i, rows_i, units=units[i])
    st.subheader(tr("Your shares"))
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
                "ticker": data.instruments[i].ticker,
                "pe": summary.pe,
                "pe_median": summary.pe_median,
                "pb": summary.pb,
                "ps": summary.ps,
                "dividend_yield": summary.dividend_yield,
                "forward_pe": latest.forward_pe if latest else None,
                "ev_ebitda": latest.ev_to_ebitda if latest else None,
                "yahoo_pe": latest.trailing_pe if latest else None,
                "since": summary.since,
                "source": _source(by_id_statements.get(i, [])),
            }
        )
    st.dataframe(
        rows,
        column_config={
            "ticker": tr("Ticker"),
            "pe": st.column_config.NumberColumn(
                "P/E",
                format="%.1f",
                help=tr("Price / earnings per share of the last twelve months."),
            ),
            "pe_median": st.column_config.NumberColumn(
                tr("Typical P/E"),
                format="%.1f",
                help=tr("The median P/E over the days it could be worked out."),
            ),
            "pb": st.column_config.NumberColumn(
                "P/B", format="%.1f", help=tr("Price / equity per share.")
            ),
            "ps": st.column_config.NumberColumn(
                "P/S",
                format="%.1f",
                help=tr("Price / revenue per share of the last twelve months."),
            ),
            "dividend_yield": st.column_config.NumberColumn(
                tr("Dividend yield"),
                format="percent",
                help=tr("Dividends of the last twelve months / price."),
            ),
            "forward_pe": st.column_config.NumberColumn(
                tr("Forward P/E"),
                format="%.1f",
                help=tr("By Yahoo: price / expected earnings of the next year."),
            ),
            "ev_ebitda": st.column_config.NumberColumn(
                "EV/EBITDA", format="%.1f", help=tr("By Yahoo.")
            ),
            "yahoo_pe": st.column_config.NumberColumn(
                tr("P/E by Yahoo"),
                format="%.1f",
                help=tr("For comparison; Yahoo may count earnings differently."),
            ),
            "since": st.column_config.DateColumn(
                tr("Since"), help=tr("First day with a P/E worked out.")
            ),
            "source": tr("Results from"),
        },
        hide_index=True,
    )
    st.caption(tr("Empty where a company made a loss, or where results are missing or too old."))
    if differing:
        st.warning(
            tr(
                "The P/E worked out differs from Yahoo's by more than 30 % for {tickers}. "
                "Usually a quarter missing in Yahoo's results, a one-off gain or loss, or "
                "results reported in other units: look at the reported results below before "
                "relying on it.",
                tickers=", ".join(differing),
            )
        )
    adjusted = [data.instruments[i].ticker for i in companies if units[i] != 1.0]
    if adjusted:
        st.caption(
            tr(
                "Traded units that are not one reported share each (depositary receipts, "
                "other share classes) are counted with the ratio Yahoo's market value "
                "implies: {ratios}.",
                ratios=", ".join(
                    tr("{ticker} {ratio} per share", ticker=data.instruments[i].ticker,
                       ratio=f"{units[i]:.4g}")
                    for i in companies if units[i] != 1.0
                ),
            )
        )  # fmt: skip

    left, right = st.columns(2)
    chosen = left.selectbox(
        tr("Instrument"),
        companies,
        format_func=lambda i: data.instruments[i].ticker,
        key="fundamentals_instrument",
    )
    period = common.period_picker(right, "fundamentals_period")
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
        st.subheader(tr("Price / earnings"))
        st.line_chart(pe)
    others = _frame(points, {"pb": "P/B", "ps": "P/S"})
    if others is not None:
        st.subheader(tr("Price / book and price / sales"))
        st.line_chart(others)
    dividends = _frame(points, {"dividend_yield": tr("Dividend yield")})
    if dividends is not None and (dividends.iloc[:, 0] > 0).any():
        st.subheader(tr("Dividend yield"))
        st.line_chart(dividends * 100, y_label="%")
    if pe is None and others is None:
        st.info(tr("No results to work ratios out from in this period."))


def _reported(snapshots: list[Snapshot], start: date | None) -> None:
    filled = [s for s in snapshots if not s.empty and (start is None or s.date >= start)]
    if not filled:
        return
    st.subheader(tr("As reported by Yahoo"))
    day, forward, cap = tr("Date"), tr("Forward P/E"), tr("Market cap")
    table = pd.DataFrame(
        {
            day: [s.date for s in filled],
            "P/E": [s.trailing_pe for s in filled],
            forward: [s.forward_pe for s in filled],
            "P/B": [s.price_to_book for s in filled],
            "P/S": [s.price_to_sales for s in filled],
            "EV/EBITDA": [s.ev_to_ebitda for s in filled],
            cap: [s.market_cap for s in filled],
        }
    )
    if len(filled) > 1:
        st.line_chart(table.set_index(pd.to_datetime(table[day]))[["P/E", forward]])
    st.dataframe(
        table.iloc[::-1],
        column_config={name: _RATIO for name in ("P/E", forward, "P/B", "P/S", "EV/EBITDA")}
        | {cap: st.column_config.NumberColumn(format="compact")},
        hide_index=True,
    )
    st.caption(tr("Saved on every day you update prices, so this grows from the first update on."))


def _results(statements: list[Statement], quoted_in: str) -> None:
    if not statements:
        return
    currency = statements[-1].currency
    st.subheader(tr("Reported results"))
    note = (
        tr(
            "In {currency}, as the company reports them in its SEC filings; per-share "
            "numbers converted to today's share units.",
            currency=currency,
        )
        if statements[-1].source == "sec"
        else tr("In {currency}, as the company reports them, from Yahoo.", currency=currency)
    )
    if currency != quoted_in:
        note += " " + tr(
            "The share is priced in {currency}; ratios convert at the day's rate.",
            currency=quoted_in,
        )
    st.caption(note)
    for period, label in (("annual", tr("By year")), ("quarterly", tr("By quarter"))):
        rows = [s for s in statements if s.period == period]
        if not rows:
            continue
        with st.expander(label, expanded=period == "annual"):
            st.dataframe(
                [
                    {
                        "period_end": s.period_end,
                        "revenue": s.revenue,
                        "net_income": s.net_income,
                        "margin": s.net_income / s.revenue
                        if s.net_income is not None and s.revenue
                        else None,
                        "eps": s.eps,
                        "equity": s.equity,
                        "shares": s.shares,
                    }
                    for s in reversed(rows)
                ],
                column_config={
                    "period_end": tr("Period end"),
                    "revenue": st.column_config.NumberColumn(tr("Revenue"), format="compact"),
                    "net_income": st.column_config.NumberColumn(tr("Net income"), format="compact"),
                    "margin": st.column_config.NumberColumn(tr("Margin"), format="percent"),
                    "eps": st.column_config.NumberColumn("EPS", format="%.2f"),
                    "equity": st.column_config.NumberColumn(tr("Equity"), format="compact"),
                    "shares": st.column_config.NumberColumn(tr("Shares"), format="compact"),
                },
                hide_index=True,
            )
