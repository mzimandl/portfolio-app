"""Things in the data that look wrong or out of date."""

import sqlite3

import streamlit as st

from portfolio.core import repo
from portfolio.core.analytics import checks
from portfolio.core.i18n import tr
from portfolio.core.models import TransactionKind
from portfolio.ui import common


def _detail(finding: checks.Finding) -> str:
    """The finding's detail in the current language."""
    if not finding.template:
        return finding.detail
    params = {
        name: common.kind_label(value).lower() if isinstance(value, TransactionKind) else value
        for name, value in finding.params
    }
    return tr(finding.template, **params)


def _rows(found: list[checks.Finding]) -> list[dict]:
    return [{tr("Ticker"): f.ticker, tr("Date"): f.date, tr("What"): _detail(f)} for f in found]


def _picked(found: list[checks.Finding], key: str) -> list[checks.Finding]:
    """The table of findings, and the ones whose rows are selected."""
    event = st.dataframe(
        _rows(found),
        hide_index=True,
        width="content",
        on_select="rerun",
        selection_mode="multi-row",
        key=key,
    )
    chosen = event.selection.rows if event else []
    return [found[i] for i in chosen if i < len(found)]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def _section(conn: sqlite3.Connection, name: str, found: list[checks.Finding], today) -> None:
    st.subheader(f"{tr(name)} ({len(found)})")
    st.caption(tr(checks.EXPLANATIONS[name]))
    version = st.session_state.get("checks_version", 0)
    picked = _picked(found, f"checks_{_slug(name)}_{version}")
    label = (
        tr("Mark the selected as checked ({count})", count=len(picked))
        if picked
        else tr("Mark all as checked ({count})", count=len(found))
    )
    if st.button(label, key=f"checks_mark_{_slug(name)}"):
        with conn:
            for finding in picked or found:
                repo.mark_finding_reviewed(conn, finding.identity, today)
        _done()


def _done() -> None:
    st.session_state["checks_version"] = st.session_state.get("checks_version", 0) + 1
    st.rerun()


def render() -> None:
    st.title(tr("Checks"))
    loaded = common.portfolio()
    found = checks.run_checks(loaded.data, loaded.today)
    st.caption(
        tr(
            "Looked for in the active instruments every time this page opens. Nothing in your "
            "records is changed; correct what is really wrong in Transactions. What you "
            "looked at and found in order, mark as checked: it stays hidden unless the record "
            "changes."
        )
    )
    with common.connection() as conn:
        reviewed = repo.list_reviewed_findings(conn)
        waiting = [f for f in found if f.identity not in reviewed]
        checked = [f for f in found if f.identity in reviewed]
        if not waiting:
            st.success(tr("Nothing to look at.") if checked else tr("Nothing found."))
        for name in checks.EXPLANATIONS:
            rows = [f for f in waiting if f.check == name]
            if rows:
                _section(conn, name, rows, loaded.today)
        quiet = [name for name in checks.EXPLANATIONS if all(f.check != name for f in found)]
        if found and quiet:
            st.caption(
                tr("Nothing found for: {checks}.",
                   checks=", ".join(tr(name).lower() for name in quiet))
            )  # fmt: skip
        if checked:
            with st.expander(tr("Checked ({count})", count=len(checked))):
                st.caption(tr("Findings you marked as checked. Select rows to show them again."))
                version = st.session_state.get("checks_version", 0)
                event = st.dataframe(
                    [
                        {tr("Check"): tr(f.check)} | row
                        for f, row in zip(checked, _rows(checked), strict=True)
                    ],
                    hide_index=True,
                    width="content",
                    on_select="rerun",
                    selection_mode="multi-row",
                    key=f"checks_checked_{version}",
                )
                chosen = [checked[i] for i in (event.selection.rows if event else [])]
                if st.button(tr("Show selected again"), disabled=not chosen, key="checks_unmark"):
                    with conn:
                        for finding in chosen:
                            repo.unmark_finding_reviewed(conn, finding.identity)
                    _done()
