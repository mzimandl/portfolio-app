-- Results can come from more than one source (Yahoo, SEC EDGAR); each is kept on its own.
-- SQLite cannot change a primary key, so the table is rebuilt.

CREATE TABLE statements_new (
    instrument_id INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    source        TEXT NOT NULL DEFAULT 'yahoo' CHECK (source IN ('yahoo', 'sec')),
    period        TEXT NOT NULL CHECK (period IN ('annual', 'quarterly')),
    period_end    TEXT NOT NULL CHECK (period_end GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    currency      TEXT NOT NULL REFERENCES currencies (code),
    revenue       REAL,
    net_income    REAL,
    eps           REAL,
    equity        REAL,
    shares        REAL,
    PRIMARY KEY (instrument_id, source, period, period_end)
) STRICT, WITHOUT ROWID;

INSERT INTO statements_new
    (instrument_id, source, period, period_end, currency, revenue, net_income, eps, equity, shares)
SELECT instrument_id, 'yahoo', period, period_end, currency, revenue, net_income, eps, equity,
       shares
FROM statements;

DROP TABLE statements;
ALTER TABLE statements_new RENAME TO statements;
