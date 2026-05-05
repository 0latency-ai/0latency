# CP-SYNTHESIS-PERF Stage 2.B — Embedding model preload (fix + verify + merge)

**Mode:** Autonomous CC, single task.
**Branch in:** `cp-synthesis-perf-s1` (continue, NOT a new branch).
**Estimated wall-clock:** 30–45 min.
**Predecessor:** Stage 2.A diagnosis at commit `d31abc7`.

---

## Goal (one sentence)

Preload the SentenceTransformer model at FastAPI app startup via a lifespan hook so the synthesis writer's first call hits a warm model instead of paying ~12.5s of cold-load tax, then re-profile against the user-justin validation cluster `b28b7a99fd4791cb` (21 members) to verify the embedding phase drops below 1s and total wall-clock drops below 6s, and merge `cp-synthesis-perf-s1` to master.

## Why this is the only fix needed

Stage 2.A confirmed:
- **Embedding bottleneck (72%) is cold model load only.** Writer embeds ONCE per synthesis (the output atom text), not per cluster member. 21/21 cluster members already have embeddings stored — writer doesn't touch them.
- **LLM model selection is correct.** thomas is Enterprise tier; Sonnet routing is per spec. No fix needed.
- **No batching issue.** No DB-reuse issue. Single root cause: cold model load.

One fix. One mechanism. Measurable before/after.

---

## In scope

- `api/main.py` — add or extend FastAPI `lifespan` context manager to preload the SentenceTransformer model on app startup.
- The embedder module (likely `src/storage_multitenant.py` per memory #6, or wherever Stage 2.A's diagnosis pinned the lazy-load — CC reads diagnosis note for exact path).
- Re-run profile against validation cluster `b28b7a99fd4791cb`.
- Update `docs/profile/synthesis-writer-profile-2026-05-05.md` (or write a new dated file `docs/profile/synthesis-writer-profile-2026-05-05-postfix.md`) with before/after numbers.
- STATE-LOG.md update.
- Merge `cp-synthesis-perf-s1` → master (no-ff merge commit).
- Branch cleanup: delete `cp-synthesis-perf-s1` local + origin.

## Out of scope (DO NOT TOUCH)

- The synthesis writer logic itself — preload is in API startup, not in writer.
- Tier gates (already correct).
- Recall path.
- MCP server.
- Schema migrations.
- Async embedding work (out of scope per S2.A — only revisited if preload doesn't hit the target).
- Any other lazy-loaded dependency that isn't the SentenceTransformer (unless CC observes it adds >2s to first synthesis call — then document but do NOT fix in this chain).

---

## Inputs at start

- Branch: `cp-synthesis-perf-s1`, working tree clean.
- HEAD: `d31abc7` (Stage 2.A diagnosis).
- `.env` loaded.
- Validation cluster: `b28b7a99fd4791cb` (21 members on user-justin).
- Stage 2.A diagnosis at `docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md` — read first to get exact file/line where lazy load happens.

---

## Steps

### 1. Pre-flight

```bash
cd /root/.openclaw/workspace/memory-product
git status                              # clean
git branch --show-current               # cp-synthesis-perf-s1
git log -1 --oneline                    # d31abc7
set -a && source .env && set +a
```

**Halt if:** wrong branch, dirty tree.

### 2. Read the diagnosis note + locate the lazy-load site

```bash
cd /root/.openclaw/workspace/memory-product
cat docs/profile/CP-SYNTHESIS-PERF-S2A-DIAGNOSIS.md
```

Identify from the diagnosis:
- The exact file + function + line where `SentenceTransformer(...)` is instantiated lazily.
- The model name (likely `all-MiniLM-L6-v2`).
- Whether the embedder uses a module-level singleton, a function-local variable, or some other lazy pattern.

### 3. Read the existing FastAPI lifespan (if any)

```bash
cd /root/.openclaw/workspace/memory-product
grep -n "lifespan\|@app.on_event\|startup\|FastAPI(" api/main.py | head -20
```

If a `lifespan` context manager exists, extend it. If not, add one. FastAPI deprecated `@app.on_event("startup")` in favor of `lifespan` — use `lifespan` regardless of which pattern existed before. If old `on_event` hooks exist and migrating them is non-trivial, leave them in place and add a new `lifespan` alongside (FastAPI supports this; both fire).

### 4. Implement preload

Two parts:

**Part A — refactor the embedder to expose a preload entry point.**

In whatever file holds the lazy `SentenceTransformer(...)` call (per Stage 2.A diagnosis), expose a function like:

```python
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        # warm up with one inference so the first real call doesn't pay any deferred init cost
        _embedder.encode(["warmup"], show_progress_bar=False)
    return _embedder

def preload_embedder():
    """Force the embedder to load. Call from FastAPI lifespan startup."""
    get_embedder()
```

If the embedder is already structured as a singleton (just lazy), only add `preload_embedder()` and the warmup line. Don't rewrite working code.

**Part B — call it from FastAPI lifespan.**

In `api/main.py`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    import logging
    logger = logging.getLogger(__name__)
    import time as _t
    _start = _t.time()
    from <embedder_module> import preload_embedder
    preload_embedder()
    logger.info(f"[STARTUP] SentenceTransformer preloaded in {(_t.time() - _start):.2f}s")
    yield
    # shutdown — nothing for now

app = FastAPI(lifespan=lifespan, ...)  # or merge with existing FastAPI(...) call
```

CC adapts the import path to the actual embedder module per Stage 2.A diagnosis.

```bash
python3 -c "import ast; ast.parse(open('api/main.py').read())"
python3 -c "import ast; ast.parse(open('<embedder_file>').read())"
```

**Halt if:** syntax error, or implementing this requires >100 lines of changes (means refactor scope creep).

### 5. Restart memory-api, capture startup time

```bash
systemctl restart memory-api
sleep 60   # generous — preload now adds ~10-15s to startup
systemctl is-active memory-api          # GATE: active
journalctl -u memory-api --since "2 minutes ago" --no-pager | grep -E "STARTUP|preloaded|ERROR" | head -20
```

Expected: a `[STARTUP] SentenceTransformer preloaded in <X>s` line. X should be 10-15s. That's the cost moving from synthesis-time to startup-time, which is correct and expected.

**Halt if:** service inactive, no preload log line, or preload took >30s (something's wrong).

### 6. Re-profile against validation cluster

The driver script from Stage 1 uses ANY cluster, not specifically `b28b7a99fd4791cb`. Either:
- Modify `scripts/profile_synthesis.py` to accept a `--cluster-id` arg AND default to picking the largest user-justin cluster.
- Or pass cluster_id via env var.

CC's call on the mechanism. Whatever's added should be a clean enhancement, not a hack. Then run:

```bash
cd /root/.openclaw/workspace/memory-product
python3 scripts/profile_synthesis.py --cluster-id b28b7a99fd4791cb 2>&1 | tee /tmp/profile-postfix.log
```

(Or env-var equivalent.)

Output should land at `docs/profile/synthesis-writer-profile-2026-05-05-postfix.json` and `.md`.

### 7. Verification gates

**Gate A — embedding phase dropped:**
```bash
python3 -c "
import json
p = json.load(open('docs/profile/synthesis-writer-profile-2026-05-05-postfix.json'))
phases = {ph['phase_name']: ph['duration_ms'] for ph in p['phases']}
emb = phases.get('embedding', 0)
print(f'embedding: {emb}ms (was 12585ms in Stage 1)')
assert emb < 1000, f'GATE A FAIL: embedding still {emb}ms (target <1000ms)'
print('GATE A PASS')
"
```

**Gate B — total wall-clock dropped:**
```bash
python3 -c "
import json
p = json.load(open('docs/profile/synthesis-writer-profile-2026-05-05-postfix.json'))
wc = p['wall_clock_ms']
print(f'wall_clock: {wc}ms (was 17457ms in Stage 1)')
assert wc < 6000, f'GATE B FAIL: total still {wc}ms (target <6000ms)'
print('GATE B PASS')
"
```

**Gate C — second consecutive run is also fast (steady-state warm):**
```bash
python3 scripts/profile_synthesis.py --cluster-id b28b7a99fd4791cb 2>&1 | tee /tmp/profile-postfix-2.log
python3 -c "
import json, glob
files = sorted(glob.glob('docs/profile/synthesis-writer-profile-2026-05-05-postfix*.json'))
# the second run produced its own dated file or overwrote the first; CC uses whichever path is current
p = json.load(open(files[-1]))
wc = p['wall_clock_ms']
print(f'second-run wall_clock: {wc}ms')
assert wc < 6000, f'GATE C FAIL: second run {wc}ms not steady-state fast'
print('GATE C PASS')
"
```

(If the driver script overwrites the postfix file rather than dating both runs, that's fine — the second run's numbers are what matters.)

**Halt if:** any gate fails. The fix isn't doing what we expect; investigate before declaring victory.

### 8. Update profile MD with before/after

Append a section to `docs/profile/synthesis-writer-profile-2026-05-05-postfix.md` (or write a comparison block) showing:

```
## Before / after comparison

| Phase | Stage 1 (cold) | Stage 2.B (preloaded) | Δ |
|-------|---------------|----------------------|---|
| embedding | 12585ms | <X>ms | <Y>x faster |
| llm_call | 4261ms | <X>ms | ~same |
| db_write | 416ms | <X>ms | ~same |
| tenant_load | 98ms | <X>ms | ~same |
| **wall_clock** | **17457ms** | **<X>ms** | **<Y>x faster** |

Startup cost: SentenceTransformer preload now adds ~<X>s to memory-api startup.
This is a one-time cost paid at boot, not per-synthesis.

Steady state: second consecutive run on same cluster: <X>ms wall-clock.
```

### 9. Commit

```bash
cd /root/.openclaw/workspace/memory-product
git add api/main.py <embedder_file> scripts/profile_synthesis.py docs/profile/
git status
git diff --cached --stat
```

Commit message:

```
CP-SYNTHESIS-PERF S2.B: preload SentenceTransformer at app startup

Per Stage 2.A diagnosis: the synthesis writer's 12.5s embedding phase
was 100% cold model load. Writer embeds once per synthesis (output
atom), not per cluster member; source members already have embeddings
stored. Single root cause = lazy SentenceTransformer init on first
call.

Fix: preload model via FastAPI lifespan startup hook with one warmup
inference. Cost moves from per-synthesis to startup (~<X>s added to
boot, paid once).

Verification (cluster b28b7a99fd4791cb, 21 members, user-justin):
- embedding: 12585ms → <X>ms (<Y>x faster)
- wall_clock: 17457ms → <X>ms (<Y>x faster)
- steady state (2nd consecutive run): <X>ms

[CC fills in actual numbers from gates A/B/C]

Files:
- api/main.py — lifespan startup hook
- <embedder_file> — expose preload_embedder() entry point
- scripts/profile_synthesis.py — accept --cluster-id flag
- docs/profile/synthesis-writer-profile-2026-05-05-postfix.{json,md}
```

```bash
git commit -F /tmp/s2b-msg.txt
git log -1 --stat
git push origin cp-synthesis-perf-s1
```

### 10. Merge to master

```bash
git checkout master
git pull origin master
git merge --no-ff cp-synthesis-perf-s1 -m "Merge cp-synthesis-perf-s1: profile + embedding preload (Stage 1 + 2.A + 2.B)"
git log master --oneline -8
git push origin master
```

### 11. Branch cleanup

```bash
git branch -d cp-synthesis-perf-s1
git push origin --delete cp-synthesis-perf-s1
git branch -a | grep cp-synthesis  # should be empty
```

### 12. STATE-LOG entry

```bash
cd /root/.openclaw/workspace/memory-product
cat >> STATE-LOG.md <<'EOF'

## 2026-05-05 — CP-SYNTHESIS-PERF SHIPPED

Synthesis writer latency on user-justin validation cluster
b28b7a99fd4791cb (21 members):
- Before: 17,457ms wall-clock (embedding 12,585ms = 72% cold model load).
- After: <X>ms wall-clock (embedding <Y>ms after preload).
- Improvement: <Z>x faster.

Fix: FastAPI lifespan preload of SentenceTransformer model.
Cold-load cost moved from per-synthesis (paid every call) to
app-startup (paid once at boot).

Stages: S1 (profile) → S2.A (diagnosis, no code) → S2.B (fix + verify + merge).
Branch cp-synthesis-perf-s1 merged to master and deleted.

LongMemEval and Show HN unblocked (writer now sub-6s steady state).
Next chain: Phase 5 (operational surface — redaction cascade,
webhooks, decision journals, calibration, audit access, tier polish).
EOF

git add STATE-LOG.md
git commit -m "STATE-LOG: CP-SYNTHESIS-PERF shipped, Phase 5 unblocked"
git push origin master
git log master --oneline -5
```

### 13. End-of-run signal

```bash
afplay /System/Library/Sounds/Glass.aiff
```

---

## Halt conditions specific to this task

1. **Preload itself raises an exception.** memory-api won't come up. Halt immediately, write blocked note, do NOT mask the error.
2. **Embedding phase doesn't drop below 1000ms after preload.** Diagnosis was wrong about the root cause — investigate before merging.
3. **Total wall-clock doesn't drop below 6000ms.** Some other phase regressed; halt and dump comparison table.
4. **Second consecutive run is materially slower than first.** Means preload isn't sticking (model getting GC'd or per-request reload). Halt.

---

## Halt note format

If halting, write `/root/.openclaw/workspace/memory-product/CP-SYNTHESIS-PERF-S2B-BLOCKED.md`. Do NOT stage uncommitted work.

---

## Definition of done

1. SentenceTransformer preloads at app startup.
2. Embedding phase < 1000ms on validation cluster.
3. Total wall-clock < 6000ms on validation cluster.
4. Steady-state (2nd consecutive run) also < 6000ms.
5. Profile MD updated with before/after comparison table.
6. Commit pushed to `cp-synthesis-perf-s1`.
7. Branch merged to master via `--no-ff`.
8. Branch deleted local + origin.
9. STATE-LOG.md updated and pushed.
10. No `CP-SYNTHESIS-PERF-S2B-BLOCKED.md`.
11. journalctl shows no new ERRORs (modulo known noise).

---

## Standing rules carry forward verbatim
