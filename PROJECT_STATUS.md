# Nifty 50 Dashboard - Project Status Tracker

Based on the **Master Design Specification** (`birjoossh-master-design-20260410-181006.md`), we are following the "Approach C: ISS-First, Then Views" strategic plan. Our goal is to build the robust data and analytics layer first, followed by the frontend visualizations and alerting systems.

Here is the master tracking list of all phases and their current status:

---

## Completed Phases 🚀

- **Phase 0: Minimum Backfill (1 Year) [ACHIEVED]**
  - Robust ingestion pipeline supporting idempotent Upserts.
  - Sourced ~252 trading days of Bhavcopy + Index CSVs from NSE archives.
  - Bypassed market holidays gracefully via an enhanced circuit-breaker logic.

- **Phase A: NSE Index Prices + RS Computation [ACHIEVED]**
  - Instantiated the `nifty50_index_prices` architecture.
  - Implemented the `rs_engine.py` component to calculate baseline Nifty 50 relative performance.
  - Synced data to the `mart_stock_signals` reporting table.

- **Phase B: Volume Trend Regression + Direction Consistency [ACHIEVED]**
  - Upgraded simple ratio thresholds to advanced linear regression models (`volume_trend_3m`) via Scipy.
  - Calculated `direction_consistency_20d` fraction natively via Numpy vector maps.
  - Counted active `intraday_reversal_count_20d` traps dynamically using OHLC percentage spreads.
  - Modified internal DB metrics schema safely handling SQL constraints enums explicitly.

- **Phase C: ISS Scoring Function + Signal Classification [ACHIEVED]**
  - Implemented the defining 7-factor Investment Signal Score (0-100).
  - Recalibrated scoring thresholds to prevent bubble-chasing and correct inverse-momentum correlation.
  - Deployed ACC / MOM signal classifications (EVT pending Phase E event data).
  - Validated ISS with backtest showing clear discriminative power between market states.

- **Phase D: Dashboard Views 1-2 (Market Overview + Movers) [ACHIEVED]**
  - Single-page terminal-style Streamlit UI adhering to DESIGN.md.
  - Starfish branding with responsive SVG logo.
  - KPI header, Morning Digest with hover rationale, Sector Heatmap (Plotly Treemap + Donut).
  - Sector Breadth table, Watchlist panel, Top 10 Gainers / Losers tables.
  - Full ISS screener pipeline with per-table text filters (auto-apply).
  - ⏸️ **Deferred to Phase G:** Watchlist save/pin persistence (currently YAML-based read-only).
  - ⏸️ **Deferred to Phase G:** Click-to-expand row detail modal.

---

## Active Phase ⚡

- **Phase E: Corporate Events Ingestion + EVT Signal [IN PROGRESS]**
  - Build `ingestion/corporate_actions_parser.py` + `purpose_parser.py`.
  - Build `ingestion/corporate_actions_loader.py` + `corporate_events_ingestor.py` + `corporate_events_loader.py`.
  - Wire Factor 5 in `analytics/iss_scorer.py` to use real event data.
  - Wire EVT classification (both branches) in `analytics/signal_classifier.py`.
  - Populate `last_event_type`, `last_event_date`, `days_since_last_event` in `compute_signals.py`.
  - Add `GET /events` and `GET /actions` API endpoints.
  - Unit tests for purpose_parser regex + EVT classification logic.
  - ⏸️ **Deferred to Phase I:** Live NSE site scraping for real-time events. Phase E uses CSV fixture-based ingestion.

---

## Remaining Phases ⏳

- **Phase F: Views 3-5 (Drawdown Scanner + Momentum + Volume Anomaly)**
  - View 3: Drawdown Scanner with Signal Tags (Potential Accumulation / Falling Knife / Needs Event Review).
  - View 4: Breakout & Momentum Monitor with Momentum Quality Tags.
  - View 5: Volume Anomaly Monitor (>20%, >50%, >100% spike sub-tables + contraction table).
  - ⏸️ **Deferred to Phase I:** Mobile-responsive layout (M1 is desktop-only per DESIGN.md).

- **Phase G: View 6 (Events Tracker) + View 7 (Watchlist Builder)**
  - View 6: Corporate Events timeline (depends on Phase E `fact_corporate_event` data).
  - View 7: Watchlist Builder with persistent save/pin and one-line reason annotation.
  - Implements watchlist highlight (3px gold left-border stripe) per DESIGN.md spec.

- **Phase H: Alert Rules + EOD Scheduler**
  - EOD batch scheduling (cron/APScheduler).
  - Construction of 14 alert rules (A-01 through A-14) from the master spec.
  - ⏸️ **Deferred to Phase I:** Notification delivery channels (email/Slack).

- **Phase I: Backfill + Hardening**
  - Complete 5-year historical backfill.
  - Alembic database schema migrations.
  - Live NSE scraping for corporate events (deferred from Phase E).
  - Mobile layout (deferred from Phase F).
  - Notification delivery (deferred from Phase H).
  - Deployment optimisation and monitoring.
