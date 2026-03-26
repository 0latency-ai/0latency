# Pre-Launch QA Checklist

**Before posting to Reddit/HN/X:** Run through this list to verify everything works.

---

## API Endpoints

### Core Memory
- [ ] `POST /extract` — Store memories from conversation
  ```bash
  curl -X POST https://api.0latency.ai/extract \
    -H "X-API-Key: YOUR_KEY" \
    -H "Content-Type: application/json" \
    -d '{"agent_id":"test","human_message":"I love React","agent_message":"Noted"}'
  ```
  **Expected:** 200 OK, returns extraction job ID

- [ ] `GET /memories` — List all memories
  ```bash
  curl "https://api.0latency.ai/memories?agent_id=test&limit=10" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected:** 200 OK, returns array of memories

- [ ] `GET /memories/search` — Search memories
  ```bash
  curl "https://api.0latency.ai/memories/search?agent_id=test&q=React" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected:** 200 OK, returns relevant memories

- [ ] `GET /recall` — Smart recall
  ```bash
  curl "https://api.0latency.ai/recall?agent_id=test&query=frontend%20preferences" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected:** 200 OK, increments recall_count

### Graph Features (Pro/Scale only)
- [ ] `GET /memories/graph` — Graph traversal
  ```bash
  curl "https://api.0latency.ai/memories/graph?agent_id=test&memory_id=UUID&depth=2" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected (Free):** 403 Forbidden
  **Expected (Pro/Scale):** 200 OK, returns nodes + edges

- [ ] `GET /memories/entities` — Entity listing
  ```bash
  curl "https://api.0latency.ai/memories/entities?agent_id=test" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected (Free):** 403 Forbidden
  **Expected (Pro/Scale):** 200 OK, returns entities

- [ ] `GET /memories/by-entity` — Memories by entity
  ```bash
  curl "https://api.0latency.ai/memories/by-entity?agent_id=test&entity_text=React" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected (Free):** 403 Forbidden
  **Expected (Pro/Scale):** 200 OK, returns memories

- [ ] `GET /memories/sentiment-summary` — Sentiment stats
  ```bash
  curl "https://api.0latency.ai/memories/sentiment-summary?agent_id=test" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected (Free):** 403 Forbidden
  **Expected (Pro/Scale):** 200 OK, returns counts/scores

- [ ] `GET /memories/{id}/history` — Version history
  ```bash
  curl "https://api.0latency.ai/memories/UUID/history" -H "X-API-Key: YOUR_KEY"
  ```
  **Expected (Free):** 403 Forbidden
  **Expected (Pro/Scale):** 200 OK, returns versions

### Auto-Consolidation (when built)
- [ ] `GET /memories/duplicates` — List duplicates
- [ ] `POST /memories/duplicates/{id}/merge` — Merge duplicates
- [ ] `POST /memories/duplicates/{id}/dismiss` — Dismiss suggestion
- [ ] `POST /memories/consolidate` — Run full consolidation

---

## MCP Server (0.1.4)

### Installation
- [ ] `npx @0latency/mcp-server@latest` runs without errors
- [ ] Version shows 0.1.4 in package.json
- [ ] No deprecation warnings

### Tools (Core)
- [ ] `remember` — Stores a memory, returns success
- [ ] `memory_search` — Searches and returns results
- [ ] `memory_list` — Lists all memories
- [ ] `memory_recall` — Returns relevant memories
- [ ] `seed_memories` — Bulk-loads facts
- [ ] `import_document` — Imports text/markdown
- [ ] `import_conversation` — Imports chat history
- [ ] `load_memory_pack` — Loads memory packs

Test in Claude Desktop:
```
User: "Use the 0latency remember tool to store that my favorite color is blue"
Claude: [calls remember tool] → Success

User: "What's my favorite color?"
Claude: [calls memory_search or memory_recall] → "Blue"
```

### Tools (Graph - Pro/Scale)
- [ ] `memory_graph_traverse` — Returns graph data
- [ ] `memory_entities` — Lists entities
- [ ] `memory_sentiment_summary` — Returns sentiment stats
- [ ] `memory_by_entity` — Finds memories by entity
- [ ] `memory_history` — Shows version history

---

## Website

### Landing Page (0latency.ai)
- [ ] "Get API Key" button → https://0latency.ai/dashboard (not /docs)
- [ ] "Star on GitHub" → https://github.com/jghiglia2380 (not 404)
- [ ] All nav links work
- [ ] Mobile responsive
- [ ] Load time < 2s

### Auth Flow
- [ ] `/login.html` loads
- [ ] Email signup works
- [ ] Google OAuth works
- [ ] GitHub OAuth works
- [ ] Redirects to `/dashboard.html` after login

### Dashboard
- [ ] Shows API key
- [ ] "Copy" button works
- [ ] Usage stats display
- [ ] Plan info correct
- [ ] Can generate new key
- [ ] Can delete account

### Pricing Page
- [ ] All 4 tiers listed (Free, Pro, Scale, Enterprise)
- [ ] Features correct (graph/sentiment on Scale+)
- [ ] Checkout buttons work (Stripe)
- [ ] FAQ accurate

### Docs Page
- [ ] All endpoints documented
- [ ] Curl examples work
- [ ] Code blocks syntax-highlighted
- [ ] Search works (if implemented)

---

## Database

### Migrations
- [ ] `005_graph_sentiment.sql` applied (sentiment columns + indexes)
- [ ] `006_memory_versioning.sql` applied (versioning table)
- [ ] `007_consolidation.sql` applied (when consolidation ships)
- [ ] No broken foreign keys
- [ ] All indexes exist

### Data Integrity
- [ ] Memories have embeddings
- [ ] Sentiment scores in valid range (-1 to 1)
- [ ] Confidence scores in valid range (0 to 1)
- [ ] No orphaned relationships
- [ ] Recall_count increments correctly

### Performance
- [ ] `/memories` query < 50ms (10K memories)
- [ ] `/recall` query < 100ms (semantic search)
- [ ] `/memories/graph` query < 200ms (depth=2)
- [ ] No N+1 queries
- [ ] Indexes being used (check EXPLAIN)

---

## Feature Gating

### Free Tier
- [ ] Can store/recall/search memories
- [ ] Cannot access graph endpoints (403)
- [ ] Cannot access sentiment endpoints (403)
- [ ] Cannot access entity endpoints (403)
- [ ] Cannot access versioning (403)
- [ ] Limit: 10K memories enforced

### Pro Tier ($19/mo)
- [ ] Can access graph endpoints
- [ ] Can access sentiment endpoints
- [ ] Can access entity endpoints
- [ ] Can access versioning
- [ ] Limit: 100K memories enforced

### Scale Tier ($89/mo)
- [ ] All Pro features
- [ ] Graph depth=3 allowed
- [ ] Auto-consolidation access (when shipped)
- [ ] Limit: 1M memories enforced

---

## Extraction Pipeline

### LLM Integration
- [ ] Gemini Flash fallback works (if OpenAI fails)
- [ ] Entity extraction populates entities table
- [ ] Sentiment analysis populates sentiment columns
- [ ] Confidence scoring initializes correctly
- [ ] Relationship detection creates edges

### Async Processing
- [ ] Extract endpoint returns immediately (doesn't block)
- [ ] Background job completes within 5 seconds
- [ ] Errors logged properly
- [ ] Retries on transient failures

---

## Security

### Authentication
- [ ] Invalid API key → 401 Unauthorized
- [ ] Missing API key → 422 Field required
- [ ] Expired key → 401
- [ ] Rate limiting works (if implemented)

### Authorization
- [ ] Users can only access their own memories
- [ ] Tenant isolation works (agent_id scoping)
- [ ] Feature tier enforcement (403 on blocked features)

### CORS
- [ ] Allowed origins configured
- [ ] Preflight requests work
- [ ] Credentials allowed where needed

---

## Error Handling

### API Errors
- [ ] Invalid JSON → 422 with helpful message
- [ ] Missing required fields → 422 with field names
- [ ] Server errors → 500 with generic message (no stack traces in prod)
- [ ] Database connection lost → graceful degradation

### MCP Errors
- [ ] Network failure → user-friendly error in Claude
- [ ] Invalid API key → clear "check your key" message
- [ ] 403 on paid feature → "upgrade required" message

---

## Performance

### Load Testing (if done)
- [ ] 100 concurrent users → no errors
- [ ] 1000 requests/minute → sub-200ms p95
- [ ] Database connection pool healthy
- [ ] No memory leaks
- [ ] CPU usage < 80%

### Monitoring
- [ ] Error logging works
- [ ] Performance metrics tracked
- [ ] Alerts configured (if implemented)

---

## Launch Posts

### Reddit (r/ClaudeCode)
- [ ] Post reviewed (`/root/.openclaw/workspace/memory-product/launch/reddit-claude-code-post.md`)
- [ ] All links work
- [ ] Install commands tested
- [ ] Code examples tested

### X/Twitter
- [ ] Thread reviewed (`/root/.openclaw/workspace/memory-product/launch/x-launch-thread.md`)
- [ ] Character limits OK (280 per tweet)
- [ ] Links work
- [ ] Hashtags appropriate

### Hacker News
- [ ] Post reviewed (`/root/.openclaw/workspace/memory-product/launch/hackernews-show-hn.md`)
- [ ] Title follows HN format ("Show HN: ...")
- [ ] All technical claims accurate
- [ ] Links work

---

## GitHub Repos (when created)

### Main Repo (0latency-ai/0latency)
- [ ] README.md complete (`github-prep/MAIN-REPO-README.md`)
- [ ] LICENSE file (MIT)
- [ ] CONTRIBUTING.md
- [ ] .gitignore
- [ ] Examples directory

### MCP Server (0latency-ai/mcp-server)
- [ ] README.md complete (`github-prep/MCP-SERVER-README.md`)
- [ ] Source code pushed
- [ ] package.json correct
- [ ] LICENSE file (MIT)
- [ ] .npmignore

---

## Final Checks

- [ ] All passwords/secrets removed from code
- [ ] No console.log in production
- [ ] All TODOs resolved or documented
- [ ] Version numbers consistent
- [ ] Changelog updated
- [ ] Team notified (if applicable)

---

## Rollback Plan

**If something breaks after launch:**

1. API issue → revert migration: `psql < rollback_007.sql`
2. MCP issue → tell users to install `@0latency/mcp-server@0.1.3`
3. Website issue → revert Cloudflare Pages deployment
4. Critical bug → post update on X/Reddit immediately

**Emergency contacts:**
- Justin: justin@0latency.ai
- Support: hello@0latency.ai

---

**Last updated:** March 25, 2026 5:00 AM UTC
**Status:** Ready for Justin's review when he returns from work
