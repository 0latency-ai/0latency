# CP10 Phase 2 — Multi-Agent Profiles (Codex, Gemini CLI, Aider + Generic Fallback)

**Date authored:** 2026-05-08 EOD
**Author:** Opus (chat) for CC (Sonnet) execution
**Source material:** `ROADMAP-UNIFIED-v2-CP10-CLI-CAPTURE.md` Phase 2 + `CP10-P1-AUTONOMY-SCOPE.md` (delivered) + `HANDOFF-2026-05-08-EOD-CP8-CLOSED-CP10-P1-SHIPPED.md`
**Sequencing:** CP10 P1 v0.1.1 SHIPPED 2026-05-08. P2 picks up directly. P1 hygiene chain (PyPI publish prep, GH release, client cross-tenant test, dashboard tracking, interactive parser fix) closed same day.
**Repo target:** `0latency-ai/0latency-cli` (existing, on `main`, HEAD `bb55fcf`, tag `v0.1.1`). Server-side has zero new dependencies for P2.

---

## Strategic frame (locked)

> *The wedge holds where Mem0 and Anthropic-native cannot follow.*
> Anthropic's native Claude Code memory (when/if Chyros ships) will be Claude Code-only — Anthropic cannot credibly ship multi-agent capture because it would mean promoting competitors. Mem0 has zero CLI capture. Open Brain has cross-tool ambitions but takes 30–45 minutes to set up and ships no wrapper. CP10 P2 is what makes the "every CLI agent" claim true — three additional agent profiles (Codex, Gemini CLI, Aider) plus a generic fallback for anything tty-based. Once P2 ships, the universal-positioning pitch in CP11 is grounded in working code, not roadmap promises.

**What P2 is:** A profile abstraction that makes role detection pluggable, four built-in profiles (Claude Code refactored from P1's hardcoded parser, plus Codex, Gemini CLI, Aider), a generic profile fallback for any unknown tty agent, and a profile registry on disk that users can extend or override. Performance budget unchanged: < 50ms p95.

**What P2 is NOT:** Crash recovery, backpressure, large-paste handling (P3). Windows support (P4). npm distribution, docs site, Show HN-ready demo (P4). Cursor's chat panel (Chrome extension territory, not CP10). VS Code / JetBrains terminal auto-detection (nice-to-have, P3+ optional).

---

## Why P2 now

Three reasons, in priority order:

1. **The wedge is the multi-agent claim, not the wrapper itself.** P1 shipped a wrapper that captures Claude Code. That alone is interesting but not differentiated — Anthropic could clone it tomorrow. The Mem0/Anthropic-resistant moat is *capturing every CLI agent the developer touches*. P2 turns the wrapper from "useful" into "structurally unavailable from competitors."
2. **Profile abstraction is upstream of every later P2-style feature.** P3's reliability work, P4's Show HN demo, and CP11's universal positioning all assume profiles are pluggable. Refactoring P1's hardcoded parser into a profile interface is foundational; deferring it means every later checkpoint pays the abstraction cost retroactively.
3. **Real-byte fixture discipline.** CP10 P1 Phase A's main lesson was that CC contradicted itself about whether it had verified against real Claude Code 2.1.136 bytes. P2 has *four* parsers to validate; if we don't capture real bytes from each agent up front and test against them, we will repeat the same failure across four surfaces. P2 Phase A is byte capture — not a polish step, a prerequisite.

---

## Locked decisions (P2 only)

| # | Decision | Locked value | Why |
|---|---|---|---|
| 1 | Profile interface | Python ABC `Profile` with methods `detect_role(buffer: bytes) -> Optional[Atom]`, `is_complete_turn(buffer: bytes) -> bool`, `extract_metadata(buffer: bytes) -> dict` | Subclasses implement; one parser per agent. Buffer-based, not stream-based, so profiles are testable against fixtures. |
| 2 | Profile registry | `~/.0latency/profiles/<name>.py` (built-ins shipped via `0latency_cli/profiles/`, user overrides override built-ins by name) | User-extensible from day one. Built-ins live in package; user dir is precedence. |
| 3 | Generic fallback | `GenericProfile` — captures stdin and stdout as one atom per "turn" (turn = idle period of >2s on stdout) | No role inference, but better than nothing. Fires when agent CLI isn't recognized by name. |
| 4 | Agent detection | Match on parent CLI binary name (`claude`, `codex`, `gemini`, `aider`); fall through to generic | Simple. Same mechanism the wrapper already uses for `0latency claude` subcommand routing. |
| 5 | Tool-call atoms | Codex + Aider profiles tag tool-use blocks the same way Claude Code does (`role=tool_use`, structured `payload`) | Consistent atom shape across agents — same downstream queries work. |
| 6 | Aider-specific atom field | `file_changes: list[{path, diff}]` populated by Aider profile | Aider's value-add is file edits; preserve that signal even when the wrapper is agent-agnostic. |
| 7 | Profile versioning | Each profile has `__version__ = "X.Y.Z"` and `__compat_agent_version__ = "X.Y.Z"` (the agent CLI version it was tested against) | When agent CLIs update their render format, profile bumps + tests run. Documented in `docs/profiles/<agent>.md`. |
| 8 | Fixture capture method | `script` command on the server, real interactive sessions, raw bytes saved verbatim to `tests/fixtures/<agent>-real-session.bytes` | Same lesson as CP10 P1 Phase A — real bytes only, no synthetic fixtures, no training-data guesses. |
| 9 | Fixture session length | ~10 turns per agent, mix of plain text + at least one tool-use / file-edit / multi-line code block | Long enough to surface delimiter edge cases, short enough to hand-validate. |
| 10 | Per-agent unit tests | Each profile has a parametrized pytest that replays its fixture and asserts atom-by-atom role + content correctness | Regression bar — when an agent's CLI updates, the test breaks loudly, not silently. |
| 11 | Agent-CLI install on server | Codex (OpenAI), Gemini CLI (Google), Aider (open-source) all installed on the server during fixture-capture phase; pinned version recorded in `docs/profiles/<agent>.md` | Reproducible captures. Justin/Thomas/Seb can re-run any time. |
| 12 | Performance budget | Unchanged — < 50ms p95 per turn, measured per profile | Same trust bar as P1. Profile abstraction must not introduce overhead; benchmark each profile against P1's Claude Code baseline. |
| 13 | Anti-scope discipline | Anything not on the locked decision list goes to P3 or P4. Profile registry sharing (private repos) is CP10 tier-matrix territory, P4. | P2 is small and complete. P3/P4 are where polish lives. |

---

## Decision lens (apply to every implementation choice in CC chain)

When in doubt, ask in this order:

1. **Does this preserve the verbatim invariant?** Profile must capture what the user saw, not the agent's structured-output JSON. If a profile would read an agent's JSON-RPC stream instead of the rendered terminal output, STOP — that's an integration, not a wrapper. The wrapper's job is "what the user saw."
2. **Does the profile detect the role correctly on real bytes?** Not synthetic fixtures, not training-data guesses about what the agent's output looks like. If you haven't run the agent and captured its stdout, you don't know. CP10 P1 Phase A's lesson must hold here.
3. **Would Mem0 ship this?** Mem0 ships SDK integrations, not wrappers. If a profile choice makes the wrapper feel more like an SDK shim (calling agent APIs directly, requiring agent cooperation), reverse it. Wrappers stay tty-only.
4. **Does the abstraction earn its keep at four profiles?** The profile interface should make adding a fifth profile trivial. If implementing Aider feels like fighting the abstraction, the abstraction is wrong — refactor before continuing.
5. **Local-first or cloud-first?** Unchanged from P1. Default local. Cloud is the upgrade path.

---

## Phases

P2 has two execution phases, run sequentially in CC, on a single branch `cp-p10-2-profiles` off `0latency-cli` `main`.

### Phase A — Real-byte fixture capture (foundation)

**Goal:** All four agents installed on the server, real interactive sessions captured to byte-exact fixture files, version metadata recorded. Phase A produces inputs Phase B's parsers will be tested against.

**Why this is Phase A and not "research before coding":** CP10 P1 Phase A failure mode (CC claiming verification when it had used `/bin/sh` as a stand-in) happened because byte capture was treated as a soft prerequisite. Phase A here is hard: no parser code in Phase B until fixture files exist on disk and have been hand-spot-checked.

### Phase B — Profile abstraction + four profiles + generic fallback (build)

**Goal:** Profile ABC, registry loader, four built-in profiles, generic fallback, parametrized tests, `0latency <agent>` subcommands route to the right profile, performance budget held.

---

## Tasks (10, sequenced for CC execution)

Each task has: goal, exact commands, gate, halt conditions. CC executes sequentially. Independent verification at every gate (file exists, command exit code, test pass, fixture-byte spot-check) — no summary claims.

### Task 1 — Install all four agent CLIs on the server, record versions

**Goal:** `claude`, `codex`, `gemini`, `aider` all runnable from the server's PATH. Versions pinned in `docs/profiles/<agent>.md` files (one per agent, stub initially).

**Steps:**

1. SSH to `root@164.90.156.169`.
2. `export PATH="$HOME/.local/bin:$PATH"` — Claude Code already at `/root/.local/bin/claude`.
3. Verify Claude Code present: `claude --version` → record output.
4. Install Codex: `npm install -g @openai/codex` (or current canonical install path; check `npm view @openai/codex` for latest). Record version: `codex --version`.
5. Install Gemini CLI: `npm install -g @google/gemini-cli` (check current canonical install path). Record version: `gemini --version`.
6. Install Aider: `pip install aider-chat --break-system-packages` (server has no venv for system tools). Record version: `aider --version`.
7. Create stub docs at `docs/profiles/{claude-code,codex,gemini-cli,aider}.md` with sections: "Tested CLI Version", "Render Format Notes" (empty for now), "Known Quirks" (empty), "Profile Compatibility" (empty).

**Gate G1:**
```bash
cd /root/0latency-cli
for agent in claude codex gemini aider; do
  which "$agent" || { echo "G1 FAIL: $agent missing"; exit 1; }
  "$agent" --version 2>&1 | head -1
done
ls docs/profiles/*.md | wc -l   # expect 4
echo "G1 PASS"
```

**Halt:** any agent CLI not installable on this server. If a particular install path is broken upstream, document the blocker in `docs/profiles/<agent>.md` and continue with the remaining three; come back to the missing one when fixable. Do NOT skip silently.

---

### Task 2 — Capture real-byte fixtures for all four agents

**Goal:** Four files at `tests/fixtures/cli-bytes/<agent>-real-session.bytes` containing raw stdout from a real ~10-turn interactive session. ANSI codes preserved. Each fixture has a sibling `<agent>-real-session.expected-atoms.json` documenting what each turn should parse to (hand-authored, used as the test oracle in Task 8).

**Steps for each agent (claude, codex, gemini, aider):**

1. `mkdir -p /root/0latency-cli/tests/fixtures/cli-bytes`
2. Run `script -q -c "<agent>" /root/0latency-cli/tests/fixtures/cli-bytes/<agent>-real-session.bytes` — `script` records raw bytes including ANSI.
3. In the spawned agent, run a 10-turn session. Standard turn template (vary per agent's interaction style):
   - Turn 1: a plain-text question → expect plain-text answer
   - Turn 2: a code-generation request → expect code block
   - Turn 3: a follow-up referencing turn 2 → expect text + maybe code
   - Turn 4: a tool-use trigger if applicable (Aider: file edit; Codex: code interpretation; Gemini/Claude Code: web search or filesystem action)
   - Turn 5: an interruption / partial answer
   - Turns 6–10: mix as natural
4. `exit` cleanly; verify bytes file exists and is > 1KB.
5. Hand-author `<agent>-real-session.expected-atoms.json`:
   ```json
   [
     {"turn": 1, "role": "user", "content_substring": "...first question..."},
     {"turn": 1, "role": "assistant", "content_substring": "...first answer..."},
     ...
   ]
   ```
   Use `content_substring` (not full content) so test is robust against minor whitespace shifts but catches role-detection errors.
6. Commit fixtures: `git checkout -b cp-p10-2-profiles && git add tests/fixtures/cli-bytes/ && git commit -m "Phase A: real-byte fixtures for claude, codex, gemini, aider"`.

**Gate G2:**
```bash
cd /root/0latency-cli
for agent in claude codex gemini aider; do
  bytes_file="tests/fixtures/cli-bytes/${agent}-real-session.bytes"
  json_file="tests/fixtures/cli-bytes/${agent}-real-session.expected-atoms.json"
  [ -s "$bytes_file" ] || { echo "G2 FAIL: $bytes_file missing or empty"; exit 1; }
  [ -s "$json_file" ] || { echo "G2 FAIL: $json_file missing or empty"; exit 1; }
  jq -e 'length >= 10' "$json_file" >/dev/null || { echo "G2 FAIL: $json_file has < 10 atoms"; exit 1; }
done
echo "G2 PASS"
```

**Halt:** any fixture < 1KB (probably empty session), any expected-atoms.json with < 10 atoms (session too short), any agent CLI that crashed mid-capture (re-run, capture clean session, do NOT submit a partial fixture). If a real session genuinely produces fewer than 10 turns for an agent (e.g., agent's UX guides toward a single multi-turn answer), document it in the agent's docs/profiles/<agent>.md and submit the actual session length — but ≥ 5 turns minimum. Below 5 turns, halt.

---

### Task 3 — Document each agent's render format from its real bytes

**Goal:** `docs/profiles/<agent>.md` populated for all four agents with the actual delimiters, prompt sigils, output markers, and quirks observed in the fixture files. This is the spec Phase B's parsers will implement against.

**Steps:**

1. For each agent, read its `<agent>-real-session.bytes` file (use `cat -A` or `xxd` to see control characters). Identify:
   - **Prompt sigil:** the bytes that mark the user's input prompt (e.g., `> ` for many CLIs, `> ` styled differently per agent).
   - **Assistant output start marker:** how the agent signals it's about to respond.
   - **Assistant output end marker:** how the agent signals its response is done (often a return-to-prompt-sigil).
   - **Tool-use block delimiters:** if the agent renders tool-use as distinct blocks (Claude Code does this; Codex may; Aider's file edits are a form of this).
   - **Multi-line input handling:** how the agent shows continued lines.
   - **ANSI quirks:** color codes, cursor moves, line clears that affect parsing.
2. Write each agent's `docs/profiles/<agent>.md` with sections:
   - Tested CLI Version (from Task 1)
   - Render Format Notes (the items above, with example bytes)
   - Known Quirks (anything that will trip naive parsers)
   - Profile Compatibility (what `__compat_agent_version__` should be set to)
3. Commit: `git add docs/profiles/ && git commit -m "Phase A: render format docs from real-byte analysis"`

**Gate G3:**
```bash
cd /root/0latency-cli
for agent in claude-code codex gemini-cli aider; do
  doc="docs/profiles/${agent}.md"
  for section in "Tested CLI Version" "Render Format Notes" "Known Quirks" "Profile Compatibility"; do
    grep -q "$section" "$doc" || { echo "G3 FAIL: $doc missing section '$section'"; exit 1; }
  done
  # Each doc should reference at least one byte-level example (look for backticks around hex or escape codes)
  grep -qE '`(\\x|\\033|\\u00|\\e\[)' "$doc" || { echo "G3 FAIL: $doc has no byte-level examples"; exit 1; }
done
echo "G3 PASS"
```

**Halt:** any agent's render format is so close to another's that the same parser would handle both with identical regex (means the abstraction isn't earning its keep — re-examine fixtures and find the real differentiator). Any agent's bytes are unparseable by inspection (means the wrapper would need to read structured output, not rendered output — escalate to operator review).

---

### Task 4 — Profile ABC + registry loader

**Goal:** `0latency_cli/profiles/__init__.py` defines the `Profile` abstract base class and the registry loader. P1's hardcoded Claude Code parser is NOT yet refactored — that's Task 5. This task establishes the contract.

**Steps:**

1. Create `0latency_cli/profiles/base.py`:
   ```python
   from abc import ABC, abstractmethod
   from dataclasses import dataclass
   from typing import Optional

   @dataclass
   class Atom:
       role: str  # "user" | "assistant" | "tool_use"
       content: str
       content_raw: bytes
       metadata: dict

   class Profile(ABC):
       __version__: str = "0.0.0"
       __compat_agent_version__: str = "unknown"
       agent_name: str = ""  # e.g., "claude-code"

       @abstractmethod
       def detect_role(self, buffer: bytes) -> Optional[Atom]: ...

       @abstractmethod
       def is_complete_turn(self, buffer: bytes) -> bool: ...

       def extract_metadata(self, buffer: bytes) -> dict:
           return {}
   ```
2. Create `0latency_cli/profiles/__init__.py` with a registry loader:
   ```python
   def load_profile(agent_name: str) -> Profile:
       # 1. Check ~/.0latency/profiles/<agent_name>.py (user override)
       # 2. Fall back to built-in 0latency_cli/profiles/<agent_name>.py
       # 3. If neither exists, return GenericProfile()
   ```
3. Built-in profiles live at `0latency_cli/profiles/{claude_code,codex,gemini_cli,aider,generic}.py` (created as stubs in this task; implemented in Tasks 5–9).
4. Add unit tests at `tests/test_profile_registry.py`:
   - Loads built-in profile by name → returns correct subclass
   - User override at `~/.0latency/profiles/claude_code.py` takes precedence
   - Unknown agent name returns `GenericProfile`
   - `Profile` ABC cannot be instantiated directly

**Gate G4:**
```bash
cd /root/0latency-cli
pytest tests/test_profile_registry.py -v
echo "G4 PASS"
```

**Halt:** any test failure. ABC contract bugs surface here, not in agent profile work — fix at the contract level.

---

### Task 5 — Refactor P1's Claude Code parser into `ClaudeCodeProfile`

**Goal:** P1's hardcoded role detection (in `wrapper.py` or wherever P1's hygiene chain landed it) becomes `0latency_cli/profiles/claude_code.py` implementing `Profile`. Existing P1 tests still pass. New parametrized test added that replays the Claude Code fixture from Task 2 and asserts atom-by-atom correctness.

**Steps:**

1. Read current state of P1's parser. Likely lives in `wrapper.py` or `0latency_cli/parser.py`. Locate via: `grep -rn "role_detect\|detect_role\|claude_code" 0latency_cli/`.
2. Move logic into `0latency_cli/profiles/claude_code.py`. Replace direct calls in `wrapper.py` with `profile = load_profile("claude-code"); atom = profile.detect_role(buffer)`.
3. Update `wrapper.py` to look up the profile based on the agent CLI being wrapped (`0latency claude` → `claude-code` profile; `0latency codex` → `codex` profile; etc.).
4. Run all existing P1 tests — must still pass.
5. Add `tests/test_claude_code_profile.py` with a parametrized test that:
   - Loads `tests/fixtures/cli-bytes/claude-real-session.bytes` and `claude-real-session.expected-atoms.json`
   - Feeds bytes incrementally to the profile (simulating stream)
   - Collects atoms produced
   - Asserts each atom's role + content_substring matches the expected-atoms.json oracle
6. Run that test — must pass against real bytes from Task 2.

**Gate G5:**
```bash
cd /root/0latency-cli
pytest tests/ -v   # all existing + new tests pass
pytest tests/test_claude_code_profile.py -v   # specifically must pass
echo "G5 PASS"
```

**Halt:** any P1 test breaks (regression — fix before continuing). The new fixture-replay test fails (parser doesn't match real bytes — fix the parser, not the fixture).

---

### Task 6 — `CodexProfile` implementation + tests

**Goal:** `0latency_cli/profiles/codex.py` implements `Profile` for Codex. Parametrized test replays Codex fixture from Task 2 and asserts correctness.

**Steps:**

1. Read `docs/profiles/codex.md` (from Task 3) — that's the spec.
2. Implement `CodexProfile(Profile)` mirroring `ClaudeCodeProfile`'s structure where possible. Diverge where Codex's render differs (per Task 3's docs).
3. Set `__compat_agent_version__` to the Codex version recorded in Task 1.
4. Add `tests/test_codex_profile.py` mirroring `test_claude_code_profile.py` but pointed at the Codex fixture.
5. Run; iterate parser until tests pass against real bytes.

**Gate G6:**
```bash
cd /root/0latency-cli
pytest tests/test_codex_profile.py -v
echo "G6 PASS"
```

**Halt:** if Codex's render format is so far from Claude Code's that the `Profile` ABC needs new methods, halt and propose the ABC change before implementing — do NOT bypass the ABC by adding ad-hoc methods to `CodexProfile` that aren't in the contract. The whole point of the abstraction is consistency across agents.

---

### Task 7 — `GeminiCliProfile` implementation + tests

**Goal:** Same as Task 6, for Gemini CLI.

**Steps:** Same pattern as Task 6, pointed at Gemini's docs and fixture.

**Gate G7:**
```bash
cd /root/0latency-cli
pytest tests/test_gemini_cli_profile.py -v
echo "G7 PASS"
```

**Halt:** same conditions as Task 6.

---

### Task 8 — `AiderProfile` implementation + tests

**Goal:** Same as Task 6, for Aider, plus the Aider-specific `file_changes` metadata field per Decision 6.

**Steps:**

1. Implement `AiderProfile(Profile)` with the standard atom output AND extraction of file-edit blocks into `metadata.file_changes = [{path, diff}, ...]`.
2. `tests/test_aider_profile.py` asserts:
   - Standard atoms (user/assistant/tool_use) are correctly tagged
   - At least one atom has populated `metadata.file_changes` (since the Aider fixture should include a file edit per Task 2 step 3 turn 4)
   - `file_changes` entries are well-formed (`path` is a string, `diff` is a string with diff-like content)

**Gate G8:**
```bash
cd /root/0latency-cli
pytest tests/test_aider_profile.py -v
echo "G8 PASS"
```

**Halt:** same conditions as Task 6, plus: if the Aider fixture genuinely doesn't include a file edit (rare — re-capture a fixture that does, since file edits are Aider's signature feature).

---

### Task 9 — `GenericProfile` fallback implementation + tests

**Goal:** `0latency_cli/profiles/generic.py` implements the unknown-agent fallback per Decision 3 — captures stdin and stdout as one atom per "turn" where turn = idle period of >2s on stdout. Test verifies it captures *something* sensible from any tty session.

**Steps:**

1. Implement `GenericProfile(Profile)` with idle-detection turn boundaries.
2. Capture a small fixture from an unknown agent — easiest: use `cat` or `python3 -i` (Python REPL) as the "unknown" agent. Save to `tests/fixtures/cli-bytes/generic-python-repl.bytes`.
3. `tests/test_generic_profile.py` asserts:
   - Replaying the fixture produces ≥ 1 atom per real interactive turn
   - Atoms are tagged role=user or role=assistant based on stdin vs stdout source
   - No tool_use atoms (generic profile makes no inference about tool use)

**Gate G9:**
```bash
cd /root/0latency-cli
pytest tests/test_generic_profile.py -v
echo "G9 PASS"
```

**Halt:** generic profile is so noisy on real input that it produces an atom per byte (means idle-detection threshold needs tuning — adjust until natural turns emerge).

---

### Task 10 — Wire profile selection into `wrapper.py` + cross-profile performance benchmark

**Goal:** `0latency claude`, `0latency codex`, `0latency gemini`, `0latency aider` each route to the correct profile via `load_profile()`. Anything else routes to generic. Performance benchmark from P1 re-run for each profile; p95 < 50ms held across all four.

**Steps:**

1. Update `wrapper.py` to map agent name → profile name:
   ```python
   AGENT_TO_PROFILE = {
       "claude": "claude-code",
       "codex": "codex",
       "gemini": "gemini-cli",
       "aider": "aider",
   }
   profile_name = AGENT_TO_PROFILE.get(agent_cmd, "generic")
   profile = load_profile(profile_name)
   ```
2. Update CLI subcommands (P1 added `0latency claude`; add `0latency codex`, `0latency gemini`, `0latency aider`).
3. Adapt P1's `tests/bench_overhead.py` into `tests/bench_profiles.py`:
   - Runs 100 turns per profile (Claude Code, Codex, Gemini CLI, Aider)
   - Measures wrapped vs bare per-turn overhead per profile
   - Reports p50, p95, p99 per profile
4. Run benchmark on the server. Commit raw results to `bench/results-cp10-p2-<date>.json`.

**Gate G10:**
```bash
cd /root/0latency-cli
python3 tests/bench_profiles.py --turns 100 --report /tmp/cp10-p2-bench.json
# Each profile's p95 must be < 50ms
jq -r 'to_entries[] | "\(.key) \(.value.overhead_p95_ms)"' /tmp/cp10-p2-bench.json | \
  awk '{ if ($2 >= 50.0) { print "G10 FAIL: " $1 " p95=" $2 "ms"; exit 1 } } END { print "G10 PASS" }'
```

**Halt:** any profile's p95 ≥ 50ms. Profile, find the hot path, fix, re-bench. Common culprits: regex compilation per byte (compile once, reuse), inefficient buffer slicing (use bytearray with views, not bytes copies), profile loader called per byte instead of once per session.

---

## Verification gate (overall — ALL must pass before P2 complete)

1. ✅ G1–G10 each independently passing with on-server receipts.
2. ✅ All four real-byte fixtures committed and human-spot-checked (10 turns each, sample 3 per agent for hand-validation).
3. ✅ Each profile's parametrized test passes against its real fixture (not a synthetic mock).
4. ✅ `0latency claude`, `0latency codex`, `0latency gemini`, `0latency aider` each work end-to-end on the server (capture a 5-turn session per agent through the wrapper, verify atoms land in `~/.0latency/local.db` with correct profile attribution in metadata).
5. ✅ User override mechanism verified: place a `~/.0latency/profiles/claude_code.py` that overrides the built-in, run wrapper, observe override is loaded.
6. ✅ Generic profile verified end-to-end against `python3 -i` or similar untyped agent.
7. ✅ Performance budget < 50ms p95 held across all four profiles.

**Deliverable:** `CHECKPOINT-10-PHASE-2-COMPLETE.md` in the wrapper repo, with:
- Per-agent fixture stats (bytes, turns, capture date, agent CLI version)
- Per-profile test pass receipts
- Performance benchmark JSON + summary table comparing P1 baseline to P2 per-profile
- User-override demonstration receipt
- Tag `v0.2.0` on `0latency-cli` `main` after merge

---

## Anti-scope (P2 explicitly defers these)

- ❌ Crash recovery + rolling buffer — P3.
- ❌ Atom batching, queue, backpressure — P3.
- ❌ Long-session memory bounds (4-hour test) — P3.
- ❌ Large-paste handling (1M character files) — P3.
- ❌ Windows support via winpty — P4.
- ❌ npm distribution (`npm install -g @0latency/cli`) — P4.
- ❌ Documentation site `docs.0latency.ai/cli` — P4.
- ❌ `0latency status` polish, `--explain` real implementation — P4.
- ❌ First-run flow refinements — P4.
- ❌ Telemetry — opt-in only, P4 if at all.
- ❌ Profile registry sharing (private repos for orgs) — Tier matrix territory, P4.
- ❌ VS Code / JetBrains terminal auto-detection — Nice-to-have, P3+ optional.
- ❌ Cursor's chat panel — Different surface, Chrome extension territory, not CP10.
- ❌ Server-side schema or migration changes — P2 ships zero migrations.
- ❌ Chyros-style synthesis-aware profile heuristics — separate research track.

---

## Halt conditions (specific to P2)

In addition to standard protocol halts (paste-safe failures, migration tier-2 escalation, etc.):

1. **Agent CLI not installable on server.** Document the blocker in `docs/profiles/<agent>.md`, continue with the remaining agents, return when fixable. Do NOT skip silently.
2. **Real-byte fixture is unparseable by inspection.** Means the agent uses structured output (JSON-RPC, protobuf) instead of human-readable rendering. Halt and escalate — wrappers don't read structured output (decision 1, verbatim invariant).
3. **Profile abstraction can't accommodate one of the agents without bypass methods.** Halt, propose ABC change, get operator approval, then refactor. Do NOT add ad-hoc methods to one profile that aren't in the contract.
4. **Performance budget blown by > 20%** on any profile (p95 ≥ 60ms). Halt for architecture review — likely regex-per-byte or buffer-copy hot path issue.
5. **A profile passes its fixture test but fails the end-to-end wrapper test.** Means the fixture replay diverges from real-stream behavior — investigate stream chunking, partial-buffer handling.
6. **Cross-profile test contamination.** If running test_codex_profile.py affects test_aider_profile.py outcomes, fixture isolation is broken. Halt, fix isolation.
7. **Token leakage anywhere** — stderr, logs, error messages, exception tracebacks. **Full stop, rotate keys, fix, write a regression test before proceeding.**

---

## Branch + commit plan

**Wrapper repo (`0latency-ai/0latency-cli`):**
- Branch: `cp-p10-2-profiles` off `main`.
- Commits (10, one per Task) for clean reviewability:
  1. Phase A — agent CLIs installed, version-stub docs created
  2. Phase A — real-byte fixtures captured for 4 agents
  3. Phase A — render format docs populated from fixture analysis
  4. Phase B — Profile ABC + registry loader + tests
  5. Phase B — ClaudeCodeProfile (refactor of P1's parser) + fixture-replay test
  6. Phase B — CodexProfile + fixture-replay test
  7. Phase B — GeminiCliProfile + fixture-replay test
  8. Phase B — AiderProfile + fixture-replay test
  9. Phase B — GenericProfile fallback + fixture-replay test
  10. Phase B — wrapper.py profile routing + performance benchmark across all profiles
- PR `cp-p10-2-profiles → main` after G10 + verification gate clears.
- Tag `v0.2.0` on merge.

**Server-side:** zero changes for P2. No migrations, no new endpoints. The wrapper is purely client-side.

---

## Rules CC operates under (standard, restated for completeness)

- Lead engineer mode. No middleman.
- `bash scripts/db_migrate.sh up`, NOT direct `alembic upgrade head` (does not apply to P2 since no server migrations).
- `_db_execute_rows`, NOT `_db_execute` (does not apply to P2 since no server DB work).
- `python3`, NOT `python`.
- `export PATH="$HOME/.local/bin:$PATH"` before any command that needs `claude` (the binary lives there, not on default PATH).
- Paste-safe output discipline: NEVER echo `.env` contents, tokens, API keys, or credentials anywhere — stdout, stderr, logs, traces, status output. State "Safe to paste: YES/NO" on every command.
- Independent verification at every gate: file output, command exit code, test pass, fixture-byte spot-check. No summary claims. CP10 P1 Phase A's failure mode (CC contradicting itself between chime and follow-up reads) means demand the raw artifact, not summaries.
- The "Safe to paste: YES" preamble is OUTSIDE the code block, not inside (P1 lesson — bash treats it as a command otherwise).
- End every gate or task chime with: `; afplay /System/Library/Sounds/Glass.aiff`

---

## Sequencing notes (post-P2)

- **CP10 P3** (reliability + edge cases) starts after P2 verification gate passes. Crash recovery, backpressure, large-paste, long-session — these are all stress tests of P2's profile abstraction.
- **CP10 P4** (distribution + polish) closes the chain — Windows, npm, docs site, Show HN-ready demo. P4's "every CLI agent" claim is now backed by real working profiles.
- **CP9 P1** (5-minute onboarding refresh) — picks up after P2 with the wrapper as a fourth install path. Scope refresh authored in chat, ready to deploy when CP9 build chain starts.
- **CP11 (universal positioning)** — its "every tool" claim is now grounded in working code. P2 is what makes the CP11 launch credible.

---

## One-paragraph summary for resumption

CP10 Phase 2 ships profile abstraction and four agent profiles (Claude Code refactored from P1, plus Codex, Gemini CLI, Aider) plus a generic fallback for unknown tty agents. Two execution phases on a single branch `cp-p10-2-profiles`: Phase A captures real-byte fixtures from each agent on the server (the prerequisite, not a polish step — CP10 P1 Phase A's lesson encoded structurally), Phase B builds the Profile ABC, the registry loader, four built-in profiles, the generic fallback, and routes `wrapper.py`'s agent-name dispatch into the registry. Ten tasks, ten commits, one PR, tag `v0.2.0`. Zero server-side changes — P2 is pure client work. Performance budget unchanged: < 50ms p95 per profile, benchmarked across all four against P1 baseline. Anti-scope is rigid: crash recovery, backpressure, Windows, npm, docs site, Show HN demo all defer to P3/P4. Halt conditions encode the lesson that profile abstraction must earn its keep — bypass methods are forbidden, ABC changes require operator approval. The wedge that P2 closes: Anthropic-native memory will be Claude Code-only, Mem0 has no CLI capture, Open Brain takes 30+ minutes to set up. P2 is what makes "we capture every CLI agent the developer uses" structurally available as a positioning claim — and after P2 ships, CP11's universal pitch is grounded in working code.
