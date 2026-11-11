# Portfolio app rewrite — plan

Rewrite of `../portfolio-app` (Sanic + Polars + React) as a Python + Streamlit app.
Goal: a personal portfolio tracker that stays reliable and easy to maintain for many years.

## Decisions

| Area | Decision |
|---|---|
| Language / UI | Python, Streamlit |
| Storage | SQLite, versioned migrations (`PRAGMA user_version`) |
| Data model | One unified `transactions` ledger |
| Old data | Imported from the old `portfolio.db` and verified against the old app's numbers |
| Price sources | Yahoo (yfinance) and manual valuations. Polygon and generic HTTP are dropped. |
| New in v1 | Edit/delete records, proper performance metrics (TWR, XIRR), correct historical charts, CSV import/export |
| Fees | Always in base currency, as in the old app |
| Splits | `split` transaction in the ledger; the price update suggests it when Yahoo reports a split, the user confirms |
| Dividends | Net amount received plus an optional withholding-tax field |
| Performance extras | Breakdown by type, benchmark comparison, profit split into price vs FX, invested per month/year |
| Tooling | `uv` + lockfile, `ruff`, `pytest` |

## Architecture rule

`core/` never imports Streamlit. The UI is a thin layer that calls `core`.
If Streamlit breaks or disappears, only `ui/` is rewritten.

```
portfolio-app-refactor/
  pyproject.toml, uv.lock
  config.sample.toml          # db path, base currency, locale
  src/portfolio/
    core/
      config.py
      db.py                   # connection, migrations runner
      migrations/0001_init.sql
      models.py               # dataclasses, TransactionKind enum
      repo.py                 # CRUD for instruments, transactions, valuations, prices, fx
      providers/
        base.py               # PriceProvider protocol
        yahoo.py              # prices + FX
      updater.py              # incremental price/FX refresh
      analytics/
        positions.py          # daily holdings per instrument
        overview.py           # current state per instrument
        timeseries.py         # value / invested / profit per day
        performance.py        # TWR, XIRR, per year / instrument / total
      csv_io.py               # import/export
    ui/
      app.py                  # navigation, sidebar (data freshness + refresh button)
      pages/overview.py, performance.py, charts.py,
            transactions.py, prices.py, settings.py
      formatting.py           # currency / percent formatting by locale
  scripts/import_legacy.py    # old portfolio.db -> new schema, with verification
  tests/
```

## Data model

```
currencies(code PK)
instrument_types(name PK)

instruments(
  id PK, ticker UNIQUE, name, type -> instrument_types,
  currency -> currencies,            -- quote currency
  dividend_currency -> currencies,
  valuation CHECK IN ('yahoo','manual'),
  yahoo_symbol,                      -- if different from ticker
  active
)

transactions(
  id PK, date, instrument_id -> instruments,
  kind CHECK IN ('buy','sell','deposit','withdrawal','dividend','staking_reward','split'),
  quantity,        -- units; always positive, direction comes from kind
  price,           -- per unit, in `currency` (NULL for deposit/dividend/staking)
  amount,          -- cash amount in `currency` (deposit/withdrawal/dividend)
  currency -> currencies,            -- currency actually paid/received
  fx_rate,         -- base currency per 1 unit of `currency` at the time of the transaction
  fee,             -- in base currency (as in the old app)
  tax,             -- optional withholding tax on a dividend, in `currency`; `amount` is net
  split_ratio,     -- new units per old unit (10 for a 10:1 split); only for kind = 'split'
  reinvested,      -- proceeds were reinvested (sell/withdrawal)
  note
)

valuations(instrument_id, date, value, PK(instrument_id, date))    -- manual instruments
prices(instrument_id, date, open, high, low, close, dividend, split, PK(instrument_id, date))
fx_rates(date, from_currency, to_currency, close, PK(date, from_currency, to_currency))
```

Numbers in the ledger (`quantity`, `price`, `amount`, `fx_rate`, `fee`) are stored as exact decimal
text and handled as `Decimal` in Python. Market prices and derived analytics use floats in Polars and
are rounded only for display.

### Mapping from the old database

| Old table | New rows |
|---|---|
| `trades` | `buy` (volume > 0) / `sell` (volume < 0); currency = instrument currency |
| `crypto` | `buy` / `sell` with the row's own `currency` |
| `deposits` | `deposit` (amount > 0) / `withdrawal` (amount < 0) |
| `dividends` | `dividend`, currency = instrument's `dividend_currency` |
| `staking` | `staking_reward` (quantity only) |
| `values` | `valuations` |
| `historical`, `fx` | `prices`, `fx_rates` |
| `base_rate` | `fx_rate = 1 / base_rate` (old value divides, new value multiplies) |
| evaluation `http` | only FFGLOB (inactive fund) uses it; FFGLOB and its rows are **not imported** |
| splits | NFLX 10:1 on 2025-11-17 becomes a `split` transaction during import |

## Known bugs in the old app that the rewrite fixes

- Price update picks first/last dates for only one ticker (missing `GROUP BY`).
- Charts use today's FX rate for every past date and ignore crypto and deposits.
- `/instruments/list?active=1` never returns the filtered list.
- FX update crashes when there are no crypto rows.
- Calculated dividends ignore crypto and splits.
- No edit or delete; no validation; no error reporting.

## Phases

1. **Scaffold** — `uv` project, package layout, ruff, pytest, git repo, config loading.
2. **Schema and repository** — migration runner, `0001_init.sql`, CRUD functions, tests on an in-memory DB.
3. **Legacy import** — `scripts/import_legacy.py`; saves the old app's `/overview/get` output as a
   fixture to compare against.
4. **Analytics** — positions, overview, time series (as-of joins of positions × prices × FX of that
   date), TWR and XIRR. Overview must match the legacy fixture per ticker; differences caused by
   fixed bugs are listed explicitly.
5. **Yahoo provider and updater** — incremental per instrument and currency pair, errors reported
   per ticker instead of only printed.
6. **UI** — Overview, Performance, Charts, Transactions (filterable editor with add/edit/delete),
   Prices, Settings; sidebar shows data freshness and a refresh button.
7. **CSV import/export** — full export of every table (backup); transaction import with preview.
8. **Docs** — README: install, run, backup, how to add a provider.

Each phase ends with passing tests and a commit.

## Details settled

- **Splits** — holdings are computed by replaying the ledger; a `split` multiplies the quantity held
  so far. Yahoo prices are already split-adjusted, so trades before a split are compared against
  adjusted prices by dividing their price by the later split ratios.
- **Benchmark** — a Yahoo symbol set in the config (e.g. an S&P 500 or MSCI World ETF). It is stored
  as an instrument of type `benchmark` with prices but no transactions, and is excluded from the
  portfolio totals. Comparison: portfolio TWR vs benchmark return over the same period, in base currency.
- **Price vs FX profit** — per instrument: FX profit = cost in trade currency × (current FX − FX at
  purchase); price profit = total profit − FX profit − staking rewards (same definition as the old Overview).
- **Invested per period** — net new money per month and per year, split into securities, crypto and deposits.
- **By type** — every Overview and Performance figure can be grouped by instrument type.
