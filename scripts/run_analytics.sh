#!/bin/bash
# Analytics & Signals Computation Runner
#
# Usage:
#   ./scripts/run_analytics.sh              # Compute for latest date only
#   ./scripts/run_analytics.sh --all        # Compute for ALL dates in DB
#   ./scripts/run_analytics.sh --date 2024-01-17  # Compute for specific date
#   ./scripts/run_analytics.sh --status     # Show analytics status only
#
# Computes:
#   1. 52-week highs/lows      -> fact_52wk
#   2. Stock signals           -> mart_stock_signals
#   3. Volume anomalies        -> mart_volume_anomaly
#   4. Alert evaluation        -> alerts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
source venv/bin/activate

# Defaults
MODE="latest"
TARGET_DATE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            MODE="all"
            shift
            ;;
        --date)
            MODE="date"
            TARGET_DATE="$2"
            shift 2
            ;;
        --status)
            MODE="status"
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/run_analytics.sh [OPTION]"
            echo ""
            echo "Options:"
            echo "  (no args)            Compute for the latest trade date only"
            echo "  --all                Compute for all dates in fact_eod_price"
            echo "  --date YYYY-MM-DD    Compute for a specific date"
            echo "  --status             Show analytics tables status, don't compute"
            echo "  --help               Show this help"
            echo ""
            echo "Stages:"
            echo "  1. 52-week highs/lows    -> fact_52wk"
            echo "  2. Stock signals         -> mart_stock_signals"
            echo "  3. Volume anomalies      -> mart_volume_anomaly"
            echo "  4. Alert evaluation      -> alerts"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

# ── Status mode ───────────────────────────────────────────────────────────
if [ "$MODE" == "status" ]; then
    echo "=== Analytics Tables Status ==="
    echo ""
    python -c "
from config.database import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    tables = [
        ('fact_eod_price',      'MIN(trade_date)', 'MAX(trade_date)', 'COUNT(DISTINCT trade_date)'),
        ('fact_52wk',           'MIN(trade_date)', 'MAX(trade_date)', 'COUNT(*)'),
        ('mart_stock_signals',  'MIN(calc_date)',  'MAX(calc_date)',  'COUNT(*)'),
        ('mart_volume_anomaly', 'MIN(calc_date)',  'MAX(calc_date)',  'COUNT(*)'),
        ('alerts',              'MIN(triggered_at)', 'MAX(triggered_at)', 'COUNT(*)'),
    ]
    for name, min_col, max_col, cnt_col in tables:
        try:
            result = conn.execute(text(f'SELECT {min_col}, {max_col}, {cnt_col} FROM {name}'))
            row = result.fetchone()
            print(f'  {name:25s} {row[2]:>8} rows  ({row[0]} to {row[1]})')
        except Exception as e:
            print(f'  {name:25s} (error: {e})')
" 2>/dev/null || echo "  (DB not accessible)"
    exit 0
fi

# ── Determine target date ─────────────────────────────────────────────────
if [ "$MODE" == "all" ]; then
    DATE_ARG=""
    echo "=== Computing analytics for ALL dates ==="
elif [ "$MODE" == "date" ]; then
    DATE_ARG="--date $TARGET_DATE"
    echo "=== Computing analytics for $TARGET_DATE ==="
else
    # Latest date from DB
    LATEST_DATE=$(python -c "
from config.database import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('SELECT MAX(trade_date) FROM fact_eod_price'))
    print(result.scalar())
" 2>/dev/null)
    if [ -z "$LATEST_DATE" ] || [ "$LATEST_DATE" == "None" ]; then
        echo "ERROR: No data in fact_eod_price. Run ingestion first."
        exit 1
    fi
    DATE_ARG="--date $LATEST_DATE"
    echo "=== Computing analytics for latest date: $LATEST_DATE ==="
fi

echo ""

# ── Stage 1: 52-week highs/lows ───────────────────────────────────────────
echo "[1/4] Computing 52-week highs/lows -> fact_52wk ..."
python -c "
from analytics.compute_52wk import compute_52wk
from datetime import date
import sys

date_str = '${TARGET_DATE}' if '${MODE}' == 'date' else None
if '${MODE}' == 'all':
    count = compute_52wk()
elif date_str:
    count = compute_52wk(date.fromisoformat(date_str))
else:
    count = compute_52wk()
print(f'  fact_52wk: {count} rows')
"
echo ""

# ── Stage 2: Stock signals ────────────────────────────────────────────────
echo "[2/4] Computing stock signals -> mart_stock_signals ..."
python -m analytics.compute_signals $DATE_ARG
echo ""

# ── Stage 3: Volume anomalies ─────────────────────────────────────────────
echo "[3/4] Computing volume anomalies -> mart_volume_anomaly ..."
python -m analytics.compute_volume_anomalies $DATE_ARG
echo ""

# ── Stage 4: Alert evaluation ─────────────────────────────────────────────
echo "[4/4] Evaluating alerts -> alerts ..."
python -c "
import asyncio
import sys
from datetime import date
from analytics.alert_engine import AlertEngine

calc_date = date.fromisoformat('${TARGET_DATE}') if '${MODE}' == 'date' else date.today()

async def run():
    engine = AlertEngine()
    alerts = await engine.evaluate_all_alerts(calc_date)
    fired = 0
    deduped = 0
    for alert in alerts:
        alert_id = await engine.fire_alert(alert)
        if alert_id:
            fired += 1
        else:
            deduped += 1
    print(f'  alerts: {fired} fired, {deduped} deduped ({len(alerts)} total evaluated)')

asyncio.run(run())
"
echo ""

# ── Summary ───────────────────────────────────────────────────────────────
echo "=== Analytics Computation Complete ==="
python -c "
from config.database import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    tables = [
        ('fact_52wk',           'COUNT(*)'),
        ('mart_stock_signals',  'COUNT(*)'),
        ('mart_volume_anomaly', 'COUNT(*)'),
        ('alerts',              'COUNT(*)'),
    ]
    for name, cnt_col in tables:
        try:
            result = conn.execute(text(f'SELECT {cnt_col} FROM {name}'))
            count = result.scalar()
            print(f'  {name:25s} {count:>8} rows')
        except Exception as e:
            print(f'  {name:25s} (error: {e})')
"
