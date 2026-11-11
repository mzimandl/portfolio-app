"""Export every table as CSV: uv run python scripts/export_csv.py FOLDER"""

import argparse
import sys
from pathlib import Path

from portfolio.core import db
from portfolio.core.config import load_config
from portfolio.core.csv_io import export_all


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="where to write the CSV files")
    parser.add_argument("--config", type=Path, help="config file")
    args = parser.parse_args()

    conn = db.connect(load_config(args.config).db_path)
    db.migrate(conn)
    args.folder.mkdir(parents=True, exist_ok=True)
    for name, text in export_all(conn).items():
        (args.folder / name).write_text(text, encoding="utf-8")
        print(f"{text.count(chr(10)) - 1:>7} rows  {args.folder / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
