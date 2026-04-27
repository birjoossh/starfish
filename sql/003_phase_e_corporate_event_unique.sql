-- Phase E: idempotent upsert for corporate events loader (ON CONFLICT target).
-- Safe to run on existing databases; no-op if index already exists.
CREATE UNIQUE INDEX IF NOT EXISTS idx_corp_event_dedup ON fact_corporate_event (symbol, event_date, event_type);
