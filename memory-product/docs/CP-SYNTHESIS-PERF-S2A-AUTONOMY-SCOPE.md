# CP-SYNTHESIS-PERF Stage 2.A — Embedding + Model-Selection Diagnosis

**Mode:** Autonomous CC, single task, diagnosis-only (NO code changes).
**Branch in:** `cp-synthesis-perf-s1` (continue, NOT a new branch).
**Estimated wall-clock:** 10–15 min.
**Predecessor:** CP-SYNTHESIS-PERF Stage 1 (profile shipped on this branch).

---

## Goal (one sentence)

Read the synthesis writer's embedding call site and LLM-model-selection call site, then write a 1-page diagnosis note that locks Stage 2.B's optimization scope with concrete file paths, line numbers, and confirmed root causes.

## Why this exists

Stage 1 found embedding = 72% of writer cost (12,585ms for 12 memories) and the LLM call defaulting to `claude-sonnet-4-6` regardless of tier. Both are hypotheses about CAUSE, not yet confirmed:

- Embedding hypothesis: cold model load + per-memory work that should be batched and/or skipped if `memory_service.memories.embedding` already populated.
- Model-selection hypothesis: Sonnet hardcoded somewhere in writer or jobs orchestrator, ignoring tenant tier (per CP8 spec: Haiku default for Scale, Sonnet for Enterprise).

Stage 2.B will fix whichever cause is real. Stage 2.A's job is to read the code and tell us which.

NO FIXES IN STAGE 2.A. If CC sees an obvious one-line fix, it goes in the diagnosis note as a Stage 2.B candidate — not applied here.

---

## In scope

- READ: `src/synthesis/writer.py`, `src/synthesis/clustering.py`, `src/synthesis/jobs.py`, any module they import for embedding or LLM calls.
- READ: `src/synthesis/tier_gates.py` (or wherever tier-aware model selection lives — CC discovers).
- READ: the embedder module (likely `src/storage_multitenant.py::_embed_text_local` per memory #6, or whatever the writer actually calls).
- READ: schema column `memory_service.memories.embedding` — query whether existing source memories in `b28b7a99fd4791cb` cluster have embeddings populated already.
- WRITE: ONE file, `docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md`, committed at end of run.

## Out of scope (DO NOT TOUCH)

- Any code change in `src/`, `api/`, `scripts/`, `tests/`. ZERO.
- The profile harness itself (it's already shipped in Stage 1).
- The recall path.
- Schema migrations.
- The MCP server.

---

## Inputs at start

- Branch: `cp-synthesis-perf-s1`, must be checked out, working tree clean.
- HEAD: Stage 1 closure commit + STATE-LOG entry.
- `.env` loaded.
- Validation cluster for Stage 2.C: `b28b7a99fd4791cb` (21 members on user-justin, confirmed via psql).

---

## Steps

### 1. Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git status                              # clean
git branch --show-current               # cp-synthesis-perf-s1
git log -1 --oneline                    # Stage 1 closure
set -a && source .env && set +a
```

**Halt if:** wrong branch, dirty tree.

### 2. Trace the embedding call site

```bash
cd /root/.openclaw/workspace/memory-product
grep -rn "embed" src/synthesis/ | head -30
grep -rn "_embed_text_local\|encode\|SentenceTransformer" src/synthesis/ src/storage_multitenant.py 2>/dev/null | head -30
```

Identify:
- The exact file + function + line number where the writer requests embeddings for cluster member memories.
- Whether the call is per-memory (in a loop) or batched (one call with a list).
- Whether existing `memory_service.memories.embedding` values are checked/reused, or whether embeddings are always recomputed.
- Whether the `SentenceTransformer` model is module-level/global (loaded once) or function-local (loaded per call).

### 3. Verify embedding column population

```bash
cd /root/.openclaw/workspace/memory-product
psql "$DATABASE_URL" -c "
SELECT
  COUNT(*) AS total_members,
  COUNT(embedding) AS with_embedding,
  COUNT(*) - COUNT(embedding) AS without_embedding
FROM memory_service.memories
WHERE (metadata->>'cluster_id') = 'b28b7a99fd4791cb';
"
```

Capture the exact counts. This answers: "if we read the existing embedding column instead of recomputing, how much work disappears?"

### 4. Trace the LLM model-selection call site

```bash
cd /root/.openclaw/workspace/memory-product
grep -rn "claude-sonnet\|claude-haiku\|model=" src/synthesis/ | head -30
grep -rn "tier\|plan" src/synthesis/writer.py src/synthesis/jobs.py 2>/dev/null | head -20
cat src/synthesis/tier_gates.py 2>/dev/null | head -60
```

Identify:
- The exact file + line number where the LLM model string is set or passed to the API call.
- Whether tenant tier is read at all in the writer's path.
- Whether `tier_gates.py` exposes a model-for-tier helper that the writer SHOULD be using but isn't.
- The expected model per tier per CP8 spec (Haiku for Free/Pro/Scale, Sonnet for Enterprise — confirm against `tier_gates.py` if present, else against memory).

### 5. Verify Stage 1's "Sonnet on thomas" finding

Was thomas tenant's tier actually Scale (which should be Haiku), or was it Enterprise (which is correctly Sonnet)?

```bash
cd /root/.openclaw/workspace/memory-product
psql "$DATABASE_URL" -c "
SELECT id, name, plan
FROM memory_service.tenants
WHERE id = '44c3080d-c196-407d-a606-4ea9f62ba0fc';
"
```

(That tenant_id is from the Stage 1 profile JSON.)

If `plan = 'enterprise'` then Sonnet was correct and the LLM-model finding evaporates. If `plan` is anything else (`scale`, `pro`, `free`), the regression is confirmed.

### 6. Write the diagnosis note

Create `docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md` with this structure:

```markdown
# CP-SYNTHESIS-PERF Stage 2.A — Diagnosis

**Date:** 2026-05-05
**Authored by:** CC (autonomous Stage 2.A run)
**Status:** Diagnosis only — no code changes. Locks Stage 2.B scope.

## Embedding bottleneck (72% of Stage 1 wall-clock)

### Where it happens
- File: `<exact path>`
- Function: `<name>`
- Line: `<N>`
- Code excerpt (5–10 lines):
  ```python
  <exact lines>
  ```

### Root causes confirmed
1. **Cold model load** — CONFIRMED / REFUTED / UNCLEAR.
   - Evidence: <where SentenceTransformer is instantiated; module-level vs function-local; logs showing HF cache HEAD requests>.
2. **Non-batched per-memory calls** — CONFIRMED / REFUTED / UNCLEAR.
   - Evidence: <loop vs single batched call; encode() invocation pattern>.
3. **Re-embedding memories that already have embeddings** — CONFIRMED / REFUTED / UNCLEAR.
   - Evidence: <whether code reads existing memories.embedding column; DB query result for cluster b28b7a99fd4791cb>.

### DB embedding population for validation cluster
- Cluster b28b7a99fd4791cb: <X>/21 members have embedding populated.

### Stage 2.B fix candidates (not applied)
1. Module-level SentenceTransformer instantiation OR app-startup preload via FastAPI lifespan.
2. Read existing `memory_service.memories.embedding` for cluster members; only embed those with NULL.
3. If any embeddings still need computation, batch them in one `model.encode([t1, t2, ...])` call.

## LLM model selection (24% of Stage 1 wall-clock; orthogonal cost-leak issue)

### Stage 1 observed
- Writer used `claude-sonnet-4-6` for tenant `44c3080d-c196-407d-a606-4ea9f62ba0fc` (thomas).

### Tenant plan
- `thomas` plan: `<from psql query>`.

### Where model is selected
- File: `<exact path>`
- Function: `<name>`
- Line: `<N>`
- Code excerpt (5–10 lines):
  ```python
  <exact lines>
  ```

### Tier-gating helper present?
- `src/synthesis/tier_gates.py` exists: YES / NO.
- Exposes a `model_for_tier(plan)` or equivalent: YES / NO.
- Writer currently calls it: YES / NO.

### Diagnosis
REGRESSION (Sonnet hardcoded on non-Enterprise tier) / INTENTIONAL (writer pinned to Sonnet for quality reasons documented elsewhere) / UNCLEAR.

### Stage 2.B fix candidate (not applied)
- <short sentence describing the routing fix>.

## Stage 2.B scope shape (recommendation)

Single chain combining both fixes:
- Embedding: <preload + batch + reuse> in `<file>:<lines>`.
- Model selection: route via tier_gates in `<file>:<line>`.
- Re-profile against cluster b28b7a99fd4791cb (21-member, user-justin).
- Target: total wall-clock < 5s for the validation cluster.

Estimated S2.B wall-clock: 45–60 min.

## What this diagnosis does NOT cover

- Whether Haiku output quality is sufficient for source-quote validation. If Stage 2.B routes Scale-tier to Haiku and validation rejection rate spikes, that's a Stage 2.B follow-up, not a 2.A blocker.
- Async embedding (off the critical path entirely). Out of scope until preload+batch+reuse are exhausted.
- Embedding storage strategy changes (e.g., precompute embeddings at write time so synthesis never embeds). Future architectural consideration; not in current scope.
```

CC fills in every `<placeholder>` with concrete data from steps 2–5.

### 7. Commit + push

```bash
cd /root/.openclaw/workspace/memory-product
git add docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md
git status                              # only that one file
git diff --cached --stat
git commit -m "CP-SYNTHESIS-PERF S2.A: diagnosis note (no code changes)"
git push origin cp-synthesis-perf-s1
```

### 8. End-of-run signal

```bash
afplay /System/Library/Sounds/Glass.aiff
```

---

## Halt note format

If halting, write `/root/.openclaw/workspace/memory-product/CP-SYNTHESIS-PERF-S2A-BLOCKED.md`. Do NOT stage uncommitted work.

---

## Definition of done

1. `docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md` exists with all placeholders filled.
2. Each "Root cause" line has CONFIRMED/REFUTED/UNCLEAR + concrete evidence (file:line or psql output).
3. Single commit on `cp-synthesis-perf-s1` pushed.
4. ZERO code changes outside `docs/profile/`.
5. No `CP-SYNTHESIS-PERF-S2A-BLOCKED.md`.

---

## Standing rules carry forward verbatim
