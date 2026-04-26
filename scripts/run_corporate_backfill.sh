#!/bin/bash
# Corporate Actions/Events Backfill Script
#
# Usage:
#   ./scripts/run_corporate_backfill.sh        # Download corporate data from NSE
#   ./scripts/run_corporate_backfill.sh --check # Check progress and files
#   ./scripts/run_corporate_backfill.sh --load  # Load downloaded files to DB
#
# The ingestion/backfill/corporate_downloader.py script downloads from NSE website.
# If NSE requests are blocked (403/404), download manually and place CSVs in:
#   data/corporate/actions/  for corporate actions
#   data/corporate/events/   for corporate events
# Then use --load to ingest them.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data/corporate"

cd "$PROJECT_ROOT"
source venv/bin/activate

# Parse arguments
MODE="download"
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
if [ "$MODE" == "check" ]; then
    echo "=== Corporate Actions/Events Backfill Status ==="
    echo ""

    ACTIONS_COUNT=$(count_csv_files "$DATA_DIR/actions")
    EVENTS_COUNT=$(count_csv_files "$DATA_DIR/events")

    echo "Files in data/corporate/actions/: $ACTIONS_COUNT"
    echo "Files in data/corporate/events/: $EVENTS_COUNT"
    echo ""

    if [ "$ACTIONS_COUNT" -gt 0 ]; then
        echo "Corporate Actions files:"
        ls -1 "$DATA_DIR/actions/"/*.csv 2>/dev/null | head -10
        if [ "$ACTIONS_COUNT" -gt 10 ]; then
            echo "... and $((ACTIONS_COUNT - 10)) more"
        fi
        echo ""
    fi

    if [ "$EVENTS_COUNT" -gt 0 ]; then
        echo "Corporate Events files:"
        ls -1 "$DATA_DIR/events/"/*.csv 2>/dev/null | head -10
        if [ "$EVENTS_COUNT" -gt 10 ]; then
            echo "... and $((EVENTS_COUNT - 10)) more"
        fi
        echo ""
    fi

    echo "Database status:"
    python -c "
from config.database import get_engine
from sqlalchemy import text
try:
    engine = get_engine()
    with engine.connect() as conn:
        # Corporate actions
        result = conn.execute(text('''
            SELECT MIN(ex_date), MAX(ex_date), COUNT(*)
            FROM fact_corporate_action
        '''))
        row = result.fetchone()
        print(f'  fact_corporate_action: {row[2]} rows ({row[0]} to {row[1]})')

        # Corporate events
        result = conn.execute(text('''
            SELECT MIN(event_date), MAX(event_date), COUNT(*)
            FROM fact_corporate_event
        '''))
        row = result.fetchone()
        print(f'  fact_corporate_event: {row[2]} rows ({row[0]} to {row[1]})')
except Exception as e:
    print(f'  (DB not accessible: {e})')
" 2>/dev/null || echo "  (DB not accessible)"
    exit 0
fi

# Load mode - ingest files to DB
if [ "$MODE" == "load" ]; then
    echo "=== Loading Corporate Actions/Events to Database ==="
    echo ""

    ACTIONS_COUNT=$(count_csv_files "$DATA_DIR/actions")
    EVENTS_COUNT=$(count_csv_files "$DATA_DIR/events")

    echo "Found $ACTIONS_COUNT corporate actions files"
    echo "Found $EVENTS_COUNT corporate events files"
    echo ""

    # Load corporate actions
    if [ "$ACTIONS_COUNT" -gt 0 ]; then
        echo "Loading corporate actions..."
        for file in "$DATA_DIR/actions/"*.csv; do
            if [ -f "$file" ]; then
                echo "  Processing: $(basename "$file")"
                python -m ingestion.corporate_actions_loader --file "$file" 2>&1 | tail -1
            fi
        done
        echo "Corporate actions loading complete."
        echo ""
    else
        echo "No corporate actions files to load."
        echo ""
    fi

    # Load corporate events
    if [ "$EVENTS_COUNT" -gt 0 ]; then
        echo "Loading corporate events..."
        for file in "$DATA_DIR/events/"*.csv; do
            if [ -f "$file" ]; then
                echo "  Processing: $(basename "$file")"
                python -m ingestion.corporate_events_loader --file "$file" 2>&1 | tail -1
            fi
        done
        echo "Corporate events loading complete."
        echo ""
    else
        echo "No corporate events files to load."
        echo ""
    fi

    echo "=== Load Complete ==="
    echo "Run with --check to verify data in database"
    exit 0
fi

# Default: download from NSE
echo "=== Corporate Backfill - Download from NSE ==="
echo ""
echo "Note: NSE may block automated requests."
echo "If requests fail with 403/404, manually download from:"
echo "  https://www.nseindia.com/market-data/corporate-actions"
echo ""

python -m ingestion.backfill.corporate_downloader --days 365 2>&1

echo ""
echo "=== Download Complete ==="
echo "Files saved to: $DATA_DIR/actions/ and $DATA_DIR/events/"
echo ""
echo "To load into database: ./scripts/run_corporate_backfill.sh --load"