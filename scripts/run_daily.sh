#!/bin/bash
# Daily Ingestion Runner
#
# Runs the full daily ingestion pipeline:
#   1. Download bhavcopy from NSE (or read from local source)
#   2. Parse with header validation and series filter
#   3. Load into fact_eod_price with idempotent upsert
#   4. Optional: corporate actions, corporate events, signal recompute
#
# Usage:
#   ./scripts/run_daily.sh                          # Ingest today's data
#   ./scripts/run_daily.sh --date 2024-01-15        # Ingest specific date
#   ./scripts/run_daily.sh --backfill 252           # Last 252 trading days
#   ./scripts/run_daily.sh --start 2024-01-01 --end 2024-01-31
#   ./scripts/run_daily.sh --local data/bhavcopy    # Use local CSVs
#   ./scripts/run_daily.sh --compute-signals        # Also recompute signals

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
source venv/bin/activate

# Collect all arguments and forward them to daily_run.py
python -m ingestion.daily_run "$@"
