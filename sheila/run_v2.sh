#!/bin/bash
# Sheila - Startup Smartup Intelligence v2 (Orchestration Edition)
# Stores to namespace + writes reconnect briefs to Nellie

set -euo pipefail

WORKSPACE="/root/.openclaw/workspace/sheila"
cd "$WORKSPACE"

TIMESTAMP=$(date +%Y%m%d-%H%M)
LOG_FILE="logs/scan-$TIMESTAMP.log"

mkdir -p logs

{
    echo "=== Sheila Intelligence Scan v2 - $(date '+%Y-%m-%d %H:%M UTC') ==="
    python3 scan_v2.py
    echo "Scan complete - $(date '+%H:%M UTC')"
} > "$LOG_FILE" 2>&1

# Keep last 30 days of logs
find logs -name "scan-*.log" -mtime +30 -delete 2>/dev/null || true

echo "Sheila scan complete. Results: $WORKSPACE/alerts-pending.txt"
echo "Reconnect briefs: $WORKSPACE/../nellie/reconnect-pending/"
