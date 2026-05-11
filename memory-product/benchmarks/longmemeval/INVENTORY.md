# LongMemEval Benchmark - Phase 0 Inventory
**Date**: 2026-05-10  
**Mission**: Execute full LongMemEval benchmark against production 0Latency stack

---

## 1. Prior Harness Status

### Location
`/root/.openclaw/workspace/memory-product/bench/longmemeval/`

### Contents
- **SUMMARY-20260504.md** - Baseline run summary (May 4, 2026)
- **results-baseline-20260504.json** - Baseline results (n=5, 0.0% accuracy)
- **upstream/** - LongMemEval official benchmark repository (ICLR 2025)
  - Dataset format documentation
  - Evaluation scripts (`src/evaluation/evaluate_qa.py`)
  - Generation and retrieval baselines
  
### Status: USABLE ✅
- Upstream repo cloned and intact
- Dataset format well-documented
- Evaluation pipeline exists
- **Gap**: No custom 0Latency adapter script found

---

## 2. Prior Baseline Results (2026-05-04)

### Test Parameters
- **Sample size**: 5 questions
- **Dataset**: longmemeval_s_cleaned.json
- **Sessions loaded**: 3 out of ~50 per question (extraction bottleneck)
- **Mode**: FAST_MODE
- **Total time**: 171 seconds

### Performance
- **Accuracy**: 0.0% (0/5) - Expected, insufficient context
- **p50 latency**: 443ms
- **p95 latency**: 686ms

### Key Finding
**Extraction bottleneck**: ~10 seconds per session  
**Projected full-run time**: ~70 hours for 500 questions × 50 sessions

---

## 3. Competitive Baseline - Mem0

### Published Results (2026)
**Source**: [Mem0 Research Page](https://mem0.ai/research)

- **LongMemEval score**: 93.4%
- **Token efficiency**: <7,000 tokens/retrieval (vs 25,000+ full-context)
- **Algorithm**: Token-efficient memory algorithm (latest)

### Discrepancy Notes
- User mentioned ~26% - this may refer to an older baseline or different evaluation
- Independent benchmarks cite 49.0% ([MemPalace issue #29](https://github.com/MemPalace/mempalace/issues/29))
- **Official current best**: 93.4% (Mem0's own published result)

### Other Competitive Scores
- **MemPalace**: 96.6% (verbatim storage, different approach)
- **Baseline (OpenAI full-context)**: Not explicitly stated in search results

**Strategic implication**: Beating 93.4% is aggressive. Target: >50% for Show HN credibility.

---

## 4. Dataset Structure (LongMemEval)

### Format
- **Total questions**: 500
- **Variants**:
  - `longmemeval_s_cleaned.json` - Short (115k tokens, ~40 sessions)
  - `longmemeval_m_cleaned.json` - Medium (~500 sessions)
  - `longmemeval_oracle.json` - Oracle retrieval (evidence only)

### Question Types
1. single-session-user
2. single-session-assistant
3. single-session-preference
4. temporal-reasoning
5. knowledge-update
6. multi-session
7. abstention (30 instances, skipped in retrieval eval)

### Evaluation Method
- Output format: JSONL with `question_id` and `hypothesis`
- Eval script: `src/evaluation/evaluate_qa.py`
- Grader: GPT-4o (via OpenAI API)
- Metrics: Accuracy (exact match or semantic equivalence)

---

## 5. Project Knowledge Review

### COMPETITIVE-ANALYSIS-MEM0.md (2026-03-26)
**Key takeaways**:
- Mem0 targets framework-first (LangChain, enterprises)
- 0Latency targets tool-first (Claude Code, solo devs)
- No specific LongMemEval mention in competitive doc (predates May 4 baseline)

**Gaps identified** (not benchmark-related):
- JavaScript SDK
- Multi-provider embeddings
- Documentation quality

**Benchmark gap**: No prior competitive benchmark comparison documented.

---

## 6. Required Adapter Work (Scope Assessment)

### What Exists
✅ Upstream evaluation harness  
✅ Dataset download mechanism  
✅ Eval script (`evaluate_qa.py`)  

### What's Needed
❌ **0Latency adapter script** to:
  1. Load LongMemEval questions + haystack sessions
  2. Extract sessions via `POST /v1/memory/add` (or batch endpoint)
  3. Recall via `POST /v1/memory/recall`
  4. Format output as JSONL for evaluation
  5. Capture latency metrics (p50, p95)

### Estimated Build Effort
**Optimistic**: 2-3 hours (straightforward API calls, minimal error handling)  
**Realistic**: 4-6 hours (pagination, rate limiting, session isolation, logging)  
**Worst case**: >8 hours (API compatibility issues, need batch optimization)

**Initial assessment**: < 4 hours → Proceed to Phase 2  
**Gate trigger**: If adapter hits unexpected complexity → STOP and report

---

## 7. Infrastructure Requirements

### Production Endpoint
- **API**: https://api.0latency.ai
- **Auth**: Requires tenant API key
- **Endpoints needed**:
  - `POST /v1/memory/add` - Extract memories from conversations
  - `POST /v1/memory/recall` - Recall with conversation context
  - `POST /v1/tenants` - Create dedicated benchmark tenant

### Benchmark Tenant Isolation
**Why**: Avoid polluting production tenant memories with benchmark data  
**Method**: Create via API (exercises CP9.1.5b atomic create_tenant fix)  
**Verification**: Check all 5 roles seeded (NOT EXISTS assertion)

### Resource Constraints
- **Max runtime**: 4 hours wall clock
- **Execution**: tmux or systemd-run (survive SSH disconnect)
- **Logs**: benchmarks/longmemeval/fullrun-YYYYMMDD-HHMM.log

---

## 8. Phase 1 Decision Gate - PROCEED ✅

### Criteria
- [ ] Prior harness exists? → YES (upstream code present)
- [ ] Adapter work < 4 hours? → YES (estimated 2-4 hours)
- [ ] Dataset accessible? → YES (Hugging Face download)
- [ ] Eval pipeline understood? → YES (documented)

### Decision: FORWARD TO PHASE 2

**Rationale**:
- Upstream harness provides evaluation infrastructure
- 0Latency adapter is straightforward API integration
- No major unknowns that would expand scope >4 hours

**Next**: Create dedicated benchmark tenant via production API.

---

## Sources

- [Mem0 LongMemEval Results](https://mem0.ai/research)
- [LongMemEval GitHub](https://github.com/xiaowu0162/longmemeval)
- [LongMemEval Dataset (HuggingFace)](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)
- [LongMemEval Benchmark Site](https://xiaowu0162.github.io/long-mem-eval/)
- Prior baseline: bench/longmemeval/SUMMARY-20260504.md

---

**Phase 0 Complete**: 2026-05-10  
**Next Phase**: Create benchmark tenant (Phase 2)
