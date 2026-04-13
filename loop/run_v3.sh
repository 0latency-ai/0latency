#!/bin/bash
# Loop Comprehensive Intelligence Scan v3 (Orchestration Edition)
# Now stores to namespace + writes action briefs to Lance

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace/loop"
cd "$WORKSPACE"

TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="logs/scan-$TIMESTAMP.log"

mkdir -p logs

{
    echo "=== Loop Intelligence Scan v3 - $(date '+%Y-%m-%d %H:%M UTC') ==="
    python3 scan_v3.py
    echo "Scan complete - $(date '+%H:%M UTC')"
} > "$LOG_FILE" 2>&1

# Keep last 30 days of logs
find logs -name "scan-*.log" -mtime +30 -delete 2>/dev/null || true

echo "Loop scan complete. Results: $WORKSPACE/alerts-pending.txt"
echo "Action briefs: $WORKSPACE/../lance/actions-pending/"
