#!/bin/bash
# Scout - PFL Academy Intelligence
# Runs twice daily: 8 AM and 2 PM Pacific (15:00, 21:00 UTC)

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace/scout"
cd "$WORKSPACE"

TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="logs/scan-$TIMESTAMP.log"

mkdir -p logs

{
    echo "=== Scout Intelligence Scan - $(date '+%Y-%m-%d %H:%M UTC') ==="
    python3 scan.py
    echo "Scan complete - $(date '+%H:%M UTC')"
} > "$LOG_FILE" 2>&1

# Keep last 30 days of logs
find logs -name "scan-*.log" -mtime +30 -delete 2>/dev/null || true

echo "Scout scan complete. Results: $WORKSPACE/alerts-pending.txt"
