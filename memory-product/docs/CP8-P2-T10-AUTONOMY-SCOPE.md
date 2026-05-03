# CP8 Phase 2 Task 10 — Autonomous Scope

**Task:** Add `zerolatency verify <memory_id>` CLI verb.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** `963a5e8` (Task 9 — GET /memories/{id}/source endpoint).
**Estimated wall-clock:** 45-75 min for CC.

---

## Goal

One sentence: Ship a `cli/verify.py` script that wraps `GET /memories/{id}/source` and prints the verbatim source chain in a developer-readable format, so any developer can confirm 0Latency preserved their data byte-for-byte.

This is the developer-facing proof point for the verbatim guarantee. It's also the first piece of the `cli/` directory.

---

## In scope

**Files to create:**
- `cli/verify.py` — the CLI script (standalone, no framework dependency)
- `cli/__init__.py` — empty, makes cli/ a package
- `tests/test_cli_verify.py` — NEW integration test file

**Files to read (do not modify):**
- `api/main.py` — to understand the `/memories/{id}/source` response shape (just shipped in Task 9)
- `tests/test_source_endpoint.py` — to reuse fixture UUIDs for tests
- `docs/ENDPOINTS.md` — to confirm endpoint path

**No database access.** CLI calls the API over HTTP only. No psql, no direct DB reads.

---

## Out of scope (DO NOT TOUCH)

- Any migration file (`migrations/*.sql`)
- `api/main.py` — endpoint is already shipped, do not modify
- `src/` — any file in the src directory
- `docs/ENDPOINTS.md` updates (manual review pass post-task)
- Any `/admin/*` endpoint
- Any change to authentication/authorization layer
- Package publishing (pip/npm) — out of scope for this task
- `zerolatency init`, `zerolatency recall` — separate CLI verbs, separate scope

---

## CLI contract

```
Usage: python3 cli/verify.py <memory_id> [--api-key KEY] [--base-url URL]

Environment: reads ZEROLATENCY_API_KEY from .env or environment if --api-key not passed.

Exit codes:
  0 — source found, printed successfully
  1 — memory not found (404)
  2 — auth error (401)
  3 — bad UUID (422)
  4 — network/unexpected error

Output on success (raw_turn, source_type=verbatim):
  ✓ Memory <uuid> verified
  Type:        raw_turn
  Source type: verbatim
  Depth:       0

  Source text:
  ─────────────────────────────────────────
  <full source_text content>
  ─────────────────────────────────────────

Output on success (derived, source_type=derived):
  ✓ Memory <uuid> verified
  Type:        fact
  Source type: derived
  Chain depth: <N>

  Source chain:
  [1] <memory_id> (raw_turn)
  ─────────────────────────────────────────
  <source_text>
  ─────────────────────────────────────────
  [2] <memory_id> (raw_turn)
  ...

Output on failure:
  ✗ Memory not found (404)
  ✗ Auth error — check ZEROLATENCY_API_KEY (401)
  ✗ Invalid UUID format (422)
  ✗ Error: <message> (<status_code>)
```

---

## Implementation notes

- No third-party dependencies. Use only stdlib: `argparse`, `os`, `sys`, `json`, `urllib.request`, `pathlib`.
- Load `.env` by walking up from cwd until `.env` is found or root is hit. Simple line-by-line parser — no python-dotenv.
- Base URL defaults to `http://localhost:8420`. Overridable via `--base-url` or `ZEROLATENCY_BASE_URL` env var.
- The script must be runnable as `python3 cli/verify.py <uuid>` from the workspace root.
- No `click`, no `rich`, no `typer`. Plain print statements.

---

## Steps

### Step 1 — Pre-flight gates

```bash
cd /root/.openclaw/workspace/memory-product

# Gate 1a: branch
git branch --show-current | grep -q "^master$" && echo 'G1a PASS'

# Gate 1b: working tree clean (in-scope files only)
DIRTY=$(git status --porcelain | grep -v "^??" | grep -vE "^.. (cli/|tests/test_cli_verify)")
[ -z "$DIRTY" ] && echo 'G1b PASS' || { echo "G1b FAIL: unexpected dirty files"; git status --porcelain; }

# Gate 1c: no existing BLOCKED note
[ ! -f CP8-P2-T10-BLOCKED.md ] && echo 'G1c PASS'

# Gate 1d: ZEROLATENCY_API_KEY present in .env
grep -q "^ZEROLATENCY_API_KEY=" .env && echo 'G1d PASS' || echo 'G1d FAIL: ZEROLATENCY_API_KEY missing from .env'

# Gate 1e: predecessor commit on master
git log --oneline | grep -q "963a5e8" && echo 'G1e PASS'

# Gate 1f: API service is running
curl -sf http://localhost:8420/health > /dev/null && echo 'G1f PASS'

# Gate 1g: push works as root (not claude user — push always from root shell)
git ls-remote origin HEAD > /dev/null 2>&1 && echo 'G1g PASS'
```

**HALT** if any gate fails.

### Step 2 — Read context

Read these files before writing any code:
1. `api/main.py` — find the `get_memory_source` handler, note the exact response shape
2. `tests/test_source_endpoint.py` — note the two fixture UUIDs used (raw_turn and atom)

Record the fixture UUIDs in a scratch variable for use in Step 6.

### Step 3 — Create cli/ directory and verify.py

Create `cli/__init__.py` (empty).

Create `cli/verify.py` per the contract above. Implementation checklist:
- [ ] `load_env()` function: walks up from cwd to find `.env`, parses KEY=VALUE lines, skips comments
- [ ] `build_url(base_url, memory_id)` function: constructs the endpoint URL
- [ ] `call_api(url, api_key)` function: uses `urllib.request.urlopen`, returns `(status_code, body_dict)`
- [ ] `format_output(response_dict)` function: formats per the contract above
- [ ] `main()`: argparse for `memory_id`, `--api-key`, `--base-url`; calls above; exits with correct code
- [ ] Handles `urllib.error.HTTPError` for 404/401/422
- [ ] Handles `urllib.error.URLError` for network errors
- [ ] Handles `json.JSONDecodeError` for malformed responses

### Step 4 — Syntax check

```bash
cd /root/.openclaw/workspace/memory-product
python3 -c "import ast; ast.parse(open('cli/verify.py').read())" && echo 'G4 PASS'
python3 -c "import cli.verify" && echo 'G4b PASS'
```

**HALT** on any error.

### Step 5 — Import check (no side effects)

```bash
cd /root/.openclaw/workspace/memory-product
python3 -c "
import sys
sys.argv = ['verify.py', '--help']
try:
    import cli.verify
except SystemExit:
    pass
print('G5 PASS')
"
```

### Step 6 — Functional gates (G1)

First, load env and get the fixture UUID from the test file:

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a

# Get the raw_turn fixture UUID from the test file
RAW_TURN_UUID=$(grep -o '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}' tests/test_source_endpoint.py | head -1)
echo "Fixture UUID: $RAW_TURN_UUID"
```

**Gate 6a** — happy path raw_turn:
```bash
python3 cli/verify.py "$RAW_TURN_UUID" 2>&1
# Assert: exit code 0, output contains "verified", output contains "verbatim"
python3 cli/verify.py "$RAW_TURN_UUID" 2>&1 | grep -q "verified" && echo 'G6a PASS'
```

**Gate 6b** — exit code on 404:
```bash
python3 cli/verify.py "00000000-0000-0000-0000-000000000000" 2>&1 | grep -q "not found\|404" && echo 'G6b PASS'
[ $? -ne 0 ] || python3 cli/verify.py "00000000-0000-0000-0000-000000000000"; [ $? -eq 1 ] && echo 'G6b exit PASS'
```

**Gate 6c** — exit code on bad UUID:
```bash
python3 cli/verify.py "not-a-uuid" 2>&1 | grep -qiE "invalid|uuid|422" && echo 'G6c PASS'
```

**Gate 6d** — exit code on bad key:
```bash
python3 cli/verify.py "$RAW_TURN_UUID" --api-key "zl_live_bad" 2>&1 | grep -qiE "auth|401|api.key" && echo 'G6d PASS'
```

**Gate 6e** — source_text is non-empty in output:
```bash
OUTPUT=$(python3 cli/verify.py "$RAW_TURN_UUID" 2>&1)
echo "$OUTPUT" | grep -q "Source text:" && echo "$OUTPUT" | grep -A5 "Source text:" | grep -q "track1" && echo 'G6e PASS'
```

**HALT** if any gate fails twice.

### Step 7 — Write integration tests

Create `tests/test_cli_verify.py` with 5 tests:
1. `test_verify_raw_turn_exits_zero` — runs the CLI subprocess, checks exit code 0
2. `test_verify_raw_turn_output_contains_verbatim` — checks stdout contains "verbatim"
3. `test_verify_nonexistent_exits_one` — nil UUID, exit code 1
4. `test_verify_bad_uuid_exits_three` — "not-a-uuid", exit code 3
5. `test_verify_bad_key_exits_two` — bad key, exit code 2

Use `subprocess.run` to invoke `python3 cli/verify.py`. Use the same fixture UUID as Step 6. Mark with `@pytest.mark.integration`.

### Step 8 — Test gate (G3)

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a
pytest tests/test_cli_verify.py -v --tb=short 2>&1 | tee /tmp/t10-test-output.txt
grep -q "passed" /tmp/t10-test-output.txt && ! grep -q "failed" /tmp/t10-test-output.txt && echo 'G8 PASS'
```

**HALT** on any test failure.

### Step 9 — Commit and push

```bash
cd /root/.openclaw/workspace/memory-product
git add cli/__init__.py cli/verify.py tests/test_cli_verify.py
git status  # GATE: only those 3 files staged
git diff --cached --stat
```

Write commit message to `/tmp/cp10-commit-msg.txt`:

```
CP8 Phase 2 Task 10: zerolatency verify CLI verb

Developer-facing proof point for the verbatim guarantee.
Wraps GET /memories/{id}/source in a readable CLI output.

Usage: python3 cli/verify.py <memory_id> [--api-key KEY] [--base-url URL]

Exit codes: 0=found, 1=404, 2=401, 3=422, 4=network error
No third-party dependencies — stdlib only.

Verification receipts:
[CC fills in: python3 cli/verify.py <uuid> output]
[CC fills in: pytest test_cli_verify.py output]

Files: cli/__init__.py (NEW, empty),
       cli/verify.py (NEW, ~120 lines),
       tests/test_cli_verify.py (NEW, 5 tests)
```

```bash
git commit -F /tmp/cp10-commit-msg.txt
git log -1 --stat
```

**NOTE: Do NOT run `git push` — push will be done from root shell after both T10 and T11 complete.**

---

## Halt conditions

1. **Fixture UUID not found in test file.** If `grep` returns empty, halt — tests may have changed.
2. **Any import requires a third-party package.** stdlib only. If you find yourself reaching for `requests` or `click`, stop and rewrite.
3. **Gate 6e fails: source_text missing `track1`.** The fixture may have changed. Check the raw_turn content via curl against the source endpoint directly. If the content doesn't contain `track1`, loosen Gate 6e to check for any non-empty source text, and document the change in the BLOCKED note.
4. **More than 3 files modified outside scope.** Immediate halt.

---

## Halt note format

Write `/root/.openclaw/workspace/memory-product/CP8-P2-T10-BLOCKED.md`:

```markdown
# CP8 Phase 2 Task 10 — BLOCKED

**Halted at step:** <step>
**Trigger:** <condition>
**HEAD at halt:** <git rev-parse HEAD>

## What CC tried
## What went wrong
## State of repo
## Recommended next move
```

Do NOT stage or commit any work-in-progress on halt.

---

## Definition of done

1. `cli/__init__.py` and `cli/verify.py` exist and are committed.
2. All 5 gates in Step 6 PASS.
3. All 5 tests in `tests/test_cli_verify.py` PASS.
4. Commit on local master (push deferred to after T11).
5. Commit message contains real verification receipts.
6. No `CP8-P2-T10-BLOCKED.md` exists.
7. Working tree is clean after commit.
