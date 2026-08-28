#!/usr/bin/env bash
# ==============================================================================
# PRO-VERSED Platform Launch Script (Linux / macOS)
# National Student Innovation Platform & Project Showcase
# ==============================================================================

set -e

echo "======================================================================"
echo " Starting PRO-VERSED Platform..."
echo " National Student Innovation Platform & Project Showcase"
echo "======================================================================"

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python 3 availability
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed." >&2
    exit 1
fi

# Create virtual environment if not present
if [ ! -d "venv" ]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv venv || true
fi

# Activate virtual environment if created
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Install requirements
echo "[2/3] Checking dependencies..."
pip install -r backend/requirements.txt --quiet || true

# Launch application
echo "[3/3] Launching FastAPI backend and static frontend on http://localhost:8000 ..."
cd backend
export PROVERSED_DB_PATH="${PROVERSED_DB_PATH:-/tmp/proversed.db}"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
