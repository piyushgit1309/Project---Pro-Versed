#!/usr/bin/env bash
# ==============================================================================
# PRO-VERSED Platform Launch Script (Linux/macOS)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PORT="${PORT:-8000}"
export HOST="${HOST:-0.0.0.0}"

echo "======================================================================"
echo " Starting PRO-VERSED Platform..."
echo " Launching server on http://${HOST}:${PORT} ..."
echo "======================================================================"

exec python3 main.py
