-- The "proceeds were reinvested" flag is no longer used: a sale and the buy that follows
-- are both in the ledger, and the gain on a sale is reported as realised profit.

ALTER TABLE transactions DROP COLUMN reinvested;
