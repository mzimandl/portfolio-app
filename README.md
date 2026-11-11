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

## Development

```bash
uv run pytest
uv run ruff check
uv run ruff format
```

Code under `src/portfolio/core` must not import Streamlit; `tests/test_architecture.py` checks this.
