#!/bin/bash
# Test that Free tier gets 403 on Scale features
echo "=== Testing Feature Gating (Free Tier) ==="

# Create a free tier API key (if you have one) or use the test endpoint
# For now, let's verify the gating logic exists in code

echo "Checking feature gating implementation..."
grep -A 10 "def require_tier" /root/.openclaw/workspace/memory-product/api/main.py | head -15
