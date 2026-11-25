"""Export of everything and CSV import of transactions."""

import sqlite3
from datetime import date
from decimal import Decimal

import streamlit as st

from portfolio.core import backup, csv_io, db, repo
from portfolio.core.i18n import tr
from portfolio.ui import common

_KEPT = ("date", "kind", "quantity", "price", "amount", "currency", "fx_rate", "fee", "tax",
         "split_ratio", "note")  # fmt: skip


def render() -> None:
    st.title(tr("Import / export"))
    with common.connection() as conn:
        _export(conn)
        st.divider()
        _import(conn)


def _export(conn: sqlite3.Connection) -> None:
    st.subheader(tr("Export"))
    st.caption(
        tr(
            "The database file is a complete backup: to restore it, put it where the config "
            "file points. The CSV files hold the same data in a form any spreadsheet can open."
        )
    )
    cfg = common.config()
    copies = backup.list_backups(cfg.db_path, cfg.backup_dir)
    if cfg.backup_keep == 0:
        st.caption(tr("Automatic backups are switched off (`backup_keep = 0` in the config file)."))
    else:
        st.caption(
            tr(
                "Automatic backups: a copy is made before the first use on every day the data "
                "changed, and the last {keep} are kept. Copies in `{folder}`: {count}.",
                keep=cfg.backup_keep, folder=cfg.backup_dir, count=len(copies),
            )
            + (" " + tr("The newest is {name}.", name=copies[-1].name) if copies else "")
        )  # fmt: skip
    stamp = date.today().isoformat()
    left, right, _ = st.columns([1, 1, 2])
    left.download_button(
        tr("Database file"),
        data=lambda: csv_io.database_file(conn_copy()),
        file_name=f"portfolio-{stamp}.db",
        mime="application/vnd.sqlite3",
        key="export_db",
        on_click="ignore",
    )
    right.download_button(
        tr("All tables as CSV (zip)"),
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
    st.subheader(tr("Import transactions"))
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)
    st.caption(
        tr(
            "A CSV file with the columns {columns}. Only `date`, `ticker` and `kind` are "
            "always needed. Kinds: {kinds}. Files separated by semicolons may use decimal "
            "commas. The exported `transactions.csv` has exactly this layout. Instruments "
            "must exist already.",
            columns="`" + "`, `".join(csv_io.TRANSACTION_COLUMNS) + "`",
            kinds=", ".join(f"`{kind}`" for kind in csv_io.TransactionKind),
        )
    )
    version = st.session_state.get("import_version", 0)
    uploaded = st.file_uploader(tr("CSV file"), type=["csv", "txt"], key=f"import_file_{version}")
    if uploaded is None:
        return
    try:
        rows = csv_io.parse_transactions(csv_io.decode(uploaded.getvalue()), conn)
    except csv_io.CsvError as e:
        st.error(str(e))
        return
    if not rows:
        st.info(tr("The file has no rows."))
        return

    bad = [row for row in rows if not row.ok]
    duplicates = [row for row in rows if row.duplicate]
    st.write(
        tr(
            "Rows read: **{rows}**. Usable: **{usable}**, with errors: **{bad}**, already in "
            "the database: **{duplicates}**.",
            rows=len(rows), usable=len(rows) - len(bad), bad=len(bad),
            duplicates=len(duplicates),
        )
    )  # fmt: skip
    for row in bad[:50]:
        st.error(
            tr("Line {line}", line=row.line)
            + (f" ({row.ticker})" if row.ticker else "")
            + f": {row.error}"
        )
    if len(bad) > 50:
        st.error(tr("…and {count} more.", count=len(bad) - 50))

    preview = []
    for row in rows:
        if not row.ok:
            continue
        t = row.transaction
        preview.append(
            {"line": row.line, "ticker": row.ticker}
            | {name: _cell(getattr(t, name)) for name in _KEPT}
            | {tr("already there"): row.duplicate}
        )
    if preview:
        st.dataframe(preview, hide_index=True, height=min(38 * (len(preview) + 1) + 2, 400))

    skip = True
    if duplicates:
        skip = st.checkbox(
            tr(
                "Skip the rows that are already in the database ({count})", count=len(duplicates)
            ),  # fmt: skip
            value=True,
            key="import_skip",
        )
    count = len(rows) - len(bad) - (len(duplicates) if skip else 0)
    if bad:
        st.warning(
            tr(
                "Nothing can be imported until every row is right. Fix the file and upload it "
                "again."
            )
        )
    elif st.button(tr("Import transactions ({count})", count=count), type="primary",
                   disabled=count == 0, key="import_go"):  # fmt: skip
        try:
            with conn:
                added = csv_io.import_transactions(conn, rows, skip_duplicates=skip)
        except (csv_io.CsvError, sqlite3.Error, repo.NotFoundError) as e:
            st.error(str(e))
        else:
            st.session_state["flash"] = tr("Transactions imported: {count}.", count=added)
            st.session_state["import_version"] = version + 1  # empties the upload box
            st.rerun()
