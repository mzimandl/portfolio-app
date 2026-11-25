"""Pieces every page uses: config, database access, loaded data, scope picker."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

import streamlit as st

from portfolio.core import backup, db, i18n, repo
from portfolio.core.analytics.data import PortfolioData, Series, load_data
from portfolio.core.analytics.timeseries import DayPoint, all_daily, combine
from portfolio.core.config import Config, load_config
from portfolio.core.i18n import N_, tr
from portfolio.core.models import Profile, TransactionKind
from portfolio.core.providers.base import MarketDataProvider
from portfolio.core.providers.official import OfficialProvider
from portfolio.core.providers.sec import SecProvider
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


def _prepare() -> None:
    """Before the database is used: today's backup first, then any pending migration."""
    cfg = config()
    backup.daily_backup(cfg.db_path, cfg.backup_dir, date.today(), cfg.backup_keep)
    _migrate(str(cfg.db_path))


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """A database connection for this run of the page. Use ``with conn:`` around writes."""
    path = config().db_path
    _prepare()
    conn = db.connect(path)
    try:
        yield conn
    finally:
        conn.close()


def provider() -> MarketDataProvider:
    return YahooProvider()


def official_provider() -> OfficialProvider:
    return OfficialProvider()


def sec_provider() -> SecProvider | None:
    """SEC EDGAR, only with a contact set in the config file (the SEC requires one)."""
    agent = config().sec_user_agent
    return SecProvider(agent) if agent else None


@dataclass(frozen=True)
class Loaded:
    data: PortfolioData
    daily: dict[int, list[DayPoint]]  # every instrument, inactive ones too
    today: date
    inflation: Series  # consumer price index by month, of the configured region
    profiles: dict[int, Profile]  # sector and country per instrument
    official_rates: dict[str, list[tuple[date, float]]]  # ČNB rates per currency


@st.cache_resource(max_entries=4, show_spinner=False)
def _load(
    path: str, base_currency: str, region: str | None, today: date, token: tuple, language: str
) -> Loaded:
    """``token`` changes with the database file, so a change there gives fresh data.
    ``language`` is part of the key because the data's warnings are texts."""
    conn = db.connect(path)
    try:
        data = load_data(conn, base_currency)
        index = Series(repo.list_inflation(conn, region) if region else [])
        profiles = repo.list_profiles(conn)
        rates = repo.list_official_rates(conn)
    finally:
        conn.close()
    daily = all_daily(data, today, include_inactive=True)
    return Loaded(data, daily, today, index, profiles, rates)


def portfolio() -> Loaded:
    """Data and day-by-day history, recomputed only when the database file changes.

    Shared between reruns: treat it as read-only.
    """
    path = config().db_path
    _prepare()
    stat = path.stat()
    cfg = config()
    return _load(
        str(path), cfg.base_currency, cfg.inflation_region, date.today(),
        (stat.st_mtime_ns, stat.st_size), i18n.language(),
    )  # fmt: skip


# --- formatting with the configured locale and base currency ---------------------------------


def money(value: float | None, currency: str | None = None, decimals: int = 0, **kw) -> str:
    cfg = config()
    return formatting.money(value, currency or cfg.base_currency, cfg.locale, decimals, **kw)


def percent(value: float | None, decimals: int = 1, **kw) -> str:
    return formatting.percent(value, config().locale, decimals, **kw)


def number(value: float | None, decimals: int = 0, **kw) -> str:
    return formatting.number(value, config().locale, decimals, **kw)


# --- language -------------------------------------------------------------------------------


def start_language() -> None:
    """The session's language: the one picked in the sidebar, else the config's."""
    i18n.set_language(st.session_state.setdefault("language", config().language))


def language_picker() -> None:
    st.radio(
        "Language",
        list(i18n.LANGUAGES),
        format_func=i18n.LANGUAGES.get,
        horizontal=True,
        key="language",
        label_visibility="collapsed",
    )


KIND_LABELS = {
    TransactionKind.BUY: N_("Buy"),
    TransactionKind.SELL: N_("Sell"),
    TransactionKind.DEPOSIT: N_("Deposit"),
    TransactionKind.WITHDRAWAL: N_("Withdrawal"),
    TransactionKind.DIVIDEND: N_("Dividend"),
    TransactionKind.STAKING_REWARD: N_("Staking reward"),
    TransactionKind.STAKING_CORRECTION: N_("Staking correction"),
    TransactionKind.SPLIT: N_("Split"),
    TransactionKind.FEE: N_("Fee only"),
}


def kind_label(kind: TransactionKind) -> str:
    return tr(KIND_LABELS[kind])


# --- choosing which instruments a page shows -------------------------------------------------

# Values of the scope picker; a type is "type:<name>", an instrument "instrument:<id>".
INVESTMENTS = "investments"
ALL_ACTIVE = "active"
EVERYTHING = "everything"


def is_separate(type_name: str) -> bool:
    """Whether this instrument type is reported apart from the investments."""
    return type_name in config().separate_types


def separate_label() -> str:
    """Heading for the separately reported types, e.g. "Savings"."""
    return " + ".join(config().separate_types).capitalize()


def scope_picker(loaded: Loaded, key: str) -> tuple[str, list[int]]:
    """Select box for the whole portfolio, one type or one instrument. Returns (choice, ids).

    With separately reported types configured, the default choice leaves them out.
    """
    data = loaded.data
    active = data.instrument_ids()
    everything = data.instrument_ids(include_inactive=True)
    investments = [i for i in active if not is_separate(data.instruments[i].type)]
    choices: dict[str, tuple[str, list[int]]] = {}
    if len(investments) != len(active):
        choices[INVESTMENTS] = (
            tr("Investments (without {what})", what=separate_label().lower()),
            investments,
        )
    choices[ALL_ACTIVE] = (tr("All active"), active)
    choices[EVERYTHING] = (tr("Everything, including inactive"), everything)
    for type_name in sorted({data.instruments[i].type for i in active}):
        choices[f"type:{type_name}"] = (
            tr("Type: {name}", name=type_name),
            [i for i in active if data.instruments[i].type == type_name],
        )
    for instrument_id in everything:
        instrument = data.instruments[instrument_id]
        suffix = "" if instrument.active else " " + tr("(inactive)")
        choices[f"instrument:{instrument_id}"] = (f"{instrument.ticker}{suffix}", [instrument_id])
    choice = st.selectbox(tr("Show"), list(choices), format_func=lambda c: choices[c][0], key=key)
    return choice, choices[choice][1]


def history(loaded: Loaded, instrument_ids: list[int]) -> list[DayPoint]:
    return combine(loaded.daily[i] for i in instrument_ids if i in loaded.daily)


PERIODS = {
    "all": N_("Since start"),
    "ytd": N_("This year"),
    "1y": N_("Last 12 months"),
    "3y": N_("Last 3 years"),
    "5y": N_("Last 5 years"),
}


def period_picker(column, key: str) -> str:
    return column.selectbox(tr("Period"), list(PERIODS), format_func=period_label, key=key)


def period_label(period: str) -> str:
    return tr(PERIODS[period])


def period_start(period: str, today: date) -> date | None:
    """First day of the chosen period; None means from the beginning."""
    if period == "ytd":
        return date(today.year, 1, 1)
    years = {"1y": 1, "3y": 3, "5y": 5}.get(period)
    if years is None:
        return None
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(year=today.year - years, day=28)
