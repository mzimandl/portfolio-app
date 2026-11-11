"""Compare the new analytics with the old app's saved output (see legacy_reference.py).

    uv run python scripts/compare_legacy.py [legacy/]

Only meaningful while the new database still holds the same data the reference was made from.
Prints relative differences, not the amounts themselves.
"""

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from portfolio.core import db
from portfolio.core.analytics import performance, timeseries
from portfolio.core.analytics.data import load_data
from portfolio.core.analytics.overview import overview
from portfolio.core.config import load_config

TOLERANCE = 1e-6

# old overview field -> new overview field
OVERVIEW_FIELDS = {
    "last_price": "last_price",
    "volume": "quantity",
    "average_price": "average_price",
    "investment": "invested",
    "return": "returned",
    "fees": "fees",
    "dividends": "dividends",
    "value": "value",
    "total_profit": "total_profit",
    "fx_profit": "fx_profit",
    "rewards": "rewards",
    "value_profit": "price_profit",
}


def differs(old: float | None, new: float | None) -> float | None:
    """Relative difference if the two numbers disagree, else None. Old nulls count as zero."""
    old, new = old or 0.0, new or 0.0
    difference = abs(old - new)
    if difference <= TOLERANCE * max(1.0, abs(old)):
        return None
    return difference / max(abs(old), 1e-12)


def main() -> int:
    legacy = Path(sys.argv[1] if len(sys.argv) > 1 else "legacy")
    config = load_config()
    data = load_data(db.connect(config.db_path), config.base_currency)
    today = date.today()
    problems = defaultdict(list)
    compared = 0

    # Overview: every field of every active instrument.
    new_rows = {row.ticker: row for row in overview(data, today)}
    old_rows = {row["ticker"]: row for row in json.loads((legacy / "overview.json").read_text())}
    for ticker in sorted(set(new_rows) ^ set(old_rows)):
        problems["overview"].append(f"{ticker}: only in {'new' if ticker in new_rows else 'old'}")
    for ticker in sorted(set(new_rows) & set(old_rows)):
        for old_field, new_field in OVERVIEW_FIELDS.items():
            compared += 1
            gap = differs(old_rows[ticker].get(old_field), getattr(new_rows[ticker], new_field))
            if gap is not None:
                problems["overview"].append(f"{ticker} {old_field}: differs by {gap:.3%}")

    # New money per period (the old app's Investments view).
    for span in ("year", "month"):
        old_periods = {
            str(row[span]): row["total"]
            for row in json.loads((legacy / f"investments_{span}.json").read_text())
        }
        new_periods = {
            row["period"]: row["total"] for row in performance.invested_by_period(data, span)
        }
        for period in sorted(set(old_periods) | set(new_periods)):
            compared += 1
            gap = differs(old_periods.get(period), new_periods.get(period))
            if gap is not None:
                problems[f"invested per {span}"].append(f"{period}: differs by {gap:.3%}")

    # Year-end values from the old Performance view check the day-by-day history.
    by_ticker = {data.instruments[i].ticker: i for i in data.instrument_ids()}
    old_performance = json.loads((legacy / "performance.json").read_text())
    histories = timeseries.all_daily(data, today)
    for year, tickers in sorted(old_performance.items()):
        year_end = min(date(int(year), 12, 31), today)
        for ticker, numbers in sorted(tickers.items()):
            points = histories.get(by_ticker.get(ticker), [])
            at_year_end = [p for p in points if p.date == year_end]
            if not at_year_end:
                continue
            compared += 1
            gap = differs(numbers["value_total"], at_year_end[0].value)
            if gap is not None:
                problems["year-end value"].append(f"{ticker} {year}: differs by {gap:.3%}")

    print(f"{compared} numbers compared")
    for area, lines in problems.items():
        print(f"{area}: {len(lines)} differ")
        for line in lines:
            print(f"  {line}")
    if not problems:
        print("Everything matches.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
