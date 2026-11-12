-- Findings of the Checks page that the user looked at and found in order. They stay hidden
-- as long as the finding stays the same; `key` is what makes it "the same".

CREATE TABLE reviewed_findings (
    check_name    TEXT NOT NULL,
    instrument_id INTEGER NOT NULL REFERENCES instruments (id) ON DELETE CASCADE,
    date          TEXT NOT NULL DEFAULT '',   -- '' for findings about the instrument as a whole
    key           TEXT NOT NULL,
    reviewed_on   TEXT NOT NULL,
    PRIMARY KEY (check_name, instrument_id, date, key)
) STRICT, WITHOUT ROWID;
