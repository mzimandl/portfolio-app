# Portfolio

A personal portfolio tracker: stocks, ETFs, crypto and manually valued accounts, in one base
currency. Python, Streamlit and a single SQLite file. Built to keep working for years with
little upkeep; [PLAN.md](PLAN.md) records the design decisions.

## Quick start

Needs [uv](https://docs.astral.sh/uv/). It installs the right Python by itself.

```bash
uv sync
```

```bash
cp config.sample.toml config.toml
```

```bash
uv run streamlit run src/portfolio/ui/app.py
```

The app opens at http://localhost:8501 and listens on this computer only.

## Configuration

`config.toml` is read from the current directory, or from the path in the `PORTFOLIO_CONFIG`
environment variable.

| Setting | Meaning |
|---|---|
| `db` | Path of the SQLite database. Relative paths are relative to the config file. Created on first start. |
| `base_currency` | Currency everything is reported in, e.g. `CZK`. |
| `locale` | Number formatting: `cs`, `sk`, `de` or `en`. |
| `benchmark` | Optional Yahoo symbol to compare returns against, e.g. `VWCE.DE`. |
| `separate_types` | Optional list of instrument types reported apart from the investments, e.g. `["savings"]`. They get their own totals on the Overview and are left out of the default view of returns and charts. |

## Using it

Start in **Settings**: add currencies, instrument types and instruments. Then record what
happens in **Transactions**.

| Page | Shows |
|---|---|
| Overview | What you hold now, what it cost, and the profit split into price, exchange rate and staking. Below it, every sale and what it realised. |
| Performance | Returns for the portfolio, a type or one instrument; by year; against the benchmark; new money per year or month. |
| Charts | Value, money invested and profit, day by day. |
| Transactions | The ledger: filter, add, edit, delete. A second tab holds manual valuations. |
| Prices | Stored prices and exchange rates. |
| Import / export | Backup downloads and CSV import of transactions. |
| Settings | Instruments, currencies, instrument types. |

### Transaction kinds

Numbers are always positive; the kind gives the direction.

| Kind | Fields | Meaning |
|---|---|---|
| `buy`, `sell` | quantity, price, currency, exchange rate | A trade. The currency may differ from the instrument's (crypto bought for USD). |
| `deposit`, `withdrawal` | amount, currency | Money into or out of a manually valued instrument (savings, funds). |
| `dividend` | amount, currency, optional tax | The net amount received; tax is what was withheld. |
| `staking_reward` | quantity | Units received for free. |
| `staking_correction` | quantity | Staking units taken back. They come off the staking units you hold, with no loss. |
| `split` | ratio | New units per old unit, e.g. 10 for a 10:1 split. |
| `fee` | fee | A charge on its own, not tied to another transaction. |

Every kind can also carry a fee, always in base currency. The exchange rate is base currency
per 1 unit of the transaction's currency. On deposits, withdrawals and dividends it may be
left empty: the market rate of that day is used.

### Two ways an instrument is valued

- **Yahoo:** quantity held × the latest downloaded price.
- **By hand:** the last value you entered under *Manual valuations*, plus deposits and minus
  withdrawals made on that day or later. A value entered on the day of a deposit should
  therefore be the value before that deposit; the valuations table points such days out.

### How the numbers are defined

| Number | Definition |
|---|---|
| Cost | What the units you still hold cost, at the exchange rates of their purchases. Sales use up the oldest units first (FIFO). |
| Unrealised profit | Value − cost. |
| From exchange rate | Part of the unrealised profit: what those units would cost at today's rate minus what they cost then. |
| Staking rewards | Part of the unrealised profit: staking units still held × today's price. |
| From price | The rest of the unrealised profit. |
| Realised profit | On units sold: what you got for them minus what they had cost. Units from staking cost nothing; units lost (sold at price 0) realise their cost as a loss. |
| Profit | Unrealised + realised, which equals value + sold − bought. |
| Net profit | Profit + dividends − fees. |
| Return (time-weighted) | How the investments did, regardless of when money was added. Not annualised. |
| Yearly return on your money | XIRR: the yearly rate earned given when each payment was made. |

**Benchmark.** With `benchmark` set, Performance compares in two ways. Its return is that of
holding it for the whole period with dividends reinvested, comparable with the time-weighted
return. "Your money in the benchmark" puts the same amounts in and takes them out on the same
days, which is comparable with the yearly return on your money and tells how far ahead or
behind you are. No fees or taxes are charged on the benchmark side.

Both returns include dividends and are after fees. A manually valued account that gains value
you did not deposit (an employer's pension contribution, for example) shows that as return,
which can make the time-weighted figure very large.

## Prices

The **Update prices** button, or:

```bash
uv run python scripts/update_prices.py
```

It downloads what is new since the last update for every active instrument you hold and every
currency in use. `--full` downloads all histories again. A ticker that fails is reported and
the rest still updates.

**Splits.** When Yahoo reports a split, a notice appears on every page. Choose *Add split* if
your recorded quantities are from before the split, or *Dismiss* if you already rewrote them.
Until you decide, that instrument's value is wrong.

**When Yahoo stops working.** Yahoo has no official API and the `yfinance` package breaks
now and then. First try a newer version:

```bash
uv lock --upgrade-package yfinance
```

If that does not help, everything that touches Yahoo is in
`src/portfolio/core/providers/yahoo.py`. Another source is a class with the three methods
described in `src/portfolio/core/providers/base.py`, returned from `provider()` in
`src/portfolio/ui/common.py` and used in `scripts/update_prices.py`.

## Backup

The whole database is the one file named in `config.toml`. Copying it is a complete backup;
putting it back is the restore. The *Import / export* page offers that file as a download,
plus a zip with every table as CSV. From the command line:

```bash
uv run python scripts/export_csv.py FOLDER
```

The database deliberately stays a single file (no WAL mode), so it can live in a synced
folder. Do not open the app on two computers at the same time.

## Maintenance

```bash
uv run pytest
```

```bash
uv run ruff check
```

```bash
uv run ruff format
```

**Upgrading dependencies.** The versions in `uv.lock` are the ones the app was tested with,
and it keeps working with them as long as you like. To upgrade, run `uv lock --upgrade`, then
`uv sync` and the tests. If something breaks, `git checkout uv.lock` goes back.

**Where things are.**

```
src/portfolio/
  core/                 no Streamlit in here (a test enforces it)
    config.py           the config file
    db.py               connection, migrations runner
    migrations/         numbered SQL files, applied in order on start
    models.py           records and the rules for each transaction kind
    repo.py             reading and writing records
    analytics/          positions, overview, daily history, returns
    providers/          sources of prices; yahoo.py is the only one
    updater.py          downloading new prices and rates
    csv_io.py           CSV export and import
    legacy_import.py    one-off import from the old app
  ui/                   Streamlit; each page is a render() function
scripts/                command-line entry points
tests/
```

**If Streamlit ever has to go**, only `ui/` is rewritten. The calculations, the storage and
the price updates do not depend on it.

**Changing the database layout.** Add the next numbered file to `core/migrations/`
(`0005_….sql`). It runs once, in a transaction, the next time the app or a script starts.
Never edit a migration that has already run on your database.

**Numbers.** What you type (quantities, prices, amounts, rates) is stored as exact decimal
text. Market prices and everything calculated from them are ordinary floating-point numbers,
rounded only for display.

## Importing from the old app

One-off, into an empty database:

```bash
uv run python scripts/import_legacy.py PATH_TO_OLD_DB --dry-run
```

Without `--dry-run` the data is saved to the database named in `config.toml`. The old database
is only read, and nothing is saved unless every total per ticker matches the old data.
`scripts/legacy_reference.py` and `scripts/compare_legacy.py` compare the new calculations
with the old app's own output; they are only meaningful right after an import.
