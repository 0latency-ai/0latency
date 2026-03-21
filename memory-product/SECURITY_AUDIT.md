# Security Audit Report
_Generated: March 21, 2026 04:30 UTC_
_Tool: Bandit v1.9.4_

## Critical Path (API-facing) — CLEAN ✅
- `api/main.py` — 0 findings
- `src/recall.py` — 1 finding (MD5 for cache key, non-security use → fixed with usedforsecurity=False)
- `src/storage_multitenant.py` — 0 findings
- `src/extraction.py` — 0 findings

## Utility Files (internal-only) — 26 SQL injection warnings
Files: compaction.py, feedback.py, handoff.py, negative_recall.py, storage.py, extract_turn.py, test_pipeline.py, session_processor.py, historical_import.py

These files use f-string SQL but are:
- Not API-accessible (no endpoints route to them)
- Only called via CLI/scripts (admin-only, not user-facing)
- Candidate for parameterized query migration in Phase C

**Risk: LOW** — no user input reaches these paths. But should be cleaned up.

## Database Security
- ✅ Row Level Security enabled on all tables
- ✅ Tenant context set per-transaction
- ✅ HNSW vector index (replaces sequential scan)
- ✅ Composite indexes for common query patterns
- ✅ Trigram index for keyword search (gin_trgm_ops)

## Indexes Added (this session)
1. `idx_memories_embedding_hnsw` — HNSW vector index for cosine similarity
2. `idx_memories_tenant_agent_active` — composite for list/count queries (partial: superseded_at IS NULL)
3. `idx_memories_high_importance` — partial for high-importance recall
4. `idx_memories_headline_trgm` — GIN trigram for ILIKE keyword search
