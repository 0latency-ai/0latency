#!/bin/bash
# Monitor benchmark run progress

set -a
source ../../.env
set +a

TENANT_ID="382faaf1-5cbf-49a1-b689-5ffef8918d10"

while true; do
  clear
  echo "=== LONGMEMEVAL RUN MONITOR ==="
  echo "Time: $(date)"
  echo ""
  
  # Check memory count
  MEM_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM memory_service.memories WHERE tenant_id = '$TENANT_ID'")
  SESSION_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(DISTINCT source_session) FROM memory_service.memories WHERE tenant_id = '$TENANT_ID'")
  
  echo "Memories extracted: $MEM_COUNT"
  echo "Unique sessions: $SESSION_COUNT"
  echo ""
  
  # Check if benchmark is still running
  if pgrep -f "run_benchmark.py" > /dev/null; then
    echo "Status: Running"
  else
    echo "Status: Complete or not started"
  fi
  
  echo ""
  echo "Press Ctrl+C to exit monitor"
  
  sleep 30
done
