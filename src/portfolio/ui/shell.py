"""Parts of the app shown on every page: the sidebar and the split notices."""

import streamlit as st

from portfolio.core import repo
from portfolio.core.i18n import tr
from portfolio.core.models import Transaction, TransactionKind
from portfolio.core.updater import update_market_data
from portfolio.ui import common
from portfolio.ui.formatting import parse_decimal


def sidebar() -> None:
    cfg = common.config()
    with st.sidebar, common.connection() as conn:
        common.language_picker()
        last_price = max(repo.last_price_dates(conn).values(), default=None)
        last_fx = max(repo.last_fx_dates(conn).values(), default=None)
        never = tr("never")
        st.caption(
            tr("Prices up to **{day}**", day=last_price or never)
            + "  \n"
            + tr("Rates up to **{day}**", day=last_fx or never)
        )
        if st.button(tr("Update prices"), width="stretch"):
            with st.spinner(tr("Downloading prices, exchange rates and company data…")):
                st.session_state["update_result"] = update_market_data(
                    conn,
                    common.provider(),
                    cfg.base_currency,
                    benchmark=cfg.benchmark,
                    sec=common.sec_provider(),
                    sec_tickers=cfg.sec_tickers,
                    official=common.official_provider(),
                    inflation_region=cfg.inflation_region,
                )
            st.rerun()
        result = st.session_state.get("update_result")
        if result is not None:
            days = sum(result.updated.values())
            st.success(
                tr("Series updated: {series}, days saved: {days}.",
                   series=len(result.updated), days=days)
                + (
                    " " + tr("Company data for shares: {n}.", n=len(result.fundamentals))
                    if result.fundamentals
                    else ""
                )
                + (" " + tr("SEC results: {n}.", n=len(result.sec)) if result.sec else "")
            )  # fmt: skip
            for ticker in result.new_splits:
                st.info(
                    tr("New split for {ticker}: its price history was downloaded again.",
                       ticker=ticker)
                )  # fmt: skip
            for what, why in result.errors.items():
                st.error(f"{what}: {why}")
            if st.button(tr("Dismiss"), key="dismiss_update"):
                del st.session_state["update_result"]
                st.rerun()


def pending_splits() -> None:
    """A reported split changes share counts; the user decides whether the ledger needs it."""
    with common.connection() as conn:
        for instrument_id, day, ratio in repo.pending_splits(conn):
            ticker = repo.get_instrument(conn, instrument_id).ticker
            with st.container(border=True):
                st.warning(
                    tr(
                        "**{ticker}** had a split of **{ratio} for 1** on {day}. Until you "
                        "decide, its value is wrong. Add the split if your recorded quantities "
                        "are from before it; dismiss it if you already rewrote them.",
                        ticker=ticker, ratio=f"{ratio:g}", day=day,
                    )
                )  # fmt: skip
                add, dismiss, _ = st.columns([1, 1, 4])
                if add.button(tr("Add split"), key=f"split_add_{instrument_id}_{day}"):
                    with conn:
                        repo.add_transaction(
                            conn,
                            Transaction(day, instrument_id, TransactionKind.SPLIT,
                                        split_ratio=parse_decimal(repr(ratio))),
                        )  # fmt: skip
                    st.rerun()
                if dismiss.button(tr("Dismiss"), key=f"split_dismiss_{instrument_id}_{day}"):
                    with conn:
                        repo.dismiss_split(conn, instrument_id, day)
                    st.rerun()
