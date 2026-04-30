# Database ERD: Ingestion Framework & Analytics Tables

## Tables & Data Flow

```
INGESTION SOURCES (NSE) → FETCHER → LOADER → DATABASE TABLES
```

### Core Dimension Tables

#### `dim_stock` (Master Stock Reference)
**Columns:** symbol (PK), company_name, sector, industry, nifty50_member, market_cap_cr, listing_date, face_value, isin, last_updated
**Populated by:**
- `ingestion.seed_stocks` script (one-time seed for the 50 Nifty constituents — owns sector/industry)
- Source J: `dim_stock_loader.py` (daily NSE security master refresh — owns company_name, listing_date, face_value, isin)
**Fetcher:** `NseHttpFetcher(SourceType.DIM_STOCK)` + `HybridFetcher` fallback
**Source File:** `NSE_CM_security_DDMMYYYY.csv.gz` from NSE archives (gzipped; auto-decompressed by fetcher)
**Local Drop:** `data/raw/dim_stock/`
**Upsert behaviour:** ON CONFLICT updates only file-sourced columns; sector / industry / nifty50_member are preserved (owned by seed_stocks + ConstituentsLoader).
**Related to:** All fact tables via foreign key on `symbol`

#### `dim_nifty50_constituent` (Index Membership)
**Columns:** 
- symbol (FK → dim_stock, PK part)
- effective_date (PK part)
- effective_end_date
- weight
- index_name
**Populated by:** 
- Source C: `constituents_loader.py` (HTTP fetcher downloads `ind_nifty50list.csv`)
- Source D: `reconstitution_loader.py` (local-only, manual drop into `data/raw/reconstitution/`)
**Fetcher:** 
- C: `NseHttpFetcher(SourceType.CONSTITUENTS)` + `HybridFetcher` fallback
- D: `LocalFetcher` only (no HTTP)

---

### Fact Tables: Price & Technical Data

#### `fact_eod_price` (Daily OHLCV from NSE)
**Columns:**
- trade_date (PK part)
- symbol (FK → dim_stock, PK part)
- open, high, low, close (NUMERIC(12,2))
- volume (BIGINT)
- prev_close, last, num_trades, value_traded

**Populated by:** 
- Source A: `eod_price_loader.py` (wraps existing `BhavcopyParser` + `BhavcopyLoader`)
**Fetcher:** `NseHttpFetcher(SourceType.BHAVCOPY)` + `HybridFetcher` fallback
**Source File:** `sec_bhavdata_full_DDMMYYYY.csv` from NSE archives
**Local Drop:** `data/raw/bhavcopy/`

#### `fact_52wk` (52-Week High/Low Reference)
**Columns:**
- trade_date (PK part)
- symbol (FK → dim_stock, PK part)
- wk52_high, wk52_low (NUMERIC(12,2))
- wk52_high_date, wk52_low_date (DATE)
- pct_from_high, pct_from_low (computed from fact_eod_price.close)

**Populated by:** 
- Source B: `wk52_loader.py` (new implementation)
  - Parses CSV with dynamic header detection (handles NSE format variations)
  - Applies column aliases for both legacy and 2025+ formats
  - Enriches pct_from_high/low by joining with fact_eod_price
**Fetcher:** `NseHttpFetcher(SourceType.WK52)` + `HybridFetcher` fallback
**Source File:** `CM_52_wk_High_low_DDMMYYYY.csv` from NSE archives
**Local Drop:** `data/raw/52wk/`

---

### Fact Tables: Corporate Events

#### `fact_corporate_action` (Dividends, Splits, Bonuses, Rights)
**Columns:**
- action_id (PK)
- symbol (FK → dim_stock)
- action_type, amount, ratio
- ex_date, record_date, payment_date
- announcement_date

**Populated by:** 
- Source E: `corporate_actions_loader.py` (wraps existing `CorporateActionsParser` + `CorporateActionsLoader`)
**Fetcher:** `LocalFetcher` only (per-symbol API not yet implemented)
**Local Drop:** `data/raw/corporate_actions/`

#### `fact_corporate_event` (Earnings, AGMs, Board Meetings, Announcements)
**Columns:**
- event_id (PK)
- symbol (FK → dim_stock)
- event_type (earnings, agm, board_meeting, announcement, etc.)
- event_date
- description
- source (event_calendar or announcements)

**Populated by:** 
- Source F: `event_calendar_loader.py` (wraps existing `CorporateEventsIngestor` + `CorporateEventsLoader`)
  - Source: `https://www.nseindia.com/api/event-calendar?index=equities`
- Source G: `announcements_loader.py` (wraps existing `AnnouncementsIngestor` + `AnnouncementsLoader`)
  - Source: `https://www.nseindia.com/api/corporate-announcements?index=equities`
**Fetcher:** `NseHttpFetcher` for both F & G (JSON APIs)
**Local Drop:** `data/raw/event_calendar/`, `data/raw/announcements/`

#### `fact_intraday` (Intraday OHLCV—Placeholder)
**Status:** NOT IMPLEMENTED (Source H, vendor integration pending)
**Populated by:** `intraday_loader.py` (raises `NotImplementedError`)
**Target vendor:** TrueData or Global Datafeeds (future)

---

### Analytics & Signals

#### `fact_iss_score` (Investment Signal Score Composite)
**Columns:**
- trade_date (PK part)
- symbol (FK → dim_stock, PK part)
- iss (0–100 composite score)
- component_scores (JSON: price_perf, rel_strength, drawdown, volume, events)
- signal_class (Momentum, Accumulation, EventDriven, etc.)

**Populated by:** `analytics.compute_signals` module (not part of ingestion framework)
**Dependencies:** 
- Requires fact_eod_price, fact_52wk, fact_corporate_event to be current

---

### Operations & Logging

#### `fact_ingestion_log` (Pipeline Execution Log)
**Columns:**
- run_id (PK)
- source_name (e.g., "bhavcopy", "wk52", "constituents", ...)
- table_name (target table)
- trade_date
- status (success, failure)
- rows_affected
- error_message (NULL on success)
- started_at, completed_at (TIMESTAMP)
- elapsed_seconds

**Populated by:** 
- `Pipeline.run()` via `IngestionLogger.record_success()` or `record_failure()`
- One row per pipeline execution (regardless of success/failure)

**Written by all framework components:**
- `run_pipeline.py` CLI orchestrates
- Each loader via Pipeline
- Catches both success and exception paths

---

## Data Flow Diagram (Text)

```
NSE HTTP APIs / CSV Files
    ↓
┌─────────────────────────────────────────────────────────────┐
│              INGESTION FRAMEWORK PIPELINE                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Fetcher (HTTP or Local)                                    │
│  ├─ NseHttpFetcher → NSE archives/APIs (primary)           │
│  └─ LocalFetcher → data/raw/<source>/ (fallback)           │
│      └─ HybridFetcher wraps both (HTTP→Local fallback)     │
│                 ↓                                            │
│  Loader (source-specific parser + upsert)                  │
│  ├─ DimStockLoader → dim_stock (J, gzipped CSV)            │
│  ├─ EodPriceLoader → fact_eod_price                        │
│  ├─ Wk52Loader → fact_52wk                                 │
│  ├─ ConstituentsLoader → dim_nifty50_constituent           │
│  ├─ ReconstitutionLoader → dim_nifty50_constituent (local) │
│  ├─ CorporateActionsLoader → fact_corporate_action         │
│  ├─ EventCalendarLoader → fact_corporate_event (F)         │
│  └─ AnnouncementsLoader → fact_corporate_event (G)         │
│                 ↓                                            │
│  IngestionLogger                                            │
│  └─ writes to fact_ingestion_log (row count, status, etc.) │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
PostgreSQL Database
    ├─ dim_stock (master)
    ├─ dim_nifty50_constituent (membership + weights)
    ├─ fact_eod_price (daily OHLCV)
    ├─ fact_52wk (52W high/low reference)
    ├─ fact_corporate_action (dividends, splits, bonuses)
    ├─ fact_corporate_event (earnings, AGMs, announcements)
    └─ fact_ingestion_log (audit trail)
    ↓
Analytics Layer
    ├─ compute_signals → fact_iss_score
    ├─ compute_52wk (rolling high/low validation)
    └─ compute_volume_anomalies
```

---

## CLI Entry Point & Orchestration

**`ingestion/framework/run_pipeline.py`** — Single source of truth for source-to-table wiring:

| Source | Spec | Table | Loader | Fetcher | Local Drop |
|---|---|---|---|---|---|
| dim-stock | J | dim_stock | DimStockLoader | HTTP (gzipped) + Local | data/raw/dim_stock/ |
| bhavcopy | A | fact_eod_price | EodPriceLoader | HTTP + Local | data/raw/bhavcopy/ |
| wk52 | B | fact_52wk | Wk52Loader | HTTP + Local | data/raw/52wk/ |
| constituents | C | dim_nifty50_constituent | ConstituentsLoader | HTTP + Local | data/raw/constituents/ |
| reconstitution | D | dim_nifty50_constituent | ReconstitutionLoader | Local only | data/raw/reconstitution/ |
| corporate-actions | E | fact_corporate_action | CorporateActionsLoader | Local | data/raw/corporate_actions/ |
| event-calendar | F | fact_corporate_event | EventCalendarLoader | HTTP + Local | data/raw/event_calendar/ |
| announcements | G | fact_corporate_event | AnnouncementsLoader | HTTP + Local | data/raw/announcements/ |
| intraday | H | fact_intraday | IntradayLoader | — | — |

**Usage:**
```bash
# Single source, today
python -m ingestion.framework.run_pipeline --source bhavcopy

# Single source, specific date
python -m ingestion.framework.run_pipeline --source wk52 --date 2024-01-15

# All automated sources (A, B, C, E, F, G)
python -m ingestion.framework.run_pipeline --source all --date 2024-01-15

# Backfill date range (skips weekends)
python -m ingestion.framework.run_pipeline --source bhavcopy \
  --start 2024-01-01 --end 2024-01-31

# Local-only mode (skip HTTP, use drop folders)
python -m ingestion.framework.run_pipeline --source bhavcopy --local-only
```

---

## Foreign Key Relationships

```
dim_stock
  ↑
  ├─ dim_nifty50_constituent.symbol → dim_stock.symbol
  ├─ fact_eod_price.symbol → dim_stock.symbol
  ├─ fact_52wk.symbol → dim_stock.symbol
  ├─ fact_corporate_action.symbol → dim_stock.symbol
  ├─ fact_corporate_event.symbol → dim_stock.symbol
  └─ fact_iss_score.symbol → dim_stock.symbol
```

**Idempotency:** All loaders use `ON CONFLICT (trade_date, symbol) DO UPDATE` to allow safe re-runs on the same date.

---

## Test Coverage

**Unit Tests:** `tests/unit/test_framework_loaders.py` (covers all loaders incl. DimStock)
**Fetcher Tests:** `tests/unit/test_framework_fetchers.py` (Local, HTTP, Hybrid + gzipped download)
**Pipeline Tests:** `tests/unit/test_framework_pipeline.py` (Pipeline orchestration)

**All 48 framework tests passing.**
