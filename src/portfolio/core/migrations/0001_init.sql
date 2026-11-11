-- Exact numbers (quantities, money, rates entered by the user) are stored as decimal TEXT.
-- Market data (prices, FX) is stored as REAL. Dates are ISO 'YYYY-MM-DD' TEXT.

CREATE TABLE currencies (
    code TEXT PRIMARY KEY CHECK (length(code) = 3 AND code = upper(code))
) STRICT;

CREATE TABLE instrument_types (
    name TEXT PRIMARY KEY CHECK (length(name) > 0)
) STRICT;

CREATE TABLE instruments (
    id                INTEGER PRIMARY KEY,
    ticker            TEXT NOT NULL UNIQUE CHECK (length(ticker) > 0),
    name              TEXT,
    type              TEXT NOT NULL REFERENCES instrument_types (name) ON UPDATE CASCADE,
    currency          TEXT NOT NULL REFERENCES currencies (code),
    dividend_currency TEXT REFERENCES currencies (code),
    valuation         TEXT NOT NULL CHECK (valuation IN ('yahoo', 'manual')),
    yahoo_symbol      TEXT,
    active            INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
) STRICT;

CREATE TABLE transactions (
    id            INTEGER PRIMARY KEY,
    date          TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    instrument_id INTEGER NOT NULL REFERENCES instruments (id),
    kind          TEXT NOT NULL CHECK (kind IN (
                      'buy', 'sell', 'deposit', 'withdrawal', 'dividend', 'staking_reward', 'split', 'fee')),
    quantity      TEXT,                               -- units, positive; direction comes from kind
    price         TEXT,                               -- per unit, in `currency`
    amount        TEXT,                               -- cash in `currency`; net for dividends
    currency      TEXT REFERENCES currencies (code),  -- currency actually paid or received
    fx_rate       TEXT,                               -- base currency per 1 unit of `currency`
    fee           TEXT NOT NULL DEFAULT '0',          -- in base currency
    tax           TEXT,                               -- withholding tax on a dividend, in `currency`
    split_ratio   TEXT,                               -- new units per old unit
    reinvested    INTEGER NOT NULL DEFAULT 0 CHECK (reinvested IN (0, 1)),
    note          TEXT
) STRICT;

CREATE INDEX transactions_instrument_date ON transactions (instrument_id, date);
CREATE INDEX transactions_date ON transactions (date);

CREATE TABLE valuations (
    instrument_id INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    date          TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    value         TEXT NOT NULL,
    PRIMARY KEY (instrument_id, date)
) STRICT, WITHOUT ROWID;

CREATE TABLE prices (
    instrument_id INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    date          TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    open          REAL,
    high          REAL,
    low           REAL,
    close         REAL NOT NULL,
    dividend      REAL NOT NULL DEFAULT 0,
    split         REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (instrument_id, date)
) STRICT, WITHOUT ROWID;

CREATE TABLE fx_rates (
    date          TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    from_currency TEXT NOT NULL REFERENCES currencies (code),
    to_currency   TEXT NOT NULL REFERENCES currencies (code),
    close         REAL NOT NULL,
    PRIMARY KEY (from_currency, to_currency, date)
) STRICT, WITHOUT ROWID;
