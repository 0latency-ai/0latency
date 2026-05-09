# CP10 Phase 3 — Reliability Hardening (Crash Recovery, Backpressure, Long-Session Stability)

---

## ALIGNMENT WITH CANONICAL ROADMAP

This scope doc implements all 8 canonical CP10 Phase 3 tasks from ROADMAP-UNIFIED-v2-CP10-CLI-CAPTURE.md (Phase 3, lines 243-265).

| Canonical Task | Status | Implementation | Verification Gate |
|---|---|---|---|
| 1. Long-session memory bounds (4-hour test) | ✓ Covered | Task 5 (ring buffers) + Task 11 (4-hour soak, RSS < 500MB) | G5, G11: RSS < 500MB after 4 hours, no atoms lost |
| 2. Large paste handling (1M-char) | ✓ Covered | Task 4 (UTF-8-safe chunking, 64KB) | G4: 1M-char paste, no block/drop/corrupt |
| 3. Interactive prompt handling (Y/N, password) | ✓ Covered | Task 3 (passthrough detection + transparent relay) | G3: Y/N and password prompts pass through, not captured |
| 4. Tool-call chains (distinct atoms) | ✓ Covered | Task 6 (tool-call block parser + sequencing) | G6: Each tool-call block = distinct atom with sequence metadata |
| 5. Async background tasks (long-running bash) | ✓ Covered | Task 7 (non-blocking capture thread) | G7: 5-min bash command completes, full output captured |
| 6. Crash recovery (rolling buffer + replay) | ✓ Covered | Task 1 (rolling buffer ~/.0latency/sessions/, auto-import on relaunch) | G1: kill -9 mid-session → relaunch → partial transcript recovered |
| 7. Atom batching (10-atom batches, 2s flush) | ✓ Covered | Task 8 (batch queue + timer thread) | G8: 100 atoms → 10 batches, p95 latency < 50ms |
| 8. Backpressure (10K atom cap, local queue) | ✓ Covered | Task 2 (local queue max 10K, exp backoff retry) | G2: API down 30min → atoms queue locally, flush on reconnect |

**Total tasks: 14** (8 canonical core + 3 integration/validation + 2 polish + 1 version bump).

**All canonical verification gates met. No scope reductions. No deferrals to P4.**

---

**Date authored:** 2026-05-09
**Author:** Claude Sonnet 4.5 (lead engineer mode) for CC (Sonnet) execution
**Source material:** CP10-P2-AUTONOMY-SCOPE.md (structure), CHECKPOINT-10-PHASE-2-COMPLETE.md (foundation state), operator requirements (dispatch context)
**Sequencing:** CP10 P2 v0.2.0 SHIPPED 2026-05-09 (HEAD b81e619). P3 builds on profile abstraction foundation. Profile ABC + ClaudeCodeProfile + GenericProfile are production-validated.
**Repo target:** `0latency-ai/0latency-cli` (existing, on `main`, HEAD `b81e619`, tag `v0.2.0`). Server-side has zero new dependencies for P3.
**Estimate:** 1.5 weeks active build (approx 9.5 hours effective with soak test parallelized, was 6-8hr before canonical alignment — scope increase reflects rolling buffer replay, interactive prompts, tool-call chains, async capture, atom batching now IN scope for P3)

---

## Strategic frame (locked)

> *Trust is earned through reliability under adversity, not feature count.*
> CP10 P1 shipped the wedge (verbatim capture), P2 shipped the moat (multi-agent profiles). P3 ships **production trust** — the wrapper must survive the chaos of real developer workflows: mid-turn ^C, network failures, 50KB paste bombs, 4-hour deep-work sessions. A wrapper that loses atoms, OOMs, or deadlocks fails the trust test regardless of feature completeness. P3 is what makes the wrapper safe to recommend for daily use.

**What P3 is:** Crash recovery (SIGINT/SIGTERM mid-turn), backpressure handling (API failures → local queue + retry), large-paste chunking (no OOM, no split-token corruption), long-session memory bounds (4-hour RSS cap < 500MB), and a 4-hour soak test that proves all of the above under real load.

**What P3 is NOT:** Windows support (P4). npm distribution, docs site, Show HN demo (P4). Multi-agent profile expansion for Codex/Gemini/Aider (P2 Task 6-8, deferred due to API keys — orthogonal to reliability). Tier-matrix enforcement (P4). Telemetry (P4).

---

## Why P3 now

Three reasons, in priority order:

1. **Foundation is solid, reliability is the next-highest-leverage improvement.** P2's profile abstraction works. ClaudeCodeProfile is production-validated with 77-turn interactive fixture. GenericProfile fallback covers unknown agents. The next vulnerability is **operational** — what happens when the wrapper encounters chaos (^C, network timeout, paste bomb)? P3 closes those gaps.
2. **Reliability failures are trust failures.** If the wrapper loses a single atom mid-session, or OOMs during a large paste, the user will disable it permanently. Reliability bugs are not polish issues — they are existential.
3. **P4 (Show HN, npm, docs) depends on P3's stability.** Launching publicly with crash-on-^C or OOM-on-paste means bad first impressions that are nearly impossible to recover from. P3 is a prerequisite for any launch narrative.

---

## Operator decision lens (trade-offs explicit)

### 1. Crash Recovery — Rolling Buffer + Partial Transcript Replay

**The problem:** Wrapper crashes mid-session (SIGINT, SIGTERM, kill -9, or unhandled exception). Buffered atoms not yet flushed to API are lost unless persisted locally.

**Decision: Rolling buffer to disk + auto-import on next launch (Option C)**

Chosen over:
- Option A (flush partial atom) — pollutes memory with incomplete atoms
- Option B (discard buffer + log) — loses data, violates verbatim guarantee for completed atoms

**Rationale:** Verbatim guarantee applies to ALL completed atoms, even if wrapper crashes before API flush. Rolling buffer ensures zero data loss for completed atoms.

**Rolling buffer spec:**
- Location: `~/.0latency/sessions/<session-id>.jsonl` (one line per atom, append-only)
- Flush cadence: Every atom immediately after capture (fsync for durability)
- Replay UX: On wrapper launch, detect orphaned sessions (*.jsonl files with no active PID). Auto-import with prompt: `Found N orphaned sessions (M atoms). Import? [Y/n]`. Default Y, imports all atoms to API with metadata `recovered: true`.
- Cleanup: Delete .jsonl file after successful import or explicit user decline.

**P3 ships:** Wrapper crash mid-session → rolling buffer preserves all completed atoms → next launch auto-imports → zero atom loss.

---

### 2. Backpressure — API Failure Handling Strategy

**The problem:** POST /atoms call to api.0latency.ai fails (timeout, 5xx, rate limit). Wrapper must not block the underlying agent's stdin/stdout.

**Decision: Local queue + exponential backoff retry (Option C)**

Chosen over:
- Option A (block until success) — breaks "invisible wrapper" contract
- Option B (drop atom) — defeats purpose of wrapper

**Queue implementation:**
- In-memory deque, max 10,000 atoms (approx 100MB at 10KB/atom)
- Spillover: drop-oldest + log line + alert user
- Retry: exponential backoff 1s → 2s → 4s → 8s → 16s → 32s → 60s max
- Background thread, non-blocking on main PTY loop
- Local tier: batch directly to sqlite (no API calls), still respects 10K cap for in-memory queue before sqlite flush

**P3 ships:** Failed API write → enqueue locally (max 10K atoms) → background retry → eventual delivery or explicit drop-oldest if queue fills. Local tier batches to sqlite directly.

---

### 3. Large-Paste Handling — Chunking Strategy

**The problem:** User pastes 50KB+ into agent. Wrapper must not OOM, must not split mid-UTF-8, must not lose data.

**Decision: Chunk at 64KB, UTF-8-boundary-aware (Option F)**

Chosen over:
- Option A (buffer all) — OOM risk
- Option B (fixed byte boundary) — UTF-8 corruption risk
- Option E (errors='ignore') — violates verbatim invariant

**Chunking implementation:**
- Chunk size: 64KB
- Split at last valid UTF-8 character boundary (scan backwards, validate decode)
- Each chunk tagged with chunk_index, chunk_total in atom metadata
- Log warning if paste > 1MB

**P3 ships:** Large paste → UTF-8-safe chunks → no OOM, no data loss, no corruption.

---

### 4. Long-Session Memory Bounds — RSS Target

**The problem:** 4-hour session → unbounded list growth → OOM.

**Target:** Wrapper RSS < 500MB after 4 hours (400 turns).

**Strategy:**
- Atom buffer: bounded by 64KB chunks (Task 3)
- Retry queue: max 1000 atoms, approx 10MB (Task 2)
- Session metadata: ring buffer (deque, maxlen=100 turns)
- Profile buffer: ring buffer (last 128KB)
- httpx pool: max 5 connections

**Expected RSS:** approx 105MB steady-state, 500MB target = 3.7x safety margin.

**P3 ships:** Ring buffers prevent unbounded growth. 4-hour soak test verifies RSS < 500MB.

---

## Locked decisions (P3 only)

| Decision | Value | Why |
|----------|-------|-----|
| Crash recovery strategy | Rolling buffer (~/.0latency/sessions/) + auto-import on relaunch | Zero atom loss, verbatim guarantee preserved |
| API failure handling | Local queue (max 10K) + exp backoff | No blocking + eventual delivery |
| Queue spillover policy | Drop-oldest + log + alert | Recency > history, explicit user notification at 10K cap |
| Retry schedule | 1s, 2s, 4s, 8s, 16s, 32s, 60s max | Matches server retry patterns |
| Large-paste chunk size | 64KB, UTF-8-boundary-aware | Memory efficiency + no corruption |
| Paste chunk metadata | chunk_index + chunk_total | Enables future reassembly |
| Long-session RSS target | < 500MB after 4 hours | 3.7x safety margin |
| Session metadata storage | Ring buffer (deque, maxlen=100) | Bounded memory |
| Profile detection buffer | Ring buffer (last 128KB) | Prevents unbounded growth |
| httpx connection pool | max_connections=5 | Caps overhead at approx 5MB |
| Interactive prompt handling | Heuristic detection (regex), passthrough (NOT captured) | Privacy + UX (passwords not logged) |
| Tool-call atomization | Each `<invoke>` = distinct atom with sequence metadata | Enables downstream tool usage analysis |
| Async background capture | Non-blocking capture thread (select/asyncio) | Long-running bash commands don't block wrapper |
| Atom batching | 10-atom batches OR 2-second flush timer | API efficiency + no perceived latency |
| 4-hour soak test | 100 turns/hour, RSS < 500MB, p95 < 50ms | Real load validation |
| Anti-scope discipline | No Windows, telemetry, npm, tier enforcement | P3 is reliability only |

---

## Decision lens (apply to every implementation choice)

When in doubt, ask:

1. **Does this preserve the verbatim invariant?** Explicit log > silent data loss.
2. **Does this block the user's terminal?** Wrapper must be invisible.
3. **Is this failure mode explicit or silent?** Explicit log lines > silent failures.
4. **Is memory growth bounded?** Ring buffers, max sizes, spillover policies required.
5. **Can this be tested in the 4-hour soak?** Adjust test or mitigation if failure mode surfaces later.

---

## Phases

P3 has three execution phases on branch cp-p10-3-reliability off main:

**Phase A:** Crash Recovery (foundation)
**Phase B:** Backpressure + Large-Paste (build)
**Phase C:** Long-Session Stability + 4-Hour Soak (validation)

---

## Tasks (14 total: 8 canonical core + 3 integration/validation + 2 polish + 1 version bump, sequenced for CC execution)

### Task 1 — Rolling buffer for crash recovery + auto-import on relaunch

**Goal:** All completed atoms written to `~/.0latency/sessions/<session-id>.jsonl` (rolling buffer) immediately after capture. On wrapper crash (SIGINT/SIGTERM/kill -9), atoms are preserved. Next wrapper launch detects orphaned sessions and offers auto-import.

**Files touched:**
- src/zerolatency_cli/wrapper.py (rolling buffer writer)
- src/zerolatency_cli/recovery.py (new: orphan detection + import)
- tests/test_crash_recovery.py (new: kill -9 mid-session + relaunch test)

**Steps:**

1. SSH to root@164.90.156.169
2. cd /root/0latency-cli && git checkout -b cp-p10-3-reliability
3. Edit src/zerolatency_cli/wrapper.py:
   - On session start, create `~/.0latency/sessions/<session-id>.jsonl` (mkdir -p if needed)
   - After every atom capture, append atom as JSON line + fsync
   - On clean shutdown, delete .jsonl file (session complete)
4. Create src/zerolatency_cli/recovery.py:
   - `detect_orphaned_sessions()`: scan ~/.0latency/sessions/*.jsonl, filter by PID (check /proc/<pid> or psutil), return list
   - `import_session(jsonl_path)`: read atoms, POST to API with metadata `recovered: true`, delete file on success
   - `prompt_user_import()`: "Found N orphaned sessions (M atoms). Import? [Y/n]" → call import_session() if Y
5. Edit src/zerolatency_cli/wrapper.py main():
   - Before session start, call `prompt_user_import()` if orphaned sessions exist
6. Add tests/test_crash_recovery.py:
   - Test 1: Spawn wrapper, write 10 atoms, send kill -9, assert .jsonl has 10 lines
   - Test 2: Relaunch wrapper, assert prompt shown, auto-import, .jsonl deleted, 10 atoms in API

**Success criteria:**
- Wrapper crash mid-session → .jsonl file preserved with all completed atoms
- Relaunch → orphaned session detected → user prompted → atoms imported → zero loss

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_crash_recovery.py -v | grep -q "2 passed" && echo "G1 PASS"
```

**Rollback path:** If test fails, disable rolling buffer (comment out writes), defer to P4.

**Halt conditions:** .jsonl corruption, import fails, atoms lost, user not prompted.

---

### Task 2 — Local atom queue (10K cap) + background retry thread + backpressure handling

**Goal:** Failed POST /atoms enqueues locally (max 10,000 atoms). Background thread retries with exponential backoff. Main PTY never blocks. Local tier batches directly to sqlite.

**Files touched:**
- src/zerolatency_cli/storage.py (AtomQueue, RetryWorker)
- src/zerolatency_cli/wrapper.py (queue instantiation, backpressure alerts)
- tests/test_backpressure.py (new: API down 30min, queue + flush test)

**Steps:**

1. Edit src/zerolatency_cli/storage.py:
   - Add class AtomQueue:
     - deque(maxlen=10000), thread lock
     - enqueue() logs if full, drops oldest, alerts user at 10K cap
     - dequeue() pops from queue
   - Add class RetryWorker(threading.Thread):
     - Loop: dequeue atom, retry with backoff [1,2,4,8,16,32,60]s
     - Re-enqueue if all retries fail (up to max cap)
2. Edit src/zerolatency_cli/wrapper.py:
   - Instantiate queue + worker at startup
   - On atom write failure, enqueue (don't block)
   - On shutdown, log queue size if > 0, offer to export atoms to .jsonl if > 100 queued
3. Add test tests/test_backpressure.py:
   - Test 1: Mock API to fail for 30min (1800 mock seconds), queue atoms
   - Test 2: API reconnects, assert all atoms flushed
   - Test 3: Queue hits 10K cap, assert drop-oldest + user alert

**Success criteria:**
- API down for 30 minutes → atoms queue locally (up to 10K) → API reconnects → all queued atoms flushed
- Queue exceeds 10K → drop-oldest + explicit user alert

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_backpressure.py -v | grep -q "3 passed" && echo "G2 PASS"
```

**Rollback path:** If blocking occurs, reduce queue cap, defer to P4.

**Halt conditions:** PTY blocks on API failure, atoms lost silently, no user alert at 10K cap.

---

### Task 3 — Interactive prompt passthrough (Y/N, password, etc.)

**Goal:** Detect interactive prompts (Y/N, password, confirmation dialogs) from underlying agent. Pass through transparently to user. Do NOT capture prompt text as agent output (violates privacy + clutters memory).

**Files touched:**
- src/zerolatency_cli/wrapper.py (prompt detection heuristics)
- src/zerolatency_cli/atom.py (atom metadata: is_interactive_prompt flag)
- tests/test_interactive_prompts.py (new: Y/N and password prompt tests)

**Steps:**

1. Edit src/zerolatency_cli/wrapper.py:
   - Add `is_interactive_prompt(text)` heuristic:
     - Regex: `(Y/n|y/N|\[Y/n\]|\[y/N\]|password:|enter passphrase:)`
     - Trailing `? ` or `: ` with no newline
     - Return True if match
   - On PTY read, check `is_interactive_prompt()`. If True:
     - Pass through to user terminal (do NOT buffer as atom)
     - Log debug line (not captured)
2. Edit src/zerolatency_cli/atom.py:
   - Add `is_interactive_prompt: bool = False` field (for future non-heuristic detection)
3. Add tests/test_interactive_prompts.py:
   - Test 1: Agent outputs "Delete file? [Y/n]: " → assert NOT captured as atom, passes through
   - Test 2: Agent outputs "Enter password: " → assert NOT captured, passes through
   - Test 3: Agent outputs regular text "Yes or no?" (not a prompt) → assert IS captured as atom

**Success criteria:**
- Y/N prompts, password prompts pass through transparently
- NOT captured as atoms
- User can respond directly without wrapper interference

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_interactive_prompts.py -v | grep -q "3 passed" && echo "G3 PASS"
```

**Rollback path:** If heuristic fails (false positives/negatives), make detection opt-in via env var, defer refinement to P4.

**Halt conditions:** Password prompts captured as atoms (privacy violation), user cannot respond to prompts (wrapper blocks input).

---

### Task 4 — Large-paste chunking (UTF-8-safe, 64KB) + 1M-char test

**Goal:** Input > 64KB chunked at last valid UTF-8 boundary. Each chunk tagged with metadata. Handle up to 1M-char paste without blocking, dropping, or corrupting data.

**Files touched:**
- src/zerolatency_cli/atom.py (chunk metadata)
- src/zerolatency_cli/wrapper.py (UTF-8-safe chunking logic)
- tests/test_large_paste.py (new: 1M-char paste test)

**Steps:**

1. Edit src/zerolatency_cli/atom.py:
   - Add chunk_index: Optional[int], chunk_total: Optional[int]
2. Edit src/zerolatency_cli/wrapper.py:
   - Add chunk_utf8_safe(data, max_chunk_size=65536):
     - Split data at 64KB boundaries
     - Scan backwards from boundary to find last valid UTF-8 character (no mid-character split)
     - Return chunks as list
   - On buffer > 64KB, chunk and write each atom with metadata (chunk_index, chunk_total)
   - Log warning if paste > 1MB
3. Add test tests/test_large_paste.py:
   - Test 1: Generate 1M-char UTF-8 string (mix of ASCII + multibyte chars like emoji)
   - Assert correct number of chunks (approx 16 for 1M chars at 64KB/chunk)
   - Assert chunk_index sequence correct (0, 1, 2, ..., N-1)
   - Assert reassembly (join all chunks) == original input
   - Assert no blocking (paste completes in < 5 seconds)

**Success criteria:**
- 1M-char paste completes without blocking, dropping, or corrupting data
- Chunks split at UTF-8 boundaries (no mid-character corruption)
- Chunk metadata allows reassembly

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_large_paste.py -v | grep -q "1 passed" && echo "G4 PASS"
```

**Rollback path:** If chunking fails, reduce max paste size, add user warning at 100KB.

**Halt conditions:** Mid-UTF-8 splits, chunks lost, reassembly fails, paste blocks wrapper.

---

### Task 5 — Ring buffers (session metadata + profile detection) for long-session memory bounds

**Goal:** Session metadata cache + profile buffer bounded via ring buffers. Prevent unbounded memory growth in 4-hour sessions.

**Files touched:**
- src/zerolatency_cli/wrapper.py (ring buffer implementation)
- src/zerolatency_cli/profiles.py (profile buffer cap)
- tests/test_ring_buffers.py (new: 200-turn simulation)

**Steps:**

1. Edit src/zerolatency_cli/wrapper.py:
   - Replace session_metadata: dict with deque(maxlen=100) (rolling window of last 100 turns)
   - Replace profile_buffer: list with deque(maxlen=128*1024) (128KB rolling buffer)
2. Update Profile.detect_role() docstring to note buffer is last 128KB only
3. Add test tests/test_ring_buffers.py:
   - Test 1: Simulate 200 turns, assert metadata len == 100 (oldest discarded)
   - Test 2: Feed 500KB to profile buffer, assert buffer size <= 128KB

**Success criteria:**
- Session metadata never exceeds 100 turns
- Profile buffer never exceeds 128KB
- Memory growth bounded regardless of session length

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_ring_buffers.py -v | grep -q "2 passed" && echo "G5 PASS"
```

**Rollback path:** If ring buffers break profile detection, increase cap to 256KB, defer tuning to P4.

**Halt conditions:** Unbounded growth, OOM, profile detection fails.

---

### Task 6 — Tool-call chain atomization (each tool-call block = distinct atom)

**Goal:** Parse tool-call chains from agent output. Each `<tool-call>` block captured as a distinct atom with sequence metadata. Enables downstream analysis of tool usage patterns.

**Files touched:**
- src/zerolatency_cli/wrapper.py (tool-call parser)
- src/zerolatency_cli/atom.py (tool_call_sequence metadata)
- tests/test_tool_call_chains.py (new: multi-tool-call test)

**Steps:**

1. Edit src/zerolatency_cli/atom.py:
   - Add `tool_call_index: Optional[int]` (position in chain, 0-indexed)
   - Add `tool_call_total: Optional[int]` (total tools in chain)
2. Edit src/zerolatency_cli/wrapper.py:
   - Add `parse_tool_calls(text)` function:
     - Regex to detect `<function_calls>...</function_calls>` blocks
     - Extract individual `<invoke>` blocks
     - Return list of tool calls with index
   - On detection of tool-call block, create one atom per `<invoke>` with metadata
3. Add tests/test_tool_call_chains.py:
   - Test 1: Agent outputs 3 tool calls in sequence → assert 3 atoms, tool_call_index = [0,1,2], tool_call_total = 3
   - Test 2: Single tool call → assert tool_call_index = None (not a chain)

**Success criteria:**
- Each tool-call block in a chain captured as distinct atom
- Sequence metadata (tool_call_index, tool_call_total) enables reconstruction of chains

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_tool_call_chains.py -v | grep -q "2 passed" && echo "G6 PASS"
```

**Rollback path:** If parser fails on edge cases, make tool-call atomization opt-in via env var.

**Halt conditions:** Tool calls not parsed, metadata missing, atoms lost.

---

### Task 7 — Async background task capture (long-running bash commands)

**Goal:** Long-running bash commands (5+ minutes) continue to capture output without blocking wrapper or child process. Non-blocking capture thread.

**Files touched:**
- src/zerolatency_cli/wrapper.py (async capture thread)
- tests/test_async_background.py (new: 5-min bash command test)

**Steps:**

1. Edit src/zerolatency_cli/wrapper.py:
   - Add `AsyncCaptureThread(threading.Thread)`:
     - Polls PTY for output non-blocking (select() or asyncio)
     - Writes atoms as output arrives
     - Does NOT block on child process exit
   - Instantiate on session start, runs in background
2. Add tests/test_async_background.py:
   - Test 1: Spawn `sleep 300 && echo done` (5-min bash command)
     - Assert wrapper continues capturing (not blocked)
     - After 5min, assert "done" captured as atom
   - Test 2: Kill child process mid-command, assert wrapper continues normally

**Success criteria:**
- Long-running bash commands complete without blocking wrapper
- Full output captured (no truncation)
- Wrapper continues processing other atoms during long commands

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_async_background.py -v --timeout=360 | grep -q "2 passed" && echo "G7 PASS"
```

**Rollback path:** If async capture deadlocks, fall back to synchronous capture with timeout.

**Halt conditions:** Wrapper blocks on long bash commands, output lost, deadlock.

---

### Task 8 — Atom batching (10-atom batches, 2-second flush timer)

**Goal:** Batch atoms into groups of 10 for API efficiency. Flush partial batch after 2 seconds (no user-visible latency). Local tier batches directly to sqlite.

**Files touched:**
- src/zerolatency_cli/storage.py (batch queue + flush timer)
- tests/test_atom_batching.py (new: batch size + timer tests)

**Steps:**

1. Edit src/zerolatency_cli/storage.py:
   - Add `BatchQueue`:
     - deque for pending atoms
     - Flush when len == 10 OR timer expires (2s since first atom)
     - POST /atoms/batch endpoint (or sequential POSTs if batch endpoint unavailable)
   - Add `FlushTimer(threading.Thread)`:
     - Checks queue every 100ms
     - Flushes if > 2s since first atom enqueued
2. Edit src/zerolatency_cli/wrapper.py:
   - Replace direct atom writes with BatchQueue.enqueue()
   - On shutdown, flush remaining atoms
3. Add tests/test_atom_batching.py:
   - Test 1: Write 25 atoms rapidly → assert 3 batches (10, 10, 5)
   - Test 2: Write 5 atoms, wait 2.5s → assert flushed (timer triggered)
   - Test 3: Local tier → assert batches go to sqlite, not API

**Success criteria:**
- 100 atoms → 10 batches of 10 (API efficiency)
- Partial batches flush within 2 seconds (no perceived latency)
- p95 overhead < 50ms maintained

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_atom_batching.py -v | grep -q "3 passed" && echo "G8 PASS"
```

**Rollback path:** If batching adds latency, disable batching, defer to P4.

**Halt conditions:** Batches lost, timer doesn't fire, p95 overhead > 50ms.

---

### Task 9 — httpx connection pool limit

**Goal:** httpx client capped at 5 max connections to prevent connection overhead from unbounded growth.

**Files touched:**
- src/zerolatency_cli/storage.py (httpx client config)
- tests/test_connection_pool.py (new: concurrent request test)

**Steps:**

1. Edit src/zerolatency_cli/storage.py:
   - Pass limits=httpx.Limits(max_connections=5) to httpx.Client()
2. Add test tests/test_connection_pool.py:
   - Write 20 atoms concurrently, assert max 5 connections active at any time

**Success criteria:**
- httpx connection pool never exceeds 5 connections
- Connection overhead capped at approx 5MB

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_connection_pool.py -v | grep -q "1 passed" && echo "G9 PASS"
```

**Rollback path:** If connection pool causes slowdown, increase to 10, defer tuning to P4.

**Halt conditions:** Unbounded connection growth, connection pool deadlock.

---

### Task 10 — Edge case stress tests (timeout, queue full, 5MB paste)

**Goal:** Stress-test failure modes to ensure wrapper handles extreme inputs gracefully.

**Files touched:**
- tests/test_edge_cases.py (new: stress tests)

**Steps:**

1. Add tests/test_edge_cases.py:
   - Test 1: API timeout → enqueue (verify backpressure)
   - Test 2: Queue full (10,001st atom) → drop oldest + user alert
   - Test 3: 5MB paste → approx 80 chunks (at 64KB/chunk), correct metadata, no corruption

**Success criteria:**
- All edge cases handled gracefully
- No crashes, no data corruption
- Explicit user alerts on failures

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_edge_cases.py -v | grep -q "3 passed" && echo "G10 PASS"
```

**Rollback path:** If edge cases cause crashes, add input validation limits.

**Halt conditions:** Crashes on large inputs, silent failures, data corruption.

---

### Task 11 — 4-hour soak test (integration + long-session validation)

**Goal:** Real Claude Code session, 400 turns. Assert RSS < 500MB, no crashes, zero atoms lost, p95 overhead < 50ms maintained.

**Files touched:**
- tests/soak_test_4hr.py (new: 4-hour integration test)
- README.md (soak test instructions)

**Steps:**

1. Create tests/soak_test_4hr.py:
   - Launch wrapper + Claude Code
   - Script 400 turns (mix of short queries, code blocks, large pastes, tool calls)
   - Log RSS every 100 turns (psutil)
   - Log p95 atom write latency every 100 turns
   - At end: assert RSS < 500MB, approx 400 atoms written, no crashes
2. Document in README how to run (requires tmux/screen for 4-hour duration)
3. Run: pytest tests/soak_test_4hr.py --timeout=14400 -v

**Success criteria:**
- 4-hour session completes without crashes
- RSS < 500MB throughout
- Zero atoms lost (all 400 accounted for)
- p95 overhead < 50ms maintained

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/soak_test_4hr.py --timeout=14400 -v > tests/soak_test_4hr.log 2>&1
grep -q "RSS.*< 500" tests/soak_test_4hr.log && grep -q "400 atoms" tests/soak_test_4hr.log && echo "G11 PASS"
```

**Note:** 4-hour wall-clock time. Run in tmux/screen.

**Rollback path:** If soak test fails (OOM, crashes), analyze bottleneck, adjust ring buffer sizes.

**Halt conditions:** Crashes, OOM, atoms lost, p95 > 50ms.

---

### Task 12 — Logging discipline audit (explicit failure lines)

**Goal:** Every failure mode has explicit log line. No silent failures.

**Files touched:**
- src/zerolatency_cli/*.py (audit all failure paths)
- tests/test_logging.py (new: failure mode log tests)

**Steps:**

1. Audit all failure paths across wrapper, storage, recovery modules:
   - Crash recovery: log orphaned session count, import status
   - Backpressure: log queue size, drop-oldest events, 10K cap alerts
   - Large paste: log chunks, size warnings (> 1MB)
   - Tool calls: log parse failures
   - Async capture: log thread errors
   - Batching: log flush events
2. Add tests/test_logging.py:
   - Test each failure mode, assert log line present (use caplog)
   - Approx 8 tests (one per major failure mode)

**Success criteria:**
- All failure modes have explicit log lines
- No silent failures

**Verification command:**
```bash
cd /root/0latency-cli
pytest tests/test_logging.py -v | grep -q "8 passed" && echo "G12 PASS"
```

**Rollback path:** If log volume is excessive, reduce verbosity to warnings only.

**Halt conditions:** Silent failures detected in audit.

---

### Task 13 — Update README + docs/reliability.md

**Goal:** Document P3 reliability features, trade-offs, soak test instructions.

**Files touched:**
- README.md (add Reliability Features section)
- docs/reliability.md (new: detailed reliability guide)

**Steps:**

1. Edit README.md:
   - Add "Reliability Features (v0.3.0)" section summarizing crash recovery, backpressure, large paste handling
2. Create docs/reliability.md:
   - Section 1: Crash recovery (rolling buffer, auto-import UX)
   - Section 2: Backpressure (queue cap, retry strategy)
   - Section 3: Large paste handling (chunking, limits)
   - Section 4: Long-session stability (ring buffers, RSS targets)
   - Section 5: How to run 4-hour soak test
   - Section 6: Trade-offs (e.g., 10K queue cap, 2s flush timer)

**Success criteria:**
- docs/reliability.md exists and covers all 8 canonical tasks
- README summarizes P3 features

**Verification command:**
```bash
cd /root/0latency-cli
test -f docs/reliability.md && grep -q "Crash Recovery" docs/reliability.md && grep -q "Backpressure" docs/reliability.md && echo "G13 PASS"
```

**Rollback path:** N/A (docs only).

**Halt conditions:** None.

---

### Task 14 — Version bump to v0.3.0 + tag + merge

**Goal:** Bump version to v0.3.0, tag release, merge to main.

**Files touched:**
- pyproject.toml (version)
- src/zerolatency_cli/__init__.py (version)

**Steps:**

1. Edit pyproject.toml: version = "0.3.0"
2. Edit src/zerolatency_cli/__init__.py: __version__ = "0.3.0"
3. Commit changes:
   ```
   git add pyproject.toml src/zerolatency_cli/__init__.py
   git commit -m "Bump version to v0.3.0 (CP10 Phase 3 - Reliability Hardening)"
   ```
4. Merge to main:
   ```
   git checkout main && git merge cp-p10-3-reliability --no-ff
   git tag v0.3.0 -m "CP10 Phase 3: Reliability Hardening - crash recovery, backpressure, long-session stability"
   git push origin main --tags
   ```

**Success criteria:**
- Version v0.3.0 tagged
- Merged to main
- All tests pass on main

**Verification command:**
```bash
cd /root/0latency-cli
git tag | grep -q "v0.3.0" && echo "G14 PASS"
```

**Rollback path:** `git checkout main && git reset --hard v0.2.0`

**Halt conditions:** Merge conflicts, tests fail on main.

---

## Verification Gates (DONE WHEN)

| Task | Evidence | Command | Success |
|------|----------|---------|---------|
| 1 | Crash recovery test pass | pytest tests/test_crash_recovery.py -v | "2 passed", .jsonl preserved, atoms recovered |
| 2 | Backpressure test pass | pytest tests/test_backpressure.py -v | "3 passed", 10K cap enforced |
| 3 | Interactive prompts pass | pytest tests/test_interactive_prompts.py -v | "3 passed", prompts NOT captured |
| 4 | Large paste test pass | pytest tests/test_large_paste.py -v | "1 passed", 1M-char no corruption |
| 5 | Ring buffer test pass | pytest tests/test_ring_buffers.py -v | "2 passed", buffers capped |
| 6 | Tool-call chains pass | pytest tests/test_tool_call_chains.py -v | "2 passed", metadata correct |
| 7 | Async background pass | pytest tests/test_async_background.py -v | "2 passed", 5-min bash captured |
| 8 | Atom batching pass | pytest tests/test_atom_batching.py -v | "3 passed", p95 < 50ms |
| 9 | Connection pool pass | pytest tests/test_connection_pool.py -v | "1 passed", max 5 conns |
| 10 | Edge cases pass | pytest tests/test_edge_cases.py -v | "3 passed", graceful failures |
| 11 | Soak test pass | grep "RSS.*< 500" tests/soak_test_4hr.log | RSS < 500MB, 400 atoms, zero lost |
| 12 | Logging audit pass | pytest tests/test_logging.py -v | "8 passed", all failure modes logged |
| 13 | Docs exist | test -f docs/reliability.md | File exists, covers all 8 canonical tasks |
| 14 | Version tagged | git tag \| grep v0.3.0 | Tag v0.3.0 present |

---

## Out of scope (explicit)

P3 does NOT include:

1. Windows support (P4)
2. Profile expansion for Codex/Gemini/Aider (P2 Tasks 6-8, API key blocked)
3. Tier-matrix enforcement (P4)
4. Telemetry (P4)
5. npm distribution (P4)
6. Atom reassembly on recall (P4+ downstream feature — P3 chunks are tagged but reassembly is client-side)
7. Multi-agent reliability quirks (P3 tests ClaudeCodeProfile only, other profiles deferred)
8. Batch API endpoint (P3 uses sequential POSTs if batch endpoint unavailable)

---

## Pre-flight requirements

1. Server: SSH to root@164.90.156.169
2. Repo: 0latency-cli at main, HEAD b81e619, tag v0.2.0
3. Python 3.11+ (present)
4. Claude Code installed (present)
5. Test deps: pytest, pexpect, psutil
6. Soak test: tmux/screen for 4-hour run
7. No server-side changes required

---

## Rollback path

If catastrophic failure:

1. git checkout main && git reset --hard v0.2.0 && pip install -e .
2. 0latency --version | grep 0.2.0
3. Diagnose, fix forward or defer

---

## Estimated time per task

| Task | Est | Cumulative | Notes |
|------|-----|------------|-------|
| 1 | 60m | 1hr | Rolling buffer + auto-import (more complex than simple discard) |
| 2 | 75m | 2.25hr | Queue (10K cap) + retry worker + backpressure tests |
| 3 | 45m | 3hr | Interactive prompt detection + passthrough |
| 4 | 60m | 4hr | Large paste chunking + 1M-char test |
| 5 | 30m | 4.5hr | Ring buffers (session + profile) |
| 6 | 45m | 5.25hr | Tool-call chain parser + atomization |
| 7 | 45m | 6hr | Async capture thread + 5-min bash test |
| 8 | 45m | 6.75hr | Atom batching + flush timer |
| 9 | 15m | 7hr | httpx connection pool config |
| 10 | 30m | 7.5hr | Edge case stress tests |
| 11 | 4hr | 11.5hr | 4-hour soak test (wall-clock) |
| 12 | 45m | 12.25hr | Logging audit (8 failure modes) |
| 13 | 45m | 13hr | Documentation (README + reliability.md) |
| 14 | 15m | 13.25hr | Version bump + tag |

**Total: approx 13.25 hours active** (9hr build + 4hr soak wall-clock + 15m wrap)

**Parallelization:** Task 11 (soak) can run in background during Tasks 12-14. Effective: approx 9.5hr.

---

## Success criteria (P3 complete when...)

1. All 14 tasks completed, all gates verified
2. pytest suite passes (100%)
3. 4-hour soak passes (RSS < 500MB, approx 400 atoms, zero atoms lost, p95 < 50ms)
4. docs/reliability.md exists, covers all 8 canonical P3 tasks
5. Version v0.3.0 tagged, merged to main
6. No P1/P2 regressions
7. Wrapper behavior unchanged for happy-path (invisible wrapper contract preserved)

---

## Post-P3 next steps (operator decision)

**Option A:** CP10 P4 (Show HN Launch) — npm, docs site, tier enforcement, telemetry, Windows, demo
**Option B:** CP10 P2 Tasks 6-8 (Codex/Gemini/Aider profiles) — unblock with API keys
**Option C:** CP11 (Enterprise Expansion) — enterprise features

**Recommendation:** P3 → P4 (launch readiness). Wrapper solid, reliability proven, time to ship publicly.

---

**END OF SCOPE**

**Operator approval required before CC execution begins.**
