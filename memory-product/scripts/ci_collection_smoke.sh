#!/usr/bin/env bash
# CP8 P5.7 T3 - CI collection smoke check
# 
# Runs pytest --collect-only to detect import errors, syntax errors,
# and other collection failures that cause silent 'no tests ran' green builds.
#
# Exit codes:
#   0 - Collection succeeded (safe to run tests)
#   3 - Collection errors detected (build should fail)

set -euo pipefail

echo "==> CI Collection Smoke Check"
echo "==> Running pytest --collect-only to verify test discovery..."

# Capture both stdout and stderr, preserve exit code
COLLECT_OUTPUT=$(python3 -m pytest tests/ --collect-only -q 2>&1)
COLLECT_EXIT=$?

# Check for collection errors in output
if echo "$COLLECT_OUTPUT" | grep -q "error during collection"; then
    echo "ERROR: Test collection failed"
    echo ""
    echo "Offending tests:"
    echo "$COLLECT_OUTPUT" | grep -E "ERROR collecting|ImportError|SyntaxError|ModuleNotFoundError" | head -20
    echo ""
    echo "Collection errors mask broken imports as green builds."
    echo "Fix import/syntax errors before running test suite."
    exit 3
elif [ $COLLECT_EXIT -ne 0 ]; then
    echo "ERROR: pytest --collect-only exited with code $COLLECT_EXIT"
    echo "$COLLECT_OUTPUT" | head -30
    exit 3
else
    # Count collected tests
    TEST_COUNT=$(echo "$COLLECT_OUTPUT" | grep -E "[0-9]+ test" | tail -1 || echo "unknown")
    echo "✓ Collection succeeded: $TEST_COUNT"
    exit 0
fi
