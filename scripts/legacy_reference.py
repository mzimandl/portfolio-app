"""Save the old app's own calculations as reference numbers for the new analytics.

Runs the old server code against its database (opened read-only) and writes the JSON its
endpoints would return. Needs the old app's dependencies, not this project's:

    uv run --no-project --with sanic --with sanic-ext --with yfinance --with polygon-api-client \
        --with 'polars==1.36.1' --with requests --with jinja2 --with pydantic \
        python scripts/legacy_reference.py PATH_TO_OLD_APP legacy/

Take the reference and run the legacy import from the same state of the old database,
otherwise the latest prices differ.
"""

import asyncio
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace


def main() -> int:
    old_app, out_dir = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # The old server opens its database on import; make sure it cannot write to it.
    real_connect = sqlite3.connect

    def read_only_connect(path, *args, **kwargs):
        return real_connect(f"file:{Path(path).resolve()}?mode=ro", *args, uri=True, **kwargs)

    sqlite3.connect = read_only_connect
    os.chdir(old_app / "api")
    sys.path.insert(0, str(old_app / "api"))
    import server  # noqa: PLC0415

    def request(**args):
        return SimpleNamespace(args=args)

    endpoints = {
        "overview": (server.overview, request()),
        "performance": (server.performance, request()),
        "investments_year": (server.investments, request(span="year")),
        "investments_month": (server.investments, request(span="month")),
        "dividends_calc": (server.dividends_calc, request()),
    }
    for name, (handler, req) in endpoints.items():
        response = asyncio.run(handler(req))
        (out_dir / f"{name}.json").write_bytes(response.body)
        print(f"{name}: {len(response.body)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
