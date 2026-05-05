# CP-SYNTHESIS-PERF Stage 1 — Profile the synthesis writer

**Mode:** Autonomous CC, single task.
**Branch in:** new branch `cp-synthesis-perf-s1` off `master` (`a21f103`).
**Estimated wall-clock:** 15–25 min.
**Predecessor:** P4.2-PATCH closed Phase 4 at `a21f103`.

---

## Goal (one sentence)

Instrument the synthesis writer with phase-boundary timing, run it once against a real user-justin cluster on prod, and produce a profile report that breaks the ~3-minute end-to-end runtime into named phases (clustering, embedding, LLM call, DB writes, etc.) so Stage 2 can target the largest slice with confidence.

## Why this exists

The writer takes ~173,958ms per cluster (1 cluster, 1415 Haiku tokens, user-justin). Mem0 publishes single-digit seconds. Stage 2 fixes this — Stage 1 measures it. No optimization decisions in Stage 1; pure instrumentation.

---

## In scope

- `src/synthesis/writer.py` — add phase-boundary timing (context-manager-style or explicit start/stop markers; CC's call on style as long as it's clean).
- `src/synthesis/clustering.py` — same.
- Any other module the writer calls into where timing is informative (CC discovers via reading the writer call graph).
- A new file `scripts/profile_synthesis.py` — driver script that runs ONE writer pass against ONE existing cluster on user-justin and emits a structured profile report (JSON + human-readable summary).
- Output: `docs/profile/synthesis-writer-profile-2026-05-05.md` — the report itself, committed to repo as the Stage 1 deliverable.

## Out of scope (DO NOT TOUCH)

- Any schema migration.
- Any optimization, caching, or parallelization. Stage 1 is measurement only — if CC sees an obvious fix, document it in the report, do NOT apply.
- Recall path (`src/recall.py`).
- The MCP server, the API endpoints, anything outside the synthesis subsystem.
- Tests beyond verifying the timing harness itself works.
- Changes to the orchestrator's external behavior — phase boundaries are read-only observation.

---

## Inputs at start

- HEAD on master: `a21f103`.
- Working tree clean.
- `.env` loaded via `set -a && source .env && set +a`.
- A known-good synthesis cluster on `user-justin` exists; reference memory_id from prior runs is `9cbe65bd-301f-444e-9bf3-f814b4f6d5ca` (from CP8 P2 Chain B). CC may pick any active cluster on user-justin — list via `psql` first.

---

## Steps (single linear sequence)

### 1. Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git fetch origin
git checkout master
git pull origin master
git status                              # clean
git log -1 --oneline                    # confirm a21f103 or descendant
git checkout -b cp-synthesis-perf-s1
set -a && source .env && set +a
```

**Halt if:** working tree dirty, master not at a21f103 or descendant, branch already exists.

### 2. Read the writer call graph

```bash
cd /root/.openclaw/workspace/memory-product
wc -l src/synthesis/writer.py src/synthesis/clustering.py src/synthesis/jobs.py 2>/dev/null
grep -n "^def \|^async def " src/synthesis/writer.py
grep -n "^def \|^async def " src/synthesis/clustering.py
```

CC reads the writer end-to-end before instrumenting. Identify the natural phase boundaries — typical synthesis writer has roughly: (a) cluster identification / member fetch, (b) embedding lookups or recomputation, (c) prompt assembly, (d) LLM call, (e) post-processing / source-quote validation, (f) DB writes (synthesis row + audit + cluster_id metadata). The exact phases depend on this codebase's structure; CC's job is to discover them, not assume them.

**Halt if:** writer module structure is materially different from what the scope assumes (>2 hours of restructuring needed to instrument).

### 3. Add phase timing instrumentation

CC's call on implementation, but the constraint is:

- **Non-invasive.** Timing is observation, not behavior change. Do not refactor the writer. Wrap, don't rewrite.
- **Structured output.** Each phase emits `{phase_name: str, start_ts: float, end_ts: float, duration_ms: int, metadata: dict}`. Metadata can carry phase-specific facts (e.g., for the LLM phase: `{model: "claude-haiku-...", input_tokens: int, output_tokens: int}`; for DB writes: `{rows_written: int}`).
- **Accumulator.** A simple in-memory list of phase records that the driver script can read after the writer returns. Easiest pattern: a `PhaseProfile` class (or dict) attached to the writer's call context, or a thread-local; CC's call.
- **Logging.** Each phase end logs a single `INFO` line: `"PROFILE phase=<name> duration_ms=<n> <key=val key=val>"` for grep-ability.

Do NOT add timing to inner loops, tight inner functions, or anything that would generate hundreds of records per run. Phases are the named macro-steps, ~5–10 per run.

```bash
python3 -c "import ast; ast.parse(open('src/synthesis/writer.py').read())"     # GATE
python3 -c "import ast; ast.parse(open('src/synthesis/clustering.py').read())" # GATE
```

**Halt if:** syntax error, or instrumentation requires >150 lines of changes (means you're refactoring, not instrumenting).

### 4. Write the driver script

Create `scripts/profile_synthesis.py`:

- Connects to prod DB (uses `DATABASE_URL` from env).
- Lists existing clusters on `user-justin` namespace; picks one with ≥3 source memories (so the LLM has substance).
- Calls the writer's public entry point on that cluster.
- Captures the phase profile records.
- Writes two files:
  - `docs/profile/synthesis-writer-profile-2026-05-05.json` (raw structured data)
  - `docs/profile/synthesis-writer-profile-2026-05-05.md` (human-readable report)
- The MD report includes: cluster ID, source memory count, total wall-clock, per-phase table (name, ms, % of total), narrative interpretation paragraph.

Driver script must be idempotent and side-effect-free for repeat runs. If the writer creates a new synthesis row in the DB as part of profiling, that's expected and fine — but the script should NOT create artificial test clusters or modify existing ones beyond what the writer normally does.

```bash
python3 -c "import ast; ast.parse(open('scripts/profile_synthesis.py').read())"
```

### 5. Run the profile

```bash
cd /root/.openclaw/workspace/memory-product
mkdir -p docs/profile
python3 scripts/profile_synthesis.py 2>&1 | tee /tmp/profile-run.log
```

Expected output:
- Console: phase-by-phase log lines, total duration, paths to written report files.
- `docs/profile/synthesis-writer-profile-2026-05-05.json` exists.
- `docs/profile/synthesis-writer-profile-2026-05-05.md` exists.

**Halt if:** writer raises an unhandled exception, or total runtime is materially different from the ~3min baseline (could mean we're profiling the wrong code path — investigate before committing).

### 6. Verification gate — profile sanity

```bash
python3 -c "
import json
p = json.load(open('docs/profile/synthesis-writer-profile-2026-05-05.json'))
phases = p['phases']
total_ms = sum(ph['duration_ms'] for ph in phases)
print(f'Phases recorded: {len(phases)}')
print(f'Total accounted: {total_ms}ms')
print(f'Wall-clock: {p[\"wall_clock_ms\"]}ms')
print(f'Coverage: {100*total_ms/p[\"wall_clock_ms\"]:.1f}%')
assert len(phases) >= 4, f'Too few phases: {len(phases)}'
assert total_ms >= 0.7 * p['wall_clock_ms'], f'Phase coverage too low: {100*total_ms/p[\"wall_clock_ms\"]:.1f}%'
print('GATE PASS')
"
```

If phase coverage is below 70%, there's significant un-instrumented work — Stage 1 isn't done. Add timing to whatever's missing and re-run.

**Halt if:** GATE FAIL after one re-instrument attempt.

### 7. Read the report and write the interpretation paragraph

CC reads the generated MD report, identifies the largest phase, and writes a 3–6 sentence interpretation paragraph at the bottom of the MD file. This paragraph names the dominant cost, names the second-largest cost, and lists 2–3 candidate hypotheses for Stage 2 to test.

NO optimization recommendations beyond hypotheses. Stage 2 decides what to fix — Stage 1 decides what's worth investigating.

### 8. Commit

```bash
cd /root/.openclaw/workspace/memory-product
git add src/synthesis/writer.py src/synthesis/clustering.py scripts/profile_synthesis.py docs/profile/
git status                              # only those files staged
git diff --cached --stat
```

Commit message (write to `/tmp/cp-synth-perf-s1-msg.txt`):

```
CP-SYNTHESIS-PERF Stage 1: profile the synthesis writer

Instruments writer + clustering with phase-boundary timing. Driver
script profiles one writer pass against a real user-justin cluster
and emits a structured report.

No behavior changes. No optimization. Stage 2 scope authored from
this report's findings.

Phase coverage: <X>% of wall-clock accounted for.
Dominant phase: <name> (<X>ms, <Y>% of total).
Wall-clock total: <X>ms (cluster <id>, N source memories).

[CC fills in actual numbers from the run]

Files:
- src/synthesis/writer.py (+N lines, instrumentation only)
- src/synthesis/clustering.py (+N lines, instrumentation only)
- scripts/profile_synthesis.py (NEW)
- docs/profile/synthesis-writer-profile-2026-05-05.{json,md} (NEW)
```

```bash
git commit -F /tmp/cp-synth-perf-s1-msg.txt
git log -1 --stat
git push origin cp-synthesis-perf-s1
```

### 9. STATE-LOG entry

```bash
cd /root/.openclaw/workspace/memory-product
cat >> STATE-LOG.md <<'EOF'

## 2026-05-05 — CP-SYNTHESIS-PERF Stage 1 SHIPPED (profile)

Branch: cp-synthesis-perf-s1 (NOT YET MERGED — awaiting operator review of profile report).
Wall-clock total: <X>ms (cluster <id>, N source memories).
Dominant phase: <name>, <Y>% of total.
Report: docs/profile/synthesis-writer-profile-2026-05-05.md

Stage 2 scope to be authored from this report. Branch held until then.
EOF

git add STATE-LOG.md
git commit -m "STATE-LOG: CP-SYNTHESIS-PERF S1 shipped (branch held for review)"
git push origin cp-synthesis-perf-s1
```

**DO NOT MERGE** to master in this chain. Stage 2 builds on this branch; merge happens after Stage 2 lands.

### 10. End-of-run signal

```bash
afplay /System/Library/Sounds/Glass.aiff
```

---

## Halt note format

If halting, write `/root/.openclaw/workspace/memory-product/CP-SYNTHESIS-PERF-S1-BLOCKED.md` with:
- Step number
- Trigger
- HEAD at halt
- What CC tried
- Recommended next move

Do NOT stage uncommitted work on halt.

---

## Definition of done

All of:

1. `src/synthesis/writer.py` and `src/synthesis/clustering.py` have phase-boundary timing.
2. `scripts/profile_synthesis.py` exists and runs cleanly.
3. `docs/profile/synthesis-writer-profile-2026-05-05.{json,md}` exist.
4. Phase coverage ≥70% of wall-clock.
5. ≥4 named phases recorded.
6. Interpretation paragraph written at bottom of MD report.
7. Single commit on branch `cp-synthesis-perf-s1` pushed to origin.
8. STATE-LOG.md updated.
9. No `CP-SYNTHESIS-PERF-S1-BLOCKED.md` exists.
10. No new ERRORs in journalctl modulo known noise.

---

## Standing rules (carry forward verbatim)

All 12 standing rules from prior chains carry forward unchanged. Forbidden-exit regex enforced. Audio chime at end. Branch isolation. Receipts in commit messages. No multi-line python heredocs. No && chains past verification gates.
