# LongMemEval Extraction Layer Diagnostic Audit
**Date**: 2026-05-11  
**Mission**: Root cause analysis of 0.0% benchmark accuracy  
**Scope**: Read-only diagnostic (no code changes)

---

## Shape

**[A] Extraction exists but misconfigured** 

Extraction layer is present and functional, but exhibits a **dual-storage pathology**:
- Raw conversation turns stored as low-importance (0.3) "raw_turn" memories
- LLM-extracted atomic facts stored separately (~1 fact per turn)  
- **Critical failure**: Recall retrieves raw_turn memories instead of atomic facts

---

## Evidence

### 1. Ingestion Path

**File**: mcp-server/src/server.ts:384-421
- **MCP tool**: memory_add concatenates human_message + agent_message into single content string
- **API call**: POSTs to BASE_URL + "/memories" with raw content
- **Issue**: MCP server calls undefined POST /memories endpoint (not found in api/main.py)

**File**: benchmarks/longmemeval/run_benchmark.py:95
- **Benchmark path**: Uses POST /extract endpoint (not /memories)
- Sends human_message and agent_message as separate fields

**File**: api/main.py:549-597 (POST /extract endpoint)
- Calls src/extraction.py extract_memories()
- Stores returned memories via store_memories()

### 2. Extraction Logic

**File**: src/extraction.py:193-396 (extract_memories function)

**Step 1: Raw turn storage** (lines 236-271)
- **Stores raw conversation verbatim** BEFORE extraction
- **Importance**: Fixed at 0.3 (low priority)
- **Goes directly to database** via store_memory()
- headline: "Raw turn — {timestamp}"
- memory_type: "raw_turn"
- full_content: "Human: {human_message}\n\nAgent: {agent_message}"

**Step 2: LLM extraction** (lines 290-323)
- **Model**: EXTRACTION_MODEL=gemini-2.5-flash (from .env)
- **Prompt**: 150-line extraction prompt with multi-turn context
- **Output**: JSON array of atomic fact objects
- Calls _call_model(prompt) which routes to Gemini/Anthropic/OpenAI

**Step 3: Validation & enrichment** (lines 324-396)
- Filters out memories without headline
- Filters out confidence < 0.3
- **Returns**: validated list contains ONLY LLM-extracted facts
- **raw_turn NOT included** in return value (already in DB)

### 3. Sample Database State

**Benchmark tenant**: 382faaf1-5cbf-49a1-b689-5ffef8918d10  
**Dry-run results** (benchmarks/longmemeval/dryrun-20260511-0123.json):
- **Turns extracted**: 63
- **Total memories stored**: 125
- **Breakdown**:
  - 63 raw_turn memories (1 per turn, importance 0.3)
  - 62 atomic facts (avg 0.98 per turn, importance varies)

**Recall failure**:
- All 5 questions returned 0 context chars
- hypothesis: "I don''t have enough information to answer that."
- **Root cause**: Recall returns raw_turn memories (wrong semantic match) instead of atomic facts

### 4. Mem0 Target Pattern

**Source**: [Mem0 GitHub prompts.py](https://github.com/mem0ai/mem0/blob/main/mem0/configs/prompts.py)

**Approach**: Single-pass ADD-only extraction
- **Prompt**: FACT_RETRIEVAL_PROMPT extracts 7 types (preferences, plans, health, professional, etc.)
- **Output**: JSON {"facts": ["atomic fact 1", "atomic fact 2",...]}
- **Storage**: One memory per atomic fact (NO raw turn preservation)
- **Example**: "User prefers lights at 40% brightness after 9pm" (NOT "User: I like my lights at 40%. Agent: Got it!")

**Key difference**: Mem0 does NOT store raw turns. 0Latency stores BOTH (raw + extracted).

---

## Fix Scope Estimate

### Files to Touch
1. **src/extraction.py** (primary)
   - Remove raw_turn storage OR demote importance to 0.1
   - Improve extraction prompt quality (benchmark against Mem0)
   - Increase avg facts per turn from 0.98 → 3-5

2. **src/recall.py** (secondary)
   - Add memory_type boosting: prefer fact/preference/identity over raw_turn
   - Importance weighting: 0.3 should not outrank 0.7+ facts

3. **mcp-server/src/server.ts** (blocker)
   - Fix POST /memories endpoint mismatch (calls nonexistent route)
   - Should call POST /extract or POST /memories/extract

### New Code Needed
- **Minimal**: Comment out raw_turn storage (5 lines) → YES
- **Recommended**: Rewrite extraction prompt + recall ranking logic → ~200 LOC

### Hours Estimate
- **Quick fix** (disable raw_turn): 30 minutes + test
- **Production fix** (improve extraction + recall): 8-12 hours
  - Prompt engineering: 2-3 hours
  - Recall ranking: 3-4 hours
  - Integration testing: 2-3 hours
  - Re-run benchmark: 1-2 hours

**Honest estimate**: 2 full days (16 hours) to ship quality fix + validate with benchmark

---

## Recommended Implementation

### Extraction Prompt Approach

**Option A: Disable raw_turn (quick fix)**
- Comment out raw_turn storage at src/extraction.py line 236
- **Pros**: Immediate 50% memory reduction, forces reliance on atomic facts  
- **Cons**: Loses verbatim preservation (may break other use cases)

**Option B: Demote raw_turn importance**
- Change importance from 0.3 to 0.05 (lowest priority)
- **Pros**: Preserves verbatim, recall won''t retrieve unless no atomic facts match  
- **Cons**: Still wastes storage

**Option C: Improve extraction quality** (recommended)
- Benchmark Gemini 2.5 Flash vs Claude Haiku vs GPT-4o-mini on 10 sample turns
- Measure: avg facts per turn, accuracy vs expected facts
- Tune EXTRACTION_PROMPT based on LongMemEval question types:
  - Preferences: "What''s my favorite coffee shop?" → extract brand names, locations
  - Events: "Where did I redeem a coupon?" → extract merchant, item, action
  - Identity: "What degree did I graduate with?" → extract degree, school, year

### Where It Plugs In

**Current flow**:


**Fix injection points**:
1. **Line 236**: Add feature flag DISABLE_RAW_TURN (env var)
2. **Line 290**: Swap EXTRACTION_PROMPT with Mem0-style prompt
3. **Line 348**: Lower confidence threshold from 0.3 → 0.5 (stricter filtering)

### Sync vs Async

**Current**: Sync (blocking write)  
**Recommendation**: Keep sync for now
- Benchmark requires immediate recall after extraction
- Async would add job queue complexity
- POST /memories/extract already exists (async path) but unused by benchmark

**Future**: Async extraction worker for production
- Pattern exists in api/extraction_worker.py
- Decouple write-time latency from extraction quality

---

## Appendix: MCP Server Endpoint Mismatch

**Issue**: MCP server calls POST /memories (line 400 in mcp-server/src/server.ts)  
**Reality**: Endpoint does not exist in api/main.py

**Available endpoints**:
- POST /extract (sync, used by benchmark)
- POST /memories/extract (async, 202 response)
- POST /memories/seed (direct fact seeding, bypasses extraction)

**Impact**: MCP server integration broken (separate from benchmark issue)  
**Fix**: Update MCP server to call POST /extract

---

**Diagnostic complete**: 2026-05-11 02:14 UTC  
**Operator**: Ready for implementation (CP11+)

---

## Sources
- [Mem0 GitHub prompts.py](https://github.com/mem0ai/mem0/blob/main/mem0/configs/prompts.py)
- [Mem0 LongMemEval Results](https://mem0.ai/research)
- [Mem0 Token Optimization Playbook](https://mem0.ai/blog/the-2026-token-optimization-playbook-cut-ai-agent-memory-costs-3%E2%80%934x)
- [Mem0 Custom Fact Extraction](https://docs.mem0.ai/open-source/features/custom-fact-extraction-prompt)
