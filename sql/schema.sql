-- Nifty 50 Dashboard — Full Schema DDL
-- Spec Section 5: All tables with spec-aligned column definitions.
-- M1 populates: dim_stock, fact_eod_price, fact_52wk.
-- Other tables exist empty, ready for M2+.

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_stock (
    symbol          VARCHAR(20)   PRIMARY KEY,
    company_name    VARCHAR(200)  NOT NULL,
    sector          VARCHAR(100)  NOT NULL,
    industry        VARCHAR(100),
    nifty50_member  BOOLEAN       NOT NULL DEFAULT TRUE,
    market_cap_cr   DECIMAL(18,2),
    listing_date    DATE          NOT NULL,
    face_value      DECIMAL(10,2) NOT NULL,
    isin            VARCHAR(12)   NOT NULL,
    last_updated    TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_stock_sector ON dim_stock (sector);
CREATE INDEX IF NOT EXISTS idx_dim_stock_nifty50 ON dim_stock (nifty50_member) WHERE nifty50_member = TRUE;

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_nifty50_constituent (
    symbol            VARCHAR(20)   NOT NULL,
    effective_from    DATE          NOT NULL,
    effective_to      DATE,
    index_weight_pct  DECIMAL(8,4),
    replaced_symbol   VARCHAR(20),
    change_type       VARCHAR(20)   NOT NULL CHECK (change_type IN ('Addition', 'Deletion', 'Rebalance')),
    review_period     VARCHAR(20)   NOT NULL,
    PRIMARY KEY (symbol, effective_from),
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE INDEX IF NOT EXISTS idx_constituent_dates ON dim_nifty50_constituent (effective_from, effective_to);

-- ============================================================
-- FACT TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS fact_eod_price (
    trade_date            DATE          NOT NULL,
    symbol                VARCHAR(20)   NOT NULL,
    open                  DECIMAL(12,2) NOT NULL,
    high                  DECIMAL(12,2) NOT NULL,
    low                   DECIMAL(12,2) NOT NULL,
    close                 DECIMAL(12,2) NOT NULL,
    prev_close            DECIMAL(12,2) NOT NULL,
    total_traded_qty      BIGINT        NOT NULL,
    total_traded_value_lakh DECIMAL(18,2) NOT NULL,
    total_trades          INTEGER       NOT NULL,
    series                VARCHAR(10)   NOT NULL,
    delivery_qty          BIGINT,
    delivery_pct          DECIMAL(6,2),
    source_file           VARCHAR(300)  NOT NULL,
    PRIMARY KEY (trade_date, symbol),
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE INDEX IF NOT EXISTS idx_eod_symbol_date ON fact_eod_price (symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_eod_date ON fact_eod_price (trade_date DESC);

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS fact_52wk (
    trade_date    DATE          NOT NULL,
    symbol        VARCHAR(20)   NOT NULL,
    wk52_high     DECIMAL(12,2) NOT NULL,
    wk52_low      DECIMAL(12,2) NOT NULL,
    wk52_high_date DATE         NOT NULL,
    wk52_low_date  DATE         NOT NULL,
    pct_from_high DECIMAL(8,4)  NOT NULL,
    pct_from_low  DECIMAL(8,4)  NOT NULL,
    PRIMARY KEY (trade_date, symbol),
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE INDEX IF NOT EXISTS idx_52wk_symbol ON fact_52wk (symbol, trade_date DESC);

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS fact_corporate_action (
    action_id                BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol                   VARCHAR(20)   NOT NULL,
    action_type              VARCHAR(20)   NOT NULL CHECK (action_type IN ('Dividend', 'Bonus', 'Split', 'Rights', 'Buyback')),
    ex_date                  DATE          NOT NULL,
    record_date              DATE,
    payment_date             DATE,
    purpose_text             VARCHAR(500)  NOT NULL,
    ratio_numerator          DECIMAL(10,4),
    ratio_denominator        DECIMAL(10,4),
    face_value               DECIMAL(10,2),
    dividend_amount_per_share DECIMAL(10,4),
    data_source              VARCHAR(100)  NOT NULL,
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE INDEX IF NOT EXISTS idx_corp_action_symbol_date ON fact_corporate_action (symbol, ex_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_corp_action_dedup ON fact_corporate_action (symbol, action_type, ex_date);

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS fact_corporate_event (
    event_id               BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol                 VARCHAR(20)   NOT NULL,
    event_date             DATE          NOT NULL,
    event_type             VARCHAR(50)   NOT NULL CHECK (event_type IN ('Earnings', 'Leadership_Change', 'M&A', 'Large_Order', 'Pledging_Change', 'Rating_Change', 'Regulatory', 'Other')),
    event_summary          VARCHAR(500)  NOT NULL,
    raw_announcement_text  TEXT,
    categorization_method  VARCHAR(20)   NOT NULL CHECK (categorization_method IN ('Manual', 'Rule', 'NLP')),
    significance_score     INTEGER       NOT NULL CHECK (significance_score BETWEEN 1 AND 5),
    price_chg_1d           DECIMAL(8,4),
    price_chg_5d           DECIMAL(8,4),
    price_chg_20d          DECIMAL(8,4),
    volume_spike_flag      BOOLEAN       NOT NULL DEFAULT FALSE,
    follow_up_required     BOOLEAN       NOT NULL DEFAULT FALSE,
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE INDEX IF NOT EXISTS idx_corp_event_symbol_date ON fact_corporate_event (symbol, event_date DESC);
CREATE INDEX IF NOT EXISTS idx_corp_event_type ON fact_corporate_event (event_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_corp_event_dedup ON fact_corporate_event (symbol, event_date, event_type);

-- ============================================================
-- MART TABLES (pre-computed analytics)
-- ============================================================

CREATE TABLE IF NOT EXISTS mart_stock_signals (
    calc_date                   DATE          NOT NULL,
    symbol                      VARCHAR(20)   NOT NULL,
    return_1d                   DECIMAL(8,4)  NOT NULL,
    return_1m                   DECIMAL(8,4)  NOT NULL,
    return_3m                   DECIMAL(8,4)  NOT NULL,
    return_1y                   DECIMAL(8,4),
    rs_vs_nifty_1m              DECIMAL(8,4),
    rs_vs_nifty_3m              DECIMAL(8,4),
    rs_vs_nifty_1y              DECIMAL(8,4),
    vol_ratio_1d                DECIMAL(8,4)  NOT NULL,
    vol_ratio_5d                DECIMAL(8,4)  NOT NULL,
    vol_ratio_20d               DECIMAL(8,4)  NOT NULL,
    drawdown_from_52w_high_pct  DECIMAL(8,4) NOT NULL,
    distance_from_52w_low_pct   DECIMAL(8,4) NOT NULL,
    avg_volume_20d              BIGINT        NOT NULL,
    volume_trend_3m             VARCHAR(20)   NOT NULL DEFAULT 'Mixed'
                                CHECK (volume_trend_3m IN ('Expanding', 'Contracting', 'Mixed')),
    iss_score                   DECIMAL(6,2)  NOT NULL DEFAULT 0,
    signal_category             VARCHAR(20)   NOT NULL DEFAULT 'Neutral'
                                CHECK (signal_category IN ('Accumulation', 'Momentum', 'EventDriven', 'Neutral')),
    accumulation_flag           BOOLEAN       NOT NULL DEFAULT FALSE,
    momentum_flag               BOOLEAN       NOT NULL DEFAULT FALSE,
    event_flag                  BOOLEAN       NOT NULL DEFAULT FALSE,
    last_event_type             VARCHAR(50),
    last_event_date             DATE,
    days_since_last_event       INTEGER,
    direction_consistency_20d   DECIMAL(5,2),
    intraday_reversal_count_20d INTEGER,
    last_event_significance     INTEGER,
    last_event_is_negative      BOOLEAN       DEFAULT FALSE,
    nifty50_member              BOOLEAN       DEFAULT TRUE,
    iss_score_breakdown         JSONB,
    PRIMARY KEY (calc_date, symbol),
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

CREATE INDEX IF NOT EXISTS idx_signals_date ON mart_stock_signals (calc_date DESC);

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS mart_volume_anomaly (
    calc_date              DATE          NOT NULL,
    symbol                 VARCHAR(20)   NOT NULL,
    volume_today           BIGINT        NOT NULL,
    avg_vol_20d            BIGINT        NOT NULL,
    volume_ratio           DECIMAL(8,4)  NOT NULL,
    spike_level            VARCHAR(20)   NOT NULL CHECK (spike_level IN ('Normal', 'Mild', 'Moderate', 'High', 'Extreme')),
    price_chg_on_spike_day DECIMAL(8,4)  NOT NULL,
    delivery_pct           DECIMAL(6,2),
    nearest_event_within_5d VARCHAR(500),
    nearest_event_type     VARCHAR(50),
    anomaly_direction      VARCHAR(10)   NOT NULL CHECK (anomaly_direction IN ('Up', 'Down')),
    va_rule                VARCHAR(60),
    PRIMARY KEY (calc_date, symbol),
    FOREIGN KEY (symbol) REFERENCES dim_stock(symbol)
);

-- ============================================================
-- AUXILIARY TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS ingestion_log (
    log_id        BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file   VARCHAR(300)  NOT NULL,
    table_name    VARCHAR(50)   NOT NULL,
    rows_inserted INTEGER       NOT NULL DEFAULT 0,
    rows_failed   INTEGER       NOT NULL DEFAULT 0,
    status        VARCHAR(20)   NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    error_message TEXT,
    started_at    TIMESTAMP     NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_date ON ingestion_log (started_at DESC);

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS symbol_alias (
    old_symbol    VARCHAR(20)   NOT NULL,
    new_symbol    VARCHAR(20)   NOT NULL,
    effective_date DATE         NOT NULL,
    reason        VARCHAR(100),
    PRIMARY KEY (old_symbol, effective_date)
);

-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS nifty50_index_prices (
    trade_date    DATE          NOT NULL,
    close         DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (trade_date)
);

-- ============================================================
-- PHASE G: WATCHLIST + ALERTS SCHEMA
-- ============================================================

-- User management for multi-user watchlist support
CREATE TABLE IF NOT EXISTS watchlist_users (
    user_id              BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username             VARCHAR(50)   NOT NULL UNIQUE,
    email                VARCHAR(100)  NOT NULL,
    created_at           TIMESTAMP     NOT NULL DEFAULT NOW(),
    notification_enabled BOOLEAN       NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_watchlist_users_email ON watchlist_users (email);

-- User watchlist with pin and reason
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

-- Alerts table for Phase H: Alert tracking and deduplication
CREATE TABLE IF NOT EXISTS alerts (
    alert_id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_name          VARCHAR(20)   NOT NULL CHECK (alert_name LIKE 'A-__'),
    symbol              VARCHAR(20),
    triggered_at        TIMESTAMP     NOT NULL DEFAULT NOW(),
    trigger_value       JSONB         NOT NULL,
    user_ids_to_notify  BIGINT[]      NOT NULL DEFAULT '{}',
    delivery_status     VARCHAR(20)   NOT NULL DEFAULT 'Pending' CHECK (delivery_status IN ('Pending', 'Sent', 'Failed')),
    dedup_key           VARCHAR(100),
    severity            VARCHAR(20)   NOT NULL DEFAULT 'Medium' CHECK (severity IN ('Critical', 'High', 'Medium', 'Low')),
    resolved_at         TIMESTAMP,
    resolution_note     VARCHAR(500)
);

CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_ids_to_notify);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts (symbol) WHERE symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (delivery_status);
CREATE INDEX IF NOT EXISTS idx_alerts_dedup ON alerts (alert_name, symbol, dedup_key)
    WHERE dedup_key IS NOT NULL;

-- User alert preferences for notification controls
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

-- Watchlist categories for auto-populated suggestions
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
    ('Volume-Confirmed Movers', 'Volume spike + positive return', '{"vol_ratio_threshold": 2.0, "min_return_1d": 0}')
ON CONFLICT (category_name) DO NOTHING;

-- --------------------------------------------------------
