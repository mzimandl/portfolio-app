# Portfolio

Personal portfolio tracker: Python, Streamlit, SQLite. See [PLAN.md](PLAN.md) for the design.

## Setup

```bash
uv sync
cp config.sample.toml config.toml
```

## Run

```bash
uv run streamlit run src/portfolio/ui/app.py
```

The config file is read from `config.toml` in the current directory, or from the path in the
`PORTFOLIO_CONFIG` environment variable.

## Importing data from the old app

```bash
uv run python scripts/import_legacy.py PATH_TO_OLD_DB --dry-run
```

Without `--dry-run` the data is saved to the database named in `config.toml`, which must be empty.
The old database is only read. Nothing is saved unless every total matches the old data.

## Development

```bash
uv run pytest
uv run ruff check
uv run ruff format
```

Code under `src/portfolio/core` must not import Streamlit; `tests/test_architecture.py` checks this.
