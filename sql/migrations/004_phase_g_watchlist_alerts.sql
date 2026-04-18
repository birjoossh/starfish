-- Phase G: Watchlist Builder + Alert Engine
-- Migration: 004_phase_g_watchlist_alerts.sql

-- Enable pgcrypto extension for UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- USER MANAGEMENT (for multi-user watchlist support)
-- ============================================================

CREATE TABLE IF NOT EXISTS watchlist_users (
    user_id       BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      VARCHAR(50)   NOT NULL UNIQUE,
    email         VARCHAR(100)  NOT NULL,
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW(),
    notification_enabled BOOLEAN   NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_users_email ON watchlist_users (email);

-- ============================================================
-- USER WATCHLIST (Persistent watchlist with pin and reason)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_watchlist (
    watchlist_id  BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT        NOT NULL,
    symbol        VARCHAR(20)   NOT NULL,
    added_date    DATE          NOT NULL DEFAULT CURRENT_DATE,
    reason        VARCHAR(255),
    pinned        BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES watchlist_users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_watchlist_unique ON user_watchlist (user_id, symbol);
CREATE INDEX IF NOT EXISTS idx_user_watchlist_user ON user_watchlist (user_id);
CREATE INDEX IF NOT EXISTS idx_user_watchlist_pinned ON user_watchlist (user_id, pinned);

-- ============================================================
-- ALERTS TABLE (For Phase H: Alert tracking and deduplication)
-- ============================================================

CREATE TABLE IF NOT EXISTS alerts (
    alert_id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_name        VARCHAR(20)   NOT NULL CHECK (alert_name LIKE 'A-__'),
    symbol            VARCHAR(20),
    triggered_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    trigger_value     JSONB         NOT NULL,
    user_ids_to_notify BIGINT[]     NOT NULL DEFAULT '{}',
    delivery_status   VARCHAR(20)   NOT NULL DEFAULT 'Pending' CHECK (delivery_status IN ('Pending', 'Sent', 'Failed')),
    dedup_key         VARCHAR(100),
    severity          VARCHAR(20)   NOT NULL DEFAULT 'Medium' CHECK (severity IN ('Critical', 'High', 'Medium', 'Low')),
    resolved_at       TIMESTAMP,
    resolution_note   VARCHAR(500)
);

CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_ids_to_notify);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts (symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (delivery_status);
CREATE INDEX IF NOT EXISTS idx_alerts_dedup ON alerts (alert_name, symbol, dedup_key)
    WHERE dedup_key IS NOT NULL;

-- ============================================================
-- USER ALERT PREFERENCES (For Phase H: User notification controls)
-- ============================================================

CREATE TABLE IF NOT EXISTS user_alert_preferences (
    preference_id   BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT        NOT NULL,
    alert_name      VARCHAR(20)   NOT NULL CHECK (alert_name LIKE 'A-__'),
    channels        VARCHAR(50)[] NOT NULL DEFAULT '{}',
    enabled         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES watchlist_users(user_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_alert_pref_unique ON user_alert_preferences (user_id, alert_name);
CREATE INDEX IF NOT EXISTS idx_user_alert_pref_user ON user_alert_preferences (user_id);

-- ============================================================
-- WATCHLIST CATEGORIES (For Phase G: Auto-populated categories)
-- ============================================================

CREATE TABLE IF NOT EXISTS watchlist_categories (
    category_id     BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name   VARCHAR(50)   NOT NULL UNIQUE,
    description     VARCHAR(255),
    filter_logic    JSONB         NOT NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- Insert default categories
INSERT INTO watchlist_categories (category_name, description, filter_logic) VALUES
    ('Contrarian Opportunities', 'Deep drawdown + volume contraction + ISS threshold', '{"drawdown_pct_threshold": -20, "vol_ratio_threshold": 0.85, "min_iss": 50}'),
    ('Momentum Leaders', 'High ISS + positive RS + momentum flag', '{"min_iss": 70, "min_rs_3m": 0, "momentum_flag": true}'),
    ('Event-Driven Candidates', 'Event flag + upcoming event within window', '{"event_flag": true, "days_window": 10, "min_significance": 3}'),
    ('Volume-Confirmed Movers', 'Volume spike + positive return', '{"vol_ratio_threshold": 2.0, "min_return_1d": 0}');

-- ============================================================
-- SEQUENCES
-- ============================================================

CREATE SEQUENCE IF NOT EXISTS watchlist_id_seq START WITH 1 INCREMENT BY 1;
