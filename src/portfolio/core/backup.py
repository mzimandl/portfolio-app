"""Dated copies of the database file, one per day it changed."""

import re
import sqlite3
from datetime import date
from pathlib import Path


def _pattern(db_path: Path) -> re.Pattern:
    return re.compile(
        rf"^{re.escape(db_path.stem)}-\d{{4}}-\d{{2}}-\d{{2}}{re.escape(db_path.suffix)}$"
    )


def list_backups(db_path: Path, backup_dir: Path) -> list[Path]:
    """Backups of this database, oldest first."""
    if not backup_dir.is_dir():
        return []
    pattern = _pattern(db_path)
    return sorted(p for p in backup_dir.iterdir() if pattern.match(p.name))


def daily_backup(db_path: Path, backup_dir: Path, today: date, keep: int) -> Path | None:
    """Copy the database as it is now, at most once a day, and drop the oldest copies.

    Meant to run before the day's first use, so the copy holds the state from before today's
    changes. Nothing is copied when ``keep`` is 0, when the database does not exist yet, or
    when it has not changed since the newest copy. Returns the new copy, if one was made.
    """
    if keep <= 0 or not db_path.is_file() or db_path.stat().st_size == 0:
        return None
    target = backup_dir / f"{db_path.stem}-{today.isoformat()}{db_path.suffix}"
    if target.exists():
        return None
    existing = list_backups(db_path, backup_dir)
    if existing and existing[-1].stat().st_mtime_ns >= db_path.stat().st_mtime_ns:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    partial.unlink(missing_ok=True)
    # SQLite's own copy: consistent even if something is writing at the same moment.
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        copy = sqlite3.connect(partial)
        try:
            source.backup(copy)
        finally:
            copy.close()
    finally:
        source.close()
    partial.replace(target)
    for old in list_backups(db_path, backup_dir)[:-keep]:
        old.unlink()
    return target
