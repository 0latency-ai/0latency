#!/bin/bash
# Dual-namespace recall: queries both thomas + user-justin namespaces, merges results
# Usage: recall-dual.sh "context query" [budget_tokens]
# Phase 4: fires /feedback after recall

API_KEY="zl_live_jk13qjxlpiltqs3t157rvfypsa6xa40o"
API_URL="https://api.0latency.ai/recall"
FEEDBACK_SCRIPT="$(dirname "$0")/feedback.sh"
LOG="/root/logs/recall-dual.log"

CONTEXT="${1:-session recall}"
BUDGET="${2:-4000}"

ts() { date -u +"%Y-%m-%d %H:%M:%S UTC"; }

log() { echo "[$(ts)] $1" >> "$LOG"; }

log "=== Dual recall: ${CONTEXT:0:80} ==="

# Build payload
make_payload() {
  python3 -c "
import json, sys
print(json.dumps({
  'agent_id': sys.argv[1],
  'conversation_context': sys.argv[2],
  'budget_tokens': int(sys.argv[3])
}))
" "$1" "$2" "$3"
}

# Query thomas namespace
THOMAS_RESP=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d "$(make_payload thomas "$CONTEXT" "$BUDGET")")

THOMAS_USED=$(echo "$THOMAS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('memories_used',0))" 2>/dev/null || echo 0)
THOMAS_BLOCK=$(echo "$THOMAS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('context_block',''))" 2>/dev/null || echo "")

log "thomas: ${THOMAS_USED} memories"

# Query user-justin namespace
JUSTIN_RESP=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d "$(make_payload user-justin "$CONTEXT" "$BUDGET")")

JUSTIN_USED=$(echo "$JUSTIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('memories_used',0))" 2>/dev/null || echo 0)
JUSTIN_BLOCK=$(echo "$JUSTIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('context_block',''))" 2>/dev/null || echo "")

log "user-justin: ${JUSTIN_USED} memories"

# Merge and output
python3 << PYEOF
thomas_block = """$THOMAS_BLOCK"""
user_justin_block = """$JUSTIN_BLOCK"""

merged = []
if thomas_block.strip():
    merged.append("## From thomas namespace\n" + thomas_block)
if user_justin_block.strip():
    merged.append("## From user-justin namespace (Chrome extension)\n" + user_justin_block)

if merged:
    print("\n\n".join(merged))
else:
    print("(no memories recalled from either namespace)")
PYEOF

# Phase 4: log feedback event
log "feedback: thomas=${THOMAS_USED} user-justin=${JUSTIN_USED} total=$((THOMAS_USED + JUSTIN_USED))"

# Fire feedback for any returned memory IDs (both namespaces)
for RESP in "$THOMAS_RESP" "$JUSTIN_RESP"; do
  IDS=$(echo "$RESP" | python3 -c "import sys,json; ids=json.load(sys.stdin).get('memory_ids',[]); print(' '.join(ids))" 2>/dev/null || echo "")
  if [ -n "$IDS" ] && [ -x "$FEEDBACK_SCRIPT" ]; then
    for MID in $IDS; do
      "$FEEDBACK_SCRIPT" "used" "$MID" "dual_recall" &
    done
  fi
done
