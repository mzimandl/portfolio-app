"""Things in the data that look wrong or out of date."""

import sqlite3

import streamlit as st

from portfolio.core import repo
from portfolio.core.analytics import checks
from portfolio.ui import common


def _rows(found: list[checks.Finding]) -> list[dict]:
    return [{"Ticker": f.ticker, "Date": f.date, "What": f.detail} for f in found]


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
    st.subheader(f"{name} ({len(found)})")
    st.caption(checks.EXPLANATIONS[name])
    version = st.session_state.get("checks_version", 0)
    picked = _picked(found, f"checks_{_slug(name)}_{version}")
    label = (
        f"Mark {len(picked)} selected as checked" if picked else f"Mark all {len(found)} as checked"
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
    st.title("Checks")
    loaded = common.portfolio()
    found = checks.run_checks(loaded.data, loaded.today)
    st.caption(
        "Looked for in the active instruments every time this page opens. Nothing in your "
        "records is changed; correct what is really wrong in Transactions. What you looked at "
        "and found in order, mark as checked: it stays hidden unless the record changes."
    )
    with common.connection() as conn:
        reviewed = repo.list_reviewed_findings(conn)
        waiting = [f for f in found if f.identity not in reviewed]
        checked = [f for f in found if f.identity in reviewed]
        if not waiting:
            st.success("Nothing to look at." if checked else "Nothing found.")
        for name in checks.EXPLANATIONS:
            rows = [f for f in waiting if f.check == name]
            if rows:
                _section(conn, name, rows, loaded.today)
        quiet = [name for name in checks.EXPLANATIONS if all(f.check != name for f in found)]
        if found and quiet:
            st.caption("Nothing found for: " + ", ".join(name.lower() for name in quiet) + ".")
        if checked:
            with st.expander(f"Checked ({len(checked)})"):
                st.caption("Findings you marked as checked. Select rows to show them again.")
                version = st.session_state.get("checks_version", 0)
                event = st.dataframe(
                    [
                        {"Check": f.check} | row
                        for f, row in zip(checked, _rows(checked), strict=True)
                    ],
                    hide_index=True,
                    width="content",
                    on_select="rerun",
                    selection_mode="multi-row",
                    key=f"checks_checked_{version}",
                )
                chosen = [checked[i] for i in (event.selection.rows if event else [])]
                if st.button("Show selected again", disabled=not chosen, key="checks_unmark"):
                    with conn:
                        for finding in chosen:
                            repo.unmark_finding_reviewed(conn, finding.identity)
                    _done()
