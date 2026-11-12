-- A new kind, 'staking_correction': staking units taken back. They are removed from the
-- staking units held and realise no loss, unlike a sell at price 0.
-- SQLite cannot change a CHECK constraint, so the table is rebuilt.

CREATE TABLE transactions_new (
    id            INTEGER PRIMARY KEY,
    date          TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    instrument_id INTEGER NOT NULL REFERENCES instruments (id),
    kind          TEXT NOT NULL CHECK (kind IN (
                      'buy', 'sell', 'deposit', 'withdrawal', 'dividend', 'staking_reward',
                      'staking_correction', 'split', 'fee')),
    quantity      TEXT,                               -- units, positive; direction comes from kind
    price         TEXT,                               -- per unit, in `currency`
    amount        TEXT,                               -- cash in `currency`; net for dividends
    currency      TEXT REFERENCES currencies (code),  -- currency actually paid or received
    fx_rate       TEXT,                               -- base currency per 1 unit of `currency`
    fee           TEXT NOT NULL DEFAULT '0',          -- in base currency
    tax           TEXT,                               -- withholding tax on a dividend, in `currency`
    split_ratio   TEXT,                               -- new units per old unit
    note          TEXT
) STRICT;

INSERT INTO transactions_new
    (id, date, instrument_id, kind, quantity, price, amount, currency, fx_rate, fee, tax,
     split_ratio, note)
SELECT id, date, instrument_id, kind, quantity, price, amount, currency, fx_rate, fee, tax,
       split_ratio, note
FROM transactions;

DROP TABLE transactions;
ALTER TABLE transactions_new RENAME TO transactions;

CREATE INDEX transactions_instrument_date ON transactions (instrument_id, date);
CREATE INDEX transactions_date ON transactions (date);

-- The legacy import had stored the old app's negative staking rows as sells at price 0.
UPDATE transactions
SET kind = 'staking_correction', price = NULL, currency = NULL, fx_rate = NULL, note = NULL
WHERE kind = 'sell' AND note = 'Negative staking in the old app';
