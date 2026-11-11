"""Current state of the portfolio."""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from portfolio.core.analytics.overview import OverviewRow, overview, summarize
from portfolio.ui import common

_MONEY = st.column_config.NumberColumn(format="localized")
_COLUMNS = {
    "ticker": "Ticker",
    "name": "Name",
    "type": "Type",
    "currency": "Currency",
    "quantity": st.column_config.NumberColumn("Quantity", format="%.6g"),
    "last_price": st.column_config.NumberColumn("Last price", format="localized"),
    "average_price": st.column_config.NumberColumn("Average buy price", format="localized"),
    "value": st.column_config.NumberColumn("Value", format="localized"),
    "invested": st.column_config.NumberColumn("Bought / deposited", format="localized"),
    "returned": st.column_config.NumberColumn("Sold / withdrawn", format="localized"),
    "reinvested": st.column_config.NumberColumn("Of that reinvested", format="localized"),
    "total_profit": st.column_config.NumberColumn("Profit", format="localized"),
    "price_profit": st.column_config.NumberColumn("From price", format="localized"),
    "fx_profit": st.column_config.NumberColumn("From exchange rate", format="localized"),
    "rewards": st.column_config.NumberColumn("Staking rewards", format="localized"),
    "dividends": st.column_config.NumberColumn("Dividends", format="localized"),
    "fees": st.column_config.NumberColumn("Fees", format="localized"),
    "net_profit": st.column_config.NumberColumn("Net profit", format="localized"),
}
_ROUNDED = (
    "value", "invested", "returned", "reinvested", "total_profit", "price_profit", "fx_profit",
    "rewards", "dividends", "fees", "net_profit",
)  # fmt: skip

_SEPARATE_COLUMNS = ["ticker", "name", "type", "currency", "value", "invested", "returned",
                     "reinvested", "total_profit", "fees", "net_profit"]  # fmt: skip


def _rounded(row: dict) -> dict:
    return {k: round(v) if k in _ROUNDED and v is not None else v for k, v in row.items()}


def _headline(rows: list[OverviewRow], *, with_dividends: bool) -> None:
    total = summarize(rows)["total"]
    still_in = total["invested"] - total["returned"]
    put_in = total["invested"]
    cells = [*st.columns(3), *st.columns(3)] if with_dividends else st.columns(3)
    cells[0].metric("Value", common.number(total["value"]))
    cells[1].metric("Still invested" if with_dividends else "Still deposited",
                    common.number(still_in))  # fmt: skip
    cells[2].metric(
        "Profit",
        common.number(total["total_profit"], signed=True),
        delta=common.percent(total["total_profit"] / put_in) if put_in else None,
        help="The percentage is the profit relative to everything ever put in.",
    )
    if with_dividends:
        cells[3].metric("Dividends", common.number(total["dividends"]))
        cells[4].metric("Fees", common.number(total["fees"]))
        cells[5].metric("Net profit", common.number(total["net_profit"], signed=True))
    if total["missing"]:
        st.warning(
            "No price or exchange rate for: " + ", ".join(total["missing"])
            + ". They count as zero in the totals."
        )  # fmt: skip


_GAIN = "background-color: rgba(46, 160, 67, 0.30)"
_LOSS = "background-color: rgba(218, 54, 51, 0.30)"


def _tint(profit: float | None) -> str:
    if profit is None or pd.isna(profit) or profit == 0:
        return ""
    return _GAIN if profit > 0 else _LOSS


def _tinted(rows: list[dict]):
    """The rows as a table whose lines are light green in profit and light red in loss."""
    return pd.DataFrame(rows).style.apply(
        lambda row: [_tint(row.get("total_profit"))] * len(row), axis=1
    )


def _table(rows: list[OverviewRow], columns: list[str]) -> None:
    st.dataframe(
        _tinted([_rounded(asdict(row)) for row in rows]),
        column_config=_COLUMNS,
        column_order=columns,
        hide_index=True,
        height=min(38 * (len(rows) + 1) + 2, 900),
    )


def render() -> None:
    st.title("Overview")
    loaded = common.portfolio()
    base = loaded.data.base_currency
    include_inactive = st.toggle("Include inactive instruments", key="overview_inactive")
    rows = overview(loaded.data, loaded.today, include_inactive=include_inactive)
    if not rows:
        st.info("No transactions yet. Add instruments in Settings, then transactions.")
        return
    investments = [row for row in rows if not common.is_separate(row.type)]
    separate = [row for row in rows if common.is_separate(row.type)]

    if investments:
        _headline(investments, with_dividends=True)
        st.caption(
            f"All amounts in {base}. Profit = value + sold − bought. "
            "Net profit adds dividends and subtracts fees."
            + (f" {common.separate_label()} is not included here." if separate else "")
        )

        st.subheader("By type")
        by_type = [
            _rounded({"type": name} | {k: v for k, v in sums.items() if k != "missing"})
            for name, sums in sorted(summarize(investments, key=lambda row: row.type).items())
        ]
        type_columns = ["type", "value", "invested", "returned", "total_profit", "price_profit",
                        "fx_profit", "rewards", "dividends", "fees", "net_profit"]  # fmt: skip
        st.dataframe(
            _tinted(by_type), column_config=_COLUMNS, column_order=type_columns, hide_index=True
        )

        st.subheader("Instruments")
        _table(investments, list(_COLUMNS))

    if separate:
        st.header(common.separate_label())
        _headline(separate, with_dividends=False)
        if not investments:
            st.caption(f"All amounts in {base}.")
        _table(separate, _SEPARATE_COLUMNS)
