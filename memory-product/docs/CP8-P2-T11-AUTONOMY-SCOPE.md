# CP8 Phase 2 Task 11 — Autonomous Scope

**Task:** Nightly contract test — write a sentinel atom, verify verbatim preservation.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** T10 commit (Task 10 must be committed before T11 begins).
**Estimated wall-clock:** 45-60 min for CC.

---

## Goal

One sentence: Ship `scripts/contract_test.py` — a script that writes a sentinel atom, extracts memories from it, finds the resulting atom by sentinel, and calls `GET /memories/{id}/source` to verify the sentinel string is preserved byte-for-byte — then wire it as a daily cron job.

This is the ongoing proof that 0Latency's write paths do not corrupt or summarize verbatim content. If this test ever fails in production, it means a write path regression has occurred.

---

## In scope

**Files to create:**
- `scripts/contract_test.py` — the contract test script
- `tests/test_contract_test.py` — unit tests for the script's helper functions

**Files to modify:**
- `/etc/cron.d/0latency-contract-test` — NEW cron file (create via bash, not a Python file)

**Files to read (do not modify):**
- `api/main.py` — to understand `/memories/extract` and `/memories/{id}/source` request shapes
- `cli/verify.py` — to reuse the `.env` loader pattern
- `tests/test_source_endpoint.py` — to understand existing fixture patterns

**No new migrations.** No schema changes. Read/write via API only.

---

## Out of scope (DO NOT TOUCH)

- Any migration file (`migrations/*.sql`)
- `api/main.py` — do not modify
- `src/` — any file in the src directory
- `cli/verify.py` — do not modify
- Any `/admin/*` endpoint
- Any change to authentication/authorization layer
- alerting/paging integrations (log to file only in v1)

---

## Contract test design

### What the test does (one run):

1. Generate a unique sentinel string: `0latency-contract-{ISO8601-timestamp}-{8-char-random-hex}`
2. POST to `/memories/extract` with a raw conversation containing the sentinel string as the human turn
3. Poll for the resulting atom in the response (up to 10s, 1s intervals)
4. From the extract response, get the memory IDs of written atoms
5. For each atom ID, call `GET /memories/{id}/source`
6. Assert: at least one atom's `source_text` contains the sentinel string verbatim
7. Print result: PASS or FAIL with details
8. Exit code: 0 = PASS, 1 = FAIL, 2 = error (network/auth)

### Sentinel conversation format:

```json
{
  "agent_id": "contract-test",
  "conversation": [
    {"role": "human", "content": "VERBATIM CONTRACT TEST: {sentinel_string}"},
    {"role": "agent", "content": "Acknowledged. Sentinel recorded."}
  ]
}
```

POST to `POST /memories/extract` (the standard extraction endpoint).

### Script contract:

```
Usage: python3 scripts/contract_test.py [--api-key KEY] [--base-url URL] [--agent-id ID]

Defaults:
  --base-url: http://localhost:8420
  --agent-id: contract-test
  Reads ZEROLATENCY_API_KEY from .env or environment.

Output:
  [2026-05-02T08:00:00Z] CONTRACT TEST START
  [2026-05-02T08:00:00Z] Sentinel: 0latency-contract-20260502T080000Z-a3f9b2c1
  [2026-05-02T08:00:00Z] POST /memories/extract → 200, 3 atoms written
  [2026-05-02T08:00:01Z] Checking atom <uuid-1>... source_text contains sentinel: YES
  [2026-05-02T08:00:01Z] CONTRACT TEST PASS — sentinel preserved in atom <uuid-1>
  
  OR:
  
  [2026-05-02T08:00:01Z] Checking atom <uuid-1>... source_text contains sentinel: NO
  [2026-05-02T08:00:01Z] Checking atom <uuid-2>... source_text contains sentinel: NO
  [2026-05-02T08:00:01Z] CONTRACT TEST FAIL — sentinel not found in any atom source_text
  [2026-05-02T08:00:01Z] Sentinel was: 0latency-contract-20260502T080000Z-a3f9b2c1
  [2026-05-02T08:00:01Z] Atoms checked: [<uuid-1>, <uuid-2>]

Log file: /var/log/0latency/contract-test.log (append mode, same format as stdout)
```

### Implementation notes:

- stdlib only: `argparse`, `os`, `sys`, `json`, `urllib.request`, `datetime`, `secrets`, `time`, `pathlib`, `logging`
- Reuse `.env` loader pattern from `cli/verify.py` (copy the function, do not import from cli — scripts should be self-contained)
- Log directory `/var/log/0latency/` must be created if it doesn't exist (use `mkdir -p`)
- The script must handle the case where `/memories/extract` returns 0 atoms (some tenants may have extraction filters). In this case: log a WARNING and exit 0 (not a contract failure — a configuration issue)
- Max wait for atom writes: 15 seconds total, 1s polling interval

---

## Steps

### Step 1 — Pre-flight gates

```bash
cd /root/.openclaw/workspace/memory-product

# Gate 1a: branch
git branch --show-current | grep -q "^master$" && echo 'G1a PASS'

# Gate 1b: T10 committed (cli/verify.py exists in git tree)
git ls-files cli/verify.py | grep -q "cli/verify.py" && echo 'G1b PASS' || echo 'G1b FAIL: T10 not committed'

# Gate 1c: no existing BLOCKED note
[ ! -f CP8-P2-T11-BLOCKED.md ] && echo 'G1c PASS'

# Gate 1d: ZEROLATENCY_API_KEY present
grep -q "^ZEROLATENCY_API_KEY=" .env && echo 'G1d PASS' || echo 'G1d FAIL'

# Gate 1e: API service running
curl -sf http://localhost:8420/health > /dev/null && echo 'G1e PASS'

# Gate 1f: working tree clean
DIRTY=$(git status --porcelain | grep -v "^??" | grep -vE "^.. (scripts/contract_test|tests/test_contract_test)")
[ -z "$DIRTY" ] && echo 'G1f PASS' || { echo "G1f FAIL"; git status --porcelain; }
```

**HALT** if any gate fails.

### Step 2 — Read context

Read:
1. `api/main.py` — find the `/memories/extract` handler. Note the exact request body shape (fields, required vs optional).
2. `cli/verify.py` — copy the `load_env()` function pattern.
3. `tests/test_source_endpoint.py` — note the `agent_id` used for test fixtures.

Record the exact `/memories/extract` request shape before writing the script.

### Step 3 — Create scripts/contract_test.py

Implement per the design above. Checklist:
- [ ] `load_env()` — copy from cli/verify.py pattern
- [ ] `generate_sentinel()` — returns `0latency-contract-{timestamp}-{8hex}`
- [ ] `setup_logging(log_dir)` — configures both stdout and file handler
- [ ] `write_sentinel(base_url, api_key, agent_id, sentinel)` — POSTs to /memories/extract, returns list of atom UUIDs
- [ ] `check_sentinel(base_url, api_key, atom_ids, sentinel)` — calls /memories/{id}/source for each, returns (found: bool, matching_id: str|None)
- [ ] `main()` — orchestrates the above, correct exit codes

### Step 4 — Syntax check

```bash
cd /root/.openclaw/workspace/memory-product
python3 -c "import ast; ast.parse(open('scripts/contract_test.py').read())" && echo 'G4 PASS'
```

### Step 5 — Dry-run import check

```bash
cd /root/.openclaw/workspace/memory-product
python3 -c "
import sys
sys.argv = ['contract_test.py', '--help']
import importlib.util
spec = importlib.util.spec_from_file_location('contract_test', 'scripts/contract_test.py')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass
print('G5 PASS')
"
```

### Step 6 — Live run gate

```bash
cd /root/.openclaw/workspace/memory-product
set -a && source .env && set +a

python3 scripts/contract_test.py 2>&1 | tee /tmp/contract-test-output.txt
EXIT_CODE=$?
echo "Exit code: $EXIT_CODE"

# Gate 6a: exits 0 or exits 0 with WARNING (0-atom case)
[ $EXIT_CODE -eq 0 ] && echo 'G6a PASS' || echo 'G6a FAIL'

# Gate 6b: output contains PASS or WARNING
grep -qE "CONTRACT TEST PASS|WARNING" /tmp/contract-test-output.txt && echo 'G6b PASS'

# Gate 6c: log file was created
[ -f /var/log/0latency/contract-test.log ] && echo 'G6c PASS'

# Gate 6d: sentinel string appears in log
SENTINEL=$(grep "Sentinel:" /tmp/contract-test-output.txt | awk '{print $NF}')
echo "Sentinel was: $SENTINEL"
[ -n "$SENTINEL" ] && echo 'G6d PASS'
```

**HALT** if G6a fails (non-zero exit means FAIL or error — investigate before proceeding).

### Step 7 — Write unit tests

Create `tests/test_contract_test.py` with 4 tests:
1. `test_generate_sentinel_format` — sentinel matches expected pattern `0latency-contract-{...}-{8hex}`
2. `test_generate_sentinel_unique` — two calls produce different sentinels
3. `test_load_env_parses_key_value` — mock a temp .env file, verify load_env returns dict with expected keys
4. `test_generate_sentinel_contains_timestamp` — sentinel contains today's date substring

These are unit tests only — no network calls. Import the functions directly from `scripts/contract_test.py` using `importlib`.

### Step 8 — Test gate

```bash
cd /root/.openclaw/workspace/memory-product
pytest tests/test_contract_test.py -v --tb=short 2>&1 | tee /tmp/t11-test-output.txt
grep -q "passed" /tmp/t11-test-output.txt && ! grep -q "failed" /tmp/t11-test-output.txt && echo 'G8 PASS'
```

**HALT** on any test failure.

### Step 9 — Install cron job

```bash
# Create log directory
mkdir -p /var/log/0latency
chmod 755 /var/log/0latency

# Write cron file — runs daily at 03:15 UTC
cat > /etc/cron.d/0latency-contract-test << 'EOF'
# 0Latency nightly verbatim contract test
# Verifies sentinel atoms are preserved byte-for-byte through the write path
SHELL=/bin/bash
15 3 * * * root cd /root/.openclaw/workspace/memory-product && set -a && source .env && set +a && python3 scripts/contract_test.py >> /var/log/0latency/contract-test.log 2>&1
EOF

chmod 644 /etc/cron.d/0latency-contract-test

# Gate 9a: cron file exists and is readable
[ -f /etc/cron.d/0latency-contract-test ] && echo 'G9a PASS'

# Gate 9b: cron syntax valid (crontab -T if available, else just grep the pattern)
grep -q "15 3 \* \* \*" /etc/cron.d/0latency-contract-test && echo 'G9b PASS'
```

### Step 10 — Commit and push

```bash
cd /root/.openclaw/workspace/memory-product
git add scripts/contract_test.py tests/test_contract_test.py
git status  # GATE: only those 2 files staged (cron file is outside repo, not tracked)
git diff --cached --stat
```

Write commit message to `/tmp/cp11-commit-msg.txt`:

```
CP8 Phase 2 Task 11: nightly verbatim contract test

Cron-driven sentinel test: write known atom, verify source_text
preserved byte-for-byte via GET /memories/{id}/source.

Runs daily at 03:15 UTC via /etc/cron.d/0latency-contract-test.
Logs to /var/log/0latency/contract-test.log.
Exit 0 = PASS, 1 = FAIL (write path regression), 2 = error.

Verification receipts:
[CC fills in: python3 scripts/contract_test.py output]
[CC fills in: pytest test_contract_test.py output]
[CC fills in: cat /etc/cron.d/0latency-contract-test]

Files: scripts/contract_test.py (NEW),
       tests/test_contract_test.py (NEW, 4 unit tests)
```

```bash
git commit -F /tmp/cp11-commit-msg.txt
git log -1 --stat
git push origin master
```

**NOTE: This is the final task in the chain — push IS required here.**

---

## Halt conditions

1. **`/memories/extract` returns unexpected shape.** If the response body doesn't have a `memories` or `memory_ids` field, halt and document the actual shape in the BLOCKED note.
2. **Live run exits 1 (FAIL).** This means the write path is actually broken, not a script bug. Halt, dump the output, do not commit.
3. **Live run exits 2 (error).** Network or auth issue. Check ZEROLATENCY_API_KEY, check service health, retry once. Halt if still failing.
4. **`/var/log/0latency/` not writable.** Halt — don't proceed without logging.
5. **More than 3 files modified outside scope.** Immediate halt.

---

## Halt note format

Write `/root/.openclaw/workspace/memory-product/CP8-P2-T11-BLOCKED.md`:

```markdown
# CP8 Phase 2 Task 11 — BLOCKED

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

1. `scripts/contract_test.py` exists, committed, exits 0 on live run.
2. `/etc/cron.d/0latency-contract-test` installed and valid.
3. `/var/log/0latency/contract-test.log` exists with a PASS entry.
4. All 4 unit tests in `tests/test_contract_test.py` PASS.
5. Both T10 and T11 pushed to origin/master in a single push.
6. Commit message contains real live-run output and test results.
7. No `CP8-P2-T11-BLOCKED.md` exists.
