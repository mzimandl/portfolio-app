"""Figures for a tax return."""

import streamlit as st

from portfolio.core.analytics import taxes
from portfolio.core.i18n import N_, tr
from portfolio.ui import common


def _money(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format="localized", help=help)


def _round(value: float | None) -> int | None:
    return None if value is None else round(value)


def rules() -> taxes.TaxRules:
    cfg = common.config()
    return taxes.TaxRules(cfg.tax_holding_years, cfg.tax_proceeds_limit, cfg.tax_crypto_types)


_RATE_CHOICES = {
    "daily": N_("ČNB, rate of each day"),
    "unified": N_("ČNB, unified rate of the year"),
    "recorded": N_("As recorded"),
}


def _rates(loaded: common.Loaded, year: int) -> tuple[taxes.Rates | None, str]:
    """The exchange rates chosen for the year's figures, and how to describe them."""
    official = taxes.OfficialRates(loaded.official_rates, loaded.today)
    if loaded.data.base_currency != "CZK" or not official:
        return None, tr("at the exchange rates you entered")
    choice = st.radio(
        tr("Exchange rates"),
        list(_RATE_CHOICES),
        format_func=lambda c: tr(_RATE_CHOICES[c]),
        horizontal=True,
        key="taxes_rates",
        help=tr(
            "A Czech tax return converts with the rates of the Czech National Bank: either "
            "the rate of the day of each payment, or the unified rate of the year (the "
            "average of the rates on the last day of each month) for all of them. Use one way "
            "for the whole year."
        ),
    )
    if choice == "daily":
        return official.by_day(), tr("at the ČNB rate of the day of each payment")
    if choice == "unified":
        used = sorted({c for c in official.series if c in _currencies(loaded)} - {"CZK"})
        known = {c: official.unified(c, year) for c in used}
        shown = ", ".join(
            f"{c} {common.number(rate, 3)}" for c, rate in known.items() if rate is not None
        )
        st.caption(
            tr("Unified rates {year}: {rates}.", year=year, rates=shown)
            if shown
            else tr("The unified rates of {year} are known once the year is over.", year=year)
        )
        return (
            official.by_year(),
            tr(
                "at the ČNB unified rate of the year of each payment (purchases in earlier "
                "years at that year's)"
            ),
        )
    return None, tr("at the exchange rates you entered")


def _currencies(loaded: common.Loaded) -> set[str]:
    data = loaded.data
    found = {i.currency for i in data.instruments.values()}
    found |= {e.currency for events in data.events.values() for e in events if e.currency}
    return found


def render() -> None:
    st.title(tr("Taxes"))
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
        tr(
            "Figures from your records in {currency}. Two rules are applied, both set in the "
            "config file: a sale of units held longer than {years} years is exempt, and so "
            "are all sales of a year whose proceeds do not exceed {limit}, counted apart for "
            "securities and for {crypto}. Units are sold oldest first. This is an overview to "
            "work from, not tax advice: check the rules that apply to the year and to you.",
            currency=data.base_currency, years=applied.holding_years, limit=limit,
            crypto=", ".join(applied.crypto_types) or "crypto",
        )
    )  # fmt: skip
    _held(data, ids, today, applied)

    available = taxes.years(data, ids)
    if not available:
        st.info(tr("No sales, dividends or staking recorded yet."))
        return
    year = st.selectbox(tr("Year"), available, key="taxes_year")
    rates, described = _rates(loaded, year)
    st.caption(tr("Money below is converted {how}.", how=described))

    st.subheader(tr("Sales in {year}", year=year))
    parts = taxes.sales(data, ids, year, applied, rates)
    if not parts:
        st.caption(tr("Nothing was sold."))
    else:
        st.dataframe(
            [
                {
                    "group": tr(group.group),
                    "proceeds": round(group.proceeds),
                    "under_limit": tr("yes") if group.under_limit else tr("no"),
                    "profit": round(group.profit),
                    "long_proceeds": round(group.long_proceeds),
                    "long_profit": round(group.long_profit),
                    "short_proceeds": round(group.short_proceeds),
                    "short_profit": round(group.short_profit),
                    "not_exempt": round(group.not_exempt),
                }
                for group in taxes.summary(parts, applied)
            ],
            column_config={
                "group": tr("Group"),
                "proceeds": _money(
                    tr("Proceeds"), tr("Everything received for sales in the year.")
                ),
                "under_limit": st.column_config.TextColumn(
                    tr("Within the limit"),
                    help=tr("Whether the proceeds do not exceed {limit}.", limit=limit),
                ),
                "profit": _money(tr("Profit"), tr("Proceeds minus what the sold units had cost.")),
                "long_proceeds": _money(tr("Held longer: proceeds")),
                "long_profit": _money(tr("Held longer: profit")),
                "short_proceeds": _money(tr("Held shorter: proceeds")),
                "short_profit": _money(tr("Held shorter: profit")),
                "not_exempt": _money(
                    tr("Profit not exempt"),
                    tr(
                        "Zero within the limit; otherwise the profit on units held shorter. "
                        "Fees are not deducted here."
                    ),
                ),
            },
            hide_index=True,
        )
        st.dataframe(
            [
                {
                    "sold": part.date,
                    "ticker": part.ticker,
                    "group": tr(part.group),
                    "bought": part.acquired,
                    "quantity": part.quantity,
                    "proceeds": round(part.proceeds),
                    "cost": round(part.cost),
                    "profit": round(part.profit),
                    "long_held": part.long_held,
                }
                for part in parts
            ],
            column_config={
                "sold": tr("Sold"),
                "ticker": tr("Ticker"),
                "group": tr("Group"),
                "bought": tr("Bought"),
                "quantity": st.column_config.NumberColumn(tr("Quantity"), format="%.6g"),
                "proceeds": _money(tr("Proceeds")),
                "cost": _money(tr("Cost")),
                "profit": _money(tr("Profit")),
                "long_held": tr("Held longer"),
            },
            hide_index=True,
        )
        st.caption(tr("One line for every purchase a sale took units from."))
        _estimated(sum(part.estimated for part in parts))

    st.subheader(tr("Dividends in {year}", year=year))
    paid = taxes.dividends(data, ids, year, rates)
    if not paid:
        st.caption(tr("None recorded."))
    else:
        st.dataframe(
            [
                {
                    "ticker": row.ticker,
                    "currency": row.currency,
                    "payments": row.payments,
                    "gross": round(row.gross),
                    "tax": round(row.tax),
                    "net": round(row.net),
                }
                for row in paid
            ]
            + [
                {
                    "ticker": tr("Total"),
                    "gross": round(sum(row.gross for row in paid)),
                    "tax": round(sum(row.tax for row in paid)),
                    "net": round(sum(row.net for row in paid)),
                }
            ],
            column_config={
                "ticker": tr("Ticker"),
                "currency": tr("Paid in"),
                "payments": tr("Payments"),
                "gross": _money(
                    tr("Before tax"), tr("Received plus the tax you recorded as withheld.")
                ),
                "tax": _money(
                    tr("Tax withheld"), tr("Only where you entered it with the dividend.")
                ),
                "net": _money(tr("Received")),
            },
            hide_index=True,
        )
        _estimated(sum(row.estimated for row in paid))

    rewards = taxes.staking(data, ids, year, rates)
    if rewards:
        st.subheader(tr("Staking in {year}", year=year))
        st.dataframe(
            [
                {"ticker": r.ticker, "quantity": r.quantity, "value": _round(r.value)}
                for r in rewards
            ],
            column_config={
                "ticker": tr("Ticker"),
                "quantity": st.column_config.NumberColumn(
                    tr("Received"),
                    format="%.6g",
                    help=tr("Units received, less the ones taken back."),
                ),
                "value": _money(
                    tr("Value when received"), tr("Each reward at the closing price of its day.")
                ),
            },
            hide_index=True,
        )


def _estimated(count: int) -> None:
    if count:
        st.warning(
            tr(
                "Lines using the rate you entered: {count}. The chosen rates have none for "
                "that currency or year (a unified rate is known only once its year is over).",
                count=count,
            )
        )


def _held(data, ids: list[int], today, applied: taxes.TaxRules) -> None:
    active = [i for i in ids if data.instruments[i].active]
    rows = taxes.held(data, active, today, applied)
    if not rows:
        return
    st.subheader(tr("What you hold today"))
    st.dataframe(
        [
            {
                "ticker": row.ticker,
                "group": tr(row.group),
                "long_quantity": row.long_quantity or None,
                "long_value": _round(row.long_value) if row.long_quantity else None,
                "long_profit": _round(row.long_profit) if row.long_quantity else None,
                "short_quantity": row.short_quantity or None,
                "short_value": _round(row.short_value) if row.short_quantity else None,
                "short_profit": _round(row.short_profit) if row.short_quantity else None,
                "next": row.next_exempt,
                "next_quantity": row.next_quantity or None,
            }
            for row in rows
        ],
        column_config={
            "ticker": tr("Ticker"),
            "group": tr("Group"),
            "long_quantity": st.column_config.NumberColumn(
                tr("Held longer: quantity"),
                format="%.6g",
                help=tr(
                    "Units held longer than {years} years: a sale of them today would be exempt.",
                    years=applied.holding_years,
                ),
            ),
            "long_value": _money(tr("Held longer: value")),
            "long_profit": _money(tr("Held longer: profit")),
            "short_quantity": st.column_config.NumberColumn(
                tr("Held shorter: quantity"), format="%.6g"
            ),
            "short_value": _money(tr("Held shorter: value")),
            "short_profit": _money(tr("Held shorter: profit")),
            "next": st.column_config.DateColumn(
                tr("Next"),
                help=tr("The first day the oldest of the units held shorter can be sold exempt."),
            ),
            "next_quantity": st.column_config.NumberColumn(
                tr("Next quantity"), format="%.6g", help=tr("How many units that is.")
            ),
        },
        hide_index=True,
        height=min(38 * (len(rows) + 1) + 2, 420),
    )
    st.caption(
        tr(
            "Sales take the oldest units first, so the units held longer are the ones a sale "
            "would use up first."
        )
    )
