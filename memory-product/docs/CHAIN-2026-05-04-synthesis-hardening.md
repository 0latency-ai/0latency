**This chain conforms to docs/CC-CHAIN-FRAMEWORK.md. Estimated wall-clock: 3–4 hours. Stages: 6. Tier: 0 (code + docs only, no migrations).**

=== CHAIN: Synthesis Hardening + LongMemEval Kickoff ===

CONTEXT
Phase 4B shipped (commit 7a11105) — synthesis clustering at 37.4s, 3.3× over Phase 2 baseline. CP8 Phase 2 synthesis writer is functionally complete. This chain closes 6 backlog items in one autonomous run: LongMemEval scaffolding + sampled baseline run, synthesis cron install, T8 verbatim guarantee doc, T11 hollow-pass guard, analytics_events schema-qualifier, and 3 of the 19 `_db_execute + split('|||')` cleanups. After this chain, LongMemEval has a real number to anchor Show HN messaging, synthesis runs unattended on cron, and three classes of latent bug are killed.

PLATFORM CONSTRAINTS
- pgvector 0.8.1 on DO managed PG (HNSW filter quirks; documented in clustering.py).
- memory-api on port 8420 (REST), 0latency-mcp on port 3100 (MCP).
- Python 3.11 venv at /root/.openclaw/workspace/memory-product/venv.
- LongMemEval public repo: github.com/xiaowu0162/LongMemEval (MIT). Dataset on HF: xiaowu0162/longmemeval. Use the `_s` (short) split for first-pass — same questions, shorter contexts, ~10× faster eval.
- Justin's tenant id: 44c3080d-c196-407d-a606-4ea9f62ba0fc. Read API key from .env or DB; never echo.
- Schema reminder: memory_service.memories has columns headline/context/full_content (NOT a single 'content' column). All NOT NULL. tenants PK is `id` not `tenant_id`.

STANDING RULES (apply to every stage)
- SSH context: ssh root@164.90.156.169 → cd /root/.openclaw/workspace/memory-product
- psql pattern: cd /root/.openclaw/workspace/memory-product && set -a && source .env && set +a && psql "$DATABASE_URL"
- Never echo secrets to stdout. Read from .env or query tenants table; never print api_key_live values.
- Inner BEGIN/COMMIT in any SQL files = silent failure trap. Don't introduce.
- Self-verify every claimed end state with a real probe (curl/journalctl/git/psql) before declaring a stage done.
- After ANY service-restarting stage: sleep 8 && curl -sf http://localhost:8420/health && curl -sf http://localhost:3100/health. Both must return 200 before proceeding.
- On any unrecoverable failure: write halt-report to /tmp/chain-halt-stage-N.md with full diagnostic context (command, output, hypothesis), fire chime, stop chain.
- Tier 0 chain: no migrations, no schema changes. If a stage requires schema change, halt — wrong tier.
- Decision tree convention: "ON FAIL" branches are mandatory. Every fork pre-decided in this prompt.

PRE-FLIGHT (CC runs, decides, proceeds or aborts)
Run these and assert on output. Do not proceed past pre-flight on any failure — write /tmp/chain-halt-preflight.md and fire chime.

  1. cd /root/.openclaw/workspace/memory-product && git rev-parse HEAD
     EXPECT: 7a11105... (Phase 4B head)
     ON FAIL: halt — repo state diverged from handoff.

  2. cd /root/.openclaw/workspace/memory-product && set -a && source .env && set +a && alembic current 2>&1 | tail -1
     EXPECT: a70dd7b2538c (head)
     ON FAIL: halt — migration state diverged.

  3. systemctl is-active memory-api 0latency-mcp
     EXPECT: active\nactive
     ON FAIL: systemctl restart memory-api 0latency-mcp && sleep 8 && retry once. If still failing, halt.

  4. curl -sf http://localhost:8420/health -o /dev/null -w "%{http_code}\n" && curl -sf http://localhost:3100/health -o /dev/null -w "%{http_code}\n"
     EXPECT: 200\n200
     ON FAIL: halt — services unhealthy despite active state.

  5. df -h / | awk 'NR==2 {print $4}'
     EXPECT: > 5G free
     ON FAIL: halt — insufficient disk for LongMemEval dataset (~2GB) + venv work.

  6. python3 -c "import sys; assert sys.version_info >= (3, 11), sys.version" && which python3
     EXPECT: no error
     ON FAIL: halt — wrong Python.

If all 6 pass: log "PRE-FLIGHT PASSED" and proceed to Stage 1.

═══════════════════════════════════════════════════════════════════
STAGE 1 — Analytics events schema-qualifier fix
═══════════════════════════════════════════════════════════════════
Goal: Eliminate "relation 'analytics_events' does not exist" retry storm. Two writes per request currently fail then retry. Single-line-class fix.

Files: search across api/ and src/ for unqualified analytics_events writes. Likely 1–3 sites.

Steps:
  1. grep -rn "analytics_events" --include="*.py" /root/.openclaw/workspace/memory-product/api /root/.openclaw/workspace/memory-product/src | grep -v "memory_service.analytics_events" | grep -v "test_" | tee /tmp/analytics-sites.txt
  2. For each site found: replace the unqualified table reference with memory_service.analytics_events. Preserve surrounding code. If the file uses `SET search_path` already (unlikely), document and skip.
  3. cat /tmp/analytics-sites.txt — if empty, the bug is already fixed (commit 175d51c per OPERATIONS.md §10 may have closed it). Log "ALREADY FIXED — skipping stage" and proceed to Stage 2.

Decision tree:
  IF sites found AND all are simple INSERT/UPDATE references → schema-qualify them inline.
  IF a site uses dynamic SQL building → leave with TODO comment, document in stage report, don't risk breaking it.
  IF zero sites found → mark stage as already-shipped, proceed.

Verification gate:
  - systemctl restart memory-api && sleep 8
  - curl -sf -X POST http://localhost:8420/recall -H "X-API-Key: <read from tenants table>" -H "Content-Type: application/json" -d '{"query":"test","agent_id":"user-justin"}' -o /dev/null -w "%{http_code}\n"
    EXPECT: 200
  - journalctl -u memory-api --since "30 seconds ago" --no-pager | grep -ci "analytics_events.*does not exist"
    EXPECT: 0
  - ON FAIL: git diff > /tmp/analytics-diff.txt; git checkout -- .; halt with /tmp/chain-halt-stage-1.md including the diff.

Commit (only if changes made):
  git add -A && git commit -m "fix: schema-qualify analytics_events writes — kill retry storm

Memory-api was hitting 'analytics_events' unqualified vs the actual table
memory_service.analytics_events, producing two failed retries per request.
Storage and dedup were unaffected; this kills log noise that was about to
pollute LongMemEval logs.

Files: <list>"
  git push origin master
  Capture commit SHA → log as STAGE_1_COMMIT.

═══════════════════════════════════════════════════════════════════
STAGE 2 — T11 contract test hollow-pass guard
═══════════════════════════════════════════════════════════════════
Goal: scripts/contract_test.py currently exits 0 when 0 atoms are extracted (hollow pass). Guard against this.

Files: scripts/contract_test.py

Steps:
  1. Read scripts/contract_test.py end-to-end. Identify where extraction completes and where exit happens.
  2. Add an assertion: if the post-extraction atom count for the sentinel write is 0, exit 1 with a clear log line "CONTRACT TEST HOLLOW PASS: 0 atoms extracted — verbatim guarantee not exercised".
  3. Add a second assertion: if the sentinel string is not byte-for-byte present in any extracted atom's full_content, exit 1 with "CONTRACT TEST FAILED: sentinel not preserved verbatim".
  4. Preserve all existing passing logic — additive only.

Decision tree:
  IF the test already has these guards → log "ALREADY GUARDED" and skip.
  IF the test structure makes it hard to insert (e.g., async pattern unfamiliar) → add minimal sync guard at the end before exit and document the limitation.

Verification gate:
  - python3 scripts/contract_test.py 2>&1 | tee /tmp/contract-test-output.txt
    Expected: exit 0 (the actual sentinel is preserved on the live system)
  - Synthetic hollow-pass test: temporarily monkey-patch by setting an env var that forces 0-atom return, run again, verify exit 1. Then unset env var.
    IF that's too invasive → skip the synthetic test and rely on the guard's logical correctness; document.
  - ON FAIL (real run exits non-zero): this is a NOVEL FINDING — the verbatim contract is broken on prod. Halt with /tmp/chain-halt-stage-2.md, do NOT proceed.

Commit:
  git add scripts/contract_test.py && git commit -m "fix(contract): guard contract test against hollow pass

Previously contract_test.py exited 0 when 0 atoms were extracted, falsely
asserting verbatim preservation when no extraction had even run. Now exits
1 with explicit log on either (a) zero atoms post-extraction or (b) sentinel
string missing from extracted full_content.

This is the verbatim-guarantee proof point referenced in
CHECKPOINT-8-SCOPE-v3.md Phase 2 Task 11."
  git push origin master
  Capture SHA → STAGE_2_COMMIT.

═══════════════════════════════════════════════════════════════════
STAGE 3 — VERBATIM-GUARANTEE.md (CP8 Phase 2 Task 8)
═══════════════════════════════════════════════════════════════════
Goal: Author docs/VERBATIM-GUARANTEE.md documenting how all four write paths preserve raw atoms before extraction.

Files: docs/VERBATIM-GUARANTEE.md (new)

Steps:
  1. Read the four write paths to confirm preservation behavior. For each: read code, document exactly what gets written and where the verbatim copy lives.
     a. /memories/extract endpoint (api/main.py) — raw input → DB row → extraction job
     b. /memories/seed endpoint (api/main.py) — direct structured write
     c. /memories/checkpoint endpoint — Haiku-summarized but parent atoms preserved
     d. Chrome extension capture path (look for the relevant handler — probably also /memories/extract or a dedicated route)
     e. MCP memory_write tool (in 0latency-mcp-unified) — wraps /seed
  2. For each path, document: (i) what raw input arrives, (ii) which DB column holds the verbatim copy (full_content), (iii) what derived rows reference it via parent_memory_ids, (iv) how /memories/{id}/source can resolve back to verbatim text.
  3. Include a "Proof points" section: reference T9 endpoint, T10 CLI verb, T11 contract test.
  4. Include a "Known limitations" section: what's NOT covered (e.g., if a path bypasses verbatim preservation, document it honestly).
  5. Cross-reference: link from this doc to OPERATIONS.md §6.2 (memories schema) and from CHECKPOINT-8-SCOPE-v3.md Phase 2.

Decision tree:
  IF a write path does NOT preserve verbatim → that's a NOVEL FINDING. Document the gap in the doc, BUT also halt the chain with /tmp/chain-halt-stage-3.md flagging the broken contract. Don't proceed to subsequent stages until reviewed.
  IF all four paths preserve verbatim → document and proceed.

Verification gate:
  - File exists at docs/VERBATIM-GUARANTEE.md, ≥150 lines, contains sections: "Write paths", "Proof points", "Known limitations", "Cross-references".
  - Doc internally consistent (no contradictions with OPERATIONS.md or CHECKPOINT-8-SCOPE-v3.md).
  - Manually verify one claim: pick one atom UUID from memory_service.memories, query GET /memories/{id}/source, confirm verbatim chain resolves.

Commit:
  git add docs/VERBATIM-GUARANTEE.md && git commit -m "docs: VERBATIM-GUARANTEE.md — CP8 Phase 2 Task 8

Documents how all four write paths (extract/seed/checkpoint/MCP) preserve
raw atoms verbatim before any extraction or summarization runs. Cross-
references T9 source endpoint, T10 CLI verify verb, T11 contract test as
proof points.

Closes the implicit T8 task that never got an autonomy scope doc."
  git push origin master
  Capture SHA → STAGE_3_COMMIT.

═══════════════════════════════════════════════════════════════════
STAGE 4 — Synthesis cron install + first scheduled run
═══════════════════════════════════════════════════════════════════
Goal: Install scripts/synthesis-cron.service + .timer, enable, verify timer fires, first scheduled run completes successfully.

Files: scripts/synthesis-cron.service, scripts/synthesis-cron.timer (already exist per HANDOFF v5; verify)

Steps:
  1. ls -la scripts/synthesis-cron.* — confirm both files exist. If missing, halt with /tmp/chain-halt-stage-4.md.
  2. cat the .service and .timer files. Verify:
     - .service ExecStart points to a real script that POSTs to /synthesis/run
     - .timer OnCalendar is sensible (per CP8 v3: daily at off-peak; 03:00 UTC is fine for now)
     - User= is set (probably root; document)
  3. Install: cp scripts/synthesis-cron.service /etc/systemd/system/ && cp scripts/synthesis-cron.timer /etc/systemd/system/
  4. systemctl daemon-reload
  5. systemctl enable --now synthesis-cron.timer
  6. systemctl list-timers synthesis-cron.timer --no-pager
     EXPECT: NEXT line shows future time, ACTIVATES line is sensible.
  7. Manually fire once to verify the unit works end-to-end (don't wait for OnCalendar):
     systemctl start synthesis-cron.service
     sleep 5
     journalctl -u synthesis-cron.service --since "30 seconds ago" --no-pager | tail -50 > /tmp/cron-first-run.log
  8. Verify the run completed: grep for "synthesis.perf" or "synthesis_written" in journal output. The run targets ~37s clustering (Phase 4B baseline); allow up to 300s wall-clock for safety.

Decision tree:
  IF .service or .timer files missing → halt (these were marked SHIPPED in handoff but not installed; novel state).
  IF unit fails on manual start → review logs, fix one round if it's an obvious config issue (e.g., wrong path, missing env var). On second failure, halt with full diagnostic.
  IF unit succeeds but takes >300s → don't halt; document the slow run in the report and recommend Phase 4C optimization.
  IF first scheduled run write does NOT produce a synthesis row → halt; the writer is broken.

Verification gate:
  - systemctl is-active synthesis-cron.timer → active
  - cd memory-product && set -a && source .env && set +a && psql "$DATABASE_URL" -c "SELECT count(*) FROM memory_service.memories WHERE memory_type='synthesis' AND created_at > now() - interval '5 minutes';" -t
    EXPECT: ≥ 1
  - On the +5 min synthesis count being 0: halt — the unit ran but didn't write.

Commit (if any code changes; usually only systemd files which aren't in repo):
  IF the .service/.timer content was edited in repo: commit "chore(synthesis): install cron units to /etc/systemd/system + verify first scheduled run"
  IF only system-level install (no repo changes): no commit, just log STAGE_4_INSTALLED=true and the journalctl excerpt.

═══════════════════════════════════════════════════════════════════
STAGE 5 — Three _db_execute + split('|||') cleanups
═══════════════════════════════════════════════════════════════════
Goal: Knock out 3 of the 19 documented call sites with the |||-split vulnerability class. Mechanical migration to _db_execute_rows pattern.

Files: src/recall.py and any other module containing the pattern.

Steps:
  1. grep -rn "_db_execute" --include="*.py" /root/.openclaw/workspace/memory-product/src /root/.openclaw/workspace/memory-product/api | grep -v "_db_execute_rows" | grep -v "test_" | tee /tmp/db-execute-sites.txt
  2. wc -l /tmp/db-execute-sites.txt — confirm there are at least 3 sites with the |||-split pattern. (HANDOFF says 19 remain.)
  3. Pick 3 sites in order of clearest scope:
     - Prefer sites where the |||-split is immediately followed by a tuple unpack — easiest mechanical conversion.
     - Skip sites that build dynamic SQL with f-strings around the split — too risky for this chain, defer.
     - Skip recall.py hot paths if they would require restart-and-re-bench to validate — unless adjacent to already-migrated sites.
  4. For each chosen site:
     a. Read 30 lines of context around the call.
     b. Replace _db_execute with _db_execute_rows.
     c. Replace the split('|||') unpack with native tuple-row indexing.
     d. Run the file's import alone (python3 -c "import path.to.module") to catch syntax errors before bigger tests.
  5. After all 3 sites converted: systemctl restart memory-api && sleep 8 && curl -sf http://localhost:8420/health.
  6. Smoke test: hit /recall once with a real query, verify 200 + sane response shape.

Decision tree:
  IF fewer than 3 ||| sites exist (cleanup happened upstream) → migrate however many do exist, document the count, proceed.
  IF a site's conversion breaks behavior in smoke test → git checkout that file, document the regression, drop that site, try a different one. Net stage outcome: as many sites as cleanly migrated, ≥1 minimum.
  IF restart fails → git checkout -- . (revert ALL stage 5 changes), restart, halt with /tmp/chain-halt-stage-5.md.

Verification gate:
  - systemctl is-active memory-api → active
  - curl -sf -X POST http://localhost:8420/recall -H "X-API-Key: <read from DB>" -H "Content-Type: application/json" -d '{"query":"synthesis testing","agent_id":"user-justin","top_k":5}' | python3 -c "import sys, json; r=json.load(sys.stdin); assert 'memories' in r or 'context' in r or 'context_block' in r, r" 
    (Accept any of the known recall response keys; just assert non-error JSON.)
  - journalctl -u memory-api --since "60 seconds ago" --no-pager | grep -ci "error\|traceback" → 0
  - ON FAIL: revert, halt.

Commit:
  git add -A && git commit -m "refactor: migrate N _db_execute call sites to _db_execute_rows

Closes N of the 19 documented |||-split-vulnerability sites
(OPERATIONS.md §10.3). Removes risk of column misalignment when content
contains the literal '|||' separator.

Sites migrated:
- <file>:<line>
- <file>:<line>
- <file>:<line>"
  git push origin master
  Capture SHA → STAGE_5_COMMIT.

═══════════════════════════════════════════════════════════════════
STAGE 6 — LongMemEval scaffolding + sampled baseline run
═══════════════════════════════════════════════════════════════════
Goal: Stand up LongMemEval harness, run sampled subset (~50 questions) against 0Latency /recall, produce baseline accuracy/latency JSON. Full run is a follow-up chain.

Files: bench/longmemeval/ (new directory), bench/longmemeval/run_eval.py, bench/longmemeval/results-baseline-<timestamp>.json

Steps:
  1. mkdir -p /root/.openclaw/workspace/memory-product/bench/longmemeval && cd /root/.openclaw/workspace/memory-product/bench/longmemeval
  2. git clone https://github.com/xiaowu0162/LongMemEval.git upstream || (cd upstream && git pull)
  3. Inspect upstream/README.md and upstream/data/ to understand dataset structure. Look specifically for the `_s` (short) split.
  4. Download dataset: the README will specify HF or direct download. Use the `_s` split. Store under bench/longmemeval/data/.
     IF download requires HF auth → check .env for HF_TOKEN; if missing, skip dataset download and use any sample data shipped in upstream/. Document in stage report.
  5. Write bench/longmemeval/run_eval.py:
     - Parses LongMemEval question format (typically: {question_id, question, evidence_sessions, expected_answer, ...})
     - For each question: write the evidence sessions to 0Latency via /memories/extract under a dedicated agent_id (e.g., "lme-bench-<question_id>"), wait for extraction to complete, then call /recall with the question, capture the response and latency.
     - Score: simple substring match of expected_answer against the recall response. (LongMemEval has more sophisticated grading; substring-match is the first-pass MVP — note this in the doc.)
     - Output: results JSON with per-question {question_id, recall_latency_ms, expected, got, match: bool} and aggregate {accuracy, p50_latency, p95_latency, n_questions}.
     - Use a NEW dedicated tenant key for this benchmark to keep data isolated. Either create one via the existing tenant-creation path OR reuse an existing benchmark tenant if one exists (check tenants table for `name LIKE '%bench%'`).
  6. Sampled run: take first 50 questions from the `_s` split. Execute. Write results to bench/longmemeval/results-baseline-<UTC-timestamp>.json.
  7. Generate summary: bench/longmemeval/SUMMARY-<timestamp>.md with accuracy, latency percentiles, observations, known limitations of this MVP grader.

Decision tree:
  IF dataset download fails → use any sample provided in upstream repo (often there's a small example). Sample run on 5–10 examples instead of 50. Document. The point is the harness is wired up; full data run is a follow-up.
  IF tenant key creation fails → reuse Justin's tenant on a dedicated agent_id `lme-bench-2026-05-04`. Cleanup is a future task.
  IF accuracy is shockingly low (< 20%) → don't halt — that's a real signal worth seeing. Document prominently in summary, recommend prompt/extraction tuning as follow-up.
  IF the first 5 questions take > 60s each → reduce sample size to 20 and document slow-extraction as a finding.
  IF /recall errors at high rate → halt with /tmp/chain-halt-stage-6.md; recall is broken under benchmark load.

Verification gate:
  - bench/longmemeval/results-baseline-*.json exists, contains aggregate stats, n_questions ≥ 5.
  - bench/longmemeval/SUMMARY-*.md exists, ≥80 lines, includes the aggregate numbers.
  - run_eval.py runs to completion without uncaught exception.

Commit:
  git add bench/longmemeval && git commit -m "feat(bench): LongMemEval harness + sampled baseline (n=N)

CP7 quality benchmark scaffolding. Wires upstream LongMemEval dataset
(xiaowu0162/LongMemEval) to 0Latency /recall via dedicated tenant +
agent_id. First-pass MVP grader uses substring match; production-grade
grader is a follow-up.

Sampled baseline (n=N, _s split):
- Accuracy: X%
- p50 recall latency: Yms
- p95 recall latency: Zms

Full-dataset run queued for next chain after grader hardening."
  git push origin master
  Capture SHA → STAGE_6_COMMIT.

═══════════════════════════════════════════════════════════════════
POST-FLIGHT (CC runs after Stage 6)
═══════════════════════════════════════════════════════════════════
  1. cd /root/.openclaw/workspace/memory-product && git log --oneline -10 → log to report
  2. systemctl is-active memory-api 0latency-mcp synthesis-cron.timer → all should be active
  3. curl -sf http://localhost:8420/health && curl -sf http://localhost:3100/health → both 200
  4. cd memory-product && set -a && source .env && set +a && psql "$DATABASE_URL" -c "SELECT count(*) FROM memory_service.memories WHERE memory_type='synthesis';" -t → log count
  5. Re-run pre-flight checks 1–6 (HEAD will be the Stage 6 commit, not 7a11105 — that's expected).

Then write /tmp/chain-report-synthesis-hardening-$(date -u +%Y%m%d-%H%M%S).md:

```
# Chain Report: Synthesis Hardening + LongMemEval Kickoff
**Started:** <ISO timestamp>
**Ended:** <ISO timestamp>
**Wall-clock:** <duration>
**Final HEAD:** <commit SHA>

## Stage outcomes

| Stage | Status | Commit | Notes |
|-------|--------|--------|-------|
| 1. analytics_events fix | shipped/skipped/halted | <SHA> | <one line> |
| 2. T11 hollow-pass guard | shipped/skipped/halted | <SHA> | <one line> |
| 3. VERBATIM-GUARANTEE.md | shipped/skipped/halted | <SHA> | <one line> |
| 4. Synthesis cron install | shipped/skipped/halted | n/a | <one line> |
| 5. _db_execute cleanups | shipped/skipped/halted | <SHA> | N sites migrated |
| 6. LongMemEval baseline | shipped/skipped/halted | <SHA> | accuracy=X%, p50=Yms |

## Key numbers
- LongMemEval accuracy: X% (n=N, _s split, MVP substring grader)
- LongMemEval p50/p95 recall latency: Yms / Zms
- _db_execute sites remaining: <19 - N>
- Synthesis cron: next firing at <time>

## Anomalies observed
<bullets, or "none">

## Recommended next chain
<3–5 bullets prioritized by Mem0-vs-0latency lens. Examples:
- Phase 4C: target <10s clustering (push K lower, batch embeddings)
- LongMemEval full-dataset run with hardened grader
- Remaining N _db_execute sites
- Synthesis quality eyeball — manual review of N synthesis rows
- Show HN draft authoring once LongMemEval has full-dataset numbers>

## Files changed (cumulative)
<git diff --stat 7a11105..HEAD>
```

═══════════════════════════════════════════════════════════════════
FINAL ACTION (literal, standalone tool call, never chained)
═══════════════════════════════════════════════════════════════════

afplay /System/Library/Sounds/Glass.aiff
