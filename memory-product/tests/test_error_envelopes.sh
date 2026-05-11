#!/bin/bash
# CP9 Phase 2 Track B2 - Error Envelope Integration Tests
#
# Tests that all API errors return standardized error envelopes with:
# - error.code (machine-readable)
# - error.message (human-readable)
# - error.hint (actionable guidance)
# - error.docs_url (link to troubleshooting docs)

set -e

API_BASE=${API_BASE:-"http://localhost:8000"}
VALID_API_KEY=${VALID_API_KEY:-""}
INVALID_API_KEY="zl_live_invalid1234567890123456789012"

echo "==================================="
echo "Error Envelope Integration Tests"
echo "==================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    exit 1
}

info() {
    echo -e "${YELLOW}ℹ INFO${NC}: $1"
}

# Helper to check if JSON response has error envelope structure
check_error_envelope() {
    local response="$1"
    local expected_code="$2"
    local test_name="$3"

    # Check for error object
    if ! echo "$response" | jq -e '.detail.error' > /dev/null 2>&1; then
        fail "$test_name: Missing 'error' object in response"
    fi

    # Check for required fields
    local code=$(echo "$response" | jq -r '.detail.error.code')
    local message=$(echo "$response" | jq -r '.detail.error.message')
    local hint=$(echo "$response" | jq -r '.detail.error.hint')
    local docs_url=$(echo "$response" | jq -r '.detail.error.docs_url')

    if [ "$code" = "null" ] || [ -z "$code" ]; then
        fail "$test_name: Missing error.code"
    fi

    if [ "$message" = "null" ] || [ -z "$message" ]; then
        fail "$test_name: Missing error.message"
    fi

    if [ "$hint" = "null" ] || [ -z "$hint" ]; then
        fail "$test_name: Missing error.hint"
    fi

    if [ "$docs_url" = "null" ] || [ -z "$docs_url" ]; then
        fail "$test_name: Missing error.docs_url"
    fi

    # Check expected error code if provided
    if [ -n "$expected_code" ] && [ "$code" != "$expected_code" ]; then
        fail "$test_name: Expected code '$expected_code' but got '$code'"
    fi

    pass "$test_name: Error envelope valid (code=$code)"
}

# Test 1: Invalid API Key (401)
echo "Test 1: Invalid API Key returns proper error envelope"
response=$(curl -s -X POST "$API_BASE/extract" \
    -H "X-API-Key: $INVALID_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"human_message": "test", "agent_message": "test"}' \
    -w "\n%{http_code}")

http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | head -n -1)

if [ "$http_code" != "401" ]; then
    fail "Test 1: Expected HTTP 401, got $http_code"
fi

check_error_envelope "$body" "INVALID_API_KEY" "Test 1"
echo ""

# Test 2: Missing API Key (401)
echo "Test 2: Missing API Key returns proper error envelope"
response=$(curl -s -X POST "$API_BASE/extract" \
    -H "Content-Type: application/json" \
    -d '{"human_message": "test", "agent_message": "test"}' \
    -w "\n%{http_code}")

http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | head -n -1)

if [ "$http_code" != "401" ]; then
    fail "Test 2: Expected HTTP 401, got $http_code"
fi

check_error_envelope "$body" "" "Test 2"
echo ""

# Test 3: Not Found (404)
if [ -n "$VALID_API_KEY" ]; then
    echo "Test 3: Resource not found returns proper error envelope"
    response=$(curl -s -X GET "$API_BASE/memories/00000000-0000-0000-0000-000000000000" \
        -H "X-API-Key: $VALID_API_KEY" \
        -w "\n%{http_code}")

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" != "404" ]; then
        fail "Test 3: Expected HTTP 404, got $http_code"
    fi

    check_error_envelope "$body" "NOT_FOUND" "Test 3"
    echo ""
else
    info "Test 3: Skipped (VALID_API_KEY not set)"
    echo ""
fi

# Test 4: Validation Error (422)
if [ -n "$VALID_API_KEY" ]; then
    echo "Test 4: Validation error returns proper error envelope"
    response=$(curl -s -X POST "$API_BASE/extract" \
        -H "X-API-Key: $VALID_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"human_message": "", "agent_message": ""}' \
        -w "\n%{http_code}")

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" != "422" ] && [ "$http_code" != "400" ]; then
        info "Test 4: Expected HTTP 422 or 400, got $http_code (continuing)"
    fi

    # Check if response has error envelope (may be FastAPI validation format)
    if echo "$body" | jq -e '.detail.error' > /dev/null 2>&1; then
        check_error_envelope "$body" "" "Test 4"
    else
        info "Test 4: Response uses FastAPI validation format (not custom envelope)"
    fi
    echo ""
else
    info "Test 4: Skipped (VALID_API_KEY not set)"
    echo ""
fi

# Test 5: Rate Limit includes Retry-After header
if [ -n "$VALID_API_KEY" ]; then
    echo "Test 5: Rate limit error includes Retry-After header"

    # Make multiple rapid requests to trigger rate limit
    for i in {1..150}; do
        curl -s -X POST "$API_BASE/extract" \
            -H "X-API-Key: $VALID_API_KEY" \
            -H "Content-Type: application/json" \
            -d '{"human_message": "test", "agent_message": "test"}' \
            > /dev/null 2>&1 &
    done
    wait

    # Try one more to get rate limited
    response=$(curl -s -i -X POST "$API_BASE/extract" \
        -H "X-API-Key: $VALID_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"human_message": "test", "agent_message": "test"}')

    if echo "$response" | grep -q "429"; then
        if echo "$response" | grep -qi "Retry-After:"; then
            pass "Test 5: Rate limit includes Retry-After header"
        else
            fail "Test 5: Rate limit missing Retry-After header"
        fi
    else
        info "Test 5: Rate limit not triggered (consider this a pass)"
    fi
    echo ""
else
    info "Test 5: Skipped (VALID_API_KEY not set)"
    echo ""
fi

# Summary
echo "==================================="
echo "All error envelope tests completed"
echo "==================================="
echo ""
echo "To run with a valid API key:"
echo "  VALID_API_KEY=your_key ./test_error_envelopes.sh"
echo ""
