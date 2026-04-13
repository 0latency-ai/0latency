#!/bin/bash
# Scout - PFL Academy Intelligence v2 (Orchestration Edition)
# Stores to namespace + writes lead briefs to Shea

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace/scout"
cd "$WORKSPACE"

TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="logs/scan-$TIMESTAMP.log"

mkdir -p logs

{
    echo "=== Scout Intelligence Scan v2 - $(date '+%Y-%m-%d %H:%M UTC') ==="
    python3 scan_v2.py
    echo "Scan complete - $(date '+%H:%M UTC')"
} > "$LOG_FILE" 2>&1

# Keep last 30 days of logs
find logs -name "scan-*.log" -mtime +30 -delete 2>/dev/null || true

echo "Scout scan complete. Results: $WORKSPACE/alerts-pending.txt"
echo "Lead briefs: $WORKSPACE/../shea/leads-pending/"
