"""Streamlit entry point: `streamlit run src/portfolio/ui/app.py`."""

import streamlit as st

from portfolio.core.config import ConfigError
from portfolio.ui import common, shell
from portfolio.ui.pages import charts, overview, performance, prices, settings, transactions

st.set_page_config(page_title="Portfolio", layout="wide")


def main() -> None:
    try:
        common.config()
    except ConfigError as e:
        st.error(str(e))
        st.stop()

    page = st.navigation(
        [
            st.Page(overview.render, title="Overview", url_path="overview", default=True),
            st.Page(performance.render, title="Performance", url_path="performance"),
            st.Page(charts.render, title="Charts", url_path="charts"),
            st.Page(transactions.render, title="Transactions", url_path="transactions"),
            st.Page(prices.render, title="Prices", url_path="prices"),
            st.Page(settings.render, title="Settings", url_path="settings"),
        ]
    )
    shell.sidebar()
    shell.pending_splits()
    for warning in common.portfolio().data.warnings:
        st.warning(warning)
    page.run()


main()
