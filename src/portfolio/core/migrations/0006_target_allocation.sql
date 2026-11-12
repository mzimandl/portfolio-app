-- The share of the investments each instrument type should have, in percent.

CREATE TABLE target_allocation (
    type  TEXT PRIMARY KEY REFERENCES instrument_types (name) ON UPDATE CASCADE ON DELETE CASCADE,
    share TEXT NOT NULL
) STRICT, WITHOUT ROWID;
