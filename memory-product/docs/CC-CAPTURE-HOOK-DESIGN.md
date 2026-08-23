# Claude Code capture: hook design brief

**Status: INSTALLED ON THE MAC 2026-08-23 — proven end to end.**
Box (`164.90.156.169`) is deliberately NOT installed. See §0-POST.
Design author: Claude Opus 5 · 2026-08-22 · Pre-flight: Claude Opus 5 · 2026-08-23
Follows: `docs/CAPTURE-COVERAGE-AUDIT.md`

---

## 0-PRE. Pre-flight result, install steps, rollback

Everything below §0 is the original design brief and is unchanged. This
section records what was built and tested against the live API, the one
acceptance criterion that did **not** pass, and the exact commands to install
and to roll back. It is retained as written for provenance; **what was
actually installed, and where, is recorded in §0-POST below.**

### Artifacts (staged, not wired)

| file | role |
|---|---|
| `staging/cc-capture/cc-capture-hook.py` | the `Stop` hook — resolves the turn from `transcript_path`, writes one spool file, exits 0. No network. |
| `staging/cc-capture/cc-capture-drain.py` | the drainer — posts spooled turns to `/memories/extract` (202 path), retries with backoff, keeps a local shipped-key ledger, alerts on drain lag. |

### Pre-flight test results (live API, synthetic transcript, throwaway tenant)

| # | requirement | result |
|---|---|---|
| 1 | hook resolves the turn and spools it | **PASS** — skipped the `tool_result` decoy and the `isSidechain` record, paired `u-0001` with the assistant *text* record `a-0002` (not the `tool_use` record) |
| 2 | dedup key holds across a simulated streaming repost | **PASS** — hook fired 6× on the same turn, spool held exactly 1 file, `turn_key` identical every fire |
| 3 | ledger dedup across a re-spool + re-drain | **PASS** — second drain logged `DEDUP … not re-posting`, ledger stayed at 1 line, no second row written |
| 4 | forced API failure spools to disk and exits 0, never 2 | **PASS** — connection refused → 3 backoff attempts, spool file retained, hook exit 0. Hook also exits 0 on unwritable spool, garbage stdin, and missing transcript |
| 5 | turns land with `agent_id=claude-code` | **PASS** — 3/3 rows |
| 6 | turns land with `source_type=claude_code_mcp` | **PASS** — after the fix in `64255e7`; see below. Originally FAILED as `api_extract` |

Receipt for 5/6 (tenant `ZZ_HOOK_PREFLIGHT`, since dropped):

```
 agent_id    | source_type | memory_type | headline
 claude-code | api_extract | raw_turn    | Raw turn — 2026-08-23 18:37:54 UTC
 claude-code | api_extract | fact        | Kestrel staging deploy key rotates every 90 days
 claude-code | api_extract | fact        | Kestrel staging deploy key stored in ops vault at kestrel/
```

### RESOLVED (was a blocker) — `source_type=claude_code_mcp` on the async path

`X-Client` is sent by the drainer and **ignored**, because the surface tag is
never wired into the async path:

- `api/main.py:888` — `POST /memories/extract` does **not** declare
  `surface: str = Depends(client_surface)`. Only `/extract` (666), `/seed`
  (804), `/batch_extract` (2171), `/bulk_import` (2294) and `/thread_import`
  (2374) do.
- `api/extraction_worker.py:169` — `process_extraction_job` calls
  `extract_memories(..., source="api_extract")`, hardcoded. That value becomes
  `source_type` (`src/extraction.py:641`).

So §6 cost 3 ("attribution is currently impossible") is **still open**, and it
is a stated prerequisite for shipping. The design's own endpoint choice — the
202 async path, correctly chosen for the latency reasons in §3 — is the one
extraction path with no surface plumbing.

**Fixed in `64255e7`** (authorised separately, its own commit): the
`client_surface` dependency was added to `/memories/extract` and the resolved
tag threaded through `process_extraction_job` into `extract_memories(source=...)`,
defaulting to `api_extract` when absent. Re-proved end to end through the full
hook → spool → drain path:

| case | result |
|---|---|
| `X-Client: claude_code_mcp` | row `66462fe7`, `agent_id='claude-code'`, `source_type='claude_code_mcp'` — **PASS** |
| no `X-Client` header | `source_type='api_extract'` (2 rows) — **PASS**, existing callers unaffected |
| `X-Client: totally_made_up` | `source_type='api_extract'` (2 rows) — **PASS**, unrecognised values still fall through |

So §6 cost 3 is closed: Claude Code writes are now distinguishable by both
`agent_id` and `source_type`, and per-surface coverage is measurable.

> **Deploy note.** The worker fleet is 10 units — `zerolatency-worker` plus
> `@1`–`@9`. Restarting only some of them leaves stale workers running the
> previous function signature; that is exactly how the first run of this proof
> failed (`process_extraction_job() takes from 5 to 6 positional arguments but
> 7 were given`, from two workers last started three days earlier). Restart all
> ten, and confirm no worker PID predates the edit.

### Exact install steps — DO NOT RUN WITHOUT REVIEW

Run on the host where Claude Code runs (the Mac for session capture; the paths
below are the box's, adjust `~` accordingly).

```bash
# 1. Confirm the pre-condition holds (expect: {}  and  "No such file")
cat ~/.claude/settings.json; ls ~/.claude/hooks

# 2. Back up settings.json before touching it
cp ~/.claude/settings.json ~/.claude/settings.json.bak-$(date +%Y%m%d-%H%M%S)

# 3. Place the scripts
mkdir -p ~/.claude/hooks ~/.claude/cc-capture/spool
cp /root/.openclaw/workspace/memory-product/staging/cc-capture/cc-capture-hook.py  ~/.claude/hooks/
cp /root/.openclaw/workspace/memory-product/staging/cc-capture/cc-capture-drain.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/cc-capture-*.py

# 4. Wire the Stop hook.  async:true is mandatory (§3); never asyncRewake.
cat > ~/.claude/settings.json <<'JSON'
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/cc-capture-hook.py",
            "async": true,
            "timeout": 5
          }
        ]
      }
    ]
  }
}
JSON

# 5. Drain on a timer (cron shown; systemd timer equivalent is fine)
#    ZERO_LATENCY_API_KEY must be exported in the drainer's environment.
( crontab -l 2>/dev/null; \
  echo '*/10 * * * * ZERO_LATENCY_API_KEY=$(cat ~/.claude/cc-capture/.key) python3 ~/.claude/hooks/cc-capture-drain.py >> ~/.claude/cc-capture/drain.log 2>&1' \
) | crontab -

# 6. Verify on the next real turn
ls -la ~/.claude/cc-capture/spool && tail ~/.claude/cc-capture/hook.log
```

Per §8, item 1 is still worth doing first: the composition of the `Stop`
payload at runtime is inferred from the binary's schema, **not observed**. The
hook degrades safely if `transcript_path` is absent (logs and exits 0), but
confirm it is populated before trusting coverage.

### Exact rollback

Single command — removes the hook wiring, the drain schedule, and the scripts,
leaving `settings.json` as it was:

```bash
cp ~/.claude/settings.json.bak-* ~/.claude/settings.json 2>/dev/null || echo '{}' > ~/.claude/settings.json; \
crontab -l 2>/dev/null | grep -v cc-capture-drain | crontab -; \
rm -rf ~/.claude/hooks/cc-capture-hook.py ~/.claude/hooks/cc-capture-drain.py
```

The spool at `~/.claude/cc-capture/` is left in place deliberately so nothing
captured is lost on rollback; `rm -rf ~/.claude/cc-capture` removes it too.

---

## 0-POST. Install record — 2026-08-23

Installed and verified on **the Mac only** (`MacBook-Air-7.local`,
`/Users/justin/.claude/`). Claude Code runs there; that is the only host where
a `Stop` hook can fire.

### The box is deliberately NOT installed

`root@164.90.156.169:~/.claude/settings.json` is still `{}`, mtime still
2026-05-10, and was never opened for writing. Claude Code has not run on the
box since 2026-05-10 — no binary on `PATH`, no process, no transcript since.
A hook installed there would be inert and would capture nothing, forever.
**Do not "complete" the install by wiring the box.** That is not an omission.

### What deviated from §0-PRE's install steps

| step | as written | as installed | why |
|---|---|---|---|
| 4 | `cat > settings.json <<'JSON'` | merged via `python3`, `hooks` key appended | the Mac's `settings.json` is a live 867-byte config (`mcpServers.jupyter`, `permissions`, `model`, …), not `{}`. The heredoc would have destroyed it. A JSON round-trip was proven byte-identical first, so the merge could not reformat the untouched keys. |
| 4 | `python3 ~/.claude/hooks/...` | `/usr/bin/python3 /Users/justin/.claude/hooks/...` | absolute paths: PATH-independent in the hook's shell, and immune to a Homebrew Python upgrade |
| 5 | cron on the box | cron on the Mac | follows the hook |

### Rollback, corrected for the Mac

§0-PRE's rollback ends `|| echo '{}' > ~/.claude/settings.json`. On the Mac
that is destructive: if the backup were ever missing, it would replace a live
config with an empty object. Use this instead — it removes only the `hooks`
key, needs no backup, and fails loudly rather than truncating:

```bash
/usr/bin/python3 -c "import json;p='/Users/justin/.claude/settings.json';d=json.load(open(p));d.pop('hooks',None);open(p,'w').write(json.dumps(d,indent=2,ensure_ascii=False)+'\n')" && crontab -l 2>/dev/null | grep -v cc-capture-drain | crontab - && rm -f ~/.claude/hooks/cc-capture-hook.py ~/.claude/hooks/cc-capture-drain.py
```

Verified against a copy: output is byte-identical to the pre-install backup.

### KNOWN GAP — `claude -p` does not fire `Stop` hooks

Headless/print mode runs the session and writes a transcript, but the `Stop`
hook is **never invoked**. Tested twice on CLI 2.1.241, with and without
`--max-turns`; `hook.log` never moved and the spool stayed empty. The same
hook fires reliably in interactive sessions.

**Consequence: unattended Claude Code chains are not captured.** Anything
driven by `claude -p` — scripts, cron jobs, CI, agent pipelines — is invisible
to this hook, and the more automated the usage the larger the blind spot.
`docs/CAPTURE-COVERAGE-AUDIT.md` coverage numbers should not be read as
covering headless traffic. Closing this needs a different surface (an
SDK-side wrapper or a drain over transcript files); it is not a tuning issue.

### Cloudflare blocks the urllib default User-Agent

The drainer could not POST at all from the Mac: Cloudflare 403s the default
`Python-urllib/3.x` (Error 1010). Fixed in `e2cdee8`. Pre-flight missed it
because it ran entirely on the box, whose traffic never reaches that edge
path. The same defect was found and fixed in `cli/verify.py` (`3ba7574`),
where it had been breaking the CLI for every customer not on the box. Both
SDKs set or inherit an acceptable User-Agent and are unaffected.

### Proof of capture

Real interactive turn → natural hook fire → cron drain → row:

```
                  id                  |  agent_id   |   source_type   | memory_type
--------------------------------------+-------------+-----------------+-------------
 f99cc1d1-0641-4d47-809d-759685b1b33f | claude-code | claude_code_mcp | raw_turn
```

Verbatim source confirmed through `cli/verify.py` against that id.

---

## 0. Why this document exists

Repairs 3a–3c (this session) fixed the plumbing: the MCP transport was
corrected to SSE, the server was re-enabled for the `/Users/justin` project,
the dead credential was replaced with the live one, and a Claude Code session
wrote the **first row it has ever written** to `memory_service.memories`
(`aa597e09-457b-4290-a090-a26d9df57d7e`, 2026-08-22 20:16:09+00).

That proves the write path works. It does **not** produce capture.

`memory_add` is a tool the model elects to call. Nothing fires it on a turn
boundary. A model concentrating on the actual task will not call it, and the
resulting 0% coverage looks identical to a correct configuration — which is
exactly the failure mode the audit found and which the repair does not
address.

Thomas works because `/root/.openclaw/hooks/memory-extract/handler.js` fires
on `type=message action=received|sent` unconditionally, with no model
involvement. It produced 68% of all captured rows. **That difference — event
versus tool call — is the gap this brief is about.**

---

## 1. The hook surface

`~/.claude/settings.json` is currently `{}` on both the Mac and the box.
`~/.claude/hooks/` does not exist on either. Nothing is installed.

### 1.1 Events that exist

Ten hook events are registered in the installed binary
(`~/.local/share/claude/versions/2.1.240`, Claude Code 2.1.240):

| event | fires | per-turn? |
|---|---|---|
| `SessionStart` | session opens | no — once |
| `UserPromptSubmit` | user submits a prompt | **yes** |
| `PreToolUse` | before each tool call | yes, but ~20× per turn |
| `PostToolUse` | after each tool call | yes, but ~20× per turn |
| `Notification` | permission/idle notifications | irregular |
| `Stop` | main agent finishes responding | **yes — one per response** |
| `SubagentStart` / `SubagentStop` | subagent lifecycle | per subagent |
| `PreCompact` | before context compaction | rare |
| `SessionEnd` | session closes | no — once |

### 1.2 Payload vocabulary

The following payload keys are present in the binary's hook schema:
`hook_event_name`, `session_id`, `transcript_path`, `cwd`, `permission_mode`,
`tool_name`, `tool_input`, `tool_response`, `prompt`, `trigger`, `source`,
`reason`, `stop_hook_active`, `last_assistant_message`.

Mapped to events:

| event | carries |
|---|---|
| `UserPromptSubmit` | `prompt` — **the verbatim user text**, plus `session_id`, `transcript_path`, `cwd` |
| `Stop` | `stop_hook_active`, `last_assistant_message`, `session_id`, `transcript_path`, `cwd` |
| `PreToolUse` | `tool_name`, `tool_input`, + common fields |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, + common fields |
| `PreCompact` | `trigger`, `custom_instructions` |
| `SessionStart` | `source` |
| `SessionEnd` | `reason` |

> **Evidence grade.** Event names and schema field names are read directly out
> of the 2.1.240 binary and are reliable. The exact *composition* of each
> event's JSON at runtime is inferred from that schema, **not observed** — no
> hook was installed, per the no-implementation constraint. §8 lists this as
> the first thing to confirm, and it is cheap to confirm.

### 1.3 Config shape, and the field that matters

Each hook entry supports `command`, `timeout`, `matcher`, and three flags that
decide whether capture can ever be safe:

- **`async`** — *"If true, hook runs in background without blocking."*
- **`asyncRewake`** — *"If true, hook runs in background and wakes the model on
  exit code 2 (blocking error). Implies async."*
- `once` — *"If true, hook runs once and is removed after execution."*

`async: true` is the single most important field in this document. See §3.

---

## 2. Which event gives verbatim turn pairs

**No single event carries both halves of a turn.**

- `UserPromptSubmit` carries the user's text verbatim in `prompt`, but fires
  *before* the assistant has said anything.
- `Stop` fires once when the assistant finishes, and carries
  `last_assistant_message` — but the user prompt that caused it is not in the
  payload.

Both carry `transcript_path`. So there are two viable shapes:

**(a) `Stop` alone, reading the transcript.** One fire per response. Read the
JSONL at `transcript_path`, walk back from the tail to the preceding real user
prompt, emit the pair. Complete, verbatim, single-fire.

**(b) `UserPromptSubmit` + `Stop`, paired in a sidecar.** Mirrors Thomas's
`received`/`sent` pairing. Requires holding state between two processes and
handles the abandoned-turn case badly (user prompts, session is killed, `Stop`
never fires, the half-turn leaks).

**(a) is correct.** `Stop` is the only event that is exactly one-per-response
and has access to both halves.

### What `Stop` misses

1. **Aborted responses.** User hits escape mid-stream → no `Stop`. That turn is
   lost. Acceptable: an interrupted answer is usually not worth storing.
2. **Subagent work.** Sidechain turns fire `SubagentStop`, not `Stop`. Over the
   measured 7 days this Mac logged **zero** sidechain records, so it is not
   currently material — but a workflow-heavy week would hide all delegated
   reasoning from capture.
3. **Tool detail.** `Stop` sees the final assistant message. The 1,372 tool
   calls that produced it are in the transcript but not in the payload. This is
   a feature, not a loss — see §5.
4. **Compaction.** If a session compacts mid-way, `transcript_path` still holds
   the full JSONL, so history is not lost to the reader. `PreCompact` is not
   needed for capture.

---

## 3. Failure behavior — capture must never block

This is the constraint that kills the obvious design.

Measured latency of the extraction endpoints on this box, last 30 days
(`memory_service.api_usage`):

| endpoint | calls | p50 | p95 | max |
|---|---:|---:|---:|---:|
| `/extract` (synchronous) | 190 | **6,130 ms** | **22,824 ms** | **130,961 ms** |
| `/memories/extract` (202 async) | 56 | 0 ms | 9,062 ms | 29,196 ms |

A `Stop` hook that calls `/extract` inline adds **six seconds to the median
response and twenty-three seconds at p95**, every turn. At the observed maximum
it would hang the session for over two minutes. That is not a capture system,
it is a tax on every interaction.

Worse, a default (synchronous) hook that fails does not fail quietly:

- non-zero exit → error surfaced to the session,
- **exit code 2 → treated as a *blocking error*; on `Stop` the model is told it
  cannot stop and the stderr is fed back to it.**

So a naive implementation converts "the memory API is down" into "Claude will
not stop responding." The capture system must be incapable of that.

### Required failure posture

1. **`async: true`, always.** The hook returns immediately; the session never
   waits on the network. Never `asyncRewake` — waking the model on a capture
   failure is precisely the coupling to avoid.
2. **Never exit 2.** Capture has no opinion the model needs. Exit 0
   unconditionally; log failures to a file.
3. **Write to disk first, ship separately.** The hook's only job is to append
   the turn to a spool directory — a local file write, sub-millisecond, no
   network. A separate drainer posts to `/memories/extract` (the 202 path,
   never the synchronous one) and retries. This is exactly Thomas's
   architecture: `handler.js` queues to `queue/`, `turn_hook.py` ships it.
4. **API down = spool grows.** Nothing user-visible. Bounded — see §5.
5. **Set a short `timeout` anyway** as a backstop against a wedged spool write.

> Note the cautionary detail from Thomas's own queue: it holds 305 files, newest
> `2026-08-20 21:09`, and has captured nothing for ~24h *while still firing*.
> A spool that silently stops draining looks exactly like a spool that has
> nothing to do. Whatever is built here needs drain-lag alerting, not just a
> spool.

---

## 4. Dedup and turnKey under streaming

The brief is right to flag this. The Chrome extension's defect is worth stating
precisely, because the lesson is not the one the phrase "unstable turnKey"
suggests.

`0latency-chrome-extension/content/observer.js` installs a `MutationObserver`
over `document.body` with `{childList: true, subtree: true, characterData:
true}`. Every mutation calls `checkForNewMessages(node)` →
`queueMessages(...)` → `processQueue()`, which posts. **There is no dedup key
at all** — no `Set` of processed ids, no guard. During a streaming reply the
DOM mutates once per token-ish, so the same message is enqueued and re-posted
tens of times. The identity of a turn was implicitly "the current text of this
DOM node," which changes continuously. That is why it duplicates.

**Claude Code does not have this problem, and the design must not import it.**
`Stop` fires once, after the response is complete. There is no streaming
partial state at the hook boundary. Dedup is therefore a *safety net against
retry*, not a core mechanism.

### Proposed turn key

```
turn_key = sha256(session_id ‖ assistant_message_uuid)
```

The transcript JSONL assigns every record a stable `uuid`, fixed at write time
and never mutated. Keying on the assistant record's `uuid` gives an identifier
that is:

- **stable** — assigned once, never rewritten (unlike DOM text),
- **unique per turn** — no collision across sessions or restarts,
- **idempotent under retry** — the drainer can re-post the same spool file
  safely,
- **computable offline** — no server round-trip to decide whether to send.

Do **not** key on content hash: identical text in two turns is legitimate and
would be silently dropped. Do **not** key on timestamp: two turns can share a
second.

Enforcement should be belt-and-braces: the spool filename *is* the turn key
(so a double-fire overwrites rather than appends), and the drainer records
shipped keys in a small local ledger. Server-side dedup already exists and will
reinforce rather than insert, but it must not be the only line of defense —
reinforcement silently inflates `recall_count` and corrupts ranking.

---

## 5. Volume, batching, backpressure, cost

### Measured, not estimated

From `~/.claude/projects/*/*.jsonl` on this Mac, 7-day window:

| metric | value |
|---|---:|
| main-thread records | 4,246 |
| sessions | 20 |
| **real human prompts** | **69** |
| `tool_result` records (masquerading as `user`) | 1,372 |
| assistant records containing `tool_use` | 1,372 |
| assistant records containing text | 554 |
| sidechain (subagent) records | 0 |
| payload size p50 / p90 / p99 / max | 665 B / 3.6 KB / 32 KB / 642 KB |
| total transcript volume | 11.0 MB |

### The correction this forces

The audit's headline — *"6,778 user+assistant turns, 925 today"* — counts
transcript records. **Records are not turns.** Twenty of every twenty-one
"user" records are `tool_result` payloads the harness generated, and the
majority of "assistant" records are `tool_use` blocks, not prose. This session
is representative: 2 real prompts, 88 tool results.

The actual conversational volume is **69 human prompts and ~554 assistant text
blocks per week** — roughly **10 turns per day**, not 925.

That changes the engineering entirely:

- **Batching is unnecessary.** Ten spool files a day does not need batching.
  Batching would add latency-to-durability and a partial-failure story for no
  benefit. Ship one turn per request.
- **Cost is negligible.** ~70 extractions/week at the async endpoint.
- **Backpressure is about correctness, not throughput.** The spool will never
  be large. Cap it anyway (e.g. 5,000 files / 500 MB) and drop *oldest-first*
  with a logged counter, so a drain outage degrades visibly instead of filling
  the disk — this box has had a disk emergency before
  (`HANDOFF-2026-05-14-DISK-EMERGENCY.md`).
- **Do not capture tool traffic.** Capturing `PreToolUse`/`PostToolUse` would
  turn ~10 meaningful turns/day into ~200 rows/day of `tool_result` JSON, bury
  the signal, and inflate the corpus that recall has to rank. The audit already
  notes recall quality problems; feeding it tool plumbing makes them worse.

---

## 6. Recommendation

**Install a single `Stop` hook, `async: true`, that spools the turn to disk and
exits 0. Drain the spool from a separate scheduled process that posts to
`/memories/extract`.**

Concretely:

| decision | choice |
|---|---|
| event | `Stop` only |
| mode | `async: true`; never `asyncRewake` |
| hook work | resolve the turn from `transcript_path`, write one spool file named by `turn_key`, exit 0 |
| network in hook | none |
| drainer | separate process (cron/systemd timer), posts to `/memories/extract` (202), retries with backoff |
| turn key | `sha256(session_id ‖ assistant_uuid)` |
| scope | main thread now; revisit `SubagentStop` when sidechain volume is non-zero |
| tool events | not captured |

### The tradeoff, stated

**What this buys.** Capture stops being discretionary. It fires on every
completed response whether or not the model is thinking about memory, which is
the only property that distinguishes Thomas's working path from the MCP path
that has produced zero rows for the entire life of the product.

**What it costs.**

1. **Fidelity.** `Stop` gives the final assistant message and the preceding
   prompt. The reasoning and the 20:1 tool traffic that produced the answer are
   not captured. For a turn like this session's, the stored memory would be the
   brief and the summary — not the diagnostic path that found the psycopg2
   status divergence. That is a real loss, and it is the right trade: the
   alternative buries the corpus.

2. **A new silent-failure surface.** Moving capture off the session's critical
   path is what makes it safe, and is also what makes it possible for capture to
   stop without anyone noticing — the exact failure Thomas's queue is exhibiting
   right now (305 files, 24h stale, still firing). **Drain-lag monitoring is not
   optional; it is part of the deliverable.** Recommend alerting on
   `max(spool_file_age) > 1h` and on zero rows in 24h for the CC `agent_id`.

3. **Attribution is currently impossible.** The proof row landed as
   `agent_id='default'`, `source_type='api'` — indistinguishable from
   Chrome-extension traffic. Before this ships, Claude Code writes need their
   own `agent_id` (and ideally a `source_type`), or coverage can never be
   measured per surface again. This is a prerequisite, not a nicety.

4. **Aborted turns are lost.** Accepted.

**Rejected alternatives.** `UserPromptSubmit`+`Stop` pairing (leaks half-turns,
duplicates Thomas's statefulness for no gain). Synchronous hook (6s p50 tax,
and exit-2 can refuse to let the session stop). `PostToolUse` capture (20× the
volume, near-zero signal). MCP `memory_add` as the primary path (discretionary —
this is the thing being replaced).

---

## 7. Explicitly out of scope

Per the governing brief, this document does not touch: the similarity floor or
any recall threshold; the Stage 1 supersession dry run; benchmark numbers or the
benchmark tenant; API key rotation; the Chrome extension.

---

## 8. Confirm before building

1. **Fire a throwaway `Stop` hook that only appends its stdin JSON to a log**,
   and read one real payload. Confirms §1.2 — specifically whether
   `last_assistant_message` is populated on `Stop` and whether it is the full
   text or a summary. Everything in §2 depends on this and it is ~10 minutes.
2. Confirm `async: true` hooks genuinely do not delay session teardown when the
   command sleeps.
3. Decide the `agent_id` / `source_type` for Claude Code writes (§6, cost 3).
4. Decide spool location and drain cadence; decide whether the drainer is a
   systemd timer on the Mac or whether turns ship to the box for draining.

**HALT — awaiting review.**
