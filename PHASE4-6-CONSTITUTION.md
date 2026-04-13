# PHASE 4–6 CONSTITUTION
## Logic Blueprint for Junior Agent Execution
### Version: 1.0 — April 5, 2026
### Authority: Principal Architect (Opus)
### Target executor: Sonnet/Haiku via Claude Code

---

## §0 — PREAMBLE: ZERO FALSE-POSITIVE MERGES

This document is a **hard constraint set**, not guidance. Every rule is a MUST.
If any condition says HALT, the agent halts and logs why. No interpretation.
No "probably fine." No rounding. No skipping steps because they seem redundant.

**Prime directive:** It is always better to keep two duplicate memories than to merge two distinct ones. False negatives (missed merges) are recoverable. False positives (bad merges) corrupt the knowledge graph.

---

## §1 — THE THRESHOLD ENGINE

### §1.1 — Go/No-Go Gate (P90 Rule)

Before ANY merge code executes — before even reading candidates — the agent MUST run this query and evaluate the result:

```sql
SELECT
  consolidation_type,
  COUNT(*) AS n,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY classification_confidence) AS p90
FROM consolidation_queue
WHERE status = 'classified'
  AND consolidation_type = 'DUPLICATE'
GROUP BY consolidation_type;
```

**Decision table (no interpolation, no judgment):**

| P90 result | Decision | Agent action |
|---|---|---|
| `NULL` or `n < 10` | **NO-GO** | Log `GATE_BLOCKED: insufficient_data (n={n})`. HALT. Do nothing. |
| `p90 < 0.85` | **NO-GO** | Log `GATE_BLOCKED: p90={p90}`. Execute §1.2 (Prompt Tuning). HALT. Do not merge. |
| `0.85 ≤ p90 < 0.90` | **CAUTION-GO** | Set `merge_threshold = p90`. Set `max_merges_per_run = 5`. Log `GATE_CAUTION: p90={p90}, threshold={p90}`. Proceed to §2. |
| `p90 ≥ 0.90` | **GO** | Set `merge_threshold = p90`. Set `max_merges_per_run = 10`. Log `GATE_GO: p90={p90}, threshold={p90}`. Proceed to §2. |

**Current telemetry (April 5, 2026):** P90 = 0.90, n = 12 duplicates → **GO**. `merge_threshold = 0.90`. `max_merges_per_run = 10`.

### §1.2 — Prompt Tuning Protocol (P90 < 0.85)

If the P90 gate returns NO-GO, the agent MUST NOT attempt to "fix" the classifier prompt autonomously. Instead, execute this exact sequence:

1. **Diagnose.** Run:
```sql
SELECT
  classification_confidence,
  similarity_score,
  classification_reasoning,
  memory_id_a,
  memory_id_b
FROM consolidation_queue
WHERE consolidation_type = 'DUPLICATE'
  AND classification_confidence < 0.85
ORDER BY classification_confidence ASC
LIMIT 10;
```

2. **Fetch the memory text for each low-confidence pair.** For each row returned:
```sql
SELECT id, headline, content, memory_type FROM memories WHERE id IN ($memory_id_a, $memory_id_b);
```

3. **Write a diagnostic file.** Output to `/root/logs/prompt-tuning-diagnostic-{date}.md`:
   - The 10 lowest-confidence DUPLICATE pairs with full memory text
   - The current P90 value
   - The current classifier prompt (read from `src/consolidation/classifier.py`, the `CLASSIFICATION_PROMPT` variable)

4. **Log and HALT:**
```
PROMPT_TUNING_REQUIRED: p90={p90}, low_conf_pairs=10 dumped to /root/logs/prompt-tuning-diagnostic-{date}.md
ACTION_REQUIRED: Human or Opus must review diagnostic and revise CLASSIFICATION_PROMPT before Phase 4 can proceed.
```

5. **Do not modify the classifier prompt.** Do not retry. Do not lower thresholds. HALT.

### §1.3 — The Identity Lock (ABSOLUTE)

Before evaluating ANY pair for merge, check:

```sql
SELECT memory_type FROM memories WHERE id = $memory_id_a;
SELECT memory_type FROM memories WHERE id = $memory_id_b;
```

**If EITHER memory has `memory_type = 'identity'`:**
- Set queue status to `rejected`
- Set `classification_reasoning` to `IDENTITY_LOCK: memory_type=identity is immutable`
- **Skip. No exceptions. No confidence override. No human override path.**

This is not a threshold check. It is a categorical exclusion.

---

## §2 — THE ARCHIVAL-BEFORE-ACTION SAFETY LOOP

This is the core invariant of Phase 4. Every merge operation is a transaction with a strict ordering. Violation of ordering = data loss.

### §2.0 — Pre-Flight Safeguards

Before processing ANY pair, run:

```python
# 1. Kill switch
if os.environ.get('CONSOLIDATION_ENABLED', 'true') != 'true':
    log("SAFEGUARD: kill_switch=active"); return 0

# 2. Daily merge cap
today_count = SELECT COUNT(*) FROM consolidation_queue
    WHERE status = 'processed' AND processed_at::date = CURRENT_DATE;
if today_count >= 50:
    log(f"SAFEGUARD: daily_cap={today_count}/50"); return 0

# 3. Anomaly detector — if >20% of all memories flagged today, HALT
total = SELECT COUNT(*) FROM memories;
flagged_today = SELECT COUNT(*) FROM consolidation_queue
    WHERE created_at::date = CURRENT_DATE;
if total > 0 and (flagged_today / total) > 0.20:
    log(f"SAFEGUARD: anomaly={flagged_today}/{total}"); return 0
```

All three must pass. If any fails, log reason and return 0 merges.

### §2.1 — Candidate Selection

```sql
SELECT * FROM consolidation_queue
WHERE status = 'classified'
  AND consolidation_type IN ('DUPLICATE', 'UPDATE')
  AND classification_confidence >= {merge_threshold}  -- from §1.1
ORDER BY classification_confidence DESC
LIMIT {max_merges_per_run};  -- from §1.1
```

**Exclusions applied post-query (in code, not SQL):**
- Skip if EITHER `memory_id_a` or `memory_id_b` no longer exists in `memories` table
- Skip if EITHER memory's `created_at` is within last 10 minutes (recency guard)
- Skip if EITHER memory has `memory_type = 'identity'` (§1.3)

### §2.2 — The Archive Transaction (CRITICAL PATH)

For each candidate pair, the following steps execute **in this exact order**. If any step fails, the entire pair is skipped and marked `status = 'rejected'` with the error.

```
STEP 1: READ    — Fetch full row for mem_a and mem_b from `memories`
STEP 2: ARCHIVE — INSERT both into `memory_archive` (see below)
STEP 3: VERIFY  — SELECT COUNT(*) FROM memory_archive WHERE original_memory_id IN (mem_a.id, mem_b.id) — must equal 2
STEP 4: ACT     — Execute the merge (type-dependent, see §2.3)
STEP 5: MARK    — UPDATE consolidation_queue SET status = 'processed'
```

**STEP 3 is non-negotiable.** If the count ≠ 2, the agent MUST NOT proceed to STEP 4. Log `ARCHIVE_VERIFY_FAILED: expected=2, got={count}, pair={pair_id}` and skip.

**Archive INSERT (STEP 2) — exact columns:**

```sql
INSERT INTO memory_archive
  (original_memory_id, tenant_id, agent_id, headline, content,
   memory_type, importance, embedding, original_created_at, archived_reason)
VALUES
  ($id, $tenant_id, $agent_id, $headline, $content,
   $memory_type, $importance, $embedding, $created_at, $reason);
```

`$reason` values: `'consolidated'` for DUPLICATE merges, `'superseded'` for UPDATE losers.

### §2.3 — Merge Execution (Type-Dependent)

**TYPE = DUPLICATE:**

1. Call LLM with merge prompt (see §2.4 for exact prompt)
2. Parse JSON response — if parse fails, skip pair, log error
3. UPDATE `memories` SET headline, content, importance on `mem_a.id`:
   - `importance` = `MAX(mem_a.importance, mem_b.importance)`
   - `headline` and `content` from LLM merge result
4. DELETE from `memories` WHERE `id = mem_b.id`
5. UPDATE `memory_archive` SET `consolidated_into = mem_a.id` WHERE `original_memory_id = mem_b.id`

**TYPE = UPDATE:**

1. Determine newer: `newer = mem_b if mem_b.created_at > mem_a.created_at else mem_a`
2. `older = the other one`
3. DELETE from `memories` WHERE `id = older.id`
4. UPDATE `memory_archive` SET `archived_reason = 'superseded'`, `consolidated_into = newer.id` WHERE `original_memory_id = older.id`

**TYPE = CONTRADICTION:** Never auto-processed. If a CONTRADICTION row somehow enters the candidate set (it shouldn't per §2.1 SQL), reject it immediately.

### §2.4 — LLM Merge Prompt (Exact Text)

```
Merge these two memories into one concise memory.
Keep all unique facts from both. Use the higher importance score ({max_importance}).
Use the earlier creation date.

Memory A: {headline_a} — {content_a}
Memory B: {headline_b} — {content_b}

Respond with JSON only:
{"headline": "merged headline", "content": "merged content"}
```

**Parse rule:** Strip markdown fences if present. `json.loads()` the result. If it fails, skip the pair. Do not retry the LLM call.

### §2.5 — Logging (Every Merge)

Append to `/root/logs/merger-{YYYY-MM-DD}.log`:

```
{ISO_TIMESTAMP} | MERGED | type={DUPLICATE|UPDATE} | conf={confidence} | sim={similarity} | a={memory_id_a} | b={memory_id_b} | archived=VERIFIED
```

On error:

```
{ISO_TIMESTAMP} | ERROR | pair={pair_id} | step={1-5} | error={message}
```

### §2.6 — Post-Run Integrity Check

After all pairs in a run are processed, execute:

```sql
-- Every processed pair must have exactly 2 archive entries
SELECT cq.id AS pair_id,
  (SELECT COUNT(*) FROM memory_archive ma
   WHERE ma.original_memory_id IN (cq.memory_id_a, cq.memory_id_b)) AS archive_count
FROM consolidation_queue cq
WHERE cq.status = 'processed'
  AND cq.processed_at::date = CURRENT_DATE
  AND (SELECT COUNT(*) FROM memory_archive ma
       WHERE ma.original_memory_id IN (cq.memory_id_a, cq.memory_id_b)) != 2;
```

If this returns ANY rows, log `INTEGRITY_VIOLATION: pairs with missing archives` and the pair IDs. Set `CONSOLIDATION_ENABLED=false` (write to a flag file or env). This is a circuit breaker.

---

## §3 — RESTORE FUNCTION

The agent MUST also deploy this restore capability:

```
INPUT:  archive_id (UUID from memory_archive)
STEPS:
  1. SELECT * FROM memory_archive WHERE id = $archive_id
  2. If not found → error
  3. INSERT INTO memories (id, tenant_id, agent_id, headline, content,
       memory_type, importance, embedding, created_at)
     VALUES (original_memory_id, tenant_id, agent_id, headline, content,
       memory_type, importance, embedding, original_created_at)
  4. DELETE FROM memory_archive WHERE id = $archive_id
  5. Log: RESTORED | archive_id={archive_id} | memory_id={original_memory_id}
```

---

## §4 — PHASE 5: CROSS-AGENT PROPAGATION

### §4.1 — Trigger Condition

After every successful merge in §2.3, call propagation detection. Not before. Not in a separate cron. Inline, after STEP 5.

### §4.2 — Propagation Detection Logic

```sql
SELECT id, agent_id, headline, content,
       1 - (embedding <=> $merged_embedding::vector) AS similarity
FROM memories
WHERE tenant_id = $tenant_id
  AND agent_id != $source_agent_id
  AND 1 - (embedding <=> $merged_embedding::vector) > 0.80
ORDER BY embedding <=> $merged_embedding::vector
LIMIT 10;
```

`$merged_embedding` = the embedding of the surviving memory (mem_a for DUPLICATE, newer for UPDATE).

### §4.3 — Propagation Queuing (NOT execution)

For each result from §4.2:

```sql
INSERT INTO consolidation_queue
  (tenant_id, agent_id, memory_id_a, memory_id_b, similarity_score,
   consolidation_type, status, classification_reasoning)
VALUES
  ($tenant_id, $target_agent_id, $target_memory_id, $surviving_memory_id,
   $similarity, 'UPDATE', 'classified',
   'Cross-agent propagation from ' || $source_agent_id);
```

**These entries go through the normal merge pipeline on the NEXT run.** They are not auto-executed. They still must pass the threshold gate, the identity lock, and the archive loop.

### §4.4 — Propagation Does NOT Touch Identity

Same §1.3 lock applies. If the target memory is `memory_type = 'identity'`, do not queue it. Skip silently.

---

## §5 — PHASE 6: WEEKLY REPORT

### §5.1 — Report Query (Single Query)

```sql
SELECT
  (SELECT COUNT(*) FROM memories) AS total_memories,
  (SELECT COUNT(*) FROM memories WHERE created_at > NOW() - INTERVAL '7 days') AS new_this_week,
  (SELECT COUNT(*) FROM consolidation_queue WHERE status='processed' AND processed_at > NOW() - INTERVAL '7 days') AS merged_this_week,
  (SELECT COUNT(*) FROM consolidation_queue WHERE consolidation_type='CONTRADICTION' AND created_at > NOW() - INTERVAL '7 days') AS contradictions_this_week,
  (SELECT COUNT(*) FROM recall_telemetry WHERE created_at > NOW() - INTERVAL '7 days') AS recalls_this_week,
  (SELECT AVG(memories_returned) FROM recall_telemetry WHERE created_at > NOW() - INTERVAL '7 days') AS avg_recall_results,
  (SELECT COUNT(*) FROM recall_feedback WHERE feedback_type='used' AND created_at > NOW() - INTERVAL '7 days') AS memories_used,
  (SELECT COUNT(*) FROM recall_feedback WHERE feedback_type='ignored' AND created_at > NOW() - INTERVAL '7 days') AS memories_ignored,
  (SELECT COUNT(*) FROM recall_feedback WHERE feedback_type='miss' AND created_at > NOW() - INTERVAL '7 days') AS recall_misses;
```

### §5.2 — Quality Score Formula (Deterministic)

```
used = memories_used OR 0
ignored = memories_ignored OR 0
usage_rate = used / MAX(used + ignored, 1)

quality_score = INT(
    usage_rate * 40
  + MIN(merged_this_week / MAX(total_memories * 0.01, 1), 1) * 20
  + MIN(recalls_this_week / 100, 1) * 20
  + (1 - MIN(contradictions_this_week / 10, 1)) * 20
)
```

Score range: 0–100. No rounding tricks. INT truncates.

### §5.3 — Report Output

Write to `/root/logs/weekly-report-{YYYY-MM-DD}.txt` AND insert into `memories` table as:
- `agent_id = 'system'`
- `memory_type = 'report'`
- `importance = 0.7`
- `headline = 'Weekly Report {date} — Score {score}/100'`

### §5.4 — Cron

```
0 6 * * 1  cd /var/www/0latency && /usr/bin/python3 -m src.consolidation.weekly_report >> /root/logs/weekly-report-cron.log 2>&1
```

---

## §6 — COLD-START RULES

Current feedback volume: 9 records. Target for full weighting: 50.

Until `SELECT COUNT(*) FROM recall_feedback` ≥ 50:

1. **Classification confidence is the primary merge signal.** Feedback weight = 0.
2. **Do not run the importance_adjuster.** The `HAVING COUNT(*) >= 3` clause in the adjuster query provides natural protection, but to be explicit: if total feedback < 50, skip the adjuster cron entirely.
3. **Do not lower merge thresholds** to "get things moving." The P90 gate is the floor.
4. **Weighted transition at 50+:** Once count ≥ 50, classification weight = 80%, feedback weight = 20%. This is informational for the future Phase 7 design — the junior agent does NOT implement weighted scoring. It uses the P90 gate only.

---

## §7 — CRON SCHEDULE SUMMARY

| Job | Schedule | Script | Log |
|---|---|---|---|
| Classifier | `*/30 * * * *` | `src.consolidation.classifier` | `/root/logs/classifier-cron.log` |
| Merger | `0 * * * *` (hourly) | `src.consolidation.merger` | `/root/logs/merger-cron.log` |
| Importance adjuster | `0 4 * * *` (daily, **disabled until feedback ≥ 50**) | `src.consolidation.importance_adjuster` | `/root/logs/importance-cron.log` |
| Weekly report | `0 6 * * 1` (Monday) | `src.consolidation.weekly_report` | `/root/logs/weekly-report-cron.log` |

---

## §8 — WHAT THE AGENT MUST NOT DO

1. **Must not modify the classifier prompt.** (§1.2)
2. **Must not lower any threshold below what P90 computes.** (§1.1)
3. **Must not merge CONTRADICTION type pairs.** (§2.3)
4. **Must not merge identity memories.** (§1.3)
5. **Must not skip the archive verification step.** (§2.2, STEP 3)
6. **Must not execute propagation merges inline** — they queue for next run. (§4.3)
7. **Must not run importance adjuster if feedback count < 50.** (§6)
8. **Must not retry failed LLM calls.** One shot per pair per run. (§2.4)
9. **Must not process more than `max_merges_per_run` in a single execution.** (§1.1)
10. **Must not declare completion without running the §2.6 integrity check.**

---

## §9 — VERIFICATION CHECKLIST (Post-Deployment)

The agent must run ALL of these and ALL must pass before reporting "Phase 4 complete":

```bash
# 1. Archive table has entries
psql -c "SELECT COUNT(*) FROM memory_archive" # must be > 0

# 2. Merger log exists and shows MERGED lines
cat /root/logs/merger-$(date +%Y-%m-%d).log | grep MERGED

# 3. Restore works — pick one archived memory and round-trip it
ARCHIVE_ID=$(psql -t -c "SELECT id FROM memory_archive LIMIT 1" | tr -d ' ')
# restore it, verify it exists in memories, then re-archive it

# 4. Kill switch works
CONSOLIDATION_ENABLED=false python3 -m src.consolidation.merger
# Log must show "kill_switch=active" and 0 merges

# 5. Integrity check returns 0 rows
psql -c "SELECT cq.id FROM consolidation_queue cq WHERE cq.status='processed' AND cq.processed_at::date=CURRENT_DATE AND (SELECT COUNT(*) FROM memory_archive ma WHERE ma.original_memory_id IN (cq.memory_id_a, cq.memory_id_b)) != 2"
# must return 0 rows

# 6. No identity memories were touched
psql -c "SELECT COUNT(*) FROM memory_archive WHERE original_memory_id IN (SELECT id FROM memories WHERE memory_type='identity')"
# must return 0
```

---

*End of Constitution. No addenda permitted without Opus review.*
