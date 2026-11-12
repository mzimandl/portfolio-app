# Notes for AI agents

A personal portfolio tracker: Python, Streamlit, one SQLite file. One user, runs locally.
[README.md](README.md) explains use and the definitions of every number; [PLAN.md](PLAN.md)
records why things are the way they are. Read the README's "How the numbers are defined"
before touching a calculation. This file holds what those two do not: how to work here and
what has already gone wrong.

## The goal that decides most questions

The app has to keep working for many years with little upkeep. In practice:

- **No new dependencies** without asking. Runtime needs only `streamlit` and `yfinance`
  (pandas comes with Streamlit and is used in `ui/` only). Analytics are plain Python on
  purpose; the old app broke when Polars changed.
- **`core/` never imports Streamlit or `portfolio.ui`.** `tests/test_architecture.py` enforces
  it. Calculations go to `core/analytics/`, pages only format and draw.
- Prefer a small explicit rule over a clever general one, and write the rule down in the
  README table of definitions when it changes a number the user sees.

## Commands

```bash
uv run pytest
```

```bash
uv run ruff check
```

```bash
uv run ruff format
```

```bash
uv run streamlit run src/portfolio/ui/app.py
```

All three checks must pass before a commit. Line length is 100. `sqlite3` is not installed as
a command-line tool here: query the database with `uv run python` and the `sqlite3` module,
or better through `portfolio.core.repo` and `load_data`.

## The user and the data

- The user writes in Czech; answer in Czech. Code, UI texts, docs and commit messages are in
  English. Base currency is CZK, locale `cs`.
- `portfolio.db` in the project folder is the user's **real data**. It is git-ignored, as are
  `config.toml` and every `*.db`. Never put its contents into a commit, a test or a fixture.
- **Before changing data in it**: ask unless the user already said to, copy the file first
  (`portfolio.before-<what>.db`; the automatic daily copy in `backups/` may be older than
  the user's last edit), make the change through `repo` functions inside `with conn:`,
  then print the affected totals before and after. Net profit should usually stay the same
  when a record is only re-classified.
- A change of schema is a migration, never a manual edit (see below).
- The old app is in `../portfolio-app` (Sanic, Polars, React) and its database is the user's
  cloud-synced original. Do not modify either. `core/legacy_import.py` and the
  `scripts/*legacy*` files exist only for that one-off import.

## Layout

```
src/portfolio/core/
  config.py        config.toml: db, base_currency, locale, benchmark, separate_types
  db.py            connect(), migrate()
  backup.py        daily_backup(): dated copy before the day's first use
  migrations/      0001 … 0006, applied in order by PRAGMA user_version
  models.py        records; which fields each transaction kind requires or allows
  repo.py          all SQL. Functions never commit: the caller wraps them in `with conn:`
  analytics/
    data.py        load_data(): everything read once into PortfolioData (floats)
    positions.py   replaying one instrument's events: quantity, FIFO lots, sales, cash
    overview.py    current state per instrument; sales(); lots(); summarize()
    timeseries.py  DayPoint per calendar day; combine(); thin() for charts
    performance.py twr, xirr, yearly, monthly, drawdown, benchmark (holding_return, same_money)
    dividends.py   recorded dividends and those the price data reports
    checks.py      data-quality findings
    allocation.py  values against target shares; how to split new money
    taxes.py       sales by holding period, dividends and staking per year
  providers/       base.py is the interface, yahoo.py the only implementation
  updater.py       incremental download of prices and rates; split detection; benchmark
  csv_io.py        export of every table, import of transactions
src/portfolio/ui/
  app.py           navigation; each page module has a render() function
  shell.py         sidebar (freshness, Update prices) and split notices
  common.py        config, connection, cached portfolio(), scope picker, formatting helpers
  pages/           overview, performance, charts, dividends, taxes, transactions, prices, checks,
                   data (Import / export), settings
tests/             one file per core module, plus test_ui_smoke.py
```

## Data model rules

- One `transactions` ledger. Kinds: `buy`, `sell`, `deposit`, `withdrawal`, `dividend`,
  `staking_reward`, `staking_correction`, `split`, `fee`. **Numbers are always positive**; the
  kind gives the direction. Adding a kind means: `models.py` (enum, `_REQUIRED`/`_ALLOWED`),
  a migration that rebuilds the table (SQLite cannot alter a CHECK; copy
  `0004_staking_correction.sql`), `positions.apply`, the label in `ui/pages/transactions.py`,
  `VALID` in `tests/test_models.py`, the README table.
- What the user types (quantity, price, amount, rate, fee) is stored as decimal TEXT and is a
  `Decimal` in `models`/`repo`. Market data is REAL. `load_data` turns everything into floats
  for the calculations; rounding happens only for display.
- **`fx_rate` is base currency per 1 unit of the transaction's currency** (CZK per EUR). The
  old app stored the inverse. Fees are always in base currency.
- A trade's currency is what was really paid and may differ from the instrument's currency,
  which is the one its downloaded prices are in (CSG.AS is priced in EUR and bought in CZK;
  crypto is priced in EUR and sometimes bought in USD). `Lot.cost` is in the **instrument's**
  currency, converted at the market rate of the purchase day; `Lot.cost_base` is what was
  really paid. The value always comes from the downloaded price × the instrument currency's
  rate.
- Migrations: add the next numbered file; never edit one that exists, the user's database has
  already run it. Each runs in a transaction. Write a test like the ones in `tests/test_db.py`
  that runs the earlier migrations, inserts old-style rows, then migrates.
- No WAL mode: the database must stay a single file because it may live in a synced folder.

## Conventions the numbers rely on

- Sales use up the oldest units first (FIFO). Staking units cost nothing.
- A `sell` at price 0 means units really lost; it realises their cost as a loss.
- A transfer fee paid in coins is recorded as a `sell` at that day's market price with a
  `fee` of the same amount in base currency: no cash effect, the fee shows under Fees.
- A `staking_correction` takes units back from staking lots first and realises no loss.
- Returns: a fee counts as money put in, a dividend as money taken out, so returns include
  dividends and are after fees. `DayPoint.put_in` / `taken_out` already contain them.
- Time-weighted return: on the day of a trade the holding from the day before is first valued
  at the price of that day's first trade (`DayPoint.early_gain`), then the money put in joins
  it; money taken out counts until the end of its day. See `performance._day_growth`. Exact
  for purchases and for selling everything; a partial sale away from the close leaves a
  small error for the rest of that day.
- The Taxes page states facts and applies two configurable rules (`TaxRules`). Do not build
  more tax law into it without the user asking; tax rules change and differ by year.
- `Sale.parts` says which purchases a sale took its units from; taxes and the sales table
  both rely on FIFO there.
- Manual instruments (savings, pension): value = last entered valuation + deposits −
  withdrawals on that day or later. A deposit on the valuation's own day is added on top.
- Types listed in `separate_types` (the user has `["savings"]`) get their own totals on the
  Overview and are left out of the default scope elsewhere. Use `common.is_separate()`.
- The benchmark is an instrument of type `benchmark` with prices and no transactions, so it
  never appears in `data.instrument_ids()`.
- Downloaded prices are real closes (`auto_adjust=False`) and split-adjusted by Yahoo. A
  quantity from before a split is scaled with the later split ratios when compared with them.

- A finding of the Checks page has an `identity` (check, instrument, day, key). The user can
  mark it as checked (`reviewed_findings` table); it shows again when the identity changes.
  A new check must give a `key` whenever its detail text contains something that changes by
  itself, like a value at today's price.
- In tests, a read through the fixture connection leaves a transaction open and blocks the
  page's writes ("database is locked"): call `database.rollback()` after reading.

## Streamlit traps already hit

- **`st.cache_resource` / `st.cache_data` do not hash arguments whose name starts with an
  underscore.** The data cache once ignored the database's modification time for that reason
  and showed stale numbers until a restart. The cache key is `(mtime_ns, size)` of the file.
- **Restart the server after changing Python code.** Pages are imported modules; a browser
  reload often keeps running the old code.
- `Loaded` from `common.portfolio()` is shared between reruns: treat it as read-only.
- `AppTest` cannot follow a rerun through `st.navigation`. Test a page on its own with
  `run_page("name")` in `tests/test_ui_smoke.py`; sidebar and split notices live in
  `ui/shell.py` for the same reason. Wrap results in `clean(at)` to fail on exceptions.
- Page tests address tables by position (`at.dataframe[2]`). Adding a table to a page shifts
  them; update the indices in the same change.
- Widget keys in the transaction form include the edited row and the kind, and the tables'
  keys include a version counter, so a selection does not survive a save. Keep that.
- Tables are tinted with a pandas Styler (`_tinted` in `pages/overview.py`); number formats
  come from `column_config` and still apply.
- Streamlit's own settings in `.streamlit/config.toml` are read only when the app starts from
  the project folder.

## Working style that fits this project

- Every change of a calculation gets a test with numbers small enough to check by hand, and a
  comment giving the arithmetic. Then run it on the real database and compare with the result
  before the change; say which numbers moved and why.
- Verify UI changes in the running app, not only with `AppTest`.
- One commit per finished piece of work, message in the imperative, with the reason in the
  body. Update README (use, definitions) and PLAN (decisions) in the same commit.
- `# fmt: skip` is used where a hand-laid-out list or call reads better than the formatter's.

## State of things (2026-11-12)

Everything planned is built: the eight phases in PLAN.md, then staking corrections, benchmark
with the same cash flows, sales and purchases-held tables, drawdown, allocation shares,
monthly returns, the Dividends and Checks pages, consistent numbers for trades paid in
another currency, automatic daily backups, marking findings as checked, a tax overview, target allocation and
a more exact time-weighted return on trade days. The Checks page lists the records in the user's data that still look wrong;
they are the user's to verify against statements, not something to fix unasked.
