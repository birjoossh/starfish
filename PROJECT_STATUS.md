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

- **Phase E: Corporate Events Ingestion + EVT Signal [ACHIEVED]**
  - `ingestion/corporate_actions_parser.py` + `purpose_parser.py` + loaders; `corporate_events_ingestor.py` + `corporate_events_loader.py` with idempotent upsert on `(symbol, event_date, event_type)`.
  - `analytics/compute_signals.py` joins past and **next** `fact_corporate_event` rows (days to next event + significance) for both EVT branches; `event_flag` includes upcoming window.
  - Factor 5 in `analytics/iss_scorer.py` uses past significance or, when absent, upcoming significance inside the EVT window.
  - `GET /events` and `GET /actions` aligned to actual DDL (`significance_score`, `action_type`, `purpose_text`, etc.).
  - `ingestion/daily_run.py` supports `--corporate-actions`, `--corporate-events`, and `--compute-signals`.
  - Unit tests: `tests/test_purpose_parser.py`, `tests/test_signal_classifier.py` (EVT branches).
  - ⏸️ **Deferred to Phase I:** Live NSE site scraping for real-time events. Phase E remains CSV / fixture friendly.

- **Phase F: Views 3-5 (Drawdown Scanner + Momentum + Volume Anomaly) [ACHIEVED]**
  - Streamlit tabs **Drawdown**, **Momentum**, **Volume** (`dashboard/phase_f.py` + `dashboard/app.py`).
  - View 3: threshold slider, sector multiselect, KPI counts, tagged table (Potential Accumulation / Falling Knife Risk / Needs Event Review), drawdown vs distance scatter.
  - View 4: active MOM table with tier labels, near-breakout radar (within ~5% of 52W high, ISS≥50), RS vs Nifty 3M bar chart.
  - View 5: optional `mart_volume_anomaly` when populated; else four buckets from `vol_ratio_1d` (>20% / >50% / >100% vs 20D + contraction).
  - ⏸️ **Deferred to Phase I:** Mobile-responsive layout (M1 is desktop-only per DESIGN.md).

- **Phase G: View 6 (Events Tracker) + View 7 (Watchlist Builder) [ACHIEVED]**
  - View 6: Corporate Events timeline with filters, date range, event type, significance scoring, and price impact visualization.
  - View 7: Watchlist Builder with four categories (Contrarian Opportunities, Momentum Leaders, Event-Driven Candidates, Volume-Confirmed Movers).
  - Database: `watchlist_users`, `user_watchlist`, `alerts`, `user_alert_preferences`, `watchlist_categories` tables.
  - API: `/api/v1/events/*` (list, timeline, upcoming, symbol, type, summary) + `/api/v1/watchlist/*` (CRUD, categories, export).
  - Analytics: `analytics/watchlist_builder.py` with auto-population logic for 4 categories.
  - ⏸️ **Deferred to Phase I:** Multi-user authentication (currently single-user mode with user_id=1).

---

## Active Phase ⚡

**Phase I: Backfill + Hardening** (in progress)
- ✅ Mobile layout infrastructure (`dashboard/phase_i.py`)
- ✅ Docker setup (Dockerfile + docker-compose.yml)
- ✅ Environment config (.env.example)
- ⏳ 5-year historical backfill (requires NSE archive access)
- ⏳ Live NSE scraping (deferred from Phase E)
- ⏳ Notification delivery (deferred from Phase H)

---

## Completed Phases (This Session)

- **Phase H: Alert Rules + EOD Scheduler** ✅
  - EOD batch scheduling (APScheduler) in `scheduler/eod_scheduler.py`
  - 14 alert rules (A-01 through A-14) in `analytics/alert_conditions.py`
  - Alert engine in `analytics/alert_engine.py` with deduplication
  - Notification infrastructure ready (channels deferred)

- **Phase I: Backfill + Hardening** (in progress)
  - Mobile layout (`dashboard/phase_i.py`)
  - Docker deployment (Dockerfile + docker-compose.yml)
  - Environment configuration (.env.example)
  - ⏸️ **Deferred:** 5-year backfill (requires NSE archive access)
  - ⏸️ **Deferred:** Live NSE scraping
  - ⏸️ **Deferred:** Notification delivery
