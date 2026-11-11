"""Parts of the app shown on every page: the sidebar and the split notices."""

import streamlit as st

from portfolio.core import repo
from portfolio.core.models import Transaction, TransactionKind
from portfolio.core.updater import update_market_data
from portfolio.ui import common
from portfolio.ui.formatting import parse_decimal


def sidebar() -> None:
    cfg = common.config()
    with st.sidebar, common.connection() as conn:
        last_price = max(repo.last_price_dates(conn).values(), default=None)
        last_fx = max(repo.last_fx_dates(conn).values(), default=None)
        st.caption(
            f"Prices up to **{last_price or 'never'}**  \nRates up to **{last_fx or 'never'}**"
        )
        if st.button("Update prices", width="stretch"):
            with st.spinner("Downloading prices and exchange rates…"):
                st.session_state["update_result"] = update_market_data(
                    conn, common.provider(), cfg.base_currency, benchmark=cfg.benchmark
                )
            st.rerun()
        result = st.session_state.get("update_result")
        if result is not None:
            days = sum(result.updated.values())
            st.success(f"{len(result.updated)} series updated, {days} days saved.")
            for ticker in result.new_splits:
                st.info(f"New split for {ticker}: its price history was downloaded again.")
            for what, why in result.errors.items():
                st.error(f"{what}: {why}")
            if st.button("Dismiss", key="dismiss_update"):
                del st.session_state["update_result"]
                st.rerun()


def pending_splits() -> None:
    """A reported split changes share counts; the user decides whether the ledger needs it."""
    with common.connection() as conn:
        for instrument_id, day, ratio in repo.pending_splits(conn):
            ticker = repo.get_instrument(conn, instrument_id).ticker
            with st.container(border=True):
                st.warning(
                    f"**{ticker}** had a split of **{ratio:g} for 1** on {day}. Until you decide, "
                    "its value is wrong. Add the split if your recorded quantities are from "
                    "before it; dismiss it if you already rewrote them."
                )
                add, dismiss, _ = st.columns([1, 1, 4])
                if add.button("Add split", key=f"split_add_{instrument_id}_{day}"):
                    with conn:
                        repo.add_transaction(
                            conn,
                            Transaction(day, instrument_id, TransactionKind.SPLIT,
                                        split_ratio=parse_decimal(repr(ratio))),
                        )  # fmt: skip
                    st.rerun()
                if dismiss.button("Dismiss", key=f"split_dismiss_{instrument_id}_{day}"):
                    with conn:
                        repo.dismiss_split(conn, instrument_id, day)
                    st.rerun()
