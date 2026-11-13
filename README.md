# Portfolio

A personal portfolio tracker: stocks, ETFs, crypto and manually valued accounts, in one base
currency. Python, Streamlit and a single SQLite file. Built to keep working for years with
little upkeep; [PLAN.md](PLAN.md) records the design decisions. The app it replaced is kept in
the `legacy` branch. [AGENTS.md](AGENTS.md) holds working notes for
AI agents (and anyone else changing the code).

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
| `backup_dir` | Optional folder for the automatic backups. Default: `backups` next to the database. |
| `backup_keep` | Optional number of automatic backups to keep. Default 30; 0 switches them off. |
| `tax_holding_years` | Optional. How long units have to be held for their sale to count as exempt on the Taxes page. Default 3. |
| `tax_proceeds_limit` | Optional. Yearly proceeds from sales up to which all of them count as exempt. Default 100000. |
| `tax_crypto_types` | Optional. Instrument types for which that limit is counted apart from the securities. Default `["crypto"]`. |
| `separate_types` | Optional list of instrument types reported apart from the investments, e.g. `["savings"]`. They get their own totals on the Overview and are left out of the default view of returns and charts. |

## Using it

Start in **Settings**: add currencies, instrument types and instruments. Then record what
happens in **Transactions**.

| Page | Shows |
|---|---|
| Overview | What you hold now, what it cost, and the profit split into price, exchange rate and staking. With a target allocation set, how far each type is from it and how to split new money. Below, every sale and what it realised, and the purchases still held with their age. |
| Performance | Returns for the portfolio, a type or one instrument; the deepest drop; by year and by month; each instrument's part of the profit; against the benchmark; new money per year or month. |
| Charts | Value, money invested, profit and the drop from the high, day by day. |
| Dividends | Received per year and instrument, yield on cost and on value, and what the price data says was due. |
| Taxes | What you hold split by the holding period; a year's sales by the purchases they used, with what is left after the exemptions; dividends and staking of the year. |
| Transactions | The ledger: filter, add, edit, delete. A second tab holds manual valuations. |
| Prices | Stored prices and exchange rates. |
| Checks | Things that look wrong or out of date: old prices, trade prices and exchange rates far from the market, leftovers, dividends not recorded. It changes none of your records. A finding you looked at can be marked as checked; it stays hidden until the record behind it changes. |
| Import / export | Backup downloads and CSV import of transactions. |
| Settings | Instruments, currencies, instrument types, target allocation. |

### Transaction kinds

Numbers are always positive; the kind gives the direction.

| Kind | Fields | Meaning |
|---|---|---|
| `buy`, `sell` | quantity, price, currency, exchange rate | A trade, in the currency you really paid or received. It may differ from the instrument's: see below. |
| `deposit`, `withdrawal` | amount, currency | Money into or out of a manually valued instrument (savings, funds). |
| `dividend` | amount, currency, optional tax | The net amount received; tax is what was withheld. |
| `staking_reward` | quantity | Units received for free. |
| `staking_correction` | quantity | Staking units taken back. They come off the staking units you hold, with no loss. |
| `split` | ratio | New units per old unit, e.g. 10 for a 10:1 split. |
| `fee` | fee | A charge on its own, not tied to another transaction. |

Every kind can also carry a fee, always in base currency. The exchange rate is base currency
per 1 unit of the transaction's currency. On deposits, withdrawals and dividends it may be
left empty: the market rate of that day is used.

### Paying in another currency than the instrument's

An instrument's currency is the one its downloaded prices are in. A trade can be in any
currency: a share priced in EUR bought for CZK on another exchange, or a coin priced in EUR
bought for USD. Enter the price and currency you really paid. The value always comes from the
downloaded price and the exchange rate of the instrument's currency, and the purchase is
converted to that currency at the market rate of its day, so the average buy price and the
split into price and exchange rate are the same whatever you paid with.

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
| From exchange rate | Part of the unrealised profit: what those units cost in the instrument's currency, at today's rate, minus what you paid. |
| Staking rewards | Part of the unrealised profit: staking units still held × today's price. |
| From price | The rest of the unrealised profit. |
| Realised profit | On units sold: what you got for them minus what they had cost. Units from staking cost nothing; units lost (sold at price 0) realise their cost as a loss. |
| Profit | Unrealised + realised, which equals value + sold − bought. |
| Net profit | Profit + dividends − fees. |
| Return (time-weighted) | How the investments did, regardless of when money was added. Not annualised. On the day of a trade the holding is first valued at the trade's price, so new money earns only from the price it was invested at. |
| Yearly return on your money | XIRR: the yearly rate earned given when each payment was made. |
| Deepest drop | The largest fall of the time-weighted return from a high. Measured on the return, so new money does not hide it. |
| Share | An instrument's, type's or currency's part of the value of all investments. |
| To be on target | Target share × value of all investments − value of the type. |
| Buy now | The new money split between the types that would still be below their target after it is added, in proportion to how far below. Nothing is sold. |

**Taxes.** The Taxes page lists facts and applies two rules from the config file: a sale of
units held longer than `tax_holding_years` is exempt, and all sales of a year are exempt when
their proceeds do not exceed `tax_proceeds_limit`, counted apart for securities and crypto.
"Profit not exempt" is the profit on units held shorter in a year over the limit; fees are not
deducted. The same rules are applied to every year, also to years when the law was different.
Amounts use the exchange rates you entered, which may not be the ones a tax office expects.
It is an overview to work from, not tax advice.

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

**Automatic.** Before the app or the price script first uses the database on a day, it copies
it to the `backups` folder as `portfolio-YYYY-MM-DD.db`, so each copy holds the state from
before that day's changes. No copy is made when nothing changed since the last one. The
newest 30 are kept. To go back, stop the app and put a copy in place of the database file.
If the database lives in a synced folder, the copies are synced with it; set `backup_dir` to
keep them elsewhere.

**By hand.** The whole database is the one file named in `config.toml`. Copying it is a
complete backup; putting it back is the restore. The *Import / export* page offers that file as a download,
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
    backup.py           dated copies of the database
    migrations/         numbered SQL files, applied in order on start
    models.py           records and the rules for each transaction kind
    repo.py             reading and writing records
    analytics/          positions, overview, daily history, returns, dividends, checks, allocation, taxes
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
(`0007_….sql`). It runs once, in a transaction, the next time the app or a script starts.
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
