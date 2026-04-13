#!/bin/bash
# Test webhook with sample GitHub payloads

SERVER_URL="${1:-http://localhost:8765}"
WEBHOOK_SECRET="${GITHUB_WEBHOOK_SECRET}"

echo "🧪 Testing 0Latency Contribution Reviewer"
echo "Server: $SERVER_URL"
echo ""

# Health check
echo "1. Health check..."
HEALTH=$(curl -s "$SERVER_URL/health")
echo "   Response: $HEALTH"
echo ""

# Stats check
echo "2. Stats check..."
STATS=$(curl -s "$SERVER_URL/stats")
echo "   Response: $STATS"
echo ""

# Test bug report webhook
echo "3. Test bug report webhook..."
PAYLOAD='{"action":"labeled","issue":{"number":123,"title":"App crashes on login","body":"Steps to reproduce:\n1. Open app\n2. Enter credentials\n3. Click login\n4. App crashes\n\nExpected: Should login\nActual: Crashes","html_url":"https://github.com/test/repo/issues/123","user":{"login":"testuser","email":"test@example.com"},"labels":[{"name":"bug"}]},"repository":{"full_name":"0latency/test"},"sender":{"login":"testuser"}}'

# Generate signature
SIGNATURE="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)"

RESPONSE=$(curl -s -X POST "$SERVER_URL/contribution-review" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -d "$PAYLOAD")

echo "   Response: $RESPONSE"
echo ""

# Test merged PR webhook
echo "4. Test merged PR webhook..."
PR_PAYLOAD='{"action":"closed","pull_request":{"number":456,"title":"Fix memory leak in auth module","body":"This PR fixes a critical memory leak discovered during testing.\n\nChanges:\n- Added proper cleanup in AuthManager\n- Updated tests\n- Documentation","html_url":"https://github.com/test/repo/pull/456","user":{"login":"contributor","email":"contributor@example.com"},"merged":true,"additions":120,"deletions":45,"changed_files":3},"repository":{"full_name":"0latency/test"},"sender":{"login":"contributor"}}'

PR_SIGNATURE="sha256=$(echo -n "$PR_PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)"

PR_RESPONSE=$(curl -s -X POST "$SERVER_URL/contribution-review" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: $PR_SIGNATURE" \
  -d "$PR_PAYLOAD")

echo "   Response: $PR_RESPONSE"
echo ""

echo "✅ Tests complete!"
echo ""
echo "Check your database and logs to verify processing:"
echo "  sudo journalctl -u 0latency-reviewer -n 20"
echo "  psql -d 0latency -c 'SELECT * FROM contribution_reviews ORDER BY created_at DESC LIMIT 5;'"
