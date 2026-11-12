"""Export of everything and CSV import of transactions."""

import sqlite3
from datetime import date
from decimal import Decimal

import streamlit as st

from portfolio.core import backup, csv_io, db, repo
from portfolio.ui import common

_KEPT = ("date", "kind", "quantity", "price", "amount", "currency", "fx_rate", "fee", "tax",
         "split_ratio", "note")  # fmt: skip


def render() -> None:
    st.title("Import / export")
    with common.connection() as conn:
        _export(conn)
        st.divider()
        _import(conn)


def _export(conn: sqlite3.Connection) -> None:
    st.subheader("Export")
    st.caption(
        "The database file is a complete backup: to restore it, put it where the config file "
        "points. The CSV files hold the same data in a form any spreadsheet can open."
    )
    cfg = common.config()
    copies = backup.list_backups(cfg.db_path, cfg.backup_dir)
    if cfg.backup_keep == 0:
        st.caption("Automatic backups are switched off (`backup_keep = 0` in the config file).")
    else:
        newest = f"; the newest is {copies[-1].name}" if copies else ""
        st.caption(
            f"Automatic backups: a copy is made before the first use on every day the data "
            f"changed, and the last {cfg.backup_keep} are kept. There are {len(copies)} in "
            f"`{cfg.backup_dir}`{newest}."
        )
    stamp = date.today().isoformat()
    left, right, _ = st.columns([1, 1, 2])
    left.download_button(
        "Database file",
        data=lambda: csv_io.database_file(conn_copy()),
        file_name=f"portfolio-{stamp}.db",
        mime="application/vnd.sqlite3",
        key="export_db",
        on_click="ignore",
    )
    right.download_button(
        "All tables as CSV (zip)",
        data=lambda: csv_io.export_zip(conn_copy()),
        file_name=f"portfolio-{stamp}.zip",
        mime="application/zip",
        key="export_zip",
        on_click="ignore",
    )


def conn_copy() -> sqlite3.Connection:
    """A connection of its own: the download is prepared after the page run has finished."""
    return db.connect(common.config().db_path)


def _cell(value):
    if isinstance(value, Decimal):
        return float(value)
    return value.value if isinstance(value, csv_io.TransactionKind) else value


def _import(conn: sqlite3.Connection) -> None:
    st.subheader("Import transactions")
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)
    st.caption(
        "A CSV file with the columns `" + "`, `".join(csv_io.TRANSACTION_COLUMNS) + "`. Only "
        "`date`, `ticker` and `kind` are always needed. Kinds: "
        + ", ".join(f"`{kind}`" for kind in csv_io.TransactionKind)
        + ". Files separated by semicolons may use decimal commas. The exported "
        "`transactions.csv` has exactly this layout. Instruments must exist already."
    )
    version = st.session_state.get("import_version", 0)
    uploaded = st.file_uploader("CSV file", type=["csv", "txt"], key=f"import_file_{version}")
    if uploaded is None:
        return
    try:
        rows = csv_io.parse_transactions(csv_io.decode(uploaded.getvalue()), conn)
    except csv_io.CsvError as e:
        st.error(str(e))
        return
    if not rows:
        st.info("The file has no rows.")
        return

    bad = [row for row in rows if not row.ok]
    duplicates = [row for row in rows if row.duplicate]
    st.write(
        f"**{len(rows)}** rows read: **{len(rows) - len(bad)}** usable, **{len(bad)}** with "
        f"errors, **{len(duplicates)}** already in the database."
    )
    for row in bad[:50]:
        st.error(f"Line {row.line}" + (f" ({row.ticker})" if row.ticker else "") + f": {row.error}")
    if len(bad) > 50:
        st.error(f"…and {len(bad) - 50} more.")

    preview = []
    for row in rows:
        if not row.ok:
            continue
        t = row.transaction
        preview.append(
            {"line": row.line, "ticker": row.ticker}
            | {name: _cell(getattr(t, name)) for name in _KEPT}
            | {"already there": row.duplicate}
        )
    if preview:
        st.dataframe(preview, hide_index=True, height=min(38 * (len(preview) + 1) + 2, 400))

    skip = True
    if duplicates:
        skip = st.checkbox(
            f"Skip the {len(duplicates)} rows that are already in the database",
            value=True,
            key="import_skip",
        )
    count = len(rows) - len(bad) - (len(duplicates) if skip else 0)
    if bad:
        st.warning(
            "Nothing can be imported until every row is right. Fix the file and upload it again."
        )
    elif st.button(f"Import {count} transactions", type="primary", disabled=count == 0,
                   key="import_go"):  # fmt: skip
        try:
            with conn:
                added = csv_io.import_transactions(conn, rows, skip_duplicates=skip)
        except (csv_io.CsvError, sqlite3.Error, repo.NotFoundError) as e:
            st.error(str(e))
        else:
            st.session_state["flash"] = f"{added} transactions imported."
            st.session_state["import_version"] = version + 1  # empties the upload box
            st.rerun()
