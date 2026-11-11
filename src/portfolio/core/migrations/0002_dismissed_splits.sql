-- A split reported by the price source is offered to the user as a 'split' transaction.
-- Splits the user declined (or that the ledger already accounts for) are remembered here.

CREATE TABLE dismissed_splits (
    instrument_id INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    date          TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    PRIMARY KEY (instrument_id, date)
) STRICT, WITHOUT ROWID;

-- Splits already in the database come from the old app, whose ledger was adjusted by hand.
INSERT INTO dismissed_splits (instrument_id, date)
SELECT instrument_id, date FROM prices WHERE split != 0;
