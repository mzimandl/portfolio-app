-- Company results as reported (annual and quarterly), used to work out P/E, P/B and P/S for
-- every past day, and the ratios Yahoo reports, saved once a day so their history grows.

CREATE TABLE statements (
    instrument_id INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    period        TEXT NOT NULL CHECK (period IN ('annual', 'quarterly')),
    period_end    TEXT NOT NULL CHECK (period_end GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    currency      TEXT NOT NULL REFERENCES currencies (code),  -- what the company reports in
    revenue       REAL,
    net_income    REAL,   -- attributable to common shareholders
    eps           REAL,   -- diluted, per share as counted today (Yahoo adjusts for splits)
    equity        REAL,   -- at the period end
    shares        REAL,   -- outstanding at the period end
    PRIMARY KEY (instrument_id, period, period_end)
) STRICT, WITHOUT ROWID;

-- A row with every ratio empty means: asked that day, the source has none (funds, crypto).
CREATE TABLE fundamentals (
    instrument_id  INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    date           TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    trailing_pe    REAL,
    forward_pe     REAL,
    price_to_book  REAL,
    price_to_sales REAL,
    ev_to_ebitda   REAL,
    market_cap     REAL,  -- in the instrument's currency
    PRIMARY KEY (instrument_id, date)
) STRICT, WITHOUT ROWID;
