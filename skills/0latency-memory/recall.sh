#!/bin/bash
# 0Latency Memory Recall Wrapper
# Query memories by semantic search

set -euo pipefail

API_KEY="${ZEROLATENCY_API_KEY:-zl_live_jk13qjxlpiltqs3t157rvfypsa6xa40o}"
AGENT_ID="thomas"
API_URL="https://api.0latency.ai/recall"

if [ $# -lt 1 ]; then
    cat << 'USAGE'
Usage: recall.sh CONTEXT [BUDGET_TOKENS]

Recall memories using semantic search.

Arguments:
  CONTEXT         Conversation context (what you're trying to recall)
  BUDGET_TOKENS   Optional token budget (default: 4000, max: 16000)

Examples:
  recall.sh "Who is Palmer from ZeroClick?"
  recall.sh "Email forwarding configuration for 0latency.ai"
  recall.sh "Launch checklist status" 8000

Note: The API will extract the search query from the conversation context.

USAGE
    exit 1
fi

CONTEXT="$1"
BUDGET="${2:-4000}"

# Build JSON payload
if command -v jq &>/dev/null; then
    PAYLOAD=$(jq -n \
        --arg agent "$AGENT_ID" \
        --arg ctx "$CONTEXT" \
        --argjson budget "$BUDGET" \
        '{agent_id: $agent, conversation_context: $ctx, budget_tokens: $budget}')
else
    PAYLOAD=$(python3 - "$AGENT_ID" "$CONTEXT" "$BUDGET" << 'PYEOF'
import json, sys
agent_id, ctx, budget = sys.argv[1:4]
payload = {"agent_id": agent_id, "conversation_context": ctx, "budget_tokens": int(budget)}
print(json.dumps(payload))
PYEOF
    )
fi

# Call API and format response
RESPONSE=$(curl -s -X POST "$API_URL" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

# Phase 4: Post feedback for recalled memories (fire-and-forget, non-blocking)
FEEDBACK_SCRIPT="$(dirname "$0")/feedback.sh"
if [ -x "$FEEDBACK_SCRIPT" ]; then
    MEMORIES_USED=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('memories_used',0))" 2>/dev/null || echo 0)
    MEMORY_IDS=$(echo "$RESPONSE" | python3 -c "import sys,json; ids=json.load(sys.stdin).get('memory_ids',[]); print(' '.join(ids))" 2>/dev/null || echo "")
    if [ -n "$MEMORY_IDS" ]; then
        for MID in $MEMORY_IDS; do
            "$FEEDBACK_SCRIPT" "used" "$MID" "recalled_in_session" &
        done
    fi
    # Log recall event regardless
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] recall: memories_used=$MEMORIES_USED context=${CONTEXT:0:80}" >> /root/logs/feedback.log
fi

# Pretty-print with jq if available, otherwise raw
if command -v jq &>/dev/null; then
    echo "$RESPONSE" | jq -r '.context_block // .error // .'
else
    echo "$RESPONSE"
fi
