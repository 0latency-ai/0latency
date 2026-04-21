# Graph + Sentiment Implementation Spec
**Goal:** Add graph relationships and sentiment analysis to 0Latency API
**Timeline:** Ship before Justin returns from work (6-8 hours)
**Justification:** Required for Pro/Scale tier differentiation, competitive parity with Mem0

---

## 1. Graph Features (Relationship Mapping)

### Database Schema Changes
**New table: `memory_relationships`**
```sql
CREATE TABLE memory_service.memory_relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
  agent_id VARCHAR(128) NOT NULL,
  source_memory_id UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
  target_memory_id UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
  relationship_type VARCHAR(64) NOT NULL, -- 'causes', 'relates_to', 'contradicts', 'supports', 'requires', 'implies'
  strength FLOAT NOT NULL DEFAULT 0.5 CHECK (strength >= 0 AND strength <= 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(tenant_id, agent_id, source_memory_id, target_memory_id, relationship_type)
);

CREATE INDEX idx_memory_relationships_agent ON memory_service.memory_relationships(agent_id, tenant_id);
CREATE INDEX idx_memory_relationships_source ON memory_service.memory_relationships(source_memory_id);
CREATE INDEX idx_memory_relationships_target ON memory_service.memory_relationships(target_memory_id);
```

**New table: `memory_entities`**
```sql
CREATE TABLE memory_service.memory_entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES memory_service.tenants(id),
  agent_id VARCHAR(128) NOT NULL,
  entity_text VARCHAR(512) NOT NULL,
  entity_type VARCHAR(64), -- 'person', 'organization', 'concept', 'technology', 'location', 'product'
  first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  mention_count INT NOT NULL DEFAULT 1,
  UNIQUE(tenant_id, agent_id, entity_text, entity_type)
);

CREATE INDEX idx_memory_entities_agent ON memory_service.memory_entities(agent_id, tenant_id);
```

**Junction table: `memory_entity_links`**
```sql
CREATE TABLE memory_service.memory_entity_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id UUID NOT NULL REFERENCES memory_service.memories(id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES memory_service.memory_entities(id) ON DELETE CASCADE,
  UNIQUE(memory_id, entity_id)
);

CREATE INDEX idx_memory_entity_links_memory ON memory_service.memory_entity_links(memory_id);
CREATE INDEX idx_memory_entity_links_entity ON memory_service.memory_entity_links(entity_id);
```

### Extraction Logic (LLM-powered)
**When `/extract` is called:**
1. Extract memories as usual (existing flow)
2. **NEW: Entity extraction prompt**
   - Input: human_message + agent_message
   - Output: JSON array of entities with types
   - Model: GPT-4o-mini (fast + cheap)
   - Upsert into `memory_entities` (increment mention_count if exists)
   - Link to memories via `memory_entity_links`

3. **NEW: Relationship detection prompt** (run AFTER memory extraction)
   - Input: newly extracted memories + top 10 semantically similar existing memories
   - Output: JSON array of relationships between memories
   - Model: GPT-4o (better reasoning)
   - Insert into `memory_relationships`

**Prompt templates:**
```
Entity extraction:
"Extract all named entities from this conversation turn. For each entity, identify its type (person, organization, concept, technology, location, product). Return as JSON array: [{text: string, type: string}]"

Relationship detection:
"Given these memories, identify semantic relationships between them. Valid types: causes, relates_to, contradicts, supports, requires, implies. Return as JSON: [{source_id: uuid, target_id: uuid, type: string, strength: 0-1}]"
```

### API Endpoints

**GET `/memories/graph`** — Get related memories via graph traversal
```python
@router.get("/memories/graph")
async def get_memory_graph(
    agent_id: str = Query(...),
    memory_id: str = Query(...),
    depth: int = Query(2, ge=1, le=3),  # Max traversal depth
    min_strength: float = Query(0.3, ge=0, le=1),
    tenant: dict = Depends(require_api_key),
):
    # Recursive graph traversal from memory_id
    # Returns: nodes (memories) + edges (relationships)
```

**GET `/memories/entities`** — List all entities for an agent
```python
@router.get("/memories/entities")
async def list_entities(
    agent_id: str = Query(...),
    entity_type: Optional[str] = Query(None),
    min_mentions: int = Query(1),
    limit: int = Query(50),
    tenant: dict = Depends(require_api_key),
):
    # Returns entities with mention counts + related memories
```

**GET `/memories/by-entity`** — Get all memories mentioning an entity
```python
@router.get("/memories/by-entity")
async def memories_by_entity(
    agent_id: str = Query(...),
    entity_text: str = Query(...),
    tenant: dict = Depends(require_api_key),
):
    # Returns memories linked to this entity
```

---

## 2. Sentiment Analysis

### Database Schema Changes
**Add columns to `memories` table:**
```sql
ALTER TABLE memory_service.memories
ADD COLUMN sentiment VARCHAR(16), -- 'positive', 'negative', 'neutral'
ADD COLUMN sentiment_score FLOAT CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
ADD COLUMN sentiment_intensity FLOAT CHECK (sentiment_intensity >= 0 AND sentiment_intensity <= 1),
ADD COLUMN confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
ADD COLUMN recall_count INT DEFAULT 0,
ADD COLUMN last_recalled_at TIMESTAMPTZ;
```

### Extraction Logic
**When `/extract` is called:**
1. Extract memories as usual
2. **NEW: Sentiment analysis** (parallel with entity extraction)
   - Input: each extracted memory's text
   - Output: sentiment label + score (-1 to 1) + intensity (0 to 1)
   - Model: GPT-4o-mini with structured output
   - Store in memories table

**Prompt template:**
```
"Analyze the sentiment of this statement. Return JSON:
{
  sentiment: 'positive' | 'negative' | 'neutral',
  score: -1.0 to 1.0 (negative to positive),
  intensity: 0.0 to 1.0 (weak to strong)
}

Examples:
- 'I love React' → {sentiment: 'positive', score: 0.8, intensity: 0.9}
- 'Vue is okay' → {sentiment: 'neutral', score: 0.1, intensity: 0.3}
- 'I hate debugging' → {sentiment: 'negative', score: -0.7, intensity: 0.8}"
```

### API Enhancements

**Update `/memories` list endpoint** — Add sentiment filters
```python
@router.get("/memories")
async def list_memories(
    agent_id: str = Query(...),
    sentiment: Optional[str] = Query(None),  # NEW: filter by sentiment
    min_sentiment_score: Optional[float] = Query(None),  # NEW
    max_sentiment_score: Optional[float] = Query(None),  # NEW
    # ... existing params
):
```

**New endpoint: `/memories/sentiment-summary`** — Aggregate sentiment stats
```python
@router.get("/memories/sentiment-summary")
async def sentiment_summary(
    agent_id: str = Query(...),
    tenant: dict = Depends(require_api_key),
):
    # Returns: {positive_count, negative_count, neutral_count, avg_score, avg_intensity}
```

---

## 3. Pricing Tier Gating

**Free tier (10K memories):**
- ✅ Core memory storage/recall
- ✅ Temporal decay
- ✅ Basic search
- ❌ Graph relationships
- ❌ Sentiment analysis
- ❌ Entity extraction

**Pro tier ($19/mo, 100K memories):**
- ✅ Everything in Free
- ✅ Graph relationships (depth=2)
- ✅ Sentiment analysis
- ✅ Entity extraction
- ✅ Advanced filters

**Scale tier ($89/mo, 1M memories):**
- ✅ Everything in Pro
- ✅ Graph relationships (depth=3)
- ✅ Batch operations
- ✅ Priority support

### Implementation: Feature gating in API
```python
def check_feature_access(tenant: dict, feature: str) -> bool:
    plan = tenant.get("plan", "free")
    
    if feature in ["graph", "sentiment", "entities"]:
        return plan in ["pro", "scale"]
    
    if feature == "graph_depth_3":
        return plan == "scale"
    
    return True  # Free tier features

# Usage in endpoints:
if not check_feature_access(tenant, "graph"):
    raise HTTPException(403, detail="Graph features require Pro or Scale tier. Upgrade at 0latency.ai/pricing")
```

---

## 4. Migration Plan

1. **Schema migration** (5 min)
   - Run SQL migrations on Supabase
   - No downtime (additive changes only)

2. **Deploy new extraction logic** (10 min)
   - Update `/extract` endpoint with entity + sentiment + relationship extraction
   - Backward compatible (existing memories unaffected)

3. **Deploy new API endpoints** (5 min)
   - Add graph/entity/sentiment endpoints
   - Feature-gated by plan

4. **Backfill existing memories** (OPTIONAL, can run async)
   - Background job to add sentiment/entities to existing memories
   - Not blocking launch

---

## 5. Testing Plan

**Unit tests:**
- Entity extraction returns valid JSON
- Relationship detection between memories
- Sentiment scoring accuracy
- Feature gating works (403 on free tier)

**Integration tests:**
- Full extraction flow with graph + sentiment
- Graph traversal API
- Entity filtering
- Sentiment queries

**Manual testing:**
- Store 10 memories with relationships
- Query `/memories/graph` — verify traversal
- Query `/memories/entities` — verify entity list
- Query `/memories?sentiment=positive` — verify filter

---

## 6. Cost Analysis

**Per extraction (with graph + sentiment):**
- Entity extraction: ~$0.0002 (GPT-4o-mini, ~200 tokens)
- Sentiment analysis: ~$0.0001 (GPT-4o-mini, ~100 tokens)
- Relationship detection: ~$0.002 (GPT-4o, ~500 tokens, only if similar memories exist)
- **Total per extraction: ~$0.0023** (less than a quarter cent)

**At scale:**
- 10K extractions/day = $23/day = $690/month in LLM costs
- Covered by Pro tier revenue ($19/user × 50 users = $950/month)

---

## 7. Confidence Scoring (ADDED TO TONIGHT'S BUILD)

**Initial confidence calculation:**
- Base: 0.5 (default)
- +0.2 if extracted from explicit statement ("I prefer React")
- +0.1 if corroborated by multiple turns
- +0.1 if related to existing high-confidence memories
- -0.2 if contradicts existing memories (flag for review)

**Confidence increases over time:**
- +0.05 each time memory is recalled and used (cap at 0.95)
- Track `recall_count` and `last_recalled_at`

**Confidence API additions:**
- `/memories` endpoint returns confidence score
- `/recall` endpoint increments recall_count + updates last_recalled_at
- Filter: `?min_confidence=0.7` (only high-confidence memories)

---

## 8. Launch Checklist

- [ ] SQL migrations written + tested on dev DB
- [ ] Entity extraction implemented
- [ ] Relationship detection implemented
- [ ] Sentiment analysis implemented
- [ ] **Confidence scoring implemented**
- [ ] New API endpoints built
- [ ] Feature gating added
- [ ] MCP tools updated (optional — can ship API first)
- [ ] Docs updated (0latency.ai/docs.html)
- [ ] Pricing page updated (mention graph + sentiment + confidence)
- [ ] Deploy to production
- [ ] Test with Justin's API key
- [ ] Announce to Ryan Hudson

---

## Next Steps

1. **Justin reviews this spec** — approve or request changes
2. **Thomas spawns Opus coding agent** — builds it (6-8 hour window)
3. **Deploy + test** — when Justin returns from work
4. **Ship to production** — live tonight

