#!/bin/bash
# Integration test for CP9 P2 T1: Time-to-First-Memory instrumentation
# Tests all 4 install paths emit onboarding events correctly

set -euo pipefail
set -a && source .env && set +a

echo "=== CP9 P2 T1 Onboarding Events Integration Test ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
    ((TESTS_PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    ((TESTS_FAILED++))
}

info() {
    echo -e "${YELLOW}ℹ INFO:${NC} $1"
}

# Cleanup function
cleanup() {
    if [ -n "${TEST_TENANT_IDS:-}" ]; then
        info "Cleaning up test tenants..."
        for tenant_id in $TEST_TENANT_IDS; do
            psql "$DATABASE_URL" -c "DELETE FROM memory_service.onboarding_events WHERE tenant_id = '$tenant_id'" > /dev/null 2>&1 || true
            psql "$DATABASE_URL" -c "DELETE FROM memory_service.memories WHERE tenant_id = '$tenant_id'" > /dev/null 2>&1 || true
        done
    fi
}

trap cleanup EXIT

# Create test tenant with proper API key format
create_test_tenant() {
    local path=$1
    local tenant_name="test-onboarding-${path}-$(date +%s)"
    
    # Generate proper API key: zl_live_ + 32 hex chars = 40 total
    local api_key="zl_live_$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
    local tenant_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
    
    psql "$DATABASE_URL" -c "
        INSERT INTO memory_service.tenants (id, name, api_key_live, email)
        VALUES ('$tenant_id', '$tenant_name', '$api_key', '$tenant_name@test.local')
    " > /dev/null
    
    echo "$tenant_id:$api_key"
}

# Test /memories/extract endpoint
test_extract_endpoint() {
    local path=$1
    info "Testing /memories/extract with X-Install-Path: $path"
    
    local tenant_data=$(create_test_tenant $path)
    local tenant_id=${tenant_data%:*}
    local api_key=${tenant_data#*:}
    TEST_TENANT_IDS="$TEST_TENANT_IDS $tenant_id"
    
    sleep 1
    
    # First memory add
    local response=$(curl -s -X POST "http://localhost:8420/memories/extract" \
        -H "X-API-Key: $api_key" \
        -H "X-Install-Path: $path" \
        -H "Content-Type: application/json" \
        -d '{"content": "My name is Alice and I work at TechCorp as a data scientist. My favorite programming language is Python.", "agent_id": "test-agent"}')
    
    local job_id=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null || echo "")
    
    if [ -z "$job_id" ]; then
        fail "[$path extract] Failed to get job_id: $response"
        return
    fi
    
    sleep 6
    
    # Check onboarding event
    local event_count=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id' AND event_type = 'first_memory_add'
    " | tr -d ' ')
    
    if [ "$event_count" = "1" ]; then
        pass "[$path extract] Onboarding event created"
    else
        fail "[$path extract] Expected 1 event, got $event_count"
        return
    fi
    
    # Verify path
    local recorded_path=$(psql "$DATABASE_URL" -t -c "
        SELECT install_path FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if [ "$recorded_path" = "$path" ]; then
        pass "[$path extract] Path recorded correctly"
    else
        fail "[$path extract] Expected '$path', got '$recorded_path'"
    fi
    
    # Verify elapsed_seconds
    local elapsed=$(psql "$DATABASE_URL" -t -c "
        SELECT elapsed_seconds FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if (( $(echo "$elapsed > 0" | bc -l) )) && (( $(echo "$elapsed < 300" | bc -l) )); then
        pass "[$path extract] Elapsed ${elapsed}s is reasonable"
    else
        fail "[$path extract] Elapsed ${elapsed}s out of range"
    fi
    
    # Second memory - no duplicate
    curl -s -X POST "http://localhost:8420/memories/extract" \
        -H "X-API-Key: $api_key" \
        -H "X-Install-Path: $path" \
        -H "Content-Type: application/json" \
        -d '{"content": "I also enjoy hiking and my birthday is in March.", "agent_id": "test-agent"}' > /dev/null
    
    sleep 2
    
    local event_count_after=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if [ "$event_count_after" = "1" ]; then
        pass "[$path extract] No duplicate on second memory"
    else
        fail "[$path extract] Duplicate created, count: $event_count_after"
    fi
}

# Test /atoms endpoint  
test_atoms_endpoint() {
    local path=$1
    info "Testing /atoms with X-Install-Path: $path"
    
    local tenant_data=$(create_test_tenant $path)
    local tenant_id=${tenant_data%:*}
    local api_key=${tenant_data#*:}
    TEST_TENANT_IDS="$TEST_TENANT_IDS $tenant_id"
    
    sleep 1
    
    local atom_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
    curl -s -X POST "http://localhost:8420/atoms" \
        -H "Authorization: Bearer $api_key" \
        -H "X-Install-Path: $path" \
        -H "Content-Type: application/json" \
        -d '{
            "id": "'$atom_id'",
            "agent_id": "test-agent",
            "role": "user",
            "content": "My name is Bob and I prefer coffee over tea. I live in Seattle."
            "verbatim": true,
            "surface": "cli"
        }' > /dev/null
    
    sleep 1
    
    local event_count=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if [ "$event_count" = "1" ]; then
        pass "[$path atoms] Onboarding event created"
    else
        fail "[$path atoms] Expected 1 event, got $event_count"
        return
    fi
    
    local recorded_path=$(psql "$DATABASE_URL" -t -c "
        SELECT install_path FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if [ "$recorded_path" = "$path" ]; then
        pass "[$path atoms] Path recorded correctly"
    else
        fail "[$path atoms] Expected '$path', got '$recorded_path'"
    fi
    
    # Second atom
    local atom_id2=$(python3 -c 'import uuid; print(uuid.uuid4())')
    curl -s -X POST "http://localhost:8420/atoms" \
        -H "Authorization: Bearer $api_key" \
        -H "X-Install-Path: $path" \
        -H "Content-Type: application/json" \
        -d '{
            "id": "'$atom_id2'",
            "agent_id": "test-agent",
            "role": "user",
            "content": "I work as a designer and my hobby is photography.",
            "verbatim": true,
            "surface": "cli"
        }' > /dev/null
    
    sleep 1
    
    local event_count_after=$(psql "$DATABASE_URL" -t -c "
        SELECT COUNT(*) FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if [ "$event_count_after" = "1" ]; then
        pass "[$path atoms] No duplicate on second atom"
    else
        fail "[$path atoms] Duplicate created, count: $event_count_after"
    fi
}

# Test missing header defaults to "unknown"
test_missing_header() {
    info "Testing missing X-Install-Path header"
    
    local tenant_data=$(create_test_tenant "unknown")
    local tenant_id=${tenant_data%:*}
    local api_key=${tenant_data#*:}
    TEST_TENANT_IDS="$TEST_TENANT_IDS $tenant_id"
    
    sleep 1
    
    curl -s -X POST "http://localhost:8420/memories/extract" \
        -H "X-API-Key: $api_key" \
        -H "Content-Type: application/json" \
        -d '{"content": "My favorite food is pizza and I speak Spanish fluently.", "agent_id": "test-agent"}' > /dev/null
    
    sleep 6
    
    local recorded_path=$(psql "$DATABASE_URL" -t -c "
        SELECT install_path FROM memory_service.onboarding_events
        WHERE tenant_id = '$tenant_id'
    " | tr -d ' ')
    
    if [ "$recorded_path" = "unknown" ]; then
        pass "[missing header] Defaults to 'unknown'"
    else
        fail "[missing header] Expected 'unknown', got '$recorded_path'"
    fi
}

TEST_TENANT_IDS=""

echo "--- Testing /memories/extract endpoint ---"
test_extract_endpoint "sdk"
test_extract_endpoint "cli"
test_extract_endpoint "mcp"
test_extract_endpoint "web"

echo ""
echo "--- Testing /atoms endpoint ---"
test_atoms_endpoint "sdk"
test_atoms_endpoint "cli"
test_atoms_endpoint "mcp"
test_atoms_endpoint "web"

echo ""
echo "--- Testing edge cases ---"
test_missing_header

echo ""
echo "=== Test Summary ==="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed ✗${NC}"
    exit 1
fi
