"""Streamlit entry point: `streamlit run src/portfolio/ui/app.py`."""

import streamlit as st

from portfolio.core.config import ConfigError
from portfolio.core.i18n import tr
from portfolio.ui import common, shell
from portfolio.ui.pages import (
    charts,
    checks,
    data,
    dividends,
    fundamentals,
    glossary,
    overview,
    performance,
    prices,
    settings,
    taxes,
    transactions,
)

st.set_page_config(page_title="Portfolio", layout="wide")


def main() -> None:
    try:
        common.config()
    except ConfigError as e:
        st.error(str(e))
        st.stop()
    common.start_language()

    page = st.navigation(
        [
            st.Page(overview.render, title=tr("Overview"), url_path="overview", default=True),
            st.Page(performance.render, title=tr("Performance"), url_path="performance"),
            st.Page(charts.render, title=tr("Charts"), url_path="charts"),
            st.Page(dividends.render, title=tr("Dividends"), url_path="dividends"),
            st.Page(fundamentals.render, title=tr("Fundamentals"), url_path="fundamentals"),
            st.Page(taxes.render, title=tr("Taxes"), url_path="taxes"),
            st.Page(transactions.render, title=tr("Transactions"), url_path="transactions"),
            st.Page(prices.render, title=tr("Prices"), url_path="prices"),
            st.Page(checks.render, title=tr("Checks"), url_path="checks"),
            st.Page(data.render, title=tr("Import / export"), url_path="data"),
            st.Page(settings.render, title=tr("Settings"), url_path="settings"),
            st.Page(glossary.render, title=tr("Glossary"), url_path="glossary"),
        ]
    )
    shell.sidebar()
    shell.pending_splits()
    for warning in common.portfolio().data.warnings:
        st.warning(warning)
    page.run()


main()
