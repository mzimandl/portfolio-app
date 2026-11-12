import sqlite3

import pytest

from portfolio.core import db


def write_migrations(tmp_path, files: dict[str, str]):
    for name, sql in files.items():
        (tmp_path / name).write_text(sql)
    return tmp_path


def test_migrate_creates_schema_and_is_repeatable(conn):
    assert db.schema_version(conn) >= 1
    version = db.schema_version(conn)
    assert db.migrate(conn) == version
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"instruments", "transactions", "valuations", "prices", "fx_rates"} <= tables


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO transactions (date, instrument_id, kind) VALUES ('2024-01-01', 99, 'buy')"
        )


def test_writes_need_a_commit(tmp_path):
    path = tmp_path / "sub" / "p.db"
    first = db.connect(path)
    db.migrate(first)
    first.execute("INSERT INTO currencies (code) VALUES ('CZK')")
    first.close()  # no commit
    second = db.connect(path)
    assert second.execute("SELECT count(*) FROM currencies").fetchone()[0] == 0
    with second:
        second.execute("INSERT INTO currencies (code) VALUES ('CZK')")
    second.close()
    third = db.connect(path)
    assert third.execute("SELECT count(*) FROM currencies").fetchone()[0] == 1


def test_only_pending_migrations_run(tmp_path):
    connection = db.connect(":memory:")
    directory = write_migrations(tmp_path, {"0001_a.sql": "CREATE TABLE a (x);"})
    assert db.migrate(connection, directory) == 1
    write_migrations(tmp_path, {"0002_b.sql": "CREATE TABLE b (x);"})
    assert db.migrate(connection, directory) == 2
    assert db.schema_version(connection) == 2


def test_failed_migration_is_rolled_back(tmp_path):
    connection = db.connect(":memory:")
    directory = write_migrations(
        tmp_path,
        {
            "0001_a.sql": "CREATE TABLE a (x);",
            "0002_b.sql": "CREATE TABLE b (x); INSERT INTO a VALUES (1); CREATE TABLE a (x);",
        },
    )
    with pytest.raises(db.MigrationError, match="0002_b.sql"):
        db.migrate(connection, directory)
    assert db.schema_version(connection) == 1
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
    assert tables == {"a"}
    assert connection.execute("SELECT count(*) FROM a").fetchone()[0] == 0


def test_gap_in_migration_numbers_is_rejected(tmp_path):
    directory = write_migrations(tmp_path, {"0001_a.sql": "", "0003_c.sql": ""})
    with pytest.raises(db.MigrationError, match="without gaps"):
        db.migrate(db.connect(":memory:"), directory)


def test_database_newer_than_app_is_rejected(tmp_path):
    connection = db.connect(":memory:")
    connection.execute("PRAGMA user_version = 5")
    connection.commit()
    directory = write_migrations(tmp_path, {"0001_a.sql": "CREATE TABLE a (x);"})
    with pytest.raises(db.MigrationError, match="newer version"):
        db.migrate(connection, directory)


def test_migration_3_drops_the_reinvested_column_and_keeps_the_rows(tmp_path):
    """Run migrations 1-2, add a row the old way, then let the rest run."""
    from importlib import resources

    source = resources.files("portfolio.core") / "migrations"
    for entry in source.iterdir():
        if entry.name.startswith(("0001", "0002")):
            (tmp_path / entry.name).write_text(entry.read_text())
    connection = db.connect(":memory:")
    assert db.migrate(connection, tmp_path) == 2
    connection.executescript(
        """
        INSERT INTO currencies VALUES ('CZK');
        INSERT INTO instrument_types VALUES ('stock');
        INSERT INTO instruments (ticker, type, currency, valuation)
            VALUES ('X', 'stock', 'CZK', 'yahoo');
        INSERT INTO transactions (date, instrument_id, kind, quantity, price, currency, fx_rate,
                                  reinvested, note)
            VALUES ('2024-01-02', 1, 'sell', '1.5', '100', 'CZK', '1', 1, 'kept');
        """
    )
    connection.commit()

    assert db.migrate(connection) >= 3
    columns = [row[1] for row in connection.execute("PRAGMA table_info(transactions)")]
    assert "reinvested" not in columns
    row = connection.execute("SELECT date, kind, quantity, note FROM transactions").fetchone()
    assert tuple(row) == ("2024-01-02", "sell", "1.5", "kept")
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migration_4_turns_negative_staking_sells_into_corrections(tmp_path):
    from importlib import resources

    source = resources.files("portfolio.core") / "migrations"
    for entry in source.iterdir():
        if entry.name.startswith(("0001", "0002", "0003")):
            (tmp_path / entry.name).write_text(entry.read_text())
    connection = db.connect(":memory:")
    assert db.migrate(connection, tmp_path) == 3
    connection.executescript(
        """
        INSERT INTO currencies VALUES ('EUR');
        INSERT INTO instrument_types VALUES ('crypto');
        INSERT INTO instruments (ticker, type, currency, valuation)
            VALUES ('ETH', 'crypto', 'EUR', 'yahoo');
        INSERT INTO transactions (date, instrument_id, kind, quantity, price, currency, fx_rate,
                                  note)
            VALUES ('2023-04-18', 1, 'sell', '0.004', '0', 'EUR', '1',
                    'Negative staking in the old app'),
                   ('2024-02-28', 1, 'sell', '0.0002', '0', 'EUR', '1', NULL);
        """
    )
    connection.commit()

    assert db.migrate(connection) >= 4
    rows = [
        tuple(row)
        for row in connection.execute(
            "SELECT id, kind, quantity, price, currency, fx_rate, note FROM transactions"
        )
    ]
    assert rows == [
        (1, "staking_correction", "0.004", None, None, None, None),
        (2, "sell", "0.0002", "0", "EUR", "1", None),
    ]
    indexes = {row[1] for row in connection.execute("PRAGMA index_list(transactions)")}
    assert {"transactions_instrument_date", "transactions_date"} <= indexes
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
