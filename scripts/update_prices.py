"""Download new prices and exchange rates: uv run python scripts/update_prices.py [--full]"""

import argparse
import sys
from pathlib import Path

from portfolio.core import db, repo
from portfolio.core.config import load_config
from portfolio.core.providers.yahoo import YahooProvider
from portfolio.core.updater import update_market_data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="config file")
    parser.add_argument("--full", action="store_true", help="download every history again")
    args = parser.parse_args()

    config = load_config(args.config)
    conn = db.connect(config.db_path)
    db.migrate(conn)
    result = update_market_data(
        conn, YahooProvider(), config.base_currency, benchmark=config.benchmark, full=args.full
    )

    days = sum(result.updated.values())
    print(f"Updated {len(result.updated)} series, {days} days saved.")
    for ticker in result.new_splits:
        print(f"  New split for {ticker}: its whole price history was downloaded again.")
    for what, why in result.errors.items():
        print(f"  FAILED {what}: {why}")
    instruments = {i.id: i.ticker for i in repo.list_instruments(conn)}
    for instrument_id, day, ratio in repo.pending_splits(conn):
        print(
            f"  Split waiting for your decision: {instruments[instrument_id]} {day}, ratio "
            f"{ratio:g}. Until it is added as a transaction or dismissed, the value is wrong."
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
