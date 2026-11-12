import os
import sqlite3
from datetime import date

from portfolio.core import db
from portfolio.core.backup import daily_backup, list_backups


def make_db(path, rows=1):
    conn = db.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS t (x)")
    for _ in range(rows):
        conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()


def count(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT count(*) FROM t").fetchone()[0]
    finally:
        conn.close()


def older(path, seconds=10):
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime - seconds))


def test_one_copy_a_day_of_the_state_before_todays_changes(tmp_path):
    source, backups = tmp_path / "p.db", tmp_path / "backups"
    make_db(source)
    copy = daily_backup(source, backups, date(2024, 5, 1), keep=30)
    assert copy == backups / "p-2024-05-01.db"
    assert count(copy) == 1

    make_db(source, rows=2)  # today's work
    assert daily_backup(source, backups, date(2024, 5, 1), keep=30) is None
    assert count(copy) == 1  # still the morning's state

    older(copy)
    assert count(daily_backup(source, backups, date(2024, 5, 2), keep=30)) == 3


def test_nothing_is_copied_when_nothing_changed(tmp_path):
    source, backups = tmp_path / "p.db", tmp_path / "backups"
    make_db(source)
    older(source)
    assert daily_backup(source, backups, date(2024, 5, 1), keep=30)
    assert daily_backup(source, backups, date(2024, 5, 2), keep=30) is None
    assert len(list_backups(source, backups)) == 1


def test_only_the_newest_copies_are_kept(tmp_path):
    source, backups = tmp_path / "p.db", tmp_path / "backups"
    make_db(source)
    backups.mkdir()
    (backups / "other-2024-01-01.db").write_text("not ours")
    for day in range(1, 6):
        for existing in list_backups(source, backups):
            older(existing)
        assert daily_backup(source, backups, date(2024, 5, day), keep=3)
    assert [p.name for p in list_backups(source, backups)] == [
        "p-2024-05-03.db", "p-2024-05-04.db", "p-2024-05-05.db",
    ]  # fmt: skip
    assert (backups / "other-2024-01-01.db").exists()
    assert not list(backups.glob("*.part"))


def test_switched_off_or_no_database_yet(tmp_path):
    source, backups = tmp_path / "p.db", tmp_path / "backups"
    assert daily_backup(source, backups, date(2024, 5, 1), keep=30) is None
    make_db(source)
    assert daily_backup(source, backups, date(2024, 5, 1), keep=0) is None
    assert not backups.exists()
    assert list_backups(source, backups) == []
