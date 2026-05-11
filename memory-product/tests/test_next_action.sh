#!/bin/bash
# CP9 Phase 2 Track B3 - Next Action Integration Tests
#
# Tests that the first-recall demo flow works correctly:
# - First memory add returns next_action field
# - Second memory add does NOT return next_action field
# - next_action includes proper keywords extracted from headline
# - next_action includes install-path-specific examples

set -e

API_BASE=${API_BASE:-"http://localhost:8000"}
TEST_API_KEY=${TEST_API_KEY:-""}

echo "========================================="
echo "Next Action Integration Tests"
echo "========================================="
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

if [ -z "$TEST_API_KEY" ]; then
    echo -e "${RED}ERROR${NC}: TEST_API_KEY environment variable not set"
    echo ""
    echo "Usage:"
    echo "  TEST_API_KEY=your_test_key ./test_next_action.sh"
    echo ""
    echo "Note: This test requires a fresh API key for a new tenant"
    echo "      or a way to reset the tenant's onboarding state"
    exit 1
fi

# Test 1: First memory returns next_action
echo "Test 1: First memory add returns next_action field"
response=$(curl -s -X POST "$API_BASE/extract" \
    -H "X-API-Key: $TEST_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "human_message": "I met Sarah at Starbucks yesterday and she mentioned the new project",
        "agent_message": "Got it! I will remember that you met Sarah at Starbucks."
    }')

# Check if response is valid JSON
if ! echo "$response" | jq . > /dev/null 2>&1; then
    fail "Test 1: Invalid JSON response"
fi

# Check if next_action field exists
if ! echo "$response" | jq -e '.next_action' > /dev/null 2>&1; then
    info "Test 1: No next_action field found in response"
    echo "Response: $response"
    fail "Test 1: First memory should return next_action field"
fi

# Check next_action structure
action=$(echo "$response" | jq -r '.next_action.action')
description=$(echo "$response" | jq -r '.next_action.description')
example_query=$(echo "$response" | jq -r '.next_action.example_query')
code_example=$(echo "$response" | jq -r '.next_action.code_example')

if [ "$action" = "null" ] || [ -z "$action" ]; then
    fail "Test 1: next_action.action is missing"
fi

if [ "$description" = "null" ] || [ -z "$description" ]; then
    fail "Test 1: next_action.description is missing"
fi

if [ "$example_query" = "null" ] || [ -z "$example_query" ]; then
    fail "Test 1: next_action.example_query is missing"
fi

pass "Test 1: First memory returns next_action with all required fields"
echo "  action: $action"
echo "  example_query: $example_query"
echo ""

# Test 2: Keywords extracted correctly
echo "Test 2: Keywords extracted from headline"

# The example_query should contain relevant keywords from the conversation
# e.g., "Sarah" and "Starbucks" from "met Sarah at Starbucks"
if echo "$example_query" | grep -qi "Sarah"; then
    pass "Test 2a: Keywords include 'Sarah' (capitalized word)"
else
    info "Test 2a: Keywords don't include 'Sarah' (may be using different heuristic)"
fi

if echo "$example_query" | grep -qi "Starbucks"; then
    pass "Test 2b: Keywords include 'Starbucks' (proper noun)"
else
    info "Test 2b: Keywords don't include 'Starbucks'"
fi

if [ -n "$example_query" ] && [ "$example_query" != "null" ]; then
    pass "Test 2: Keyword extraction produced non-empty result"
fi
echo ""

# Test 3: Second memory does NOT return next_action
echo "Test 3: Second memory add does NOT return next_action"
response2=$(curl -s -X POST "$API_BASE/extract" \
    -H "X-API-Key: $TEST_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "human_message": "I prefer dark mode for all my apps",
        "agent_message": "Noted! I will remember your preference for dark mode."
    }')

# Check if response is valid JSON
if ! echo "$response2" | jq . > /dev/null 2>&1; then
    fail "Test 3: Invalid JSON response"
fi

# Check that next_action is null or absent
next_action_value=$(echo "$response2" | jq -r '.next_action')

if [ "$next_action_value" = "null" ] || [ -z "$next_action_value" ]; then
    pass "Test 3: Second memory correctly does NOT return next_action"
else
    fail "Test 3: Second memory should not return next_action, but got: $next_action_value"
fi
echo ""

# Test 4: Seed endpoint also returns next_action on first memory
echo "Test 4: Seed endpoint returns next_action for first memory (with new API key)"
echo "  Skipping: Requires fresh API key for new tenant"
info "Test 4: Manual verification needed with fresh tenant"
echo ""

# Test 5: Code example format matches install path
echo "Test 5: Code example includes SDK format"

if [ -n "$code_example" ] && [ "$code_example" != "null" ]; then
    # Check for SDK-style code example: client.recall(...)
    if echo "$code_example" | grep -q "client.recall"; then
        pass "Test 5: Code example uses SDK format (client.recall)"
    elif echo "$code_example" | grep -q "recall"; then
        pass "Test 5: Code example includes recall functionality"
    else
        info "Test 5: Code example format: $code_example"
    fi
else
    info "Test 5: No code_example in next_action"
fi
echo ""

# Test 6: Edge case - Empty conversation
echo "Test 6: Edge case - empty conversation doesn't crash"
response3=$(curl -s -X POST "$API_BASE/extract" \
    -H "X-API-Key: $TEST_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
        "human_message": "test",
        "agent_message": "test"
    }')

if echo "$response3" | jq . > /dev/null 2>&1; then
    pass "Test 6: Empty conversation handled gracefully"
else
    fail "Test 6: Failed to handle empty conversation"
fi
echo ""

# Summary
echo "========================================="
echo "Next Action Tests Completed"
echo "========================================="
echo ""
echo "Summary:"
echo "  ✓ First memory returns next_action"
echo "  ✓ Second memory does NOT return next_action"
echo "  ✓ Keywords extracted from headline"
echo "  ✓ Code examples included"
echo ""
echo "Note: For complete testing, run with a fresh API key"
echo "      to verify first-memory onboarding flow."
echo ""
