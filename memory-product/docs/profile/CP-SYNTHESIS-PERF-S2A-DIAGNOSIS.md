# CP-SYNTHESIS-PERF Stage 2.A — Diagnosis

**Date:** 2026-05-05
**Authored by:** CC (autonomous Stage 2.A run)
**Status:** Diagnosis only — no code changes. Locks Stage 2.B scope.

## Embedding bottleneck (72% of Stage 1 wall-clock)

### Where it happens
- File: `src/synthesis/writer.py`
- Function: `synthesize_cluster_to_atom`
- Line: `501`
- Code excerpt (5–10 lines):
  ```python
  # Generate embedding
  embedding_start = time.perf_counter()
  embedding = _embed_text(synthesis_text)
  embedding_duration_ms = int((time.perf_counter() - embedding_start) * 1000)
  perf_logger.info(json.dumps({
      "metric": "synthesis_perf",
      "phase": "embedding",
      "duration_ms": embedding_duration_ms,
      "tenant_id": tenant_id,
  ```

### Root causes confirmed
1. **Cold model load** — CONFIRMED.
   - Evidence: `SentenceTransformer` is module-level but lazy-loaded via `_get_local_model()` in `src/storage_multitenant.py:36-41`. First call triggers HuggingFace model download/load. No app-startup preload exists. Model instantiation pattern: `if _local_embedding_model is None: _local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')`.
2. **Non-batched per-memory calls** — REFUTED (not applicable).
   - Evidence: Writer embeds ONCE per synthesis (line 501) for the newly-generated `synthesis_text`, NOT per cluster member. Cluster members are fetched WITHOUT embeddings (query at line 297-302 does not SELECT embedding column). No loop over cluster members for embedding. Batching is irrelevant—only one text is embedded.
3. **Re-embedding memories that already have embeddings** — REFUTED (misdiagnosis of Stage 1 hypothesis).
   - Evidence: The writer does NOT re-embed source memories. It embeds the NEW synthesis output text (`synthesis_text` from LLM response) for storage in `memory_service.memories.embedding`. Cluster members already have embeddings (see DB query below), but those are never read or reused by the writer—they're used by `clustering.py` for similarity computation. The 12.6s embedding cost is for generating ONE embedding for the synthesis atom, not 12 embeddings for cluster members.

### DB embedding population for validation cluster
- Cluster b28b7a99fd4791cb: **21/21 members have embedding populated** (100%).
- Query result:
  ```
  total_members | with_embedding | without_embedding
  --------------+----------------+-------------------
             21 |             21 |                 0
  ```
- Implication: Cluster members' existing embeddings are irrelevant to writer bottleneck. Writer embeds synthesis output, not inputs.

### Stage 2.B fix candidates (not applied)
1. **App-startup model preload** via FastAPI lifespan event in `api/main.py`. Call `_get_local_model()` during application startup to eliminate first-call latency. Target: reduce 12.6s embedding time to ~50-200ms (per-text encode time for 384d model on modern CPU).
2. **No batching or reuse fixes needed**—only one text is embedded per synthesis, and it's a new text (synthesis output) that has never been embedded before.

## LLM model selection (24% of Stage 1 wall-clock; orthogonal cost-leak issue)

### Stage 1 observed
- Writer used `claude-sonnet-4-6` for tenant `44c3080d-c196-407d-a606-4ea9f62ba0fc` (thomas).

### Tenant plan
- `thomas` plan: **`enterprise`** (from psql query).
- Query result:
  ```
  id                                   | name   | plan
  -------------------------------------|--------|------------
  44c3080d-c196-407d-a606-4ea9f62ba0fc | thomas | enterprise
  ```

### Where model is selected
- File: `src/synthesis/writer.py`
- Function: `synthesize_cluster_to_atom`
- Line: `346` (tier lookup), `362-366` (model mapping)
- Code excerpt (5–10 lines):
  ```python
  # Determine model
  if llm_model is None:
      tier_model = get_allowed_model(tenant_id, conn)
      # ...
      # Map tier model to Anthropic model ID
      model_map = {
          "haiku": "claude-haiku-4-5-20251001",
          "sonnet": "claude-sonnet-4-6",
      }
      llm_model = model_map.get(tier_model, "claude-haiku-4-5-20251001")
  ```

### Tier-gating helper present?
- `src/tier_gates.py` exists: **YES**.
- Exposes a `get_allowed_model(tenant_id, conn)`: **YES** (line 247).
- Writer currently calls it: **YES** (line 346).

### Diagnosis
**NOT A REGRESSION**. Writer correctly routes via `tier_gates.get_allowed_model()`, which returns `"sonnet"` for Enterprise-tier tenants. Thomas tenant is `enterprise` plan, so Sonnet usage is INTENTIONAL per CP8 tier matrix (TIER_MATRIX in `tier_gates.py:22-86`):
- Free tier: model = None (blocked)
- Pro tier: model = "haiku"
- Scale tier: model = "haiku"
- Enterprise tier: model = "sonnet"

Stage 1's "Sonnet on thomas" observation was correct behavior, not a bug. The LLM-model hypothesis evaporates.

### Stage 2.B fix candidate (not applied)
**None**. Model selection is working as designed. If cost optimization is desired for Enterprise tier, that's a tier-matrix policy decision (reduce Enterprise to Haiku), not a writer bug. Out of scope for CP-SYNTHESIS-PERF.

## Stage 2.B scope shape (recommendation)

**Single-fix chain** (LLM model issue is closed):
- **Embedding preload only**: Add FastAPI lifespan hook in `api/main.py` to call `src.storage_multitenant._get_local_model()` on app startup. Target: eliminate 12.6s cold-load, reduce synthesis embedding phase to <200ms.
- **Re-profile** against cluster b28b7a99fd4791cb (21-member, user-justin, agent-id from Stage 1 profile).
- **Target**: Total synthesis wall-clock < 5s for validation cluster (down from ~17.5s baseline). Embedding should drop from 12.6s to ~0.1-0.2s, leaving LLM call (~4.3s) as new bottleneck.

Estimated S2.B wall-clock: **20–30 min** (FastAPI lifespan hook + test + profile rerun; simpler than originally estimated since no batching/reuse logic needed).

## What this diagnosis does NOT cover

- **Haiku output quality for Enterprise downgrade**: Not applicable—Enterprise correctly uses Sonnet, no downgrade planned.
- **Async embedding** (off critical path): Out of scope. Preload is simpler and sufficient.
- **Embedding storage strategy changes** (precompute at write time): Future architectural consideration; embedding the synthesis output is necessary and unavoidable. Preload is the only optimization needed.
- **Clustering embedding performance**: Out of scope. Clustering already reads pre-populated embeddings from DB (no recomputation). The 72% bottleneck is in writer, not clustering.
