# CP10 Phase 1 — Wrapper Foundation (Claude Code, macOS/Linux)

**Date authored:** 2026-05-08
**Author:** Opus (chat) for CC (Sonnet) execution
**Source material:** `ROADMAP-UNIFIED-v2-CP10-CLI-CAPTURE.md` Phase 1 + `CHECKPOINT-10-SCOPE.md`
**Sequencing:** CP10 P1 *scope* authored before CP9 P1 ships; CP10 P1 *execution* gated on CP9 P1 install paths existing. Scope doc is safe to lock now; CC kickoff waits for CP9 P1 close.
**Estimate:** 1.5 weeks active build (matches roadmap)
**Repo target:** NEW — `0latency-ai/0latency-cli` (separate from `mcp-server` and `0latency` main)

---

## Strategic frame (locked)

> *Enterprise drives architecture, consumer drives surface.*
> CP10 is the **developer-employee surface** that ties bottoms-up CLI adoption to the enterprise memory plane procurement is buying. P1 ships the smallest credible wedge: a working PTY wrapper for Claude Code on macOS/Linux that writes verbatim atoms either locally (sqlite, free tier) or to `api.0latency.ai/atoms` (paid tiers). Symmetric to the Chrome extension's DOM observer — passive, verbatim, agent-agnostic, no agent cooperation required.

**What P1 is:** A working wrapper for *one* agent (Claude Code) on *two* OSes (macOS, Linux), with verbatim role-tagged atom writes, OAuth device-code auth, and a local-first sqlite path. Performance < 50ms p95 verified on a 30-minute real session.

**What P1 is NOT:** Codex, Gemini CLI, Aider (those are P2). Windows (P4). Crash recovery, large-paste handling, backpressure (P3). Tier-matrix server-side enforcement of CLI-specific tier gates (P4). Documentation site `docs.0latency.ai/cli` (P4).

---

## Locked decisions (P1 only)

| # | Decision | Locked value | Why |
|---|---|---|---|
| 1 | Primary language | Python 3.11+ | Matches Chrome extension tooling, FastAPI server, and `mcp-server`. One repo, one build pipeline. npm distribution wraps the Python binary in P4 — **NOT P1**. |
| 2 | PTY library | stdlib `pty` + `os` + `select` (POSIX) | Zero deps for the hot path. macOS + Linux both POSIX-clean. Windows comes via `winpty` shim in P4. |
| 3 | Atom write contract | Existing `POST /atoms` endpoint, no schema changes | Wrapper is a client. Server is unchanged. Means CP10 P1 ships zero migrations. |
| 4 | Local-first storage | sqlite at `~/.0latency/local.db`, schema mirrors server `memories` table subset | Same atom shape on both sides, so future sync (P3+) is a row-copy, not a translation. |
| 5 | Auth flow | OAuth 2.0 device-code grant against new `/oauth/device` endpoint | Standard, terminal-friendly, no localhost callback server needed. **Server-side endpoint is in scope for this CP10 P1 execution chain — see Task 5.** |
| 6 | Credential storage | `~/.0latency/credentials` JSON, mode `0600`, owned by user | Symmetric with existing `.env` discipline. No keychain integration in P1 (P4 polish). |
| 7 | Default write target | `--local` for unauthed; cloud (`api.0latency.ai`) for authed; explicit `--local` flag forces local even when authed | Local-first invariant. User can always opt out of cloud. |
| 8 | Role detection scope | Claude Code only, hardcoded for P1 | Profile abstraction is P2's deliverable. P1 keeps it inline; refactor lands when it's needed for the second agent. |
| 9 | ANSI handling | Strip for `content`, preserve raw for `content_raw` | Strip lets recall search work; raw preserves verbatim invariant. Both fields ship from day one. |
| 10 | Performance budget | < 50ms p95 per turn, measured over 100-turn session | Hard target. Wrapper that adds visible lag fails the trust test. |
| 11 | Atom batching in P1 | None — write each atom synchronously | P3 adds batching + queue + backpressure. P1 keeps the failure modes obvious. |
| 12 | Scope of license | MIT, repo public from day one | Trust signal. Wrapper code is the most-scrutinized surface in the stack. |
| 13 | Telemetry | None in P1 | Opt-in telemetry is P4. Default-off forever. |

---

## Decision lens (apply to every implementation choice in CC chain)

When in doubt, ask in this order:

1. **Does this preserve the verbatim invariant?** If atoms might be summarized, transformed, or dropped silently — STOP. The wrapper exists *because* agent-decided `memory_add` is unreliable; replicating that unreliability defeats the purpose.
2. **Does this break the user's terminal experience?** If the user can tell a wrapper is present (lag, misrendered output, dropped keystrokes), the wrapper is broken regardless of what it captured.
3. **Would Mem0 ship this?** Mem0's wedge is consumer-onboarding-strong, cross-surface-weak. CP10 widens that weakness. If a decision makes the wrapper feel more like a Mem0 add-on (cloud-only, opaque, agent-coupled), reverse it.
4. **Does this require server changes that aren't already in scope?** If yes, push the change to a server-side branch; do NOT add server work to the wrapper repo's PR.
5. **Local-first or cloud-first?** Default local. Cloud is the upgrade path, never the requirement.

---

## Tasks (8, sequenced for CC execution)

Each task has: goal, exact commands, gate, and halt conditions. CC executes sequentially. Independent verification (DB row, file output, curl receipt) required at every gate — no summary claims.

### Task 1 — Repo skeleton + Python package layout

**Goal:** New repo `0latency-ai/0latency-cli`, MIT license, `pyproject.toml`, runnable `0latency --version` command.

**Steps:**

1. SSH: `gh repo create 0latency-ai/0latency-cli --public --license mit --description "Verbatim CLI capture wrapper for Claude Code, Codex, Gemini CLI, Aider"`
2. Clone locally on the server: `cd /root && git clone git@github.com:0latency-ai/0latency-cli.git && cd 0latency-cli`
3. Create package layout:
   ```
   0latency-cli/
   ├── pyproject.toml
   ├── README.md (one paragraph + install)
   ├── LICENSE (MIT — generated by gh repo create)
   ├── src/
   │   └── zerolatency_cli/
   │       ├── __init__.py
   │       ├── __main__.py        # entry point
   │       ├── cli.py             # argparse / click — TBD in Task 2
   │       ├── wrapper.py         # PTY loop — Task 3
   │       ├── profiles.py        # Claude Code role detection — Task 4
   │       ├── auth.py            # OAuth device-code — Task 5
   │       ├── storage.py         # sqlite + http write paths — Task 6
   │       └── atom.py            # atom dataclass + serialization
   └── tests/
       └── test_smoke.py          # `0latency --version` returns 0
   ```
4. `pyproject.toml`: package name `0latency-cli`, entry point `0latency = "zerolatency_cli.__main__:main"`, Python `>=3.11`, deps `httpx`, `click` (for `0latency` CLI), `platformdirs` (for `~/.0latency` cross-OS-correct path).

**Gate G1:**
```bash
cd /root/0latency-cli
pip install -e . --break-system-packages
0latency --version | grep -q "0latency-cli" && echo "G1 PASS"
```

**Halt:** entry point not registered, `pip install -e` fails, `0latency` not on PATH after install.

---

### Task 2 — CLI surface (`0latency login`, `0latency claude`, `0latency status`)

**Goal:** CLI parses three subcommands. `claude` is the wrapped-agent command. `login` and `status` are stubs that print "not implemented" — they get filled in by Tasks 5 + 7.

**Steps:**

1. `cli.py` uses `click`. Three subcommands:
   - `0latency claude [agent_args...]` — runs wrapper around `claude` (Claude Code binary). All args after `claude` pass through to the agent verbatim.
   - `0latency login` — stub for Task 5.
   - `0latency status` — stub for Task 7.
2. Add `--local` flag at top level (overrides cloud writes when authed).
3. Add `--explain` dry-run flag — prints what would be captured without running the agent. P1 implements as a 3-line "would wrap claude with role detection profile X" stub; P4 makes it useful.
4. Help text on each subcommand. README updated with usage.

**Gate G2:**
```bash
0latency claude --help | grep -q "claude" && echo "G2.1 PASS"
0latency login --help | grep -q "login" && echo "G2.2 PASS"
0latency status --help | grep -q "status" && echo "G2.3 PASS"
0latency --local claude --help | grep -q "local" && echo "G2.4 PASS"
```

**Halt:** any subcommand missing, `--local` not recognized, `--help` exits non-zero.

---

### Task 3 — PTY-based stdio interception

**Goal:** `wrapper.py` spawns the Claude Code binary in a pseudo-terminal, tees stdin and stdout cleanly, and exits with the child's exit code. User cannot tell a wrapper is present.

**Steps:**

1. Use `pty.fork()` to create child + master fd. In child, `os.execvp("claude", argv)`.
2. In parent, `select.select()` on `[sys.stdin, master_fd]`:
   - Data on `sys.stdin` → write to `master_fd` (user input → agent).
   - Data on `master_fd` → write to `sys.stdout` AND tee to capture buffer.
3. Capture buffer is a rolling byte buffer. Role detection (Task 4) parses it incrementally.
4. Set `master_fd` to non-blocking. Handle `EIO` (child exit) cleanly — `os.waitpid()`, exit with child's status code.
5. Restore terminal state on exit (raw → cooked) using `termios` save/restore.
6. Pass through SIGWINCH (window resize) to child.

**Gate G3:**
- Run `0latency claude` interactively, type `echo hello`, see exact same output as running `claude` directly. Capture transcript at `/tmp/cp10-p1-g3-transcript.txt` for human review.
- Pipe a 10K-line file through stdin: `cat /tmp/big.txt | 0latency claude`. Verify zero data loss (md5 the input vs the agent's view of input — requires a test profile that echoes input).
- Exit code: `0latency claude false; echo $?` returns 1. `0latency claude true; echo $?` returns 0.

```bash
# G3.1 — passthrough fidelity
diff <(echo "test" | claude --some-noop-flag 2>&1) <(echo "test" | 0latency claude --some-noop-flag 2>&1) && echo "G3.1 PASS"
# G3.2 — exit code propagation
0latency claude --invalid-flag-that-causes-exit-2 2>/dev/null; [ $? -eq 2 ] && echo "G3.2 PASS"
```

**Halt:** any byte difference between wrapped and unwrapped output, exit code not propagated, terminal left in raw mode after exit, SIGINT (Ctrl-C) not handled cleanly.

---

### Task 4 — Claude Code role detection (hardcoded)

**Goal:** Parse Claude Code's rendered output stream into role-tagged atoms: `user`, `assistant`, `tool_use`. Atoms emit to a callback (Task 6 wires this to storage).

**Approach (P1, hardcoded — abstraction is P2):**

Claude Code's output has identifiable structures:
- User input echo: prompt sigil (e.g., `> `) at line start in interactive mode, OR full message before first response chunk in `--print` mode.
- Assistant streaming output: continuous text between user input and the next prompt sigil.
- Tool-use blocks: Claude Code renders tool calls with delimiters like `⏺ Tool: name(args)` and `⎿  output` (verify exact strings against current Claude Code version — DO NOT guess; run a real session and copy the bytes).
- ANSI: stripped from `content`, preserved in `content_raw`.

**Steps:**

1. **First, capture ground truth.** Run a 5-turn Claude Code session manually with `script -q /tmp/claude-truth.log claude`. Inspect `/tmp/claude-truth.log` to see the EXACT delimiters used by the current Claude Code version. Document them in `profiles.py` as constants with the version string.
2. Implement a streaming parser: state machine over the byte stream that emits `Atom(role, content, content_raw, timestamp, tool_payload?)` events.
3. State transitions: `WAITING_FOR_USER → IN_USER → IN_ASSISTANT → IN_TOOL_USE → IN_ASSISTANT → ...`
4. Each atom gets `verbatim=true`, `surface="cli"`, `agent_name="claude-code"`, `agent_version=<extracted from claude --version at startup>`.
5. ANSI stripping: use `re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')` for CSI sequences. Preserve raw bytes in `content_raw`.

**Gate G4:**
- Run `0latency claude --print "what is 2+2"` (or equivalent non-interactive Claude Code call). Verify:
  - Exactly 1 `user` atom with content "what is 2+2".
  - 1+ `assistant` atoms with the model's response text.
  - `content_raw` contains ANSI; `content` does not.
- Run a 5-turn interactive session manually. Inspect emitted atoms in the local sqlite (after Task 6). Each turn produces: 1 user atom, 1 assistant atom, 0+ tool_use atoms. Verify by hand from the captured `script` log.

**Halt:**
- Claude Code's actual delimiters don't match the documented ones — STOP, dump the bytes around the expected delimiter to a halt note, and update `profiles.py` constants from real data, NOT memory.
- Any user input goes uncaptured, OR appears as part of an assistant atom — role boundary detection is wrong, fix before proceeding.
- Tool-use blocks merged into assistant atoms — same failure mode.

---

### Task 5 — OAuth device-code auth flow

**Goal:** `0latency login` runs OAuth device-code grant against `https://api.0latency.ai/oauth/device`, stores token at `~/.0latency/credentials` with mode `0600`. Subsequent `0latency claude` reads the token and uses it on cloud writes.

**Server-side dependency (in scope for this execution chain):**

The server needs a new `/oauth/device` endpoint pair before the wrapper can authenticate. This is **server work, separate PR, separate branch (`cp-p10-1-oauth-device` on the `memory-product` repo), NOT mixed with the wrapper repo**.

Server endpoints required:
- `POST /oauth/device/code` → `{device_code, user_code, verification_uri, expires_in, interval}`. Generates a code pair, stores in a new `oauth_device_codes` table (migration 032).
- `POST /oauth/device/token` → polled by client; returns `{access_token}` once user approves at `verification_uri` (existing dashboard adds an `/auth/device` page that shows `user_code` and a confirm button).

**Migration 032 (server side):**
```sql
CREATE TABLE memory_service.oauth_device_codes (
    device_code TEXT PRIMARY KEY,
    user_code TEXT UNIQUE NOT NULL,
    tenant_id UUID,                          -- NULL until user approves
    expires_at TIMESTAMPTZ NOT NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_oauth_device_user_code ON memory_service.oauth_device_codes(user_code);
```

Tier-1 migration (additive table, reversible). Goes through `bash scripts/db_migrate.sh up`.

**Wrapper-side steps:**

1. `0latency login` calls `POST /oauth/device/code`, prints to stdout:
   ```
   Open https://0latency.ai/auth/device in your browser
   Enter code: ABCD-EFGH
   Waiting for approval...
   ```
2. Polls `POST /oauth/device/token` every `interval` seconds (server returns 5–10s).
3. On approval, server returns `access_token`. Wrapper writes `~/.0latency/credentials`:
   ```json
   {"access_token": "...", "tenant_id": "...", "issued_at": "..."}
   ```
   Mode `0600`. Directory `0700`.
4. `0latency claude` reads credentials at startup; if missing or stale, prints "Run `0latency login` first, or use `--local` for offline capture." and exits 1 (unless `--local` is set, in which case writes go to sqlite without auth).

**Gate G5:**
- Server migration 032 applies cleanly via `bash scripts/db_migrate.sh up`. Reversible: `bash scripts/db_migrate.sh down` removes the table.
- Manual end-to-end: `0latency login` prints code, dashboard `/auth/device` page accepts code, wrapper receives token in < 30s, credentials file exists with mode `0600`.
- `stat -c '%a' ~/.0latency/credentials` returns `600`.
- `cat ~/.0latency/credentials | jq -r .access_token | wc -c` returns > 32 (real token).

**Halt:**
- Migration 032 fails dry-run or wrapping — see AGENTS.md migration discipline rule (P5.7 added it).
- Credentials file mode is anything other than `0600` after write.
- Token request leaks `access_token` to stdout/stderr/logs anywhere — **prime directive, full stop, rotate keys**.
- `~/.0latency/` directory is `0755` instead of `0700` — wrong, fix before proceeding.

---

### Task 6 — Local-first write path + cloud write path

**Goal:** `storage.py` exposes `write_atom(atom: Atom) -> None`. Routes to sqlite (local) or `POST /atoms` (cloud) based on auth state + `--local` flag. Both paths use the same atom shape.

**Steps:**

1. **sqlite schema.** First-run creates `~/.0latency/local.db` with:
   ```sql
   CREATE TABLE atoms (
       id TEXT PRIMARY KEY,                 -- uuid4
       tenant_id TEXT,                      -- NULL in local-only mode
       agent_id TEXT NOT NULL,              -- "claude-code-<session_uuid>"
       role TEXT NOT NULL,                  -- 'user' | 'assistant' | 'tool_use'
       content TEXT NOT NULL,               -- ANSI-stripped
       content_raw BLOB NOT NULL,           -- original bytes
       verbatim INTEGER NOT NULL DEFAULT 1,
       surface TEXT NOT NULL DEFAULT 'cli',
       agent_name TEXT NOT NULL,            -- 'claude-code'
       agent_version TEXT,
       tool_payload TEXT,                   -- JSON, NULL unless role='tool_use'
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       synced_at TIMESTAMP                  -- NULL until uploaded; P3 implements sync
   );
   CREATE INDEX idx_atoms_session ON atoms(agent_id);
   CREATE INDEX idx_atoms_unsynced ON atoms(synced_at) WHERE synced_at IS NULL;
   ```
2. **Cloud path.** `httpx.post("https://api.0latency.ai/atoms", json=atom.to_dict(), headers={"Authorization": f"Bearer {token}"}, timeout=10)`. On non-2xx, log to stderr + write to sqlite as fallback (sets up P3's queue work).
3. **Routing logic:**
   ```
   if --local OR no credentials file:
       write to sqlite only
   else:
       attempt cloud write; on failure, write to sqlite with synced_at=NULL
   ```
4. **Session ID** generated at wrapper startup (`uuid4()`), used as `agent_id` suffix so all atoms in a session group cleanly.

**Gate G6:**
- `0latency --local claude --print "what is 2+2"`: after exit, query sqlite, verify ≥ 2 rows (1 user, 1+ assistant) with correct `role` and non-empty `content`.
- Authed path: same command without `--local`. Atoms appear via `GET /memories?agent_id=claude-code-<session>` on production API. Confirm with curl + `X-API-Key`.
- Cross-tenant isolation check: try fetching the session's atoms with a different tenant's API key — returns 0 rows.

```bash
# G6.1 — local path
0latency --local claude --print "test query 12345" 
sqlite3 ~/.0latency/local.db "SELECT role, content FROM atoms WHERE content LIKE '%12345%';" | grep -q "user" && echo "G6.1 PASS"

# G6.2 — cloud path (requires login first)
SESSION_ID=$(0latency claude --print "test query 67890" 2>&1 | grep -oP 'session=\K[a-f0-9-]+')
curl -s "https://api.0latency.ai/memories?agent_id=claude-code-$SESSION_ID" -H "X-API-Key: $(jq -r .access_token ~/.0latency/credentials)" | jq '.memories | length' | grep -qE "^[2-9]|^[1-9][0-9]" && echo "G6.2 PASS"
```

**Halt:**
- Atoms missing from sqlite after a session — wrapper-to-storage path is broken.
- Cloud writes succeed but atoms invisible via `GET /memories` — agent_id namespacing wrong.
- Cross-tenant isolation fails (another tenant CAN see atoms) — **stop everything, this is a security bug**.
- sqlite db created with mode other than `0600` — fix before proceeding.

---

### Task 7 — `0latency status` command

**Goal:** `0latency status` prints auth state, last successful sync, queued (unsynced) atom count, version. Useful as a debugging primitive and for the demo.

**Output format:**
```
0latency CLI v0.1.0
Auth: logged in as tenant <uuid> (token issued 2026-05-09 14:32 UTC)
Local DB: ~/.0latency/local.db (3,421 atoms, 12 unsynced)
Last cloud sync: 2026-05-09 15:01 UTC (success)
```

If unauthed:
```
0latency CLI v0.1.0
Auth: not logged in (run `0latency login` or use `--local`)
Local DB: ~/.0latency/local.db (3,421 atoms, all local)
```

**Gate G7:**
```bash
0latency status | grep -qE "^(Auth: logged in|Auth: not logged in)" && echo "G7 PASS"
```

**Halt:** secrets (token, tenant key) printed in `status` output anywhere — **rotate keys, full stop**.

---

### Task 8 — Performance benchmark (< 50ms p95)

**Goal:** Measured overhead per turn over a 100-turn session is < 50ms at p95. Benchmark is reproducible and committed to the repo.

**Steps:**

1. Create `tests/bench_overhead.py`. Driver that:
   - Runs 100 turns of `claude --print "compute <random number>"` via `0latency claude`, then 100 turns of bare `claude --print "compute <random number>"`.
   - Measures wall-clock per turn for both. Computes (wrapped - bare) per turn → overhead distribution.
   - Reports p50, p95, p99.
2. Run benchmark on the server (which is the realistic environment).
3. Commit raw timing data to `bench/results-2026-05-XX.json` for transparency.

**Gate G8:**
```bash
cd /root/0latency-cli
python tests/bench_overhead.py --turns 100 --report /tmp/cp10-p1-bench.json
jq -r '.overhead_p95_ms' /tmp/cp10-p1-bench.json | awk '{exit ($1 < 50.0) ? 0 : 1}' && echo "G8 PASS"
```

**Halt:** p95 ≥ 50ms. Profile, find the hot path, fix, re-bench. Common culprits: synchronous httpx writes (move to thread? — P3 problem), excessive ANSI regex compilation, sqlite WAL not enabled.

---

## Verification gate (overall — ALL must pass before P1 complete)

1. ✅ G1–G8 each independently passing with on-server receipts.
2. ✅ A real 30-minute Claude Code session captured end-to-end. All user inputs and assistant outputs preserved verbatim. Tool-call blocks correctly identified. Verified by spot-check on 10 random turns vs `script` log.
3. ✅ Auth flow completes in < 30 seconds for a first-time user (Justin times himself, on camera if for the demo, otherwise just records the wall-clock).
4. ✅ Migration 032 applied to production via `db_migrate.sh up`. Reversible: dry-run shows `BEGIN ... ROLLBACK` only, no inner `COMMIT`.
5. ✅ `0latency-cli` repo public on GitHub, MIT-licensed, README has install + usage.
6. ✅ Cross-tenant isolation verified end-to-end (atoms written by tenant A invisible to tenant B's API key).

**Deliverable:** `CHECKPOINT-10-PHASE-1-COMPLETE.md` in the wrapper repo, with:
- Installer test transcript (raw output of `pip install -e . && 0latency --version`).
- Capture transcript verification (10 spot-checked turns from the 30-minute session, raw bytes side-by-side: `script` log vs sqlite content).
- Performance benchmark JSON + summary table.
- Security checklist receipts (mode `0600` on credentials, `0700` on directory, no token leakage in stderr/logs/status).
- Migration 032 apply + reverse receipts.

---

## Anti-scope (P1 explicitly defers these)

- ❌ Multi-agent profiles (Codex, Gemini CLI, Aider) — P2.
- ❌ Windows support via winpty — P4.
- ❌ Crash recovery + rolling buffer — P3.
- ❌ Atom batching, queue, backpressure — P3.
- ❌ Server-side tier gates for CLI atoms (Free unlimited local; cloud writes already gated by existing tenant tier) — P4 confirms gate behavior.
- ❌ npm distribution (`npm install -g @0latency/cli`) — P4.
- ❌ Documentation site `docs.0latency.ai/cli` — P4.
- ❌ `--explain` dry-run beyond a 3-line stub — P4.
- ❌ Telemetry of any kind — opt-in only, P4 if at all.
- ❌ Profile abstraction refactor — P2.
- ❌ Auto-detection of VS Code/JetBrains terminal — Nice-to-have, P3+ optional.
- ❌ Cursor's chat panel — Different surface, Chrome extension territory, not CP10.

---

## Halt conditions (specific to P1)

In addition to standard protocol halts (paste-safe failures, migration tier-2 escalation, etc.):

1. **Claude Code delimiter format changed since memory was last updated.** If the role-detection profile breaks against current Claude Code, halt — capture real bytes, update constants, do NOT guess from training data.
2. **PTY semantics differ on macOS vs Linux for some edge case.** If a behavior tests pass on one OS and fail on another, halt and document the divergence; do NOT paper over with platform-specific branches in the hot path without operator review.
3. **Performance budget blown by > 20%** (i.e., p95 ≥ 60ms). Halt for architecture review — likely means sqlite or httpx is on the wrong side of the loop.
4. **Token leakage anywhere** — stderr, logs, `0latency status`, error messages, exception tracebacks. **Full stop, rotate keys, fix, write a regression test before proceeding.**
5. **Cross-tenant isolation failure** in G6.2 — security bug, halt, do NOT continue, escalate immediately.
6. **Migration 032 hits Tier-2 territory** (e.g., need to alter an existing column instead of adding a new table) — should not happen given the locked design, but if it does, halt for human apply per migration discipline rule.

---

## Branch + commit plan

**Wrapper repo (`0latency-ai/0latency-cli`):**
- Branch: `cp-p10-1-foundation` off the empty `master` of the new repo.
- One commit per Task (8 commits) for clean reviewability.
- PR `cp-p10-1-foundation → master` after G8 + verification gate clears.
- Tag `v0.1.0` on merge.

**Server repo (`0latency-ai/mcp-server`, in `/root/.openclaw/workspace/memory-product/`):**
- Branch: `cp-p10-1-oauth-device` off `master`.
- Commits:
  1. Migration 032 (`oauth_device_codes` table).
  2. `POST /oauth/device/code` endpoint.
  3. `POST /oauth/device/token` endpoint.
  4. Dashboard page `/auth/device` (existing dashboard, separate file).
  5. Integration tests against real DB (per migration discipline rule).
- PR `cp-p10-1-oauth-device → master` reviewed BEFORE wrapper repo's PR merges (wrapper's auth flow depends on these endpoints being live in production).

**Sequencing:**
1. Server-side OAuth endpoints land first (Task 5's dependency).
2. Wrapper Tasks 1–4 can proceed in parallel with server work (no auth dependency).
3. Wrapper Task 5 lands after server endpoints are deployed.
4. Wrapper Tasks 6–8 finish out the chain.

---

## Rules CC operates under (standard, restated for completeness)

- Lead engineer mode. No middleman.
- `bash scripts/db_migrate.sh up`, NOT direct `alembic upgrade head` (server-side migration only — Task 5).
- `_db_execute_rows`, NOT `_db_execute` (if any server-side DB work touches the existing helpers).
- `python3`, NOT `python`.
- Paste-safe output discipline: NEVER echo `.env` contents, tokens, API keys, or credentials anywhere — stdout, stderr, logs, traces, status output. State "Safe to paste: YES/NO" on every command.
- Independent verification at every gate: DB row, file output, curl receipt. No summary claims.
- AGENTS.md migration discipline rule applies (per P5.7 task 6) — strip inner `BEGIN/COMMIT`, verify dry-run ends with `ROLLBACK`, escalate Tier-2 to operator.
- `set -a && source .env && set +a` before any DB-touching command. Never echo credentials.

---

## Sequencing notes (post-P1)

- **CP10 P2** (multi-agent profiles) starts after P1 verification gate passes. Profile abstraction is a refactor of P1's hardcoded Claude Code parser.
- **CP10 P3** (reliability + edge cases) layers on after P2.
- **CP10 P4** (distribution + polish) closes the chain — Show HN-ready.
- **CP9 P1** (5-minute onboarding) sequences with CP10 P1 — wrapper joins as the fourth install path once both ship.
- **CP11 (universal positioning)** — its "every tool" claim is more credible after CP10 P2 ships (multi-agent capture works). Recommend CP11 launch sequence after CP10 P2, not before.

---

## One-paragraph summary for resumption

CP10 Phase 1 ships a working PTY wrapper for Claude Code on macOS/Linux. Eight tasks, 1.5 weeks, new public repo `0latency-ai/0latency-cli` (MIT), one server-side migration (032 — `oauth_device_codes` table) on a separate branch. Wrapper writes verbatim role-tagged atoms to either `~/.0latency/local.db` (sqlite, free/local mode) or `https://api.0latency.ai/atoms` (cloud, authed mode). OAuth device-code flow for terminal-friendly auth. Performance budget < 50ms p95 over 100 turns, benchmark committed to repo. Hardcoded role detection for Claude Code in P1; profile abstraction is P2. Anti-scope is rigid: no multi-agent, no Windows, no crash recovery, no batching, no docs site — those are P2/P3/P4. Verification gate requires real 30-min session capture, sub-30s auth flow, cross-tenant isolation, mode-0600 credentials, and migration 032 reversibility. Sequenced behind CP9 P1 close (install paths exist) and ahead of CP10 P2 (multi-agent). Strategic frame: this is the developer-employee surface that ties bottoms-up CLI adoption to the enterprise memory plane procurement is buying — Mem0's structural weakness becomes 0Latency's wedge.
