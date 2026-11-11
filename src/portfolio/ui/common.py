"""Pieces every page uses: config, database access, loaded data, scope picker."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

import streamlit as st

from portfolio.core import db
from portfolio.core.analytics.data import PortfolioData, load_data
from portfolio.core.analytics.timeseries import DayPoint, all_daily, combine
from portfolio.core.config import Config, load_config
from portfolio.core.providers.base import MarketDataProvider
from portfolio.core.providers.yahoo import YahooProvider
from portfolio.ui import formatting


@st.cache_resource
def config() -> Config:
    return load_config()


@st.cache_resource
def _migrate(path: str) -> None:
    conn = db.connect(path)
    try:
        db.migrate(conn)
    finally:
        conn.close()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """A database connection for this run of the page. Use ``with conn:`` around writes."""
    path = config().db_path
    _migrate(str(path))
    conn = db.connect(path)
    try:
        yield conn
    finally:
        conn.close()


def provider() -> MarketDataProvider:
    return YahooProvider()


@dataclass(frozen=True)
class Loaded:
    data: PortfolioData
    daily: dict[int, list[DayPoint]]  # every instrument, inactive ones too
    today: date


@st.cache_resource(max_entries=2, show_spinner=False)
def _load(path: str, base_currency: str, today: date, _token: tuple) -> Loaded:
    conn = db.connect(path)
    try:
        data = load_data(conn, base_currency)
    finally:
        conn.close()
    return Loaded(data, all_daily(data, today, include_inactive=True), today)


def portfolio() -> Loaded:
    """Data and day-by-day history, recomputed only when the database file changes.

    Shared between reruns: treat it as read-only.
    """
    path = config().db_path
    _migrate(str(path))
    stat = path.stat()
    return _load(str(path), config().base_currency, date.today(), (stat.st_mtime_ns, stat.st_size))


# --- formatting with the configured locale and base currency ---------------------------------


def money(value: float | None, currency: str | None = None, decimals: int = 0, **kw) -> str:
    cfg = config()
    return formatting.money(value, currency or cfg.base_currency, cfg.locale, decimals, **kw)


def percent(value: float | None, decimals: int = 1, **kw) -> str:
    return formatting.percent(value, config().locale, decimals, **kw)


def number(value: float | None, decimals: int = 0, **kw) -> str:
    return formatting.number(value, config().locale, decimals, **kw)


# --- choosing which instruments a page shows -------------------------------------------------

ALL_ACTIVE = "All active"
EVERYTHING = "Everything, including inactive"


def scope_picker(loaded: Loaded, key: str) -> tuple[str, list[int]]:
    """Select box for the whole portfolio, one type or one instrument. Returns (label, ids)."""
    data = loaded.data
    active = data.instrument_ids()
    everything = data.instrument_ids(include_inactive=True)
    choices: dict[str, list[int]] = {ALL_ACTIVE: active, EVERYTHING: everything}
    for type_name in sorted({data.instruments[i].type for i in active}):
        choices[f"Type: {type_name}"] = [i for i in active if data.instruments[i].type == type_name]
    for instrument_id in everything:
        instrument = data.instruments[instrument_id]
        suffix = "" if instrument.active else " (inactive)"
        choices[f"{instrument.ticker}{suffix}"] = [instrument_id]
    label = st.selectbox("Show", list(choices), key=key)
    return label, choices[label]


def history(loaded: Loaded, instrument_ids: list[int]) -> list[DayPoint]:
    return combine(loaded.daily[i] for i in instrument_ids if i in loaded.daily)


PERIODS = ("Since start", "This year", "Last 12 months", "Last 3 years", "Last 5 years")


def period_start(period: str, today: date) -> date | None:
    """First day of the chosen period; None means from the beginning."""
    if period == "This year":
        return date(today.year, 1, 1)
    years = {"Last 12 months": 1, "Last 3 years": 3, "Last 5 years": 5}.get(period)
    if years is None:
        return None
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(year=today.year - years, day=28)
