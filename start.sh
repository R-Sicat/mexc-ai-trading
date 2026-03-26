#!/usr/bin/env bash
# Start the trading bot and dashboard together.
# Usage: ./start.sh [--bot-only] [--dashboard-only]
set -e

VENV_DIR=".venv"
BOT_ONLY=false
DASHBOARD_ONLY=false

for arg in "$@"; do
    case $arg in
        --bot-only) BOT_ONLY=true ;;
        --dashboard-only) DASHBOARD_ONLY=true ;;
    esac
done

# Ensure venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# Ensure .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env not found. Run ./setup.sh and fill in your API keys."
    exit 1
fi

source $VENV_DIR/bin/activate

# Ensure DB is initialised (safe to run multiple times)
python -c "import asyncio; from sniper.utils.db import init_db; asyncio.run(init_db())"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BOT_PID" 2>/dev/null
    kill "$DASHBOARD_PID" 2>/dev/null
    wait 2>/dev/null
    echo "Stopped."
}
trap cleanup SIGINT SIGTERM

if [ "$DASHBOARD_ONLY" = false ]; then
    echo "==> Starting trading bot..."
    python scripts/run_bot.py &
    BOT_PID=$!
    echo "    Bot PID: $BOT_PID"
fi

if [ "$BOT_ONLY" = false ]; then
    echo "==> Starting dashboard on http://localhost:8765 ..."
    uvicorn dashboard.server:app --host 0.0.0.0 --port 8765 --log-level warning &
    DASHBOARD_PID=$!
    echo "    Dashboard PID: $DASHBOARD_PID"
fi

echo ""
echo "Both services running. Press Ctrl+C to stop."
echo "Dashboard: http://localhost:8765"
echo ""

wait
