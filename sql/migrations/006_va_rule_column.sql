-- Add va_rule column to mart_volume_anomaly to store the matched
-- VA-1 through VA-7 rule label per spec §6.3.
-- Rule evaluation is priority-ordered: VA-5 first, VA-4 last before Normal.

ALTER TABLE mart_volume_anomaly
    ADD COLUMN IF NOT EXISTS va_rule VARCHAR(60);

COMMENT ON COLUMN mart_volume_anomaly.va_rule IS
    'Matched VA rule label (VA-1 Bullish Volume Surge … VA-7 Speculative Activity) or NULL for Normal';
