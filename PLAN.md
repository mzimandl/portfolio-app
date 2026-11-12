# Portfolio app rewrite — plan

**Status: all eight phases are finished.** This file is kept as the record of what was decided
and why; [README.md](README.md) describes how to use and maintain the app.

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
| Returns | Dividends count as money received and fees as money paid, so returns are after fees |

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
        data.py               # everything loaded once; exchange rates resolved
        positions.py          # replaying one instrument's ledger into a position
        overview.py           # current state per instrument, sums by type
        timeseries.py         # value / invested / profit per day
        performance.py        # TWR, XIRR, per year, benchmark, new money per period
      csv_io.py               # import/export
    ui/
      app.py                  # entry point: navigation between pages
      shell.py                # sidebar (data freshness, update button), split notices
      common.py               # config, database access, cached data, scope picker
      pages/overview.py, performance.py, charts.py,
            transactions.py, prices.py, settings.py
      formatting.py           # numbers to text and back, by locale (no Streamlit)
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
  kind CHECK IN ('buy','sell','deposit','withdrawal','dividend','staking_reward',
                 'staking_correction','split','fee'),
  quantity,        -- units; always positive, direction comes from kind
  price,           -- per unit, in `currency` (NULL for deposit/dividend/staking)
  amount,          -- cash amount in `currency` (deposit/withdrawal/dividend)
  currency -> currencies,            -- currency actually paid/received
  fx_rate,         -- base currency per 1 unit of `currency` at the time of the transaction
  fee,             -- in base currency (as in the old app)
  tax,             -- optional withholding tax on a dividend, in `currency`; `amount` is net
  split_ratio,     -- new units per old unit (10 for a 10:1 split); only for kind = 'split'
  note
)

valuations(instrument_id, date, value, PK(instrument_id, date))    -- manual instruments
prices(instrument_id, date, open, high, low, close, dividend, split, PK(instrument_id, date))
fx_rates(date, from_currency, to_currency, close, PK(date, from_currency, to_currency))
```

Numbers in the ledger (`quantity`, `price`, `amount`, `fx_rate`, `fee`) are stored as exact decimal
text and handled as `Decimal` in Python. Market prices and derived analytics use floats and are rounded only for display.

Analytics are plain Python, without Polars: the data is small (the whole day-by-day history
computes in under 0.1 s) and the old app's Polars code had already stopped working on the
current Polars release.

### Mapping from the old database

| Old table | New rows |
|---|---|
| `trades` | `buy` (volume > 0) / `sell` (volume < 0); currency = instrument currency |
| `crypto` | `buy` / `sell` with the row's own `currency` |
| `deposits` | `deposit` (amount > 0) / `withdrawal` (amount < 0); rows with only a fee become `fee` |
| `dividends` | `dividend`, currency = instrument's `dividend_currency` |
| `staking` | `staking_reward` (quantity only); negative rows become a `staking_correction` |
| `values` | `valuations` |
| `historical`, `fx` | `prices`, `fx_rates` |
| `base_rate` | `fx_rate = 1 / base_rate` (old value divides, new value multiplies) |
| evaluation `http` | only FFGLOB (inactive fund) uses it; FFGLOB and its rows are **not imported** |
| splits | none imported: the NFLX trades before its 10:1 split (2025-11-17) were already rewritten in post-split units in the old database |
| unknown tickers | rows for tickers missing from `instruments` (ADA2, BTC2, SOL2, SGLN) are skipped, as the old app ignored them |

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
3. **Legacy import** — `scripts/import_legacy.py` copies the data and compares totals per ticker
   between both databases. `scripts/legacy_reference.py` runs the old app's own calculations and
   saves them to `legacy/` (git-ignored) as reference numbers for phase 4.
4. **Analytics** — positions, overview, day-by-day history, TWR and XIRR, per year, benchmark,
   new money per period. `scripts/compare_legacy.py` checks them against the old app's output.
   Result: 665 numbers compared, 4 differ, all intended — ETH `rewards` and price profit (negative
   staking is now a sell at price 0) and price profit of the two savings accounts (the old app
   left it empty).
5. **Yahoo provider and updater** — incremental per instrument and currency pair, saved one by
   one so a failure of one ticker is reported and the rest still updates. Stores real closing
   prices (`auto_adjust=False`); the old app stored dividend-adjusted ones, which understated
   past values of dividend payers. A new split reloads that instrument's history and waits in
   `pending_splits` until the user adds a `split` transaction or dismisses it
   (`dismissed_splits`, migration 2).
6. **UI** — Overview, Performance, Charts, Transactions (filterable ledger with add, edit and
   delete, plus manual valuations), Prices, Settings. The sidebar shows data freshness and the
   update button; reported splits appear on every page until added or dismissed. Each page is a
   `render()` function so it can be tested on its own.
7. **CSV import/export** — every table as CSV (instruments named by ticker) and the database
   file itself as downloads; transactions imported from CSV with a preview, errors per line and
   detection of rows already in the database. Importing is all or nothing.
8. **Docs** — README: setup, use, definitions of the numbers, prices, backup, maintenance.

Each phase ends with passing tests and a commit.

## Added after the eight phases

Staking corrections (migration 4), benchmark with the same cash flows, list of sales, drawdown,
allocation shares, monthly returns, purchases still held, the Dividends page, the Checks page with findings that
can be marked as checked (migration 5), and automatic daily backups.

## Details settled

- **Staking corrections** — the old app stored staking units taken back as negative rewards.
  They were first imported as sells at price 0, which booked a loss on the oldest bought units.
  Since migration 4 they are `staking_correction` rows: removed from the staking units held,
  with no realised loss. A sell at price 0 remains the way to record units really lost.

- **No `reinvested` flag** — the old app marked sales whose proceeds went into other
  investments, because it dropped sold positions from its totals. Here the sale and the next buy
  are both in the ledger and the gain is reported as realised profit (FIFO lots), so the flag was
  removed (migration 3). Old CSV files with that column still import; the column is ignored.

- **Splits** — holdings are computed by replaying the ledger; a `split` multiplies the quantity held
  so far. Phase 5 must re-download an instrument's whole price history when a split appears,
  because prices stored before the split are in the old units. Yahoo prices are already split-adjusted, so trades before a split are compared against
  adjusted prices by dividing their price by the later split ratios.
- **Benchmark** — a Yahoo symbol set in the config (e.g. an S&P 500 or MSCI World ETF). It is stored
  as an instrument of type `benchmark` with prices but no transactions, and is excluded from the
  portfolio totals. Comparison: portfolio TWR vs benchmark return (dividends reinvested) over the
  same period, in base currency, and the same cash flows invested in the benchmark instead.
- **Price vs FX profit** — per instrument: FX profit = cost in the instrument's currency × current
  FX − what was paid; price profit = unrealised profit − FX profit − staking rewards. A purchase
  paid in another currency is converted to the instrument's at the market rate of its day (the old
  Overview used the trade currency, which gave no FX effect for a EUR share paid in CZK).
- **Invested per period** — net new money per month and per year, split into securities, crypto and deposits.
- **By type** — every Overview and Performance figure can be grouped by instrument type.
