#!/bin/bash
# POST /feedback after every recall
# Usage: feedback.sh <feedback_type> [memory_id] [context]
# feedback_type: used | ignored | contradicted | miss
# memory_id: UUID (optional for miss, required for others)
# context: optional string

API_KEY="zl_live_jk13qjxlpiltqs3t157rvfypsa6xa40o"
FEEDBACK_TYPE="${1:-used}"
MEMORY_ID="${2:-}"
CONTEXT="${3:-}"

PAYLOAD="{\"agent_id\":\"thomas\",\"feedback_type\":\"${FEEDBACK_TYPE}\""

if [ -n "$MEMORY_ID" ]; then
  PAYLOAD="${PAYLOAD},\"memory_id\":\"${MEMORY_ID}\""
fi

if [ -n "$CONTEXT" ]; then
  PAYLOAD="${PAYLOAD},\"context\":\"${CONTEXT}\""
fi

PAYLOAD="${PAYLOAD}}"

curl -s -X POST "https://api.0latency.ai/feedback" \
  -H "Content-Type: application/json" \
  -H "x-api-key: ${API_KEY}" \
  -d "$PAYLOAD" >> /root/logs/feedback.log 2>&1 &
