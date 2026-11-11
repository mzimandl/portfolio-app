"""Streamlit entry point: `streamlit run src/portfolio/ui/app.py`."""

import streamlit as st

from portfolio.core.config import ConfigError, load_config

st.set_page_config(page_title="Portfolio", layout="wide")


@st.cache_resource
def get_config():
    return load_config()


try:
    config = get_config()
except ConfigError as e:
    st.error(str(e))
    st.stop()

st.title("Portfolio")
st.caption("Scaffold only. Pages arrive in later phases.")
st.write(
    {
        "Database": str(config.db_path),
        "Base currency": config.base_currency,
        "Locale": config.locale,
        "Benchmark": config.benchmark or "not set",
    }
)
