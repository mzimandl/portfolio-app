"""SQLite connection and schema migrations."""

import re
import sqlite3
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

_MIGRATION_RE = re.compile(r"^(\d{4})_.+\.sql$")


class MigrationError(Exception):
    """The migration files or the database version are inconsistent."""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database with foreign keys enforced and explicit transactions.

    Writes are not saved until the caller commits; use ``with conn:`` around them.
    The default rollback journal is kept (no WAL) so the database stays a single file,
    which is safer in a cloud-synced folder.
    """
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, autocommit=True)
    conn.row_factory = sqlite3.Row
    # Must run outside a transaction, so before switching autocommit off.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.autocommit = False
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _default_migrations() -> Traversable:
    return resources.files("portfolio.core") / "migrations"


def _load_migrations(directory: Traversable) -> list[tuple[int, str, str]]:
    found = []
    for entry in directory.iterdir():
        match = _MIGRATION_RE.match(entry.name)
        if match:
            found.append((int(match.group(1)), entry.name, entry.read_text(encoding="utf-8")))
    found.sort()
    versions = [version for version, _, _ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError(f"Migration numbers must be 1..N without gaps, found {versions}")
    return found


def migrate(conn: sqlite3.Connection, directory: Traversable | Path | None = None) -> int:
    """Apply pending migrations, each in its own transaction. Returns the new version."""
    migrations = _load_migrations(directory or _default_migrations())
    current = schema_version(conn)
    latest = len(migrations)
    if current > latest:
        raise MigrationError(
            f"Database is at version {current} but this app only knows version {latest}. "
            "It was probably written by a newer version of the app."
        )
    conn.commit()
    for version, name, sql in migrations[current:]:
        try:
            conn.executescript(sql)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise MigrationError(f"Migration {name} failed: {e}") from e
    return latest
