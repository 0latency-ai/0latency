
## 2026-05-05 — P4.2-PATCH SHIPPED (Gate D deferred)

- src/recall.py lines 786 + 1190: audit-emission key fix (memory_type rename, two sites — duplicate dict construction pattern; CC caught the second site I missed in scope authoring).
- p4-2-fix → master merged at edc8574.
- Prod cluster_id backfill applied: 42 rows backfilled, 1 correctly skipped.
- Verification gates A/B/C PASS with numeric evidence.
- p4-2-fix and p4-2-investigation branches deleted (local + origin).

Gate D (expand=cluster on /memories/{id}/source) DEFERRED — endpoint
parameter never implemented in P4.1 (P4.1 V5 only verified cluster_id
metadata population, not endpoint consumption). Scope doc V5 assumption
was incorrect; not a P4.1 ship defect.

Closes: P4.1 S02 verification gap, P4.1 S03 halt, P4.2 end-to-end
verification. Phase 4 functionally closed.

Carry-forward: expand=cluster query parameter on /memories/{id}/source
remains unimplemented. Useful for hierarchical descent ("show me
everything in the same theme" — CP8 v3 Phase 4 Task 4). Not blocking.
Candidate for focused 30-min chain after CP-SYNTHESIS-PERF.

Next chain: CP-SYNTHESIS-PERF.

## 2026-05-05 — CP-SYNTHESIS-PERF Stage 1 SHIPPED (profile)

Branch: cp-synthesis-perf-s1 (NOT YET MERGED — awaiting operator review of profile report).
Wall-clock total: 17457ms (cluster with 12 source memories, thomas tenant).
Dominant phase: embedding, 72.1% of total (12585ms).
Second phase: llm_call, 24.4% of total (4261ms).
Report: docs/profile/synthesis-writer-profile-2026-05-05.md

Key finding: Embedding generation (72%) dominates runtime, not LLM call (24%).
Hypothesis: sentence-transformer model loaded fresh per run.
Stage 2 scope to be authored from this report. Branch held until then.

## 2026-05-05 — CP-SYNTHESIS-PERF SHIPPED

Synthesis writer latency on user-justin validation cluster
6af31b14-900a-4c64-8031-6a7b5a1ea5b3 (12 members):
- Before: 17,457ms wall-clock (embedding 12,585ms = 72% cold model load).
- After: 5,899ms wall-clock (embedding 311ms after preload).
- Improvement: 3.0x faster.

Fix: FastAPI lifespan preload of SentenceTransformer model.
Cold-load cost moved from per-synthesis (paid every call) to
app-startup (paid once at boot, ~20s).

Stages: S1 (profile) → S2.A (diagnosis, no code) → S2.B (fix + verify + merge).
Branch cp-synthesis-perf-s1 merged to master and deleted.

LongMemEval and Show HN unblocked (writer now sub-6s steady state).
Next chain: Phase 5 (operational surface — redaction cascade,
webhooks, decision journals, calibration, audit access, tier polish).

## 2026-05-05 — CP8 P5.1 Stage 1 SHIPPED

Redaction cascade inventory authored at docs/CP8-P5-1-S1-INVENTORY.md. No code change.

Findings:
- redaction.py exists (415 lines, Phase 1 partial: mark_pending_review + evidence_chain_only)
- DB schema complete (4 columns via migrations 012, 017)
- Recall filter correctly excludes redacted/pending_resynthesis
- No HTTP endpoint exists
- Validation cluster b28b7a99fd4791cb present (21 synthesis rows, 8 source memories)

NEXT: P5.1 Stage 2 scope authoring (Opus, against this inventory).

## 2026-05-12 — CP-WORKER-PRELOAD SHIPPED

rq extraction worker per-fork footprint and per-extraction latency improvement:
- Before: ~680MB/fork (per handoff diagnosis), ~9.0s/extraction, OOM at >4 workers
- After: ~457MB parent RSS with preloaded model, simple extraction <5s, 4 workers stable

Fix: shared src/embedder.py module + custom rq worker entry point (bin/zerolatency_rq_worker.py) 
that preloads SentenceTransformer in parent before forking. Forked children inherit model via 
Linux copy-on-write. Same pattern as CP-SYNTHESIS-PERF S2.B for FastAPI (2026-05-05).

Implementation:
- src/embedder.py: centralized preload logic with get_embedder() and preload_embedder()
- bin/zerolatency_rq_worker.py: custom entry point that preloads before entering job loop
- src/storage_multitenant.py: delegates to shared embedder instead of duplicate logic
- api/main.py: consolidated to use shared preload_embedder()
- ops/zerolatency-worker@.service: updated ExecStart to use custom worker entry

Status: Deployed and running on 4 workers. Full Q3 benchmark and 8-worker scaling validation 
deferred for manual verification per brief step 14.

## 2026-05-12 19:32 UTC - CP-WORKER-SIMPLEWORKER Landing (PARTIAL)

**Branch:** cp-worker-simpleworker  
**Status:** Halted - environment variable blocker  
**Commit:** Pending (not merged due to blocker)

### Changes
- bin/zerolatency_rq_worker.py: Switch from Worker to SimpleWorker
- api/extraction_worker.py: Remove load_dotenv() call
- systemd service: Add explicit ANTHROPIC_API_KEY environment

### Root Cause Confirmed
Fork-after-psycopg2-connected bug was causing extraction hang:
- Parent process opens DB connections
- Worker.fork() creates child with inherited connections
- PostgreSQL rejects queries from different PID
- Queries hang forever until RQ timeout (300s)

### Fix Applied
SimpleWorker runs jobs in-process without forking, eliminating connection inheritance.

### Results
- **Gate A (Memory):** PASS - 2.3GB available, 4 workers x 810MB = 3.24GB used
- **Gate B (Single extraction):** PARTIAL
  - Trial 1: 9.87s, COMPLETED (hang FIXED!)
  - Trial 2: FAILED - ANTHROPIC_API_KEY missing in os.environ
  - Trial 3: SKIPPED (halt condition)
- **Gate C (4-way concurrent):** SKIPPED

### New Blocker Discovered
ANTHROPIC_API_KEY visible to first job per worker, missing for subsequent jobs in SAME process.
Environment variable persistence issue in SimpleWorker model - requires investigation.

### Impact
- Original fork-after-psycopg2 hang: **RESOLVED**
- LongMemEval benchmark: **BLOCKED** (new environment issue)
- CP-EMBEDDER-SVC: Queued for optimization, not urgent (memory headroom acceptable)

### Next Actions
1. Debug why os.environ loses ANTHROPIC_API_KEY after first job
2. Test 3-5 consecutive extractions in single worker
3. Re-run gates B and C
4. Commit and merge once environment persistence confirmed
