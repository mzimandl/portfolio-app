"""Current state of the portfolio."""

from dataclasses import asdict

import pandas as pd
import streamlit as st

from portfolio.core import repo
from portfolio.core.analytics.allocation import allocation
from portfolio.core.analytics.overview import OverviewRow, lots, overview, sales, summarize
from portfolio.core.i18n import tr
from portfolio.ui import common


def _money(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format="localized", help=help)


def _columns() -> dict:
    """Column headings of the overview tables, in the current language."""
    return {
        "ticker": tr("Ticker"),
        "name": tr("Name"),
        "type": tr("Type"),
        "currency": tr("Currency"),
        "sector": tr("Sector"),
        "country": tr("Country"),
        "quantity": st.column_config.NumberColumn(tr("Quantity"), format="%.6g"),
        "last_price": _money(tr("Last price")),
        "average_price": _money(tr("Average buy price"), tr("Of the bought units you still hold.")),
        "value": _money(tr("Value")),
        "share": st.column_config.NumberColumn(
            tr("Share"), format="percent", help=tr("Of the value of all investments.")
        ),
        "cost_basis": _money(
            tr("Cost"), tr("What the units you still hold cost. Oldest units are sold first.")
        ),
        "unrealised_profit": _money(
            tr("Unrealised"), tr("Value minus cost of what you still hold.")
        ),
        "price_profit": _money(tr("From price"), tr("Part of the unrealised profit.")),
        "fx_profit": _money(tr("From exchange rate"), tr("Part of the unrealised profit.")),
        "rewards": _money(
            tr("Staking rewards"), tr("Staking units you still hold, at today's price.")
        ),
        "realised_profit": _money(
            tr("Realised"), tr("On units sold: what you got minus what they cost.")
        ),
        "total_profit": _money(tr("Profit"), tr("Unrealised plus realised.")),
        "dividends": _money(tr("Dividends")),
        "fees": _money(tr("Fees")),
        "net_profit": _money(tr("Net profit"), tr("Profit plus dividends minus fees.")),
        "invested": _money(tr("Bought / deposited")),
        "returned": _money(tr("Sold / withdrawn")),
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
        cells[0].metric(tr("Value"), common.number(total["value"]))
        cells[1].metric(tr("Cost of holdings"), common.number(cost))
        cells[2].metric(
            tr("Unrealised profit"),
            common.number(total["unrealised_profit"], signed=True),
            delta=_share(total["unrealised_profit"], cost),
            help=tr("Value minus cost of what you still hold. The percentage is of that cost."),
        )
        cells[3].metric(tr("Realised profit"), common.number(total["realised_profit"], signed=True))
        cells[4].metric(tr("Dividends"), common.number(total["dividends"]))
        cells[5].metric(tr("Fees"), common.number(total["fees"]))
        cells[6].metric(tr("Net profit"), common.number(total["net_profit"], signed=True))
    else:
        cells = st.columns(4)
        cells[0].metric(tr("Value"), common.number(total["value"]))
        cells[1].metric(tr("Still deposited"), common.number(cost))
        cells[2].metric(
            tr("Profit"),
            common.number(total["total_profit"], signed=True),
            delta=_share(total["total_profit"], cost),
            help=tr("Value minus the money still deposited; the percentage is relative to it."),
        )
    if total["missing"]:
        st.warning(
            tr("No price or exchange rate for: {tickers}. They count as zero in the totals.",
               tickers=", ".join(total["missing"]))
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
            "date": sale.date,
            "ticker": sale.ticker,
            "type": sale.type,
            "quantity": sale.quantity,
            "received": round(sale.proceeds),
            "cost": round(sale.cost),
            "profit": round(sale.profit),
            "held": round(sale.held_days),
        }
        for sale in sales(loaded.data, loaded.today, include_inactive=include_inactive)
        if not common.is_separate(sale.type)
    ]
    if not rows:
        return
    st.subheader(tr("Sales"))
    st.caption(
        tr(
            "Every sale and what it realised: what you received minus what those units had "
            "cost, oldest units first. Units lost (sold at price 0) show their cost as a loss."
        )
    )
    st.dataframe(
        _tinted(rows, "profit"),
        column_config={
            "date": tr("Date"),
            "ticker": tr("Ticker"),
            "type": tr("Type"),
            "quantity": st.column_config.NumberColumn(tr("Quantity"), format="%.6g"),
            "received": _money(tr("Received")),
            "cost": _money(tr("Cost")),
            "profit": _money(tr("Profit")),
            "held": tr("Held (days)"),
        },
        hide_index=True,
    )


def _with_share(row: dict, whole: float) -> dict:
    value = row.get("value")
    return row | {"share": value / whole if value is not None and whole > 0 else None}


def _groups(rows: list[OverviewRow], field: str, whole: float, key=None) -> list[dict]:
    """Sums per type or currency (or what ``key`` gives), with each group's share of the
    whole value."""
    sums = summarize(rows, key=key or (lambda row: getattr(row, field)))
    return [
        _with_share(
            _rounded({field: name} | {k: v for k, v in group.items() if k != "missing"}), whole
        )
        for name, group in sorted(sums.items())
    ]


def _against_target(rows: list[OverviewRow], base: str) -> None:
    with common.connection() as conn:
        targets = {name: float(share) / 100 for name, share in repo.list_targets(conn).items()}
    if not targets:
        return
    st.subheader(tr("Against the target"))
    values: dict[str, float] = {}
    for row in rows:
        values[row.type] = values.get(row.type, 0.0) + (row.value or 0.0)
    new_money = st.number_input(
        tr("New money to invest ({currency})", currency=base),
        min_value=0, value=0, step=1000, key="overview_new_money",
    )  # fmt: skip
    table = [
        {
            "type": row.name,
            "value": round(row.value),
            "share": row.share,
            "target": row.target,
            "difference": None if row.share is None else row.share - row.target,
            "to_target": round(row.to_target),
            "buy": round(row.buy) if new_money else None,
        }
        for row in allocation(values, targets, new_money)
    ]
    st.dataframe(
        table,
        column_config={
            "type": tr("Type"),
            "value": _money(tr("Value")),
            "share": st.column_config.NumberColumn(tr("Share"), format="percent"),
            "target": st.column_config.NumberColumn(
                tr("Target"), format="percent", help=tr("Set in Settings.")
            ),
            "difference": st.column_config.NumberColumn(
                tr("Difference"),
                format="percent",
                help=tr("Share minus target, in percentage points."),
            ),
            "to_target": _money(
                tr("To be on target"),
                tr(
                    "What to buy to reach the target share at today's value; negative means "
                    "there is that much too many."
                ),
            ),
            "buy": _money(
                tr("Buy now"),
                tr(
                    "How to split the new money: it goes to the types that would still be "
                    "below their target, in proportion to how far below. Nothing is sold."
                ),
            ),
        },
        hide_index=True,
    )


def _spread(loaded: common.Loaded, rows: list[OverviewRow], whole: float) -> None:
    """By currency, sector and country."""
    profiles = {
        loaded.data.instruments[i].ticker: profile for i, profile in loaded.profiles.items()
    }

    def label(field: str):
        def of(row: OverviewRow) -> str:
            profile = profiles.get(row.ticker)
            return (getattr(profile, field) if profile else None) or f"({row.type})"

        return of

    st.subheader(tr("Spread"))
    by_currency, by_sector, by_country = st.tabs(
        [tr("By currency"), tr("By sector"), tr("By country")]
    )
    for tab, field, note in (
        (by_currency, "currency", tr("The currency each instrument is quoted in.")),
        (by_sector, "sector", None),
        (by_country, "country", tr("Where each company is based.")),
    ):
        with tab:
            if note:
                st.caption(note)
            st.dataframe(
                _tinted(_groups(rows, field, whole, None if field == "currency" else label(field))),
                column_config=_columns(),
                column_order=[field, *_TYPE_COLUMNS[1:]],
                hide_index=True,
            )
    st.caption(
        tr(
            "Sector and country come from Yahoo for shares. Funds and coins have none of "
            "their own and are listed by type in brackets; you can set theirs in Settings."
        )
    )


def _lots(loaded: common.Loaded, include_inactive: bool) -> None:
    held = [
        lot
        for lot in lots(loaded.data, loaded.today, include_inactive=include_inactive)
        if not common.is_separate(lot.type)
    ]
    if not held:
        return
    with st.expander(tr("Purchases still held")):
        st.caption(
            tr(
                "What you hold, purchase by purchase, oldest first. Sales used up the oldest "
                "units, so these are what remains. The age is what a holding-period rule for "
                "tax would look at."
            )
        )
        staking = st.toggle(tr("Show staking rewards"), key="overview_lots_staking")
        rows = [
            {
                "bought": lot.date,
                "ticker": lot.ticker,
                "type": lot.type,
                "age": lot.age_days / 365.25,
                "quantity": lot.quantity,
                "cost": round(lot.cost),
                "value": None if lot.value is None else round(lot.value),
                "profit": None if lot.profit is None else round(lot.profit),
            }
            for lot in held
            if staking or not lot.staking
        ]
        st.dataframe(
            _tinted(rows, "profit"),
            column_config={
                "bought": tr("Bought"),
                "ticker": tr("Ticker"),
                "type": tr("Type"),
                "age": st.column_config.NumberColumn(tr("Age (years)"), format="%.1f"),
                "quantity": st.column_config.NumberColumn(tr("Quantity"), format="%.6g"),
                "cost": _money(tr("Cost")),
                "value": _money(tr("Value")),
                "profit": _money(tr("Profit")),
            },
            hide_index=True,
        )


def _table(rows: list[OverviewRow], columns: list[str]) -> None:
    whole = sum(row.value or 0.0 for row in rows)
    st.dataframe(
        _tinted([_with_share(_rounded(asdict(row)), whole) for row in rows]),
        column_config=_columns(),
        column_order=columns,
        hide_index=True,
        height=min(38 * (len(rows) + 1) + 2, 900),
    )


def render() -> None:
    st.title(tr("Overview"))
    loaded = common.portfolio()
    base = loaded.data.base_currency
    include_inactive = st.toggle(tr("Include inactive instruments"), key="overview_inactive")
    rows = overview(loaded.data, loaded.today, include_inactive=include_inactive)
    if not rows:
        st.info(tr("No transactions yet. Add instruments in Settings, then transactions."))
        return
    investments = [row for row in rows if not common.is_separate(row.type)]
    separate = [row for row in rows if common.is_separate(row.type)]

    if investments:
        _headline(investments, investments=True)
        st.caption(
            tr(
                "All amounts in {currency}. Sales use up the oldest units first. "
                "Net profit = unrealised + realised + dividends − fees.",
                currency=base,
            )
            + (
                " " + tr("{what} is not included here.", what=common.separate_label())
                if separate
                else ""
            )
        )

        whole = sum(row.value or 0.0 for row in investments)
        st.subheader(tr("By type"))
        st.dataframe(
            _tinted(_groups(investments, "type", whole)),
            column_config=_columns(),
            column_order=_TYPE_COLUMNS,
            hide_index=True,
        )
        _against_target(investments, base)
        _spread(loaded, investments, whole)

        st.subheader(tr("Instruments"))
        _table(investments, list(_columns()))
        _sales(loaded, include_inactive)
        _lots(loaded, include_inactive)

    if separate:
        st.header(common.separate_label())
        _headline(separate, investments=False)
        if not investments:
            st.caption(tr("All amounts in {currency}.", currency=base))
        _table(separate, _SEPARATE_COLUMNS)
