# TIER VALUE DELIVERY — Launch Blocker

**Problem:** Paid users don't automatically get premium features. They get the same basic experience as free tier unless they manually call advanced endpoints.

**This is a $89/mo product failure.**

---

## Changes Required (Launch-Blocking)

### 1. Auto-Enable Features by Tier in `/extract`

**Current behavior:**
```python
# Everyone gets basic memory storage
# Graph/sentiment/entities only if you call separate endpoints
```

**Required behavior:**
```python
if tier in ['pro', 'scale', 'enterprise']:
    # Automatically extract entities
    # Automatically calculate sentiment  
    # Automatically map graph relationships
    # Return enhanced response with all data
```

**Response should include:**
```json
{
  "memories_stored": 2,
  "memory_ids": ["...", "..."],
  "entities_extracted": 5,
  "relationships_created": 3,
  "sentiment_analyzed": true,
  "confidence_scores": [0.9, 0.85],
  "tier_features_used": ["graph", "sentiment", "entities"]
}
```

### 2. Upgrade `/recall` for Paid Tiers

**Current:** Same semantic search for everyone

**Required for Scale/Enterprise:**
- Entity-aware recall (boost results mentioning extracted entities)
- Graph traversal (include related memories via relationships)
- Sentiment context (surface emotional tone)
- Confidence weighting (prioritize high-confidence memories)

**Response should show value:**
```json
{
  "context_block": "...",
  "memories_used": 5,
  "entities_matched": ["React", "Palmer", "ZeroClick"],
  "graph_hops": 2,
  "sentiment_context": "positive interactions with technical contacts",
  "tier_features_used": ["entity_matching", "graph_traversal", "sentiment"]
}
```

### 3. Dashboard Value Display

**Add to dashboard.html:**

**For Scale tier users:**
```html
<div class="tier-value-summary">
  <h3>Your Scale Tier Value This Month</h3>
  <ul>
    <li>4,521 entity extractions</li>
    <li>2,103 graph queries</li>
    <li>8,944 sentiment analyses</li>
    <li>1,203 relationship mappings</li>
  </ul>
  <p>That's $X worth of AI processing included in your plan.</p>
</div>
```

**For Free tier users (upsell):**
```html
<div class="tier-upgrade-prompt">
  <h3>Unlock More Value</h3>
  <p>You've stored 87/100 memories. Upgrade to Scale for:</p>
  <ul>
    <li>Automatic entity extraction (people, orgs, tech)</li>
    <li>Graph relationships (see connections across memories)</li>
    <li>Sentiment analysis (understand emotional context)</li>
    <li>10K memory limit (100x more)</li>
  </ul>
  <button>Upgrade to Scale - $89/mo</button>
</div>
```

### 4. MCP Tier-Aware Behavior

**Current:** Same 5 basic tools for everyone

**Required:** Scale tier users get enhanced tools

**Add to MCP:**
```typescript
// When user calls memory_search on Scale tier
// Automatically include entity-based suggestions
{
  "results": [...],
  "suggestions": [
    "I noticed you mentioned React - want to explore related memories?",
    "Palmer appears in 3 connected memories - traverse the graph?"
  ]
}
```

### 5. API Response Headers (Transparency)

**Add to all responses:**
```
X-Tier: scale
X-Features-Used: graph,sentiment,entities
X-Tier-Value: entity_extraction,relationship_mapping
```

User can see what premium features were applied to their request.

---

## Implementation Priority

**CRITICAL (must ship before launch):**
1. ✅ Auto-enable entity extraction in `/extract` for paid tiers — DONE (2026-03-26 18:00 UTC)
2. ✅ Auto-enable sentiment analysis in `/extract` for paid tiers — DONE (2026-03-26 18:00 UTC)
3. ✅ Auto-enable graph relationships in `/extract` for paid tiers — DONE (2026-03-26 18:00 UTC)
4. ⏳ Enhanced `/recall` with entity matching for paid tiers — QUEUED (post-launch)
5. ✅ Response format includes tier features used — DONE (2026-03-26 18:00 UTC)

**TESTED AND VERIFIED:**
- Enterprise tier: 7 entities extracted, 9 relationships created automatically
- Free tier: 0 entities, 0 relationships (correctly restricted)
- API restarted, both tiers tested, working perfectly

**HIGH (ship within first week):**
6. Dashboard value display
7. MCP tier-aware suggestions
8. API response headers showing features used

**MEDIUM (nice-to-have):**
9. Usage analytics by feature
10. Tier upgrade prompts in dashboard

---

## Testing Checklist

**Before launch:**
- [ ] Free tier user: verify NO entity extraction, NO graph, NO sentiment
- [ ] Scale tier user: verify ALL features auto-enabled in `/extract`
- [ ] Scale tier user: verify enhanced `/recall` with entity matching
- [ ] Response format includes tier_features_used for paid tiers
- [ ] Dashboard shows Scale tier features (if time permits)

**Validation:**
```bash
# Free tier test
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: FREE_TIER_KEY" \
  -d '{"agent_id":"test","human_message":"I love React","agent_message":"noted"}'
# Should return: memories_stored only, NO entities_extracted

# Scale tier test  
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: SCALE_TIER_KEY" \
  -d '{"agent_id":"test","human_message":"I love React","agent_message":"noted"}'
# Should return: memories_stored + entities_extracted + sentiment_analyzed + relationships_created
```

---

## Code Changes Required

**File:** `/root/.openclaw/workspace/memory-product/api/main.py`

**Function:** `extract_endpoint()`

**Changes:**
1. Add tier check after authentication
2. If tier in ['pro', 'scale', 'enterprise']: call entity extraction, sentiment, graph
3. Update response format to include tier_features_used
4. Don't require separate endpoint calls - do it all in `/extract`

**Estimated time:** 2-3 hours (including testing)

**Risk:** Medium (changes core endpoint, needs careful testing)

**Rollback:** Keep old behavior as fallback, feature-flag the new behavior

---

## Success Metrics

**After launch:**
- Scale tier users should call advanced endpoints 10x LESS (because `/extract` does it automatically)
- Dashboard should show clear value ($X worth of processing included)
- Support tickets should drop ("I paid but don't see graph features")

**User quote we want:**
> "I upgraded to Scale and immediately started seeing entities, relationships, and sentiment in every memory. I didn't have to change my code at all. It just worked."

---

**THIS IS LAUNCH-BLOCKING. Fix before posting to Reddit/HN.**
