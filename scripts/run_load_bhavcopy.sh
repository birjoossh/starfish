#!/bin/bash
# NSE Bhavcopy 5-Year Backfill - Load Files to Database
#
# Usage:
#   ./scripts/run_5year_backfill.sh        # Show status
#   ./scripts/run_5year_backfill.sh --check # Check progress
#   ./scripts/run_5year_backfill.sh --load  # Load downloaded files to DB
#
# This script only loads CSV files that have already been downloaded.
# It does NOT download from NSE - use ingestion/backfill/historical_downloader.py for that.
#
# Downloaded files should be in: data/bhavcopy/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data/bhavcopy"

cd "$PROJECT_ROOT"
source venv/bin/activate

# Parse arguments
MODE="status"
if [ "$1" == "--check" ]; then
    MODE="check"
elif [ "$1" == "--load" ]; then
    MODE="load"
fi

# Helper function to count CSV files
count_csv_files() {
    local dir="$1"
    if [ -d "$dir" ]; then
        ls "$dir"/*.csv 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

# Check mode - show what we have
if [ "$MODE" == "check" ] || [ "$MODE" == "status" ]; then
    echo "=== NSE Bhavcopy 5-Year Backfill Status ==="
    echo ""

    COUNT=$(count_csv_files "$DATA_DIR")
    echo "Bhavcopy files in data/bhavcopy/: $COUNT"
    echo ""

    if [ "$COUNT" -gt 0 ]; then
        echo "Recent files:"
        ls -lt "$DATA_DIR"/*.csv 2>/dev/null | head -10
        echo ""
    fi

    echo "Database status:"
    python -c "
from config.database import get_engine
from sqlalchemy import text
try:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date)
            FROM fact_eod_price
        '''))
        row = result.fetchone()
        print(f'  fact_eod_price: {row[2]} trading days ({row[0]} to {row[1]})')
except Exception as e:
    print(f'  (DB not accessible: {e})')
" 2>/dev/null || echo "  (DB not accessible)"
    exit 0
fi

# Load mode - ingest files to DB
if [ "$MODE" == "load" ]; then
    echo "=== Loading Bhavcopy Files to Database ==="
    echo ""

    COUNT=$(count_csv_files "$DATA_DIR")
    echo "Found $COUNT bhavcopy files"
    echo ""

    if [ "$COUNT" -eq 0 ]; then
        echo "No bhavcopy files to load. Download files first with:"
        echo "  python -m ingestion.backfill.historical_downloader --years 5"
        exit 1
    fi

    # Run the backfill loader with --local flag to read from data/bhavcopy
    # Use --days 1800 to cover ~5 years of calendar days (will skip weekends/holidays)
    python -m ingestion.backfill.orchestrator --local "$DATA_DIR" --days 1800 --skip-index --skip-analytics

    echo ""
    echo "=== Load Complete ==="
    echo "Run with --check to verify data in database"
    exit 0
fi