# Starfish: Nifty 50 Investment Signal Dashboard

**Starfish** is an information-dense, terminal-inspired financial dashboard designed for rapid analysis of Nifty 50 stocks. It combines technical indicators, relative strength metrics, and corporate events into a unified **Investment Signal Score (ISS)**.

![Starfish Logo](starfish_logo.svg)

## Key Features

- **Morning Digest**: Instant overview of the top 3 high-conviction signals with rationales.
- **Unified Terminal UI**: A single-page, vertically-dense layout for maximum speed-to-insight.
- **Investment Signal Score (ISS)**: A proprietary 0-100 score based on:
  - Price Performance (3M/1Y)
  - Relative Strength vs Nifty 50
  - Drawdown & Base Recovery
  - Volume Confirmation
  - Corporate Events (Earnings, Dividends, Splits, etc.)
- **Signal Classification**:
  - `Momentum`: High ISS with positive trend and volume confirmation.
  - `Accumulation`: Deep pullbacks with contracting volume and fundamental base.
  - `EventDriven`: Priority signals for upcoming or recent corporate actions.
- **Interactive Visualizations**:
  - Sector Rotation & Breadth Heatmap.
  - Volatility vs Return Scatter Plots.
  - Sector Treemaps.

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Streamlit
- **Database**: PostgreSQL
- **Analytics**: Pandas & SQLAlchemy
- **Visualizations**: Plotly

## Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL

### Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd nifty50-dashboard
   ```

2. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables in `.env`:
   ```
   DATABASE_URL=postgresql://user:pass@localhost:5432/nifty50
   ```

### Running the Dashboard

Launch both the API and the Streamlit dashboard using the provided script:
```bash
./run.sh                # Start API + Dashboard
./run.sh --init         # Create schema + load sample data, then start
./run.sh --api-only     # Start only the FastAPI server (port 8000)
./run.sh --dash-only    # Start only the Streamlit dashboard (port 8501)
./run.sh --stop         # Stop all running services
```

---

## Operational Cadence — what to run, when

The dashboard reads exclusively from Postgres; freshness of every panel depends on the schedule below. Always activate the venv first: `source venv/bin/activate`.

> See `TODOS.md › Data Backfill Requirements` for the per-table coverage matrix and what each gap unblocks. Detailed CLI options for every command live in the **Command Reference** section that follows.

### One-time bootstrap

Run on a fresh deployment, in this order. The full sequence takes 1–2 hours, dominated by the 5-year backfill download.

| Step | Command | Produces |
|---|---|---|
| 1 · Schema | `psql "$DB_URL" -f sql/schema.sql` | All tables, indexes, FK constraints |
| 2 · Alembic baseline | `alembic stamp 0001_baseline` | Marks DB as already-migrated for future schema changes |
| 3 · Seed Nifty 50 master | `python -m ingestion.seed_stocks` | `dim_stock` rows for the current 50 constituents |
| 4 · Seed reconstitution history | `python -m ingestion.framework.run_pipeline --source reconstitution --date 2021-01-01` (CSV at `data/raw/reconstitution/nifty50_history.csv`) | `dim_nifty50_constituent` baseline (point-in-time membership) |
| 5 · 5-year EOD + index backfill | `python -m ingestion.backfill.orchestrator --start 2021-01-01 --end $(date +%F)` | `fact_eod_price` (~1,260 sessions × 50 symbols) + `nifty50_index_prices` + auto-computes `fact_52wk` / `mart_stock_signals` / `mart_volume_anomaly` post-load |
| 6 · Validate the backfill | `python -m ingestion.backfill.validator --all` | Per-year report; expect zero flags before declaring live-data-ready |
| 7 · Corporate-event seed (1 yr) | `python -m ingestion.framework.run_pipeline --source event-calendar --start $(date -v -1y +%F) --end $(date +%F)` then `--source announcements` | `fact_corporate_event` populated |

### Daily — EOD (run after NSE closes, ~6:30 PM IST)

The canonical daily runner is `./scripts/run_daily.sh`; the analytics chain is `./scripts/run_analytics.sh`. They are idempotent — safe to re-run.

| When | Command | Refreshes |
|---|---|---|
| **T+0 ~6:30 PM IST** | `./scripts/run_daily.sh` | `fact_eod_price`, `nifty50_index_prices` (and corporate actions / events when `--corporate-actions` / `--corporate-events` flags are passed) |
| **T+0 ~7:00 PM IST** | `./scripts/run_analytics.sh` | `fact_52wk`, `mart_stock_signals`, `mart_volume_anomaly`, `alerts` |

Run on every trading day, once, in this order. The daily runner accepts `--date YYYY-MM-DD` for replays and `--backfill N` for catching up after a gap; `run_analytics.sh --status` prints current row counts and date ranges across the analytics tables.

### Intraday — announcements (optional, market hours)

| Command | Refreshes | Frequency |
|---|---|---|
| `python -m ingestion.nse_scraper --source announcements` | `fact_corporate_event` (filings published since the last scrape) | Hourly during 9:15 AM – 3:30 PM IST trading window |

### Weekly

| When | Command | Why |
|---|---|---|
| **Sunday** | `python -m ingestion.backfill.validator --year $(date +%Y)` | Catches missing trading days, duplicate keys, and `pct_from_high` drift before they propagate |

### Monthly

| When | Command | Why |
|---|---|---|
| **1st of month** | `python -m ingestion.framework.run_pipeline --source dim-stock --date $(date +%F) --local-file data/raw/dim_stock/NSE_CM_security_$(date +%d%m%Y).csv` | Refreshes sector/industry/ISIN from NSE security master |
| **1st of month** | (Pending TODO-131) Snapshot `dim_stock.market_cap_cr` from NSE security master or vendor feed | Treemap cell sizing falls back to ISS until this is populated |

### Quarterly — Nifty 50 reconstitution (Mar / Sep)

| When | Command | Why |
|---|---|---|
| **Last Friday of Mar / Sep** | Drop NSE-published reconstitution CSV into `data/raw/reconstitution/` and run `python -m ingestion.framework.run_pipeline --source reconstitution --date YYYY-MM-DD` | Maintains point-in-time index membership; without this, post-reconstitution sector aggregates drift |

### Service health & operational checks

| Command | Use case |
|---|---|
| `./scripts/run_analytics.sh --status` | At-a-glance row counts + date ranges for `fact_*` / `mart_*` / `alerts` |
| `./scripts/run_corporate_backfill.sh --check` | File counts in `data/corporate/{actions,events}/` + DB row counts |
| `./scripts/run_load_bhavcopy.sh --check` | Bhavcopy file count in `data/bhavcopy/` + `fact_eod_price` coverage |
| `curl http://localhost:8000/health` | API liveness + table row counts |

---

## Command Reference

> All commands assume the venv is active: `source venv/bin/activate`

### Daily Ingestion (legacy pipeline — `ingestion/daily_run.py`)

Each run ingests **bhavcopy → `fact_eod_price`** and the **Nifty 50 index close → `nifty50_index_prices`** (the latter feeds the RS-vs-Nifty overlay on §03 Trend Workbench and `mart_stock_signals`). The index step reuses `BackfillOrchestrator`'s download/cache/upsert plumbing and is idempotent; on holidays or HTTP misses it logs and records `index_rows: 0` without failing the run. Pass `--skip-index` to bypass it.

```bash
# Today's bhavcopy + Nifty 50 index close (default)
python -m ingestion.daily_run

# A specific trading date
python -m ingestion.daily_run --date 2024-01-15

# Backfill last N calendar days
python -m ingestion.daily_run --backfill 252

# Backfill an explicit date range
python -m ingestion.daily_run --start 2024-01-01 --end 2024-03-31

# Use a local CSV directory instead of NSE download
python -m ingestion.daily_run --local /path/to/csvs

# Skip the Nifty 50 index-price step (bhavcopy only)
python -m ingestion.daily_run --date 2024-01-15 --skip-index

# Ingest bhavcopy + corporate actions + announcements + recompute signals
python -m ingestion.daily_run \
  --date 2024-01-17 \
  --corporate-actions data/ca.csv \
  --corporate-events data/ann.csv \
  --compute-signals
```

The returned stats dict includes an `index_rows` key (`1` on a successful close, `0` on holiday/miss, `None` when `--skip-index` is set).

### Ingestion Framework (`ingestion/framework/`)

The new framework provides a uniform `fetch → parse → upsert → log` contract over all 9 spec data sources. Use the `run_pipeline` CLI to trigger any source:

```bash
# Today's bhavcopy → fact_eod_price
python -m ingestion.framework.run_pipeline --source bhavcopy

# A specific source for a specific date
python -m ingestion.framework.run_pipeline --source wk52 --date 2024-01-15

# All automated sources (bhavcopy, wk52, constituents, corp actions,
# event-calendar, announcements) for a date
python -m ingestion.framework.run_pipeline --source all --date 2024-01-15

# Continue past per-source failures when running --source all
python -m ingestion.framework.run_pipeline --source all --date 2024-01-15 \
    --continue-on-error

# Skip HTTP — read only from the manual-drop folder data/raw/<source>/
python -m ingestion.framework.run_pipeline --source bhavcopy --local-only

# Load a SPECIFIC file (bypasses both HTTP and data/raw/<source>/ lookup)
python -m ingestion.framework.run_pipeline --source dim-stock \
    --date 2026-04-27 --local-file /path/to/NSE_CM_security_27042026.csv

# Backfill a date range (skips weekends, idempotent upserts)
python -m ingestion.framework.run_pipeline --source bhavcopy \
    --start 2024-01-01 --end 2024-01-31

# Source D — local-only by design (drop CSV into data/raw/reconstitution/)
python -m ingestion.framework.run_pipeline --source reconstitution \
    --date 2024-03-29
```

Available `--source` values:

| Source | Spec section | Target table |
|---|---|---|
| `dim-stock` | J | `dim_stock` (NSE security master, gzipped CSV) |
| `bhavcopy` | A | `fact_eod_price` |
| `wk52` | B | `fact_52wk` |
| `constituents` | C | `dim_nifty50_constituent` |
| `reconstitution` | D | `dim_nifty50_constituent` (local-only) |
| `corporate-actions` | E | `fact_corporate_action` |
| `event-calendar` | F | `fact_corporate_event` |
| `announcements` | G | `fact_corporate_event` |
| `intraday` | H | placeholder — skipped (vendor pending) |
| `all` | J+A+B+C+E+F+G | runs the seven automated sources in order |

**Local-drop folders** (used by `LocalFetcher` fallback when HTTP fails, and required for source D):

```
data/raw/dim_stock/          data/raw/bhavcopy/
data/raw/52wk/               data/raw/constituents/
data/raw/reconstitution/     data/raw/corporate_actions/
data/raw/event_calendar/     data/raw/announcements/
```

**Per-source filename templates** are declared in `SOURCES` (`run_pipeline.py`).
The `LocalFetcher` only looks for files matching its own source's templates,
so e.g. `--source dim-stock` will *only* match `NSE_CM_security_DDMMYYYY.csv`
and never pick up a stray bhavcopy file.

**File lifecycle:**

```
data/raw/<source>/<file>     ← drop here (or HTTP downloads here)
        │
        ▼  Pipeline.run() succeeds
data/processed/<source>/<file>   ← auto-archived after successful upsert

logs/<source>/bad_records/<file>.csv   ← rows dropped during parsing
                                         (with a _drop_reason column)
```

On failure, the source file stays in `data/raw/` for inspection.
On a re-run that produces a name collision in `data/processed/`, the new file
is suffixed with the trade date (`<stem>.<YYYY-MM-DD>.<ext>`).

Every pipeline run writes a row to `ingestion_log` (success or failure). On failure the exception bubbles to the CLI for a non-zero exit code, unless `--continue-on-error` is passed.

**Programmatic API** — the same primitives are exposed as a library if you need to embed pipelines in your own code:

```python
from datetime import date
from config.settings import settings
from ingestion.framework import (
    Pipeline, HybridFetcher, NseHttpFetcher, LocalFetcher,
    SourceType, EodPriceLoader,
)

Pipeline(
    fetcher=HybridFetcher(
        http=NseHttpFetcher(SourceType.BHAVCOPY),
        local=LocalFetcher(settings.project_root / "data/raw/bhavcopy"),
    ),
    loader=EodPriceLoader(),
    source_name="bhavcopy",
    table_name="fact_eod_price",
).run(date.today())
```

### Backfill Orchestrator (`ingestion/backfill/`)

```bash
# Backfill a date range (5-year orchestrator)
python -m ingestion.backfill.orchestrator --start 2020-01-01 --end 2024-12-31

# Backfill last N days
python -m ingestion.backfill.orchestrator --days 365

# Skip post-load analytics
python -m ingestion.backfill.orchestrator --start 2024-01-01 --end 2024-03-31 --skip-analytics

# Use cached local CSVs instead of downloading
python -m ingestion.backfill.orchestrator --start 2024-01-01 --end 2024-01-31 --local data/raw/bhavcopy
```

### Analytics

```bash
# Compute Investment Signal Score (ISS) and signals for a date
python -m analytics.compute_signals --date 2024-01-17

# Recompute 52-week highs/lows from price history
python -c "from analytics.compute_52wk import compute_52wk; from datetime import date; compute_52wk(date(2024, 1, 17))"

# Volume anomaly detection
python -m analytics.compute_volume_anomalies --date 2024-01-17

# ISS backtest
python -m analytics.iss_backtest --start 2024-01-01 --end 2024-03-31
```

### Database Setup

```bash
# Create the schema (PostgreSQL)
psql "$DB_URL" -f sql/schema.sql

# Seed the dim_stock table with Nifty 50 symbols
python -m ingestion.seed_stocks
```

### Running Tests

```bash
# Full unit test suite
pytest tests/unit/ -v --tb=short

# Just the new ingestion framework tests (40 tests)
pytest tests/unit/test_framework_fetchers.py \
       tests/unit/test_framework_loaders.py \
       tests/unit/test_framework_pipeline.py -v

# Integration scenarios
pytest integration/ -v

# With coverage
pytest tests/ --cov=ingestion --cov=analytics --cov-report=term-missing
```

### API & Dashboard (manual)

```bash
# Start FastAPI directly
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Start Streamlit dashboard directly
streamlit run dashboard/app.py --server.port 8501

# Phase I dashboard (alerts + mobile layout)
streamlit run dashboard/phase_i.py --server.port 8502
```

### NSE Scraper (event calendar / announcements)

```bash
# Scrape event calendar (writes to fact_corporate_event)
python -m ingestion.nse_scraper --source event-calendar

# Scrape corporate announcements
python -m ingestion.nse_scraper --source announcements
```

---

## Project Status

Current Phase: **Phase E Completed** (Corporate Events & Ingestion Layers) +
**Ingestion Framework** (parallel pipeline covering all 9 spec data sources).

Next Phase: **Phase F** (Sector Rotation & Breadth Tracking).

## Credits
Designed and built by **Antigravity** for the Starfish Project.
