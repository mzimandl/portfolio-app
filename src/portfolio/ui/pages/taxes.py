"""Figures for a tax return."""

import streamlit as st

from portfolio.core.analytics import taxes
from portfolio.ui import common


def _money(help: str | None = None):
    return st.column_config.NumberColumn(format="localized", help=help)


def _round(value: float | None) -> int | None:
    return None if value is None else round(value)


def rules() -> taxes.TaxRules:
    cfg = common.config()
    return taxes.TaxRules(cfg.tax_holding_years, cfg.tax_proceeds_limit, cfg.tax_crypto_types)


def render() -> None:
    st.title("Taxes")
    loaded = common.portfolio()
    data, today = loaded.data, loaded.today
    applied = rules()
    ids = [
        i
        for i in data.instrument_ids(include_inactive=True)
        if not common.is_separate(data.instruments[i].type)
    ]
    limit = common.number(applied.proceeds_limit)
    st.caption(
        f"Figures from your records in {data.base_currency}, at the exchange rates you "
        "entered. Two rules are applied, both set in the config file: a sale of units held "
        f"longer than {applied.holding_years} years is exempt, and so are all sales of a year "
        f"whose proceeds do not exceed {limit}, counted apart for securities and for "
        f"{', '.join(applied.crypto_types) or 'crypto'}. Units are sold oldest first. This is "
        "an overview to work from, not tax advice: check the rules that apply to the year "
        "and to you, and the exchange rates your tax office expects."
    )
    _held(data, ids, today, applied)

    available = taxes.years(data, ids)
    if not available:
        st.info("No sales, dividends or staking recorded yet.")
        return
    year = st.selectbox("Year", available, key="taxes_year")

    st.subheader(f"Sales in {year}")
    parts = taxes.sales(data, ids, year, applied)
    if not parts:
        st.caption("Nothing was sold.")
    else:
        st.dataframe(
            [
                {
                    "Group": group.group,
                    "Proceeds": round(group.proceeds),
                    "Within the limit": "yes" if group.under_limit else "no",
                    "Profit": round(group.profit),
                    "Held longer: proceeds": round(group.long_proceeds),
                    "Held longer: profit": round(group.long_profit),
                    "Held shorter: proceeds": round(group.short_proceeds),
                    "Held shorter: profit": round(group.short_profit),
                    "Profit not exempt": round(group.not_exempt),
                }
                for group in taxes.summary(parts, applied)
            ],
            column_config={
                "Proceeds": _money("Everything received for sales in the year."),
                "Within the limit": st.column_config.TextColumn(
                    help=f"Whether the proceeds do not exceed {limit}."
                ),
                "Profit": _money("Proceeds minus what the sold units had cost."),
                "Held longer: proceeds": _money(),
                "Held longer: profit": _money(),
                "Held shorter: proceeds": _money(),
                "Held shorter: profit": _money(),
                "Profit not exempt": _money(
                    "Zero within the limit; otherwise the profit on units held shorter. "
                    "Fees are not deducted here."
                ),
            },
            hide_index=True,
        )
        st.dataframe(
            [
                {
                    "Sold": part.date,
                    "Ticker": part.ticker,
                    "Group": part.group,
                    "Bought": part.acquired,
                    "Quantity": part.quantity,
                    "Proceeds": round(part.proceeds),
                    "Cost": round(part.cost),
                    "Profit": round(part.profit),
                    "Held longer": part.long_held,
                }
                for part in parts
            ],
            column_config={
                "Quantity": st.column_config.NumberColumn(format="%.6g"),
                "Proceeds": _money(),
                "Cost": _money(),
                "Profit": _money(),
            },
            hide_index=True,
        )
        st.caption("One line for every purchase a sale took units from.")

    st.subheader(f"Dividends in {year}")
    paid = taxes.dividends(data, ids, year)
    if not paid:
        st.caption("None recorded.")
    else:
        st.dataframe(
            [
                {
                    "Ticker": row.ticker,
                    "Paid in": row.currency,
                    "Payments": row.payments,
                    "Before tax": round(row.gross),
                    "Tax withheld": round(row.tax),
                    "Received": round(row.net),
                }
                for row in paid
            ]
            + [
                {
                    "Ticker": "Total",
                    "Before tax": round(sum(row.gross for row in paid)),
                    "Tax withheld": round(sum(row.tax for row in paid)),
                    "Received": round(sum(row.net for row in paid)),
                }
            ],
            column_config={
                "Before tax": _money("Received plus the tax you recorded as withheld."),
                "Tax withheld": _money("Only where you entered it with the dividend."),
                "Received": _money(),
            },
            hide_index=True,
        )

    rewards = taxes.staking(data, ids, year)
    if rewards:
        st.subheader(f"Staking in {year}")
        st.dataframe(
            [
                {"Ticker": r.ticker, "Received": r.quantity, "Value when received": _round(r.value)}
                for r in rewards
            ],
            column_config={
                "Received": st.column_config.NumberColumn(
                    format="%.6g", help="Units received, less the ones taken back."
                ),
                "Value when received": _money("Each reward at the closing price of its day."),
            },
            hide_index=True,
        )


def _held(data, ids: list[int], today, applied: taxes.TaxRules) -> None:
    active = [i for i in ids if data.instruments[i].active]
    rows = taxes.held(data, active, today, applied)
    if not rows:
        return
    st.subheader("What you hold today")
    st.dataframe(
        [
            {
                "Ticker": row.ticker,
                "Group": row.group,
                "Held longer: quantity": row.long_quantity or None,
                "Held longer: value": _round(row.long_value) if row.long_quantity else None,
                "Held longer: profit": _round(row.long_profit) if row.long_quantity else None,
                "Held shorter: quantity": row.short_quantity or None,
                "Held shorter: value": _round(row.short_value) if row.short_quantity else None,
                "Held shorter: profit": _round(row.short_profit) if row.short_quantity else None,
                "Next": row.next_exempt,
                "Next quantity": row.next_quantity or None,
            }
            for row in rows
        ],
        column_config={
            "Held longer: quantity": st.column_config.NumberColumn(
                format="%.6g",
                help=f"Units held longer than {applied.holding_years} years: a sale of them "
                "today would be exempt.",
            ),
            "Held longer: value": _money(),
            "Held longer: profit": _money(),
            "Held shorter: quantity": st.column_config.NumberColumn(format="%.6g"),
            "Held shorter: value": _money(),
            "Held shorter: profit": _money(),
            "Next": st.column_config.DateColumn(
                help="The first day the oldest of the units held shorter can be sold exempt."
            ),
            "Next quantity": st.column_config.NumberColumn(
                format="%.6g", help="How many units that is."
            ),
        },
        hide_index=True,
        height=min(38 * (len(rows) + 1) + 2, 420),
    )
    st.caption(
        "Sales take the oldest units first, so the units held longer are the ones a sale "
        "would use up first."
    )
