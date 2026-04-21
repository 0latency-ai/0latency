#!/bin/bash
# Tier Value Delivery Test Suite
# Verifies that paid tiers get premium features and free tiers don't

set -e

API_BASE="https://api.0latency.ai"
ENTERPRISE_KEY="zl_live_4nrnnmz1pt2dh0wlq2aq1vfqsbiu99s1"
FREE_KEY="zl_live_u9veb53ezg9f4mto32554srlhatjvfn2"

PASS_COUNT=0
FAIL_COUNT=0

echo "========================================="
echo "TIER VALUE DELIVERY TEST SUITE"
echo "========================================="
echo ""

# Helper function to test API response
test_extract() {
    local tier=$1
    local api_key=$2
    local agent_id=$3
    local expected_entities=$4
    local expected_relationships=$5
    local expected_sentiment=$6
    
    echo "Testing $tier tier..."
    
    response=$(curl -s -X POST "$API_BASE/extract" \
        -H "X-API-Key: $api_key" \
        -H "Content-Type: application/json" \
        -d "{
            \"agent_id\": \"$agent_id\",
            \"human_message\": \"Nate from YouTube discussed the AI memory wall problem. Palmer works at ZeroClick with Ryan Hudson.\",
            \"agent_message\": \"Got it - Nate (YouTube), memory wall issue, Palmer and Ryan at ZeroClick.\"
        }")
    
    # Parse response
    memories_stored=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('memories_stored', 0))")
    entities_extracted=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('entities_extracted', 0))")
    relationships_created=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('relationships_created', 0))")
    sentiment_analyzed=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('sentiment_analyzed', 'false'))")
    tier_features=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tier_features_used', []))")
    
    # Validate basic memory storage works
    if [ "$memories_stored" -lt 1 ]; then
        echo "  ❌ FAIL: No memories stored (expected at least 1)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    else
        echo "  ✅ PASS: Memories stored: $memories_stored"
        PASS_COUNT=$((PASS_COUNT + 1))
    fi
    
    # Validate entities
    if [ "$expected_entities" = "yes" ]; then
        if [ "$entities_extracted" -gt 0 ]; then
            echo "  ✅ PASS: Entities extracted: $entities_extracted (expected >0)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: Entities extracted: $entities_extracted (expected >0)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        if [ "$entities_extracted" -eq 0 ]; then
            echo "  ✅ PASS: Entities extracted: 0 (correctly restricted)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: Entities extracted: $entities_extracted (expected 0 for free tier)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
    
    # Validate relationships
    if [ "$expected_relationships" = "yes" ]; then
        if [ "$relationships_created" -gt 0 ]; then
            echo "  ✅ PASS: Relationships created: $relationships_created (expected >0)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: Relationships created: $relationships_created (expected >0)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        if [ "$relationships_created" -eq 0 ]; then
            echo "  ✅ PASS: Relationships created: 0 (correctly restricted)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: Relationships created: $relationships_created (expected 0 for free tier)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
    
    # Validate sentiment
    if [ "$expected_sentiment" = "yes" ]; then
        if [ "$sentiment_analyzed" = "True" ] || [ "$sentiment_analyzed" = "true" ]; then
            echo "  ✅ PASS: Sentiment analyzed: true"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: Sentiment analyzed: $sentiment_analyzed (expected true)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        if [ "$sentiment_analyzed" = "False" ] || [ "$sentiment_analyzed" = "false" ]; then
            echo "  ✅ PASS: Sentiment analyzed: false (correctly restricted)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: Sentiment analyzed: $sentiment_analyzed (expected false for free tier)"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
    
    # Validate tier_features_used
    if [ "$expected_entities" = "yes" ]; then
        if [[ "$tier_features" == *"entity_extraction"* ]]; then
            echo "  ✅ PASS: tier_features_used includes 'entity_extraction'"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: tier_features_used missing 'entity_extraction'"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        if [[ "$tier_features" == "[]" ]]; then
            echo "  ✅ PASS: tier_features_used is empty (correctly restricted)"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL: tier_features_used should be empty for free tier, got: $tier_features"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
    
    echo ""
}

# Test 1: Enterprise Tier (should get ALL features)
echo "TEST 1: ENTERPRISE TIER"
echo "Expected: entities >0, relationships >0, sentiment=true"
test_extract "ENTERPRISE" "$ENTERPRISE_KEY" "tier-test-enterprise-$(date +%s)" "yes" "yes" "yes"

# Test 2: Free Tier (should get NO premium features)
echo "TEST 2: FREE TIER"
echo "Expected: entities=0, relationships=0, sentiment=false"
test_extract "FREE" "$FREE_KEY" "tier-test-free-$(date +%s)" "no" "no" "no"

# Summary
echo "========================================="
echo "TEST SUMMARY"
echo "========================================="
echo "Total tests: $((PASS_COUNT + FAIL_COUNT))"
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    echo ""
    echo "Tier differentiation is working correctly:"
    echo "  • Enterprise tier receives entity extraction, graph relationships, and sentiment"
    echo "  • Free tier receives basic memory storage only"
    echo "  • Response format correctly indicates tier features used"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    echo ""
    echo "Tier differentiation is NOT working correctly."
    echo "Review the failures above and fix the /extract endpoint."
    exit 1
fi
