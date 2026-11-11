"""The Streamlit entry page renders without raising."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from portfolio.core.config import CONFIG_ENV_VAR

ROOT = Path(__file__).parent.parent
APP = str(ROOT / "src" / "portfolio" / "ui" / "app.py")


@pytest.fixture(autouse=True)
def fresh_cache():
    # The app caches its config for the whole process; tests need it reloaded.
    st.cache_resource.clear()


def test_app_renders(monkeypatch):
    monkeypatch.setenv(CONFIG_ENV_VAR, str(ROOT / "config.sample.toml"))
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert not at.error
    assert at.title[0].value == "Portfolio"


def test_app_reports_missing_config(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "missing.toml"))
    at = AppTest.from_file(APP).run()
    assert not at.exception
    assert "not found" in at.error[0].value
