"""Current state of the portfolio."""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from portfolio.core.analytics.overview import OverviewRow, lots, overview, sales, summarize
from portfolio.ui import common


def _money(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format="localized", help=help)


_COLUMNS = {
    "ticker": "Ticker",
    "name": "Name",
    "type": "Type",
    "currency": "Currency",
    "quantity": st.column_config.NumberColumn("Quantity", format="%.6g"),
    "last_price": _money("Last price"),
    "average_price": _money("Average buy price", "Of the bought units you still hold."),
    "value": _money("Value"),
    "share": st.column_config.NumberColumn(
        "Share", format="percent", help="Of the value of all investments."
    ),
    "cost_basis": _money(
        "Cost", "What the units you still hold cost. Oldest units are sold first."
    ),
    "unrealised_profit": _money("Unrealised", "Value minus cost of what you still hold."),
    "price_profit": _money("From price", "Part of the unrealised profit."),
    "fx_profit": _money("From exchange rate", "Part of the unrealised profit."),
    "rewards": _money("Staking rewards", "Staking units you still hold, at today's price."),
    "realised_profit": _money("Realised", "On units sold: what you got minus what they cost."),
    "total_profit": _money("Profit", "Unrealised plus realised."),
    "dividends": _money("Dividends"),
    "fees": _money("Fees"),
    "net_profit": _money("Net profit", "Profit plus dividends minus fees."),
    "invested": _money("Bought / deposited"),
    "returned": _money("Sold / withdrawn"),
}
_ROUNDED = (
    "value", "cost_basis", "unrealised_profit", "price_profit", "fx_profit", "rewards",
    "realised_profit", "total_profit", "dividends", "fees", "net_profit", "invested", "returned",
)  # fmt: skip
_TYPE_COLUMNS = [
    "type", "value", "share", "cost_basis", "unrealised_profit", "price_profit", "fx_profit",
    "rewards", "realised_profit", "total_profit", "dividends", "fees", "net_profit",
]  # fmt: skip
_SEPARATE_COLUMNS = [
    "ticker", "name", "type", "currency", "value", "cost_basis", "total_profit", "invested",
    "returned", "fees", "net_profit",
]  # fmt: skip


def _rounded(row: dict) -> dict:
    return {k: round(v) if k in _ROUNDED and v is not None else v for k, v in row.items()}


def _share(part: float, whole: float) -> str | None:
    return common.percent(part / whole) if whole > 0 else None


def _headline(rows: list[OverviewRow], *, investments: bool) -> None:
    total = summarize(rows)["total"]
    cost = total["cost_basis"]
    if investments:
        cells = [*st.columns(4), *st.columns(4)]
        cells[0].metric("Value", common.number(total["value"]))
        cells[1].metric("Cost of holdings", common.number(cost))
        cells[2].metric(
            "Unrealised profit",
            common.number(total["unrealised_profit"], signed=True),
            delta=_share(total["unrealised_profit"], cost),
            help="Value minus cost of what you still hold. The percentage is of that cost.",
        )
        cells[3].metric("Realised profit", common.number(total["realised_profit"], signed=True))
        cells[4].metric("Dividends", common.number(total["dividends"]))
        cells[5].metric("Fees", common.number(total["fees"]))
        cells[6].metric("Net profit", common.number(total["net_profit"], signed=True))
    else:
        cells = st.columns(4)
        cells[0].metric("Value", common.number(total["value"]))
        cells[1].metric("Still deposited", common.number(cost))
        cells[2].metric(
            "Profit",
            common.number(total["total_profit"], signed=True),
            delta=_share(total["total_profit"], cost),
            help="Value minus the money still deposited; the percentage is relative to it.",
        )
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


def _tinted(rows: list[dict], by: str = "total_profit"):
    """The rows as a table whose lines are light green in profit and light red in loss."""
    return pd.DataFrame(rows).style.apply(lambda row: [_tint(row.get(by))] * len(row), axis=1)


def _sales(loaded: common.Loaded, include_inactive: bool) -> None:
    rows = [
        {
            "Date": sale.date,
            "Ticker": sale.ticker,
            "Type": sale.type,
            "Quantity": sale.quantity,
            "Received": round(sale.proceeds),
            "Cost": round(sale.cost),
            "Profit": round(sale.profit),
            "Held (days)": round(sale.held_days),
        }
        for sale in sales(loaded.data, loaded.today, include_inactive=include_inactive)
        if not common.is_separate(sale.type)
    ]
    if not rows:
        return
    st.subheader("Sales")
    st.caption(
        "Every sale and what it realised: what you received minus what those units had cost, "
        "oldest units first. Units lost (sold at price 0) show their cost as a loss."
    )
    st.dataframe(
        _tinted(rows, "Profit"),
        column_config={
            "Quantity": st.column_config.NumberColumn(format="%.6g"),
            "Received": _money("Received"),
            "Cost": _money("Cost"),
            "Profit": _money("Profit"),
        },
        hide_index=True,
    )


def _with_share(row: dict, whole: float) -> dict:
    value = row.get("value")
    return row | {"share": value / whole if value is not None and whole > 0 else None}


def _groups(rows: list[OverviewRow], field: str, whole: float) -> list[dict]:
    """Sums per type or currency, with each group's share of the whole value."""
    sums = summarize(rows, key=lambda row: getattr(row, field))
    return [
        _with_share(
            _rounded({field: name} | {k: v for k, v in group.items() if k != "missing"}), whole
        )
        for name, group in sorted(sums.items())
    ]


def _lots(loaded: common.Loaded, include_inactive: bool) -> None:
    held = [
        lot
        for lot in lots(loaded.data, loaded.today, include_inactive=include_inactive)
        if not common.is_separate(lot.type)
    ]
    if not held:
        return
    with st.expander("Purchases still held"):
        st.caption(
            "What you hold, purchase by purchase, oldest first. Sales used up the oldest "
            "units, so these are what remains. The age is what a holding-period rule for "
            "tax would look at."
        )
        staking = st.toggle("Show staking rewards", key="overview_lots_staking")
        rows = [
            {
                "Bought": lot.date,
                "Ticker": lot.ticker,
                "Type": lot.type,
                "Age (years)": lot.age_days / 365.25,
                "Quantity": lot.quantity,
                "Cost": round(lot.cost),
                "Value": None if lot.value is None else round(lot.value),
                "Profit": None if lot.profit is None else round(lot.profit),
            }
            for lot in held
            if staking or not lot.staking
        ]
        st.dataframe(
            _tinted(rows, "Profit"),
            column_config={
                "Age (years)": st.column_config.NumberColumn(format="%.1f"),
                "Quantity": st.column_config.NumberColumn(format="%.6g"),
                "Cost": _money("Cost"),
                "Value": _money("Value"),
                "Profit": _money("Profit"),
            },
            hide_index=True,
        )


def _table(rows: list[OverviewRow], columns: list[str]) -> None:
    whole = sum(row.value or 0.0 for row in rows)
    st.dataframe(
        _tinted([_with_share(_rounded(asdict(row)), whole) for row in rows]),
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
        _headline(investments, investments=True)
        st.caption(
            f"All amounts in {base}. Sales use up the oldest units first. "
            "Net profit = unrealised + realised + dividends − fees."
            + (f" {common.separate_label()} is not included here." if separate else "")
        )

        whole = sum(row.value or 0.0 for row in investments)
        st.subheader("By type")
        st.dataframe(
            _tinted(_groups(investments, "type", whole)),
            column_config=_COLUMNS,
            column_order=_TYPE_COLUMNS,
            hide_index=True,
        )
        st.subheader("By currency")
        st.caption("The currency each instrument is quoted in.")
        st.dataframe(
            _tinted(_groups(investments, "currency", whole)),
            column_config=_COLUMNS,
            column_order=["currency", *_TYPE_COLUMNS[1:]],
            hide_index=True,
        )

        st.subheader("Instruments")
        _table(investments, list(_COLUMNS))
        _sales(loaded, include_inactive)
        _lots(loaded, include_inactive)

    if separate:
        st.header(common.separate_label())
        _headline(separate, investments=False)
        if not investments:
            st.caption(f"All amounts in {base}.")
        _table(separate, _SEPARATE_COLUMNS)
