#!/bin/bash
# Sheila - Startup Smartup Intelligence
# Runs once daily: 10 AM Pacific (17:00 UTC)

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace/sheila"
cd "$WORKSPACE"

TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="logs/scan-$TIMESTAMP.log"

mkdir -p logs

{
    echo "=== Sheila Intelligence Scan - $(date '+%Y-%m-%d %H:%M UTC') ==="
    python3 scan.py
    echo "Scan complete - $(date '+%H:%M UTC')"
} > "$LOG_FILE" 2>&1

# Keep last 30 days of logs
find logs -name "scan-*.log" -mtime +30 -delete 2>/dev/null || true

echo "Sheila scan complete. Results: $WORKSPACE/alerts-pending.txt"
