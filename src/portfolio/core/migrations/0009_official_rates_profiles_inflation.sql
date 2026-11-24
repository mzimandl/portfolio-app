-- Exchange rates of the Czech National Bank: base currency (CZK) per 1 unit of `currency`.
-- A Czech tax return converts with these, either day by day or as the yearly unified rate.
CREATE TABLE official_rates (
    currency TEXT NOT NULL CHECK (length(currency) = 3 AND currency = upper(currency)),
    date     TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    rate     REAL NOT NULL,
    PRIMARY KEY (currency, date)
) STRICT, WITHOUT ROWID;

-- What a company does and where it is based. From Yahoo, or entered by hand (manual = 1,
-- never overwritten by an update): funds and coins have none of their own.
CREATE TABLE profiles (
    instrument_id INTEGER PRIMARY KEY REFERENCES instruments (id) ON DELETE CASCADE,
    sector        TEXT,
    country       TEXT,
    fetched       TEXT NOT NULL CHECK (fetched GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    manual        INTEGER NOT NULL DEFAULT 0 CHECK (manual IN (0, 1))
) STRICT;

-- A consumer price index by month (dated the month's first day), e.g. Eurostat's HICP with
-- 2015 = 100, per region ("CZ").
CREATE TABLE inflation (
    region TEXT NOT NULL CHECK (length(region) > 0),
    month  TEXT NOT NULL CHECK (month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-01'),
    value  REAL NOT NULL,
    PRIMARY KEY (region, month)
) STRICT, WITHOUT ROWID;
