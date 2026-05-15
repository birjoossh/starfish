-- TODO-122 sub-fix: make rs_vs_nifty_1m and rs_vs_nifty_3m nullable.
--
-- Before this migration both columns were NOT NULL DEFAULT 0, which silently
-- neutralised ISS Factor 2 for stocks lacking sufficient index/return history
-- and caused the dashboard to display "0.00%" instead of "—" for an
-- incomputable metric. The spec (deviation #2) calls for NULL here so the
-- ISS scorer and UI can handle "no data" explicitly.
--
-- rs_vs_nifty_1y was already nullable, so it is untouched.
-- Existing rows keep their 0 value; new rows can now write NULL.
ALTER TABLE mart_stock_signals
    ALTER COLUMN rs_vs_nifty_1m DROP NOT NULL,
    ALTER COLUMN rs_vs_nifty_1m DROP DEFAULT,
    ALTER COLUMN rs_vs_nifty_3m DROP NOT NULL,
    ALTER COLUMN rs_vs_nifty_3m DROP DEFAULT;
