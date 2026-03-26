#!/bin/bash
# Scale Tier Feature Test
API_KEY="zl_live_synwdojae2ois01oi01mmzdqh791hfek"
BASE="https://api.0latency.ai"
AGENT="test-scale-$(date +%s)"

echo "=== Testing Scale Tier Features ==="
echo "Agent ID: $AGENT"
echo ""

# 1. Store a test memory first
echo "1. Storing test memory..."
RESPONSE=$(curl -s -X POST "$BASE/extract" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\":\"$AGENT\",\"human_message\":\"I love React for frontend work\",\"agent_message\":\"Got it\"}")
echo "Response: $RESPONSE"
sleep 3

# 2. Get memories to find an ID
echo -e "\n2. Getting memories to find ID..."
MEMORIES=$(curl -s "$BASE/memories?agent_id=$AGENT&limit=10" -H "X-API-Key: $API_KEY")
echo "Memories: $MEMORIES"
MEMORY_ID=$(echo $MEMORIES | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Memory ID: $MEMORY_ID"

# 3. Test graph traversal
echo -e "\n3. Testing graph traversal..."
curl -s "$BASE/memories/graph?agent_id=$AGENT&memory_id=$MEMORY_ID&depth=2" \
  -H "X-API-Key: $API_KEY" | jq '.' || echo "FAILED"

# 4. Test entities
echo -e "\n4. Testing entities..."
curl -s "$BASE/memories/entities?agent_id=$AGENT&limit=50" \
  -H "X-API-Key: $API_KEY" | jq '.' || echo "FAILED"

# 5. Test sentiment summary
echo -e "\n5. Testing sentiment summary..."
curl -s "$BASE/memories/sentiment-summary?agent_id=$AGENT" \
  -H "X-API-Key: $API_KEY" | jq '.' || echo "FAILED"

# 6. Test by-entity
echo -e "\n6. Testing by-entity (React)..."
curl -s "$BASE/memories/by-entity?agent_id=$AGENT&entity_text=React" \
  -H "X-API-Key: $API_KEY" | jq '.' || echo "FAILED"

echo -e "\n=== Test Complete ==="
