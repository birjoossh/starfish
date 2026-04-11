#!/usr/bin/env bash
set -euo pipefail

# ── Nifty 50 Dashboard — run all services ──────────────────────────────
# Usage:
#   ./run.sh              # Start API + Dashboard (default)
#   ./run.sh --init       # Create DB schema + load sample data first
#   ./run.sh --api-only   # Start only the FastAPI server
#   ./run.sh --dash-only  # Start only the Streamlit dashboard
#   ./run.sh --stop      # Kill all running services

source ./.env
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$PROJECT_ROOT/.pids"
LOG_DIR="$PROJECT_ROOT/.logs"

DB_NAME="${DB_NAME:-nifty50}"
DB_URL="${DB_URL:-postgresql://localhost:5433/$DB_NAME}"
API_PORT="${API_PORT:-8000}"
DASH_PORT="${DASH_PORT:-8501}"

# ── Helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[nifty50]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()  { echo -e "${RED}[FATAL]${NC} $*"; exit 1; }

mkdir -p "$PID_DIR" "$LOG_DIR"

check_db() {
    echo "DB_URL=$DB_URL"

    if ! psql "$DB_URL" -c '\q' 2>/dev/null; then
        die "Cannot connect to database at $DB_URL. Is PostgreSQL running? Have you created the database?"
    fi
    ok "Database connected"
}

check_deps() {
    local missing=()
    for cmd in python psql; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        die "Missing required commands: ${missing[*]}"
    fi
}

install_deps() {
    log "Installing Python dependencies..."
    pip install -e "$PROJECT_ROOT[dev]" 2>&1 | tail -1
    ok "Python dependencies installed"
}

wait_for_port() {
    local port=$1 name=$2 timeout=${3:-15}
    local i=0
    while ! lsof -i :"$port" &>/dev/null; do
        sleep 1
        i=$((i + 1))
        if [ "$i" -ge "$timeout" ]; then
            die "$name did not start within ${timeout}s"
        fi
    done
}

stop_services() {
    log "Stopping all services..."
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && ok "Stopped PID $pid" || warn "PID $pid already gone"
        fi
        rm -f "$pidfile"
    done
    # Fallback: kill by port if PIDs are stale
    for port in "$API_PORT" "$DASH_PORT"; do
        local pids
        pids=$(lsof -t -i :"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill 2>/dev/null && ok "Killed process on port $port" || true
        fi
    done
    ok "All services stopped"
}

# ── Init: schema + sample data ─────────────────────────────────────────
init_db() {
    log "Initializing database schema..."
    psql "$DB_URL" -f "$PROJECT_ROOT/sql/schema.sql"
    ok "Schema created"

    log "Loading sample data (3 days: Jan 15-17, 2024)..."
    local dates=("2024-01-15" "2024-01-16" "2024-01-17")
    local csvs=(
        "$PROJECT_ROOT/tests/fixtures/sample_bhavcopy.csv"
        "$PROJECT_ROOT/tests/fixtures/sample_bhavcopy_jan16.csv"
        "$PROJECT_ROOT/tests/fixtures/sample_bhavcopy_jan17.csv"
    )
    for i in "${!dates[@]}"; do
        local d="${dates[$i]}" csv="${csvs[$i]}"
        if [ ! -f "$csv" ]; then
            warn "Missing fixture $csv — skipping $d"
            continue
        fi
        log "  Ingesting $d..."
        DB_URL="$DB_URL" python -c "
from ingestion.bhavcopy_parser import BhavcopyParser
from ingestion.bhavcopy_loader import BhavcopyLoader
from datetime import date
p = BhavcopyParser()
df = p.parse('$csv', trade_date=date(*[int(x) for x in '$d'.split('-')]))
BhavcopyLoader().load(df, source_file='init_$(basename $csv)')
print(f'  Loaded {len(df)} rows for $d')
"
    done

    log "Computing analytics..."
    DB_URL="$DB_URL" python -c "
from analytics.compute_52wk import compute_52wk
from analytics.compute_signals import compute_signals
from datetime import date
for d in [date(2024,1,15), date(2024,1,16), date(2024,1,17)]:
    compute_52wk(d)
for d in [date(2024,1,15), date(2024,1,16), date(2024,1,17)]:
    compute_signals(d)
print('  Analytics computed')
"
    ok "Sample data loaded"
}

# ── Start services ─────────────────────────────────────────────────────
start_api() {
    log "Starting FastAPI on port $API_PORT..."
    DB_URL="$DB_URL" nohup uvicorn api.main:app \
        --host 0.0.0.0 \
        --port "$API_PORT" \
        --reload \
        > "$LOG_DIR/api.log" 2>&1 &
    echo $! > "$PID_DIR/api.pid"
    wait_for_port "$API_PORT" "FastAPI" 15
    ok "API running at http://localhost:$API_PORT"
    ok "  Health:  http://localhost:$API_PORT/health"
    ok "  Stocks:  http://localhost:$API_PORT/constituents"
    ok "  Prices:  http://localhost:$API_PORT/prices/RELIANCE"
}

start_dashboard() {
    log "Starting Streamlit dashboard on port $DASH_PORT..."
    DB_URL="$DB_URL" nohup streamlit run "$PROJECT_ROOT/dashboard/app.py" \
        --server.port "$DASH_PORT" \
        --server.headless true \
        > "$LOG_DIR/dashboard.log" 2>&1 &
    echo $! > "$PID_DIR/dashboard.pid"
    wait_for_port "$DASH_PORT" "Streamlit" 20
    ok "Dashboard running at http://localhost:$DASH_PORT"
}

print_digest() {
    log "Morning digest:"
    DB_URL="$DB_URL" python -m nifty50.digest 2>/dev/null || warn "Digest failed"
}

# ── Main ───────────────────────────────────────────────────────────────
ACTION="run"
case "${1:-}" in
    --init)      ACTION="init" ;;
    --api-only)  ACTION="api" ;;
    --dash-only) ACTION="dash" ;;
    --stop)      ACTION="stop" ;;
    --help|-h)   ACTION="help" ;;
esac

case "$ACTION" in
    help)
        echo "Usage: ./run.sh [option]"
        echo ""
        echo "Options:"
        echo "  (no args)     Start API + Dashboard"
        echo "  --init        Create schema + load sample data, then start"
        echo "  --api-only    Start only the FastAPI server"
        echo "  --dash-only   Start only the Streamlit dashboard"
        echo "  --stop        Stop all running services"
        echo "  --help        Show this help"
        echo ""
        echo "Environment variables:"
        echo "  DB_URL        PostgreSQL connection string (default: postgresql://localhost:5433/nifty50)"
        echo "  API_PORT      Port for FastAPI (default: 8000)"
        echo "  DASH_PORT     Port for Streamlit (default: 8501)"
        ;;
    stop)
        stop_services
        ;;
    init)
        check_deps
        install_deps
        check_db
        init_db
        start_api
        start_dashboard
        print_digest
        echo ""
        ok "All services running. Press Ctrl+C to stop."
        echo "  API:       http://localhost:$API_PORT"
        echo "  Dashboard:  http://localhost:$DASH_PORT"
        echo "  Logs:       $LOG_DIR/"
        echo "  Stop all:   ./run.sh --stop"
        # Keep script alive so Ctrl+C is intuitive
        trap 'stop_services; exit 0' INT TERM
        wait
        ;;
    api)
        check_deps
        check_db
        start_api
        echo ""
        ok "API running at http://localhost:$API_PORT"
        echo "  Logs:  $LOG_DIR/api.log"
        echo "  Stop:  ./run.sh --stop"
        trap 'stop_services; exit 0' INT TERM
        wait
        ;;
    dash)
        check_deps
        check_db
        start_dashboard
        echo ""
        ok "Dashboard running at http://localhost:$DASH_PORT"
        echo "  Logs:  $LOG_DIR/dashboard.log"
        echo "  Stop:  ./run.sh --stop"
        trap 'stop_services; exit 0' INT TERM
        wait
        ;;
    run)
        check_deps
        check_db
        start_api
        start_dashboard
        print_digest
        echo ""
        ok "All services running."
        echo "  API:       http://localhost:$API_PORT"
        echo "  Dashboard:  http://localhost:$DASH_PORT"
        echo "  Logs:       $LOG_DIR/"
        echo "  Stop all:   ./run.sh --stop"
        trap 'stop_services; exit 0' INT TERM
        wait
        ;;
esac