#!/bin/bash
# 0Latency Memory Storage Wrapper
# Fire-and-forget memory persistence to 0Latency API

set -euo pipefail

API_KEY="${ZEROLATENCY_API_KEY:-$(cat /root/.openclaw/workspace/THOMAS_API_KEY.txt 2>/dev/null || echo '')}"
AGENT_ID="thomas"
API_URL="https://api.0latency.ai/extract"
LOG_DIR="/tmp/0latency-logs"

mkdir -p "$LOG_DIR"

if [ $# -lt 2 ]; then
    cat << 'USAGE'
Usage: store.sh HUMAN_MSG AGENT_MSG [CONTEXT]

Store a conversation turn to 0Latency memory layer.

Arguments:
  HUMAN_MSG   What the human said
  AGENT_MSG   What the agent responded
  CONTEXT     Optional additional context

Examples:
  store.sh "Justin asked about Palmer" "Stored to KEY_PEOPLE.md"
  store.sh "What's the logo?" "Fixed logo on all pages" "Launch testing"

USAGE
    exit 1
fi

HUMAN_MSG="$1"
AGENT_MSG="$2"
CONTEXT="${3:-}"

# Create JSON using jq (handles escaping properly)
if command -v jq &>/dev/null; then
    PAYLOAD=$(jq -n \
        --arg agent "$AGENT_ID" \
        --arg human "$HUMAN_MSG" \
        --arg agent_msg "$AGENT_MSG" \
        --arg ctx "$CONTEXT" \
        '{agent_id: $agent, human_message: $human, agent_message: $agent_msg} + if $ctx != "" then {conversation_context: $ctx} else {} end')
else
    # Fallback: Python
    PAYLOAD=$(python3 - "$AGENT_ID" "$HUMAN_MSG" "$AGENT_MSG" "$CONTEXT" << 'PYEOF'
import json, sys
agent_id, human, agent_msg, ctx = sys.argv[1:5]
payload = {"agent_id": agent_id, "human_message": human, "agent_message": agent_msg}
if ctx: payload["conversation_context"] = ctx
print(json.dumps(payload))
PYEOF
    )
fi

# Fire-and-forget API call (background)
LOG_FILE="$LOG_DIR/store-$(date +%s).log"
curl -s -X POST "$API_URL" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  > "$LOG_FILE" 2>&1 &

echo "✓ Memory queued (pid $!, log: $LOG_FILE)"
