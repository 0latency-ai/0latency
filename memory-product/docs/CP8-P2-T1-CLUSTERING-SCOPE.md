# CP8 Phase 2 Task 1 — Autonomous Scope: Clustering Engine

**Task:** Build `synthesis/clustering.py` — find clusters of related atoms suitable for synthesis.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** `410d91a` (master, post state-of-the-world doc).
**Estimated wall-clock:** 15–30 min for CC.
**Chain position:** Chain A, task 1 of 3 (T1 → T4 → T8).

---

## Goal

One sentence: Given an `(agent_id, role_scope, recency_window)` triple, return a list of clusters where each cluster is a list of memory IDs that are semantically related, ≥48hr old, and not pinned.

This is read-only foundation work. No writes to `memory_service.memories`. No LLM calls. Pure Python + SQL clustering over existing atom embeddings.

---

## In scope

**Files to create:**
- `src/synthesis/clustering.py` — NEW
- `tests/synthesis/test_clustering.py` — NEW

**Files to read (do not modify):**
- `src/synthesis/policy.py` — for policy DSL shape (clustering may consume `consensus_requirements` later, not in this task)
- `src/storage_multitenant.py` — to find `_db_execute_rows` and tenant-scoped query helpers
- `src/tier_gates.py` — to confirm pattern for reading per-tenant config
- `migrations/` — to confirm `memories.embedding` column type and dimensions (768 expected)

**Database:** Read-only. Queries `memory_service.memories` only.

---

## Out of scope (DO NOT TOUCH)

- Any migration file (`migrations/*.sql`)
- `synthesis/writer.py` (T2 — separate scope)
- `synthesis/jobs.py` (T4 — separate scope)
- `extract_memories()` or any extraction logic
- `recall.py` or any recall-path file
- LLM calls of any kind (clustering is mechanical similarity, not synthesis)
- Any change to `memories.metadata` jsonb shape
- `synthesis_audit_events` writes (T2's responsibility)
- `synthesis_rate_limits` reads or writes (T2's responsibility)

---

## Function contract

```python
def find_clusters(
    tenant_id: str,
    agent_id: str,
    role_scope: str = "public",
    recency_window_hours_min: int = 48,
    recency_window_hours_max: int = 720,  # 30 days default upper bound
    similarity_threshold: float = 0.78,
    min_cluster_size: int = 3,
    max_cluster_size: int = 25,
) -> list[Cluster]:
    """
    Find clusters of related atom memories suitable for synthesis.

    Returns list of Cluster objects, each with:
      - memory_ids: list[uuid.UUID]
      - centroid_embedding: list[float]  # for downstream use
      - cluster_signature: str           # short human-readable summary, top 3 headlines
    """
```

Where `Cluster` is a dataclass defined in the same file:

```python
@dataclass
class Cluster:
    memory_ids: list[uuid.UUID]
    centroid_embedding: list[float]
    cluster_signature: str  # e.g. "DB schema (3 atoms), CP8 Phase 2 (5 atoms), ..."
```

**Algorithm — exact spec:**

1. Query candidate atoms:
   ```sql
   SELECT id, embedding, headline, full_content, metadata, created_at
   FROM memory_service.memories
   WHERE tenant_id = %s
     AND agent_id = %s
     AND memory_type IN ('fact', 'preference', 'instruction', 'event', 'correction', 'identity')
     AND is_pinned IS NOT TRUE
     AND created_at < NOW() - INTERVAL '%s hours'
     AND created_at > NOW() - INTERVAL '%s hours'
     AND (redaction_state IS NULL OR redaction_state = 'active')
     AND embedding IS NOT NULL
   ORDER BY created_at DESC
   LIMIT 5000;
   ```
   `is_pinned IS NOT TRUE` (not `= FALSE`) handles the legacy NULL case.
   `redaction_state IS NULL OR = 'active'` excludes `redacted`, `pending_resynthesis`, `modified` rows.

2. Use `pgvector` cosine distance for the similarity calculation. **Do not pull all 5000 embeddings into Python and run sklearn.** Instead, run an SQL clustering pass:

   ```sql
   -- For each candidate row, find its k=8 nearest neighbors above threshold
   SELECT a.id AS source_id, b.id AS neighbor_id,
          1 - (a.embedding <=> b.embedding) AS similarity
   FROM memory_service.memories a
   JOIN memory_service.memories b
     ON a.tenant_id = b.tenant_id
     AND a.agent_id = b.agent_id
     AND a.id != b.id
   WHERE a.id = ANY(%s::uuid[])  -- candidate IDs from step 1
     AND b.id = ANY(%s::uuid[])
     AND 1 - (a.embedding <=> b.embedding) >= %s  -- threshold
   ORDER BY a.id, similarity DESC;
   ```

3. Build neighbor graph in Python from the SQL result. Use union-find (DSU) to merge connected components above threshold.

4. **Soft clustering caveat:** For Phase 2, hard-cluster first (each atom in exactly one cluster — its strongest connected component). Soft clustering (atom in multiple clusters) is in the schema (Decision 1) but defer the algorithmic work to a Phase 2.5 follow-up. Document this caveat in the module docstring.

5. Filter clusters to `min_cluster_size <= len(memory_ids) <= max_cluster_size`. Discard outliers.

6. For each surviving cluster, compute centroid embedding (mean of member embeddings, normalized). Compute `cluster_signature` as the top-3 most-recent headlines joined with `; `.

7. Return list, sorted by cluster size descending.

**Edge cases:**
- Zero candidate atoms → return `[]`. Do not raise.
- One candidate atom → return `[]` (below `min_cluster_size`).
- All candidates similar (one giant cluster > `max_cluster_size`) → split by k-means with k = `ceil(N / max_cluster_size)` over the centroids. Use scipy if available; if not, halt — out of scope to add deps.
- Embedding dimension mismatch (some 768, some 384 from CP6 mixed era) → halt and write to BLOCKED note. Schema audit needed.

---

## Steps

### Step 1 — Verify candidate query returns rows on prod

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
psql "$DATABASE_URL" -c "
SELECT COUNT(*) AS candidate_count
FROM memory_service.memories
WHERE tenant_id = '44c3080d-c196-407d-a606-4ea9f62ba0fc'
  AND agent_id = 'user-justin'
  AND memory_type IN ('fact', 'preference', 'instruction', 'event', 'correction', 'identity')
  AND is_pinned IS NOT TRUE
  AND created_at < NOW() - INTERVAL '48 hours'
  AND created_at > NOW() - INTERVAL '720 hours'
  AND (redaction_state IS NULL OR redaction_state = 'active')
  AND embedding IS NOT NULL;
"
```

**Gate G2:** result must be ≥ 50 (justin's namespace has 4,197 memories per memory; >=50 atoms 48hr–30d old should be trivially true). If less than 50 → halt, fixture/state has drifted.

### Step 2 — Verify pgvector cosine distance works on this DB

```bash
psql "$DATABASE_URL" -c "
SELECT 1 - (a.embedding <=> b.embedding) AS sim
FROM memory_service.memories a, memory_service.memories b
WHERE a.tenant_id = '44c3080d-c196-407d-a606-4ea9f62ba0fc'
  AND a.agent_id = 'user-justin'
  AND b.tenant_id = a.tenant_id
  AND b.agent_id = a.agent_id
  AND a.id != b.id
  AND a.embedding IS NOT NULL
  AND b.embedding IS NOT NULL
LIMIT 1;
"
```

**Gate G2:** returns a float. If error mentions `extensions.vector` or any cast issue, **halt** — pgvector schema bug from 2026-04-29 has regressed.

### Step 3 — Implement `src/synthesis/clustering.py`

Per the function contract above. Use `_db_execute_rows` from `storage_multitenant.py` for native tuple results. Module docstring must document:
- Algorithm choice (pgvector cosine + DSU union-find)
- Soft clustering caveat (deferred)
- Embedding dimension assumption (768)
- Why pinned atoms are excluded
- Why `redaction_state` filter is applied here, not at recall

### Step 4 — Implement `tests/synthesis/test_clustering.py`

Six tests:
1. `test_returns_empty_when_no_candidates` — fresh tenant with no atoms
2. `test_clusters_meet_min_size` — verifies no returned cluster has fewer than `min_cluster_size`
3. `test_clusters_respect_max_size` — verifies splitting kicks in for over-size clusters
4. `test_pinned_atoms_excluded` — write 1 pinned atom + 4 unpinned similar; pinned atom must not appear in any cluster
5. `test_recency_window_filter` — atoms <48hr old excluded
6. `test_redacted_atoms_excluded` — atoms with `redaction_state='redacted'` not in clusters

Mark all `@pytest.mark.integration`. Use real DB. Cleanup fixtures via tenant-scoped delete in teardown.

### Step 5 — Test gate (G3)

```bash
cd /root/.openclaw/workspace/memory-product
pytest tests/synthesis/test_clustering.py -v --tb=short 2>&1 | tee /tmp/t1-test-output.txt
grep -q "passed" /tmp/t1-test-output.txt && ! grep -q "failed" /tmp/t1-test-output.txt && echo 'T1 GATE PASS'
```

**HALT** on any test failure.

### Step 6 — Smoke test on real prod data

```bash
python3 -c "
from src.synthesis.clustering import find_clusters
import os
clusters = find_clusters(
    tenant_id='44c3080d-c196-407d-a606-4ea9f62ba0fc',
    agent_id='user-justin',
    role_scope='public',
)
print(f'Found {len(clusters)} clusters')
for c in clusters[:5]:
    print(f'  size={len(c.memory_ids)} signature={c.cluster_signature[:80]}')
"
```

**Gate G2:** prints `Found N clusters` where N >= 1. If N=0 on justin's namespace, the threshold (0.78) is too aggressive — halt and dump tuning data into BLOCKED note. Do NOT lower the threshold autonomously.

### Step 7 — Commit

```bash
git add src/synthesis/clustering.py tests/synthesis/test_clustering.py
git status  # GATE: only those 2 files staged
git diff --cached --stat
```

Commit message (write to `/tmp/cp8-p2-t1-commit-msg.txt`):

```
CP8 Phase 2 T1: synthesis/clustering.py engine

Returns clusters of semantically-related atoms suitable for synthesis.
Read-only foundation; no LLM, no DB writes, no external deps beyond pgvector.

Algorithm:
- pgvector cosine distance for pairwise similarity
- Union-find (DSU) for connected-component merging
- Hard clustering only (soft clustering deferred to Phase 2.5)
- Filters: pinned atoms excluded, redacted/modified excluded,
  recency window 48hr–30d, embedding required

Function contract:
  find_clusters(tenant_id, agent_id, role_scope, recency_window_hours_min,
                recency_window_hours_max, similarity_threshold,
                min_cluster_size, max_cluster_size) -> list[Cluster]

Verification receipts:
[CC fills in: candidate count from step 1, smoke-test cluster count from step 6,
 test pass output from step 5]

Files: src/synthesis/clustering.py (NEW, +N lines, find_clusters + Cluster dataclass + DSU helpers),
       tests/synthesis/test_clustering.py (NEW, 6 integration tests)
```

```bash
git commit -F /tmp/cp8-p2-t1-commit-msg.txt
git log -1 --stat
git push origin master
```

**Final gate:** `git push` exit code 0.

---

## Halt conditions (specific to this task)

In addition to the protocol's standard halts:

1. **Embedding dimension mismatch** in candidate query results. Halt, write the dimension distribution into BLOCKED note.
2. **Smoke test returns 0 clusters** on justin's namespace. Halt — threshold tuning is a human decision.
3. **`scipy` not installed** AND a giant-cluster-split is needed. Halt — adding deps is human decision.
4. **`pgvector` cast errors** mentioning `extensions.vector`. Halt — 2026-04-29 fix regressed.
5. **Test fixture creates atoms but they don't appear in `find_clusters` output** despite passing all filter conditions. Means a query bug. Halt and dump query + fixture state.

---

## Halt note format

If halting, write `/root/.openclaw/workspace/memory-product/CP8-P2-T1-BLOCKED.md` per protocol. Include:
- Step number halted at
- Specific halt condition triggered
- Last successful gate output
- Repo state (`git status`)
- Best-guess next move

Do NOT stage or commit any work-in-progress on halt.

---

## Definition of done

All of:

1. `src/synthesis/clustering.py` exists with `find_clusters()` and `Cluster` dataclass.
2. All 6 tests in `tests/synthesis/test_clustering.py` pass.
3. Smoke test on prod data returns ≥1 cluster.
4. Single commit on master pushed to remote.
5. Commit message contains real verification receipts (candidate count, cluster count, test output).
6. No `CP8-P2-T1-BLOCKED.md` exists.
7. `journalctl -u memory-api --since "<run start>"` shows no new ERRORs.

**No deploy needed** — this module is not yet imported by any running service. T2 will import it.
