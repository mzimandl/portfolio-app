"""Import the old app's database: uv run python scripts/import_legacy.py OLD_DB [--dry-run]"""

import argparse
import sqlite3
import sys
from pathlib import Path

from portfolio.core import db
from portfolio.core.config import load_config
from portfolio.core.legacy_import import LegacyImportError, import_legacy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="database file of the old app")
    parser.add_argument("--config", type=Path, help="config file of the new app")
    parser.add_argument("--dry-run", action="store_true", help="check everything, save nothing")
    args = parser.parse_args()

    config = load_config(args.config)
    if not args.source.is_file():
        print(f"Source database not found: {args.source}")
        return 2
    if args.source.resolve() == config.db_path:
        print("Source and target are the same file.")
        return 2

    source = sqlite3.connect(f"file:{args.source.resolve()}?mode=ro", uri=True)
    target = db.connect(":memory:" if args.dry_run else config.db_path)
    db.migrate(target)
    try:
        report = import_legacy(source, target, config.base_currency)
    except LegacyImportError as e:
        target.rollback()
        print(f"Import stopped, nothing saved: {e}")
        return 1

    print("Imported:")
    for what, count in sorted(report.imported.items()):
        print(f"  {count:>7}  {what}")
    if report.skipped:
        print("Skipped:")
        for what, count in sorted(report.skipped.items()):
            print(f"  {count:>7}  {what}")
    if report.notes:
        print("Notes:")
        for note in report.notes:
            print(f"  - {note}")

    print(f"Checks: {len(report.checks) - len(report.failed_checks)} of {len(report.checks)} match")
    for check in report.failed_checks:
        print(f"  MISMATCH {check.ticker} {check.what}: old {check.old!r}, new {check.new!r}")

    if not report.ok:
        target.rollback()
        print("Nothing saved because the totals do not match.")
        return 1
    if args.dry_run:
        print("Dry run: nothing saved.")
    else:
        target.commit()
        print(f"Saved to {config.db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
