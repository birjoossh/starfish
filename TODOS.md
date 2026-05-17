# TODOS.md — Nifty 50 Dashboard

All deferred work from **Phase 1** of the spec, organized by spec milestone.
Our current plan (M1a-M1d) covers a subset of Milestones 1.1 and 1.5.
Everything below must be completed before we move to Phase 2.

**M1 scope decisions (from eng review 2026-04-10):**
- Full spec-aligned schema upfront (all 8 tables + 3 auxiliary)
- 1-year backfill (not 3 months)
- TODO-101, 102, 108-110, 001, 004 are now **IN SCOPE for M1**
- Return-based signals only; corporate event signals deferred to M2

---

## Master TODO Status

Single source of truth for the status of every TODO-### in this file. Update on completion of each item. The per-section detail blocks below stay as the spec / why / depends-on reference; this table is the at-a-glance roll-up.

Last updated: **2026-05-16** — wave-1 cleanup + UI audit. Six items shipped on `feature/wave-1-remaining-todos`: TODO-123 (VA rules), TODO-112 (seed CSV), TODO-115 (seed validation), TODO-127 (orchestrator FK-ordered), TODO-128 (validation report), TODO-124 (Alembic baseline). Tests for the first five passing (38 in the two new test files plus the existing suite); Alembic baseline verified via offline-SQL dry-run. Playwright audit of the dashboard surfaced three new tracked items: **TODO-130** (stale UI placeholders for data that's now lit — closed on `feature/todo-130-wire-stale-ui-placeholders`), **TODO-131** (`dim_stock.market_cap_cr` empty for all 50 stocks), **TODO-132** (`fact_corporate_action` has 0 rows despite table/parser/loader all done). Remaining wave-1 infra items follow: TODO-113, TODO-129, TODO-125, TODO-126.

**Sort order:** **Open / Partial items are sorted by signal-value priority** — what each TODO unlocks for the investment-decision flow on the dashboard. The reasoning per rank is in the "Why this rank" column. Done items are listed below the open set in numeric ID order, since their relative ranking no longer affects the next-action decision.

### Signal-value priority ladder (Open + Partial)

| Rank | ID | Title | Milestone | Status | Why this rank for signal value |
|---|---|---|---|---|---|
| ⭐ 1 | 132 | Run `fact_corporate_action` daily ingestion | M1.4 | ⬜ Open | Table exists (TODO-116 ✅), parser exists (TODO-117 ✅), loader exists (TODO-118 ✅), but DB has 0 rows. Daily pipeline does not invoke `CorporateActionsLoader`. Unblocks dividend-adjusted returns, ex-date markers on Trend Workbench, and ISS Factor 5 corporate-action component. |
| 2 | 131 | Populate `dim_stock.market_cap_cr` | M1.1 | ⬜ Open | Column exists (TODO-102 ✅) but is NULL for all 50 stocks. Treemap cell sizing falls back to ISS score per `dashboard/overview.py:361` caption. Needs a one-time seed (snapshot from NSE security master or Screener export) plus a refresh cadence — monthly is fine since mcap doesn't move the treemap meaningfully day-to-day. |
| 3 | 113 | Constituent maintenance loader (add/del/rebalance) | M1.3 | 🟨 Partial | `ingestion/framework/loaders/constituents_loader.py` writes a snapshot row (effective_from=trade_date, change_type='Addition') idempotently. Spec wants explicit add/del/rebalance JSON intake; defer until reconstitution math actually drifts. TODO-112 seed loader (just closed) handles the 50 ADD rows for the baseline; this item only matters when NSE publishes a real reconstitution. |
| 4 | 129 | Local download cache during backfill | M1.5 | ⬜ Open | Operational speed. No signal value. |
| 5 | 125 | `symbol_alias` table | M1.5 | ⬜ Open | Edge-case for back-test continuity through renames. Rare. |
| 6 | 126 | Composite + BRIN indexes on fact / mart tables | M1.5 | ⬜ Open | Query speed only. |

### Closed items (numeric ID order)

| ID | Title | Milestone | Status | Closed by |
|---|---|---|---|---|
| 001 | CSV column-header validation | Cross-cutting | ✅ Done | — |
| 003 | Idempotency across ingestion scripts | Cross-cutting | ✅ Done | — |

| 004 | Rate limiting for NSE downloads | Cross-cutting | ✅ Done | — |
| 101 | `fact_eod_price` columns (14) align with spec | M1.1 | ✅ Done | — |
| 102 | `dim_stock` columns (10) align with spec | M1.1 | ✅ Done | — |
| 104 | Ingestion-log table | M1.1 | ✅ Done | — |
| 106 | NSE index prices ingestion + RS-vs-Nifty overlay | M1.1 (parallel) | ✅ Done | `0a4bc43` — daily_run wiring + /trend RS overlay + 8 unit tests. RS-1M lit (2538/2657 rows non-zero); RS-3M / RS-1Y deferred to TODO-127. |
| 103 | MTO delivery data ingestion (`delivery_qty/pct`) | M1.1 | ✅ Done | — |
| 105 | Corrupted-download validation (checksum / row-count) | M1.1 | ✅ Done | — |
| 107 | `config.yaml` thresholds | M1.1 | ✅ Done | — |
| 108 | Create `fact_52wk` table | M1.2 | ✅ Done | — |
| 109 | `compute_52wk.py` rolling 252-day | M1.2 | ✅ Done | — |
| 110 | Idempotent upsert for `fact_52wk` | M1.2 | ✅ Done | — |
| 119 | Create `fact_corporate_event` table | M1.4 | ✅ Done | Table + 3 indexes (incl. unique (symbol, event_date, event_type) for idempotent upsert) already in `sql/schema.sql:108-127`. Originally landed under the Phase E corporate-events work; confirmed against spec Table 6 line-by-line on 2026-05-15. |
| 002 | `GET /health` endpoint | Cross-cutting | ✅ Done | `api/main.py:104` — checks DB connectivity, returns table row counts. Closed retroactively in the 2026-05-15 audit. |
| 111 | Create `dim_nifty50_constituent` table | M1.3 | ✅ Done | `sql/schema.sql:28-40` — composite PK (symbol, effective_from), FK to dim_stock, change_type CHECK constraint matches spec Table 4. Closed retroactively 2026-05-15. |
| 116 | Create `fact_corporate_action` table | M1.4 | ✅ Done | `sql/schema.sql:87-104` — full 12-column spec match including unique (symbol, action_type, ex_date) for idempotent dedup. Closed retroactively 2026-05-15. |
| 117 | `purpose_parser.py` regex library | M1.4 | ✅ Done | `ingestion/purpose_parser.py` — full ParsedPurpose dataclass + 9-event-type taxonomy + `event_significance()` 1-5 scorer matching spec. Closed retroactively 2026-05-15. |
| 118 | `ingest_corporate_actions.py` | M1.4 | ✅ Done | `ingestion/corporate_actions_parser.py` + `ingestion/corporate_actions_loader.py` — CorporateActionsLoader writes via INSERT … ON CONFLICT (symbol, ex_date, action_type) DO UPDATE. Closed retroactively 2026-05-15. |
| 121 | Unit tests for `purpose_parser` | M1.4 | ✅ Done | `tests/test_purpose_parser.py` — class-based coverage of dividend/bonus/split/rights/buyback/AGM/EGM/results/other across normal + edge cases. Closed retroactively 2026-05-15. |
| 122-a | `signal_category` ACC/MOM/EVT/Neutral labels | M1.5 | ✅ Done | `analytics/compute_signals.py:298` + `analytics/signal_classifier.py:50-59` — emit "Accumulation"/"Momentum"/"EventDriven"/"Neutral" per spec §6.2. Closed retroactively 2026-05-15. |
| 122-b | `volume_trend_3m` linear regression on 63d (R²≥0.30) | M1.5 | ✅ Done | `analytics/volume_engine.py:70-87` — `scipy.stats.linregress` over 63-day rolling window with `r_squared ≥ 0.30` gate; emits Expanding/Contracting/Mixed labels. Closed retroactively 2026-05-15. |
| 122-c | `direction_consistency_20d` (count up-days / 20) | M1.5 | ✅ Done | `analytics/trend_stability_engine.py:63` — also exposes `intraday_reversal_count_20d` for the same penalty term. Closed retroactively 2026-05-15. |
| 114 | `is_nifty50_member(symbol, as_of_date)` utility | M1.3 | ✅ Done | `services/universe.py` — `membership_covers` pure-logic helper + `is_nifty50_member` single-symbol + `nifty50_members_as_of` bulk variant. 11 unit tests cover open/closed intervals, exact boundaries, Deletion masking, re-entry, Rebalance, empty input. |
| NEW | Composable analytics-engine contract / signal_registry | Cross-cutting | ✅ Done | `analytics/registry.py` — `EngineSpec` dataclass + `@register_engine` decorator + `list_engines`, `get_engine_spec`, `run_engine`, `run_all` dispatchers. `analytics/__init__.py` auto-discovers the four canonical engines (returns, volume, rs, trend_stability) at import time. 7 unit tests in `tests/unit/test_registry.py`. |
| 122-d | `iss_score` 7-factor 0-100 composite wired | M1.5 | ✅ Done | Confirmed in audit: `analytics/iss_scorer.py` implements all seven factors per spec §7; `analytics/compute_signals.py:290` calls `compute_iss(row_dict)` per symbol and overwrites the line-215 placeholder with the real score at line 301. |
| 122-e | `rs_vs_nifty_*` NULL semantics | M1.5 | ✅ Done | Migration `sql/migrations/005_rs_vs_nifty_nullable.sql` drops the `NOT NULL DEFAULT 0` from `rs_vs_nifty_1m` / `rs_vs_nifty_3m` (schema.sql updated to match). `compute_signals.py` no longer fills these to 0 in `not_null_defaults`, so insufficient history flows through as NULL. `iss_scorer.py` now centralises missing-value handling in a `_missing(value)` helper that catches both `None` *and* `NaN`, so the spec's explicit defaults (`return_1y` 3 pts, `rs_vs_nifty_1y` 2 pts) fire correctly on pandas DataFrames. 9 new unit tests in `tests/test_iss_scorer.py` covering all three NaN flavours across F1/F2/F3/F6. |
| 120 | `ingest_corporate_events.py` — spec-taxonomy keyword classifier | M1.4 | ✅ Done | New `ingestion/event_classifier.py` — 8-category keyword classifier (Earnings/Leadership_Change/M&A/Large_Order/Pledging_Change/Rating_Change/Regulatory/Other) with 1-5 significance scoring per spec §M3.4 and a `is_negative_event` predicate. `corporate_events_ingestor.py` rewritten to use it; the stale `purpose_parser` reuse + Loader's `EVENT_TYPE_MAP` hack are gone. Loader now consumes the spec types directly and writes `follow_up_required` from the negative-event flag. 29 unit tests in `tests/unit/test_event_classifier.py` cover all 8 categories, priority ordering, fallback, and `is_negative` semantics. |
| 112 | Seed `nifty50_history.csv` (5-year reconstitution) | M1.3 | ✅ Done | `data/raw/reconstitution/nifty50_history.csv` — 50-row baseline (one ADD per current constituent at 2021-01-01). Loader `ingestion/nifty50_history_loader.py` validates + bulk-inserts via `INSERT … ON CONFLICT (symbol, effective_from) DO UPDATE`. Wired into backfill orchestrator step 0. Closed 2026-05-16. |
| 115 | Seed-CSV validation before insert | M1.3 | ✅ Done | `validate_history_csv()` in `ingestion/nifty50_history_loader.py` runs 8 checks: file exists, required columns, no empty symbols, parseable dates, valid ADD/DELETE actions, no duplicate (symbol, effective_from), no overlapping intervals, no two open-ended ADD rows per symbol. 13 unit tests in `tests/unit/test_nifty50_history_loader.py` including the production-file validity check. Closed 2026-05-16. |
| 123 | `mart_volume_anomaly` table — VA-1…VA-7 rules | M1.5 | ✅ Done | `analytics/compute_volume_anomalies.py:_match_va_rule` evaluates the 7 spec rules in priority order (VA-5 first, VA-4 last). New `va_rule VARCHAR(60)` column on `mart_volume_anomaly` (schema + migration `sql/migrations/006_va_rule_column.sql`). ±3-day event proximity and rolling 5-day dry-up counter computed per symbol. Wired into the post-load analytics chain: `compute_signals.py` calls `compute_volume_anomalies` after `mart_stock_signals` is populated. 25 unit tests in `tests/unit/test_volume_anomaly_engine.py` cover rule priority, threshold boundaries, NULL delivery handling, and edge cases. Closed 2026-05-16. |
| 127 | Backfill orchestrator (5-year, FK-ordered) | M1.5 | ✅ Done | `ingestion/backfill/orchestrator.py` runs in FK-correct sequence: step 0 (optional) seeds `dim_nifty50_constituent` via `nifty50_history_loader`, step 1 loads `fact_eod_price` + `nifty50_index_prices` per trading day, step 2 runs the analytics chain (52wk → signals → volume anomalies) in one pass at the end. New `--skip-constituents` flag. Closed 2026-05-16. |
| 128 | Backfill validation report (gaps, 52WK cross-check) | M1.5 | ✅ Done | `ingestion/backfill/validator.py` — per-year report covering row counts for 7 tables, monthly symbol coverage in `fact_eod_price`, missing-trading-day gap detection vs business-day calendar, duplicate-key check on `(trade_date, symbol)`, `pct_from_high` sanity, and a flag list (`ZERO_EOD_PRICES`, `HIGH_GAP_COUNT_N`, `DUPLICATE_KEYS`, `SIGNALS_NOT_COMPUTED`, `NO_INDEX_PRICES`). CLI: `python -m ingestion.backfill.validator --year 2024` for one year, `--all` for 2021→present. Closed 2026-05-16. |
| 124 | Alembic migrations for all tables | M1.5 | ✅ Done | `alembic.ini` + `alembic/env.py` (reads `settings.db_url` at import time; the `sqlalchemy.url` placeholder in alembic.ini is never used at runtime) + `alembic/versions/0001_baseline_baseline_schema.py` which runs `sql/schema.sql` verbatim via `op.execute()`. Idempotent because every CREATE in schema.sql uses IF NOT EXISTS — `alembic upgrade head` is a no-op on existing DBs after `alembic stamp 0001_baseline`. **Post-baseline rule:** `alembic/versions/` is canonical; new schema changes go through `alembic revision`, not direct edits to schema.sql or new `sql/migrations/*.sql` files. Operator README at `alembic/README`. Closed 2026-05-16. |
| 130 | Wire stale dashboard placeholders to live data | UI | ✅ Done | `api/main.py` adds a `nifty_index` block to `/market-overview` (close, prev_close, return_1d, realized_vol_20d, window_days) sourced from `nifty50_index_prices`. §01 KPI cards #1 (Nifty 50 Index) and #4 (Realized Vol · 20D) render live values when calc_date is in-window; #2 (52-Week Bracket) stays muted with a truthful "need 252 sessions, have N" hint until the index backfill reaches a year. §03 filter-row legend swaps the "RS · Nifty unavailable" warn pill for a plain `RS · Nifty` overlay tag; stats sidebar only emits the warn pill when `payload.rs_vs_nifty_series` is None (out-of-window calc_dates). §08 header hint no longer dangles the closed TODO-119/120 ref. 4 integration scenarios still pass. Closed 2026-05-16. |

**Status legend:** ✅ Done · 🟨 Partial · ⬜ Open · 🚫 Blocked (explicit hard block — call out in Notes).

**Bracketed reading of the ladder (post 2026-05-16 wave-1 close-out):**
- **Rank 1:** TODO-113 is the only remaining item with even a thin signal-value link — handling true reconstitution drift. Defer until NSE actually rebalances.
- **Ranks 2–5:** Pure infra (cache, alias table, Alembic, indexes). Necessary for Phase 1 closure but zero incremental dashboard value.
- Five items closed in this pass (123, 112, 115, 127, 128) had clustered around the M1.5 boundary; landing them in one branch keeps the merge churn cheap.

**Maintenance rules:**
1. Closing an item → update Status to ✅ and append the closing commit SHA (or PR #) to Notes.
2. Discovering a new gap → assign the next free TODO-### ID, add a row here, write the detail block below.
3. Spec-deviation items (the 5 "Must Fix" entries in the audit) flow into TODO-122 Notes — they're not separate IDs.
4. The "Spec Alignment Audit" tables below are descriptive (per-area %). The Master Status table is authoritative for TODO-### status; resolve any disagreement here.

### Cross-cutting spec deviations (post 2026-05-15 audit)

| # | Deviation | Status | TODO covering it |
|---|---|---|---|
| 1 | `signal_category` uses Bullish / Bearish (wrong labels) | ✅ Fixed — `compute_signals.py:298` emits "Accumulation"/"Momentum"/"EventDriven"/"Neutral" | 122-a |
| 2 | `rs_vs_nifty_*` = 0.0 instead of NULL | ⬜ Open | 122 + 106 |
| 3 | `iss_score` = 0.0 (the entire ISS scoring function) | ⬜ Open — `compute_signals.py:215` still hardcodes 0.0 even though `analytics/iss_scorer.py` exists | 122 |
| 4 | `volume_trend_3m` uses ratio threshold, not regression | ✅ Fixed — `volume_engine.py:70-87` uses `linregress` with R²≥0.30 | 122-b |
| 5 | `direction_consistency_20d` not computed | ✅ Fixed — `trend_stability_engine.py:63` | 122-c |

### Phase 5 — Alerting (not yet broken into TODO-###s)

Tracked at section-level for now; will be broken into individual TODOs when M1 closes.

| Item | Status |
|---|---|
| 14 alert rules A-01 … A-14 (spec §8) | ⬜ Open |
| Email / Slack / SMS delivery channels | ⬜ Open |
| Alert deduplication (5-day suppression) | ⬜ Open |
| EOD batch scheduler (DAG, spec M5.1) | ⬜ Open |

### Inline code TODOs (not in the registry)

| Location | Note | Status |
|---|---|---|
| `api/routers/watchlist.py:98` | "Replace with actual user authentication" | ⬜ Open |
| `ingestion/framework/loaders/reconstitution_loader.py:12` | "Implement upsert once CSV format confirmed" | ⬜ Open — subsumed by TODO-113 |

---

## Data Backfill Requirements

Snapshot as of **2026-05-17**. The dashboard ships against whatever's in Postgres — every gate, gauge, treemap, and signal table feeds off the same handful of tables below. Until the **Target** column is met, the corresponding dashboard surface either shows a muted pending hint (Card #2 52W Bracket, RS overlays on early dates) or relaxes its filter with a visible "gate relaxed" pill (§02 Watchlist categories).

### Coverage matrix — what's lit vs. what's still empty

| Table | Current | Target | Backfill command | Cadence | Unblocks |
|---|---|---|---|---|---|
| `dim_stock` | 6,442 rows (58 Nifty 50 members) | NSE security master fully populated | `python -m ingestion.framework.run_pipeline --source dim-stock --date YYYY-MM-DD --local-file NSE_CM_security_DDMMYYYY.csv` | Monthly (or on reconstitution) | Sector/industry labels, ISIN joins |
| `dim_stock.market_cap_cr` | **0 / 50** Nifty 50 names populated (NULL) | All 50 hydrated | Manual seed pending (TODO-131) | Monthly | Treemap cell sizing (currently falls back to ISS) |
| `dim_nifty50_constituent` | 14,450 rows · 2025-04-01 → 2026-05-08 | 2021-01-01 → today (per spec §C) | `python -m ingestion.framework.run_pipeline --source constituents --start 2021-01-01 --end YYYY-MM-DD` (and reconstitution drops in `data/raw/reconstitution/`) | On reconstitution (Mar / Sep), reseed via `data/raw/reconstitution/nifty50_history.csv` | Point-in-time membership for §03 sector RS aggregation |
| `fact_eod_price` | 111,028 rows · 43 trading days · 2026-03-11 → 2026-05-08 | **5 years** (~1,260 sessions) per spec M1.5 | `python -m ingestion.backfill.orchestrator --start 2021-01-01 --end YYYY-MM-DD` (+ `--local data/bhavcopy` for cached CSVs) | Daily EOD via `python -m ingestion.daily_run` | All return columns, 52W computation, RS series, scanner gates |
| `fact_52wk` | 111,028 rows · 43 trading days (derived) | Recomputed after each `fact_eod_price` extension | `python -m analytics.compute_52wk` | Daily EOD (auto after bhavcopy) | Drawdown scanner thresholds, breakout monitor |
| `nifty50_index_prices` | **38 rows** · 2026-03-11 → 2026-05-08 | **≥ 252 sessions** for §01 Card #2 (52W Bracket) | `python -m ingestion.daily_run` (index step) or backfill via `python -m ingestion.backfill.orchestrator` | Daily EOD; backfill once to ≥ 252 sessions | §01 Cards #1/#2/#4, §03 RS overlay outside the current 38-day window |
| `fact_corporate_action` | **0 rows** | Dividends / splits / bonuses / buybacks for last 1 year | Loader exists (`ingestion/corporate_actions_loader.py`) but **not wired into the daily pipeline** — TODO-132 | Daily EOD once wired | Dividend-adjusted returns, ex-date markers on §03 Trend Workbench, ISS Factor 5 |
| `fact_corporate_event` | 944 rows · 2026-04-28 → 2026-05-30 | Earnings / AGM / board-meeting calendar (forward + 1 year back) | `python -m ingestion.nse_scraper --source event-calendar` and `--source announcements`; framework: `--source event-calendar / announcements` | Daily (calendar) + Hourly during market hours (announcements) | §08 Events tracker, §03 event annotations, Event-Driven watchlist tab |
| `mart_stock_signals` | 111,028 rows · 43 days (derived) | Recomputed after each new `fact_eod_price` day | `python -m analytics.compute_signals --date YYYY-MM-DD` | Daily EOD (auto via orchestrator post-load step) | §01-§07 entire dashboard |
| `mart_volume_anomaly` | 111,028 rows · 43 days (derived) | Recomputed alongside signals | `python -m analytics.compute_volume_anomalies --date YYYY-MM-DD` | Daily EOD (auto via orchestrator post-load step) | §07 Volume Anomaly Monitor, VA-1…VA-7 rule tagging |
| `alerts` | 55 rows | Whatever the alert engine fires per day | `python -m alerts.alert_engine` (via `scripts/run_analytics.sh`) | Daily EOD (post-signals) | Phase 5 — out of M1 scope but rules already wired |
| `ingestion_log` | 2 rows | One row per ingestion run | Auto-written by `Pipeline.run()` | Per ingestion run | Operational visibility · drives `--check` outputs |

### What "fully populated" actually requires

Three concrete backfill jobs would clear the remaining gating issues that today force muted UI states and relaxed §02 gates:

1. **5-year EOD price history** — `python -m ingestion.backfill.orchestrator --start 2021-01-01 --end $(date +%F)` followed by `--skip-index` if index data is sourced separately, or just leave index-step enabled. Run once; ~1 hour with NSE rate limits. Unlocks 52-week math against real historical highs, kills the relaxed Contrarian/Drawdown gates, and gives §03 a full 6M/1Y/3Y window of data.
2. **Index price extension** — same orchestrator covers it, or run `python -m ingestion.backfill.orchestrator --start 2021-01-01 --end $(date +%F)` (no `--skip-index`). Specifically extends `nifty50_index_prices` past the current 38-day window so the §01 52-Week Bracket card can render an honest 52W high/low and the §03 RS overlay covers older windows.
3. **Corporate actions daily wiring** — fix TODO-132 by invoking `CorporateActionsLoader` from `ingestion/daily_run.py` (or scheduling it in the daily DAG). Backfill the last year once it's wired: `python -m ingestion.framework.run_pipeline --source corporate-actions --start 2025-05-17 --end $(date +%F)`. Unblocks the Event-Driven tab's ideal gate (currently always relaxed) and §03 ex-date markers.

### Validation cadence

After any backfill run, validate with:

```bash
python -m ingestion.backfill.validator --year 2024     # one year
python -m ingestion.backfill.validator --all           # 2021 → present
```

Flags emitted (`ZERO_EOD_PRICES`, `HIGH_GAP_COUNT_N`, `DUPLICATE_KEYS`, `SIGNALS_NOT_COMPUTED`, `NO_INDEX_PRICES`) should all clear before the dashboard is considered "live-data-ready".

---

## UI Feature Requests

Tracked per project rule (`.claude/CLAUDE.md` → "Maintain a consistent todo list of new feature requests and track its status").

| Date | Request | Status | Notes |
|---|---|---|---|
| 2026-05-10 | Configurable Near-breakout radar percent (slider) | **Done** | `dashboard/phase_f.py` — Distance + Min ISS sliders |
| 2026-05-10 | Same configurability for Active momentum and RS chart | **Done** | Min ISS slider on Active momentum; Top N slider on RS chart |
| 2026-05-10 | Sector Aggregation row click → stocks in sector with Primary Scanner cols | **Done** | `dashboard/app.py` — `on_select="rerun"` + `_render_scanner_drilldown` |
| 2026-05-10 | Treemap tile click → stock/sector details with Primary Scanner cols | **Done** | Same drill-down helper, dispatched on plotly_chart selection |
| 2026-05-11 | Consolidate dashboard to single page · 8 sections · Streamlit | **Done** | Phases 0–9 all complete on `feature/dashboard-consolidation` (latest commit `a719419`). Design locked at `design/mock_consolidated.html`. Implementation plan: `docs/dashboard_consolidation_plan.md`. §03 Trend Workbench live with multi-day price/volume/ISS analysis. §05/§06/§07 retokenized with primitives + row-click drill-in. §08 Events Tracker still wraps legacy renderer pending TODO-120 rewrite (TODO-119 table is done). |

---

## Spec Alignment Audit (2026-04-10)

Full walkthrough against `docs/nifty50_dashboard_full_spec.md` (Sections 1–9, 13).
Date: 2026-04-10. Covers everything built so far.

### Phase 1: Data Infrastructure — ~60% done

| Spec Requirement | Status | Notes |
|---|---|---|
| 8 tables + 3 auxiliary (Section 5) | **Done** | Schema matches spec column definitions exactly |
| dim_stock (10 cols) | **Done** | Seeded with 50 symbols |
| fact_eod_price (14 cols) | **Done** | All cols including series, delivery_qty/pct, source_file |
| fact_52wk (spec Table 3) | **Done** | Rolling 252-day computation, idempotent upsert |
| Bhavcopy ingestion (M1.1) | **Done** | Download, parse, header validation, series filter, idempotent load |
| Ingestion log | **Done** | Written on every load |
| config.yaml thresholds | **Done** | Series filter, volume, returns, 52w windows |
| Rate limiting | **Done** | 2s min, exponential backoff, circuit breaker |
| Local file fallback | **Done** | `LocalSource` with recursive search |
| CSV header validation | **Done** | Raises clear error listing missing columns |
| MTO delivery data (M1.1) | **Done** | Parser + loader + NSEClient + daily_run wiring complete. delivery_qty/pct now populate via T+1 MTO file. |
| NSE index prices (M2.3) | **Missing** | rs_vs_nifty_* hardcoded to 0.0. ISS Factor 2 blocked |
| dim_nifty50_constituent (M1.3) | **Missing** | Table exists but empty. No point-in-time membership |
| fact_corporate_action (M1.4) | **Missing** | Table exists but empty |
| fact_corporate_event (M1.4) | **Done** | `sql/schema.sql:108-127` — table + 3 indexes (idempotency via unique (symbol, event_date, event_type)). Empty until TODO-120 is rewritten with the spec event taxonomy. |
| purpose_parser (M1.4) | **Missing** | Not built |
| Backfill orchestrator (M1.5) | **Missing** | daily_run.py exists but no bulk 5-year loader |
| Alembic migrations (M1.5) | **Missing** | Manual DDL only |
| symbol_alias loader | **Missing** | Table exists in schema but no loader |
| Download validation | **Done** | `validate_bhavcopy_size` integrated into daily_run; rejects truncated files before parsing. |

### Phase 2: Core Analytics Engine — ~40% done

| Spec Milestone | Status | Notes |
|---|---|---|
| Returns: 1D, 1M, 3M, 1Y (M2.1) | **Done** | `returns_engine.py` |
| Volume ratios: 1d, 5d, 20d (M2.2) | **Done** | `volume_engine.py` |
| 52-week drawdown distance (M2.4) | **Done** | Merged from fact_52wk |
| mart_stock_signals population (M2.5) | **Partial** | Returns + volume + 52wk written |
| RS vs Nifty 50 (M2.3) | **Missing** | rs_vs_nifty_1m/3m/1y = 0.0 hardcoded. **ISS Factor 2 (Weight 20) blocked.** |
| volume_trend_3m regression | **Wrong method** | We use ratio threshold. Spec says: linear regression on 63-day series with R² ≥ 0.30. Labels will diverge on borderline cases. |
| direction_consistency_20d | **Missing** | Required for ISS Factor 6 (Weight 10) |
| intraday_reversal_count_20d | **Missing** | Required for Factor 6 penalty |
| ISS Scoring Function (M3.1) | **Missing** | iss_score = 0.0. The 7-factor, 0–100 composite (spec Section 7) is not built. **This is the core product value proposition.** |
| Signal classification (M3.2) | **Wrong categories** | We use "Bullish"/"Bearish"/"Neutral". Spec says "Accumulation"/"Momentum"/"EventDriven"/"Neutral". ACC/MOM/EVT rules (spec Section 6.2) not implemented. MOM tiers (Strong/Confirmed/Watch) absent. |
| mart_volume_anomaly (M3.3) | **Missing** | Table exists but empty. VA-1 through VA-7 rules not evaluated. |
| Event significance scoring (M3.4) | **Missing** | Factor 5 of ISS, EVT tag, Follow-up Required flag blocked. |

### Phase 4: Dashboard UI — ~7% done

| Spec View | Status | Gap |
|---|---|---|
| View 1: Market Overview | **Partial** | Sector breadth table exists. Missing: 5 KPI cards, advancing/declining donut, volatility gauge, performance heatmap (3 tabs). |
| View 2: Movers & Extremes | **Missing** | Top 10 gainers/losers, scatter plot (Return vs Volume), period + market cap filters. |
| View 3: Drawdown Scanner | **Missing** | Severity table, scatter plot, historical trend, ACC/Falling Knife tags. |
| View 4: Breakout/Momentum | **Missing** | MOM table with tiers, near-breakout radar, RS ranking chart. |
| View 5: Volume Anomaly | **Missing** | 3 spike sub-tables, heatmap grid, education sidebar. |
| View 6: Corporate Events | **Missing** | Calendar, timeline, upcoming events, actions feed. |
| View 7: Watchlist Builder | **Partial** | Static YAML. Spec wants: ISS-based auto-population, 4 tabs, pin/unpin, CSV export, ISS gauge. |

### Phase 5: Alerting — 0% done

| Spec Requirement | Status |
|---|---|
| 14 alert rules (A-01 through A-14, spec Section 8) | **Missing** |
| Email/Slack/SMS delivery channels | **Missing** |
| Alert deduplication (5-day suppression) | **Missing** |
| EOD batch scheduler (DAG, spec M5.1) | **Missing** |

### Key Deviations from Spec (Must Fix)

| # | Deviation | Impact |
|---|---|---|
| 1 | **signal_category uses "Bullish"/"Bearish"** instead of "Accumulation"/"Momentum"/"EventDriven" | Wrong semantic — "Bullish" means return direction, "Momentum" means multi-factor quality tag. Downstream views and alerts depend on correct categories. |
| 2 | **rs_vs_nifty_* = 0.0 instead of NULL** | Silently neutralises ISS Factor 2. Should be NULL when index data unavailable, so ISS computation can handle it explicitly. |
| 3 | **iss_score = 0.0 (not implemented)** | The entire product value proposition is the ISS. Without it, dashboard is raw data, not signal detection. |
| 4 | **volume_trend_3m uses ratio threshold, not regression** | Spec requires linear regression on 63-day series with R² goodness-of-fit. Simple ratio will mislabel borderline cases. |
| 5 | **direction_consistency_20d not computed** | ISS Factor 6 (Weight 10) can't fire. |

### Recommended Priority to Close Gaps

1. **NSE index prices ingestion** → unlocks RS → unlocks ISS Factor 2
2. **ISS scoring function** (7 factors, spec Section 7) → core product value
3. **Signal classification** (ACC/MOM/EVT, spec Section 6.2) → correct categories
4. **volume_trend_3m regression** → accurate trend labels
5. **Market Overview view** (View 1) → most-used view
6. **Movers view** (View 2) → straightforward once signals exist
7. **Corporate events ingestion** → unlocks EVT signal, Factor 5, View 6
8. **Alert rules** (14 rules, spec Section 8)

---

## Milestone 1.1 — NSE Bhavcopy Ingestion Pipeline (partially scoped)

Our plan covers: basic bhavcopy download, parse, load into `fact_eod_price`.
The spec requires significantly more.

### TODO-101: Align `fact_eod_price` columns with spec
- **What:** Our schema has 10 columns. The spec defines 14. Missing: `series` (VARCHAR), `delivery_qty` (BIGINT, nullable), `delivery_pct` (DECIMAL, nullable), `source_file` (VARCHAR). Also rename: `volume` → `total_traded_qty`, `traded_value` → `total_traded_value_lakh`, and add `total_trades` (INTEGER).
- **Why:** Downstream milestones (volume anomaly, signal computation) depend on these columns. Adding them later means backfilling from raw CSVs again.
- **Depends on:** M1a (table DDL). Update before M1b ingestion loads data.
- **Spec ref:** Section 5, Table 2 (`fact_eod_price`)

### TODO-102: Align `dim_stock` columns with spec
- **What:** Our schema has 5 columns (symbol, company_name, sector, isin, index_weight). The spec defines 10. Missing: `industry` (VARCHAR), `nifty50_member` (BOOLEAN), `market_cap_cr` (DECIMAL), `listing_date` (DATE), `face_value` (DECIMAL), `last_updated` (TIMESTAMP). Drop `index_weight` (that lives in `dim_nifty50_constituent`).
- **Why:** `nifty50_member` is used by every dashboard view to filter the universe. `market_cap_cr` drives heatmap cell sizing. `face_value` is needed for dividend yield computation in M2.
- **Depends on:** M1a (table DDL). Update before seed data is loaded.
- **Spec ref:** Section 5, Table 1 (`dim_stock`)

### TODO-103: Delivery position data ingestion (MTO file)
- **What:** Download MTO (Marketable Trade Orders) file from NSE (`MTO_<DDMMYYYY>.DAT`). Parse delivery_qty and delivery_pct. Join into `fact_eod_price` as a T+1 update pass (separate scheduled job after bhavcopy ingestion).
- **Why:** Delivery volume distinguishes real buying/selling from speculative churn. Required for volume anomaly detection (M2) and the Volume Anomaly Monitor view (View 5).
- **Depends on:** TODO-101 (delivery_qty/delivery_pct columns must exist).
- **Cons:** MTO file has a different format from bhavcopy — needs its own parser.
- **Spec ref:** Section 9, Milestone 1.1

### TODO-104: Ingestion log table
- **What:** Create a table recording: file downloaded (URL/path), rows inserted, rows failed, timestamp per run. Every ingestion job writes an entry.
- **Why:** Debugging failed ingestion runs is impossible without a log. The spec requires this as a first-class table.
- **Depends on:** M1a (DDL).
- **Spec ref:** Section 9, Milestone 1.1

### TODO-105: Corrupted download validation
- **What:** After downloading a bhavcopy ZIP, validate via checksum or row-count comparison against prior day's file. Reject and log if the file is truncated or corrupt.
- **Why:** NSE occasionally serves partial files. Without validation, corrupt data enters the pipeline and propagates to every downstream computation.
- **Depends on:** M1b (ingestion pipeline).
- **Spec ref:** Section 9, Milestone 1.1 edge cases

### TODO-106: NSE index prices ingestion
- **What:** Download Nifty 50 index daily prices from `https://archives.nseindia.com/content/indices/ind_close_all_<DDMMYYYY>.csv`. Store in a `nifty50_index_prices` table (date, close). Ingest as parallel stream alongside bhavcopy.
- **Why:** Required for Relative Strength computation (stock return minus Nifty 50 return). Every RS calculation in M2 needs this.
- **Depends on:** M1b (ingestion pipeline pattern established).
- **Spec ref:** Phase 2 Milestone 2.3, but ingested in Phase 1 as parallel stream

### TODO-107: `config.yaml` for thresholds
- **What:** Store all threshold values (volume spike multipliers, drawdown limits, return windows) in a `config.yaml` file, not hard-coded in Python.
- **Why:** Thresholds change during tuning. Hard-coding means code changes for every adjustment.
- **Depends on:** M1a (project structure).
- **Spec ref:** Section 9, environment/configuration requirements

---

## Milestone 1.2 — 52-Week High/Low

Our plan derives 52-week from `fact_eod_price` via a PostgreSQL VIEW. The spec requires a dedicated table.

### TODO-108: Create `fact_52wk` table
- **What:** Dedicated table with columns: `trade_date` (DATE), `symbol` (VARCHAR), `wk52_high`, `wk52_low`, `wk52_high_date`, `wk52_low_date`, `pct_from_high`, `pct_from_low`, `min_history_flag`. Composite PK on (trade_date, symbol). FK to `dim_stock`.
- **Why:** A VIEW recomputes on every query. With 50 stocks × 252 days, the table is ~12,600 rows — tiny. A table is faster for dashboard reads and simpler to join.
- **Depends on:** TODO-101 (`fact_eod_price` fully populated with 252+ trading days).
- **Spec ref:** Section 5, Table 3 (`fact_52wk`)

### TODO-109: `compute_52wk.py` — rolling 252-day computation
- **What:** For each (symbol, trade_date): compute MAX/MIN close over past 252 trading days, dates of those extremes, pct_from_high, pct_from_low. Must run AFTER `fact_eod_price` is loaded for the day.
- **Why:** The spec says "rolling 252 trading days" not "rolling 252 calendar days." Requires trading-day-aware lookback.
- **Depends on:** TODO-108 (table exists).
- **Edge cases:** Symbols with < 252 trading days — use available window, set `min_history_flag = TRUE`.
- **Spec ref:** Section 9, Milestone 1.2

### TODO-110: Idempotent upsert for `fact_52wk`
- **What:** `INSERT ... ON CONFLICT (trade_date, symbol) DO UPDATE` so re-running the computation doesn't create duplicates.
- **Why:** Same idempotency requirement as bhavcopy ingestion.
- **Depends on:** TODO-108.
- **Spec ref:** Section 9, Milestone 1.2 edge cases

---

## Milestone 1.3 — Nifty 50 Constituents and Reconstitution

Entire milestone is deferred from our plan.

### TODO-111: Create `dim_nifty50_constituent` table
- **What:** Columns: `symbol` (VARCHAR), `effective_from` (DATE), `effective_to` (DATE, nullable), `index_weight_pct` (DECIMAL, nullable), `replaced_symbol` (VARCHAR, nullable), `change_type` (ENUM: Addition/Deletion/Rebalance), `review_period` (VARCHAR). Composite PK on (symbol, effective_from).
- **Why:** Tracks historical Nifty 50 membership. Critical for back-testing (point-in-time membership check) and suppressing signals for newly-added stocks (< 30 days).
- **Depends on:** TODO-102 (`dim_stock` must exist for FK).
- **Spec ref:** Section 5, Table 4

### TODO-112: Seed CSV `nifty50_history.csv`
- **What:** Compile 5-year historical reconstitution data from NSE circulars into a CSV. Columns match `dim_nifty50_constituent` schema. First-run bulk insert from this file.
- **Why:** Historical membership data is the foundation for point-in-time queries. Without it, you can't answer "was RELIANCE in the index on 2023-06-15?"
- **Depends on:** TODO-111.
- **Cons:** Manual compilation from NSE circulars. Budget a few hours.
- **Spec ref:** Section 9, Milestone 1.3

### TODO-113: Constituent maintenance loader
- **What:** Subsequent runs accept `new_addition.json` / `new_deletion.json`, upsert rows, auto-set `effective_to` on outgoing stock. Bulk insert on first run, incremental upsert after.
- **Why:** NSE reconstitutes the index semi-annually (March/September). The loader must handle additions, deletions, and weight-only updates.
- **Depends on:** TODO-111, TODO-112.
- **Spec ref:** Section 9, Milestone 1.3

### TODO-114: `is_nifty50_member(symbol, as_of_date) -> bool` utility
- **What:** Query `dim_nifty50_constituent` for point-in-time membership. Returns True if the symbol had an active membership interval covering `as_of_date`.
- **Why:** Every signal computation and dashboard view needs to filter by index membership. This function is called constantly.
- **Depends on:** TODO-111.
- **Edge cases:** Same symbol re-entering after deletion (non-overlapping date ranges), weight-only updates (Rebalance type — no new interval, just update weight).
- **Spec ref:** Section 9, Milestone 1.3

### TODO-115: Seed CSV validation before insert
- **What:** Schema validation on `nifty50_history.csv` before bulk insert: check for required fields, valid date ranges, no overlapping intervals per symbol.
- **Why:** Data entry errors in the seed file create silent corruption. Catch them before they enter the DB.
- **Depends on:** TODO-112.
- **Spec ref:** Section 9, Milestone 1.3 edge cases

---

## Milestone 1.4 — Corporate Actions and Events

Entire milestone is deferred from our plan.

### TODO-116: Create `fact_corporate_action` table
- **What:** Columns: `action_id` (BIGINT AUTO PK), `symbol` (FK), `action_type` (ENUM: Dividend/Bonus/Split/Rights/Buyback), `ex_date`, `record_date`, `payment_date`, `purpose_text`, `ratio_numerator`, `ratio_denominator`, `face_value`, `dividend_amount_per_share`, `data_source`.
- **Why:** Drives price adjustment computation (M2) and the Corporate Events Tracker view (View 6).
- **Depends on:** TODO-102 (`dim_stock` FK).
- **Spec ref:** Section 5, Table 5

### TODO-117: `purpose_parser.py` — regex library for NSE purpose text
- **What:** Parse NSE's free-text "Purpose" field to extract structured fields:
  - Contains "DIVIDEND" → Dividend; parse "RS X.XX" for amount
  - Contains "BONUS" → Bonus; parse ratio "X:Y"
  - Contains "SPLIT" → Split; parse "FROM RS X TO RS Y"
  - Contains "RIGHTS" → Rights
  - Contains "BUY BACK" / "BUYBACK" → Buyback
- **Why:** NSE stores corporate actions as unstructured text. Without a parser, every downstream computation needs raw text matching.
- **Depends on:** TODO-116.
- **Edge cases:** Multi-part purpose text (interim + final dividend combined), missing amounts, non-standard formats.
- **Spec ref:** Section 9, Milestone 1.4

### TODO-118: `ingest_corporate_actions.py`
- **What:** Download corporate actions from NSE, parse with purpose_parser, insert into `fact_corporate_action`. Deduplicate on (symbol, action_type, ex_date).
- **Why:** Daily ingestion pipeline for corporate actions data.
- **Depends on:** TODO-116, TODO-117.
- **Spec ref:** Section 9, Milestone 1.4

### TODO-119: Create `fact_corporate_event` table
- **What:** Columns: `event_id` (BIGINT AUTO PK), `symbol` (FK), `event_date`, `event_type` (ENUM: Earnings/Leadership_Change/M&A/Large_Order/Pledging_Change/Rating_Change/Regulatory/Other), `event_summary`, `raw_announcement_text`, `categorization_method` (ENUM: Manual/Rule/NLP), `significance_score` (1-5), `price_chg_1d/5d/20d`, `volume_spike_flag`, `follow_up_required`.
- **Why:** Drives event significance scoring, "Needs Event Review" signal tags, and the Corporate Events Tracker view (View 6).
- **Depends on:** TODO-102 (`dim_stock` FK).
- **Spec ref:** Section 5, Table 6

### TODO-120: `ingest_corporate_events.py` + keyword classifier
- **What:** Ingest from NSE announcements feed (or CSV export). Apply keyword-based rule classification to assign `event_type`. Populate `raw_announcement_text` for future NLP enrichment.
- **Why:** Qualitative events (earnings, M&A, leadership changes) need classification to feed signal computation.
- **Depends on:** TODO-119.
- **Edge cases:** Duplicate announcements (dedup), unclassified categories (log for manual review), missing event dates.
- **Spec ref:** Section 9, Milestone 1.4

### TODO-121: Unit tests for purpose_parser
- **What:** Test each regex rule: dividend amount extraction, bonus ratio parsing, split ratio parsing, rights detection, buyback detection. Test edge cases: multi-part purpose text, missing amounts, non-standard formats.
- **Why:** The parser is the single point of failure for corporate action data quality. Silent mis-parsing corrupts every downstream computation.
- **Depends on:** TODO-117.
- **Spec ref:** Section 9, Milestone 1.4

---

## Milestone 1.5 — Schema Hardening, Backfill, and Infrastructure

Our plan covers 2 tables with manual DDL. The spec requires 8+ tables with Alembic and a backfill orchestrator.

### TODO-122: Create `mart_stock_signals` table
- **What:** Columns: `calc_date`, `symbol`, `return_1d/1m/3m/1y`, `rs_vs_nifty_1m/3m/1y`, `vol_ratio_1d/5d/20d`, `drawdown_from_52w_high_pct`, `distance_from_52w_low_pct`, `avg_volume_20d`, `volume_trend_3m`, `iss_score`, `signal_category`, `accumulation_flag`, `momentum_flag`, `event_flag`, `last_event_type/date`, `days_since_last_event`.
- **Why:** This is the central output table for the dashboard. Every view reads from this table. Without it, each view computes signals on the fly (slow, duplicative).
- **Depends on:** TODO-108 (fact_52wk), TODO-111 (constituents), TODO-116 (corporate actions), TODO-119 (corporate events). Full data layer must exist first.
- **Spec ref:** Section 5, Table 7

### TODO-123: Create `mart_volume_anomaly` table
- **What:** Columns: `calc_date`, `symbol`, `volume_today`, `avg_vol_20d`, `volume_ratio`, `spike_level` (ENUM: Normal/Mild/Moderate/High/Extreme), `price_chg_on_spike_day`, `delivery_pct`, `nearest_event_within_5d`, `nearest_event_type`, `anomaly_direction` (Up/Down).
- **Why:** Powers View 5 (Volume Anomaly Monitor). Pre-computing anomalies avoids scanning all 50 stocks' volume history on every page load.
- **Depends on:** TODO-101 (delivery data in fact_eod_price), TODO-119 (corporate events for event proximity).
- **Spec ref:** Section 5, Table 8

### TODO-124: Alembic migrations for all tables
- **What:** Set up Alembic. Generate initial migration from existing DDL for all 8+ tables. All future schema changes go through Alembic, not manual DDL.
- **Why:** By the time all 8 tables exist, manual DDL scripts are unmaintainable. Alembic tracks version history and enables safe rollbacks.
- **Depends on:** All tables finalized (TODO-101 through TODO-123).
- **Spec ref:** Section 9, Milestone 1.5

### TODO-125: `symbol_alias` table
- **What:** Map old symbol names to new ones (e.g., INFRATEL → INDUSINDBK post-merger). Used during backfill to maintain historical continuity without modifying primary records.
- **Why:** Without this, backfill data for renamed symbols creates orphan rows that don't join with current `dim_stock`.
- **Depends on:** Extended backfill (TODO-127).
- **Spec ref:** Section 9, Milestone 1.5

### TODO-126: Proper indexes on all fact/mart tables
- **What:** Composite `(trade_date, symbol)` index on all `fact_` and `mart_` tables. `symbol` index on all tables. `trade_date DESC` BRIN index on time-series tables (once data exceeds 1 year).
- **Why:** Query performance for dashboard views that filter by date range and symbol.
- **Depends on:** All tables exist.
- **Spec ref:** Section 9, Milestone 1.5

### TODO-127: Backfill orchestrator
- **What:** `backfill_orchestrator.py` that runs all ingestion steps in order with progress logging. Sequence:
  1. `dim_stock` (seed from NSE security master CSV)
  2. `dim_nifty50_constituent` (from `nifty50_history.csv`)
  3. `fact_eod_price` (bhavcopy, 5 years ≈ 1250 trading days × ~50 symbols)
  4. `fact_52wk` (derived from `fact_eod_price`)
  5. `fact_corporate_action` (5-year NSE dump)
  6. `fact_corporate_event` (best-effort from available announcements)
- **Why:** Manual step-by-step backfill is error-prone and slow. The orchestrator handles ordering (FK dependencies), retries, progress tracking, and caching downloaded files.
- **Depends on:** All ingestion scripts exist.
- **Performance target:** < 30 min for `fact_eod_price` 5-year load, < 5 min for `fact_52wk` computation.
- **Spec ref:** Section 9, Milestone 1.5

### TODO-128: Backfill validation report
- **What:** After backfill completes, generate a report: row counts per year per table, gap detection (missing trading days), cross-check `fact_52wk` rolling values against NSE 52-week file (> 2% divergence = flag).
- **Why:** Silent data quality issues are the #1 risk. Catch them before they propagate to signals.
- **Depends on:** TODO-127.
- **Spec ref:** Section 9, Milestone 1.5

### TODO-129: Local download cache during backfill
- **What:** Cache all downloaded NSE ZIP files locally during backfill. On failure, resume from cached files instead of re-downloading.
- **Why:** NSE rate-limits aggressively. A 5-year backfill hitting the network for every file will take hours. Cached files make re-runs fast.
- **Depends on:** TODO-127.
- **Spec ref:** Section 9, Milestone 1.5 edge cases

---

## Cross-cutting (apply to multiple milestones)

### TODO-001: CSV column header validation
- **What:** Before parsing any NSE CSV, validate that expected columns exist. Raise a clear error listing missing/changed columns.
- **Why:** NSE changes column names without notice. Without validation, the parser silently returns empty results.
- **Depends on:** M1b (ingestion parser). Applies to all ingestion scripts.
- **Risk:** P0 silent failure mode.

### TODO-002: Health check endpoint
- **What:** Add GET /health to FastAPI that checks DB connectivity and returns table row counts.
- **Why:** Developer experience — opaque 500 errors when PG is down.
- **Depends on:** M1c (API setup). Low effort, high value.

### TODO-003: Idempotency across all ingestion scripts
- **What:** Every INSERT uses `ON CONFLICT ... DO NOTHING` or `DO UPDATE`. No ingestion script creates duplicates on re-run.
- **Why:** Daily pipelines run multiple times during development and debugging. Duplicates corrupt every downstream computation.
- **Depends on:** All ingestion scripts (TODO-103, TODO-106, TODO-118, TODO-120).
- **Spec ref:** Section 9, Milestone 1.1 edge cases (applies universally)

### TODO-004: Rate limiting for all NSE downloads
- **What:** Exponential backoff with 2s minimum delay between NSE requests. User-agent header. Session management for cookies.
- **Why:** NSE blocks aggressive scrapers. Without rate limiting, backfill fails partway through.
- **Depends on:** All NSE download scripts.
- **Spec ref:** Section 9, Milestone 1.1 edge cases (applies universally)

---

## Cross-cutting — New from Eng Review (2026-04-10)

### TODO-NEW: Composable analytics engine contract
- **What:** Each signal type (returns, volume, drawdown, RS, events) is an independent engine module with a standard interface: `compute(symbol, date_range, price_df) -> DataFrame`. Engines register with a signal registry. Adding a new signal = new engine file + registry entry. The pipeline orchestrator runs all registered engines after ingestion.
- **Why:** The user explicitly stated composability as a core principle. Without a contract, each milestone will reinvent how signals plug in. The spec Section 13.3 defines "analytics is entirely stateless and pure Python — each engine takes a DataFrame in, returns a DataFrame out."
- **Depends on:** M1c (analytics layer exists).
- **Spec ref:** Section 13.3 Key Decision 1

---

## Phase 1 Completion Checklist

Phase 1 is complete when ALL of the following are true:

- [ ] All 8 spec tables exist (dim_stock, fact_eod_price, fact_52wk, dim_nifty50_constituent, fact_corporate_action, fact_corporate_event, mart_stock_signals, mart_volume_anomaly) + ingestion_log + symbol_alias + nifty50_index_prices
- [ ] All columns match spec definitions exactly
- [ ] Alembic migrations for all tables
- [ ] 5-year backfill runs successfully in < 30 minutes
- [ ] All ingestion scripts are idempotent with rate limiting
- [ ] `is_nifty50_member(symbol, as_of_date)` works for point-in-time queries
- [ ] `purpose_parser` extracts dividend amounts and bonus/split ratios correctly
- [ ] `fact_52wk` cross-checked against NSE 52-week file (divergence < 2%)
- [ ] Validation report confirms row counts per year
- [ ] No duplicate (trade_date, symbol) in fact_eod_price
- [ ] No NULL values in non-nullable columns for current Nifty 50 members
