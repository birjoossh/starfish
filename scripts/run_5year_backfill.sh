#!/bin/bash
# NSE Historical Data Downloader
#
# NOTE: NSE archive only has ~2 years of data available.
# For 5-year backfill, you need a paid data vendor.
#
# Usage:
#   ./scripts/run_5year_backfill.sh        # Try to download available data
#   ./scripts/run_5year_backfill.sh --check # Check progress
#   ./scripts/run_5year_backfill.sh --load   # Load downloaded files to DB

set -e

cd "$(dirname "$0")/.."

source venv/bin/activate

echo "=== NSE Historical Data Downloader ==="
echo ""

# Check mode
if [ "$1" == "--check" ]; then
    echo "=== Downloaded Files ==="
    COUNT=$(ls data/bhavcopy/*.csv 2>/dev/null | wc -l | tr -d ' ')
    echo "Files downloaded: $COUNT"
    echo ""
    echo "Date range in database:"
    python -c "
from config.database import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM fact_eod_price'))
    row = result.fetchone()
    print(f'  DB: {row[0]} to {row[1]} ({row[2]} days)')
" 2>/dev/null || echo "  (DB not accessible)"
    exit 0
fi

if [ "$1" == "--load" ]; then
    echo "=== Loading Files to Database ==="
    python -m ingestion.backfill --local data/bhavcopy
    exit 0
fi

# Default: try to download what's available (last 2 years)
echo "Downloading available NSE historical data..."
echo "Note: NSE archive typically has 1-2 years of data"
echo ""

python -m ingestion.nse_historical_downloader --years 2 --skip-index 2>&1

echo ""
echo "=== Download Complete ==="
ls -la data/bhavcopy/*.csv 2>/dev/null | wc -l
echo ""
echo "To load into database: ./scripts/run_5year_backfill.sh --load"