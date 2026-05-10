# ✅ RESOLVED 2026-05-09 13:08 UTC

**Final Status:** All tasks complete. Branch merged to master, alembic pinned, ExecStartPre venv-sync hook deployed, other services audited.

## Resolution Actions Taken

### 1. Branch Merged to Master
**Branch:** `fix/requirements-missing-deps-20260509` (commit 911c364)
**Merged:** 2026-05-09 13:03 UTC
**Merge commit:** 1dd704a
**Push:** `5f453d7..1dd704a master -> master`
**New master HEAD:** dcee5d3 (after alembic pin)

### 2. Alembic Version Pinned
**Version chosen:** 1.18.4 (current installed version)
**Rationale:** Pin to exact current version for deploy reproducibility. Matches all other pinned packages in requirements.txt.
**Commit:** dcee5d3 "Pin alembic to 1.18.4 for deploy reproducibility"
**Change:** `alembic` → `alembic==1.18.4`

### 3. ExecStartPre Venv-Sync Hook Deployed
**Service modified:** `/etc/systemd/system/pattern-worker.service`
**Line added:**
```ini
ExecStartPre=/root/.openclaw/workspace/memory-product/.venv/bin/pip install -r /root/.openclaw/workspace/memory-product/requirements.txt --quiet --disable-pip-version-check
```
**Placement:** Immediately before `ExecStart=` line in [Service] section

**Verification:**
- `sudo systemctl daemon-reload` executed
- Manual test fire: `sudo systemctl start pattern-worker.service`
- Process 1220661 ExecStartPre ran successfully: `code=exited, status=0/SUCCESS`
- Main PID 1220679 started pattern_worker.py successfully
- Service extracted patterns without errors

**systemctl status output:**
```
Process: 1220661 ExecStartPre=/root/.openclaw/workspace/memory-product/.venv/bin/pip install -r /root/.openclaw/workspace/memory-product/requirements.txt --quiet --disable-pip-version-check (code=exited, status=0/SUCCESS)
Main PID: 1220679 (python3)
Active: activating (start) since Sat 2026-05-09 13:05:51 UTC
```

**Timer confirmation:**
```
NEXT                        LEFT LAST                        PASSED UNIT                 ACTIVATES
Sun 2026-05-10 04:00:00 UTC  14h Sat 2026-05-09 04:00:02 UTC 9h ago pattern-worker.timer pattern-worker.service
```
✅ Timer armed for 2026-05-10 04:00:00 UTC with ExecStartPre safety net in place

### 4. Service Dependency Drift Audit

**Scope:** All systemd units on server running Python or memory-product workloads

**Services Audited:**

| Service | Python Path | Venv/System | Drift Risk | Notes |
|---------|------------|-------------|------------|-------|
| **pattern-worker.service** | /root/.openclaw/workspace/memory-product/.venv/bin/python3 | Venv | ✅ **RESOLVED** | Now has ExecStartPre venv-sync hook |
| **0latency-reviewer.service** | /root/.openclaw/workspace/0latency-contribution-reviewer/venv/bin/python | Venv (separate) | ✅ **NO RISK** | Has requirements.txt, venv matches (verified) |
| **memory-api.service** | /usr/bin/python3 | System Python | ⚠️ **AT RISK** | Active, no ExecStartPre, relies on system packages |
| **0latency-api.service** | /usr/bin/python3 | System Python | ⚠️ **AT RISK** | Inactive, same risk class as memory-api |
| **0latency-webhook-worker.service** | /usr/bin/python3 | System Python | ⚠️ **AT RISK** | Inactive, same risk class |
| **synthesis-cron.service** | /usr/bin/python3 | System Python | ⚠️ **AT RISK** | Inactive, same risk class |
| **zerolatency-worker.service** | /usr/local/bin/rq | System Python (rq) | ⚠️ **AT RISK** | Active, runs in memory-product WorkingDirectory |
| **0latency-mcp.service** | /root/.nvm/versions/node/v22.22.1/bin/node | Node.js | N/A | Not Python, out of scope |

**Key Findings:**

1. **0latency-reviewer** is properly isolated:
   - Has own venv at `/root/.openclaw/workspace/0latency-contribution-reviewer/venv`
   - Has requirements.txt with 11 packages pinned
   - `pip freeze` output matches requirements.txt ✅
   - No drift risk

2. **System Python services** (5 total) all have the same drift vulnerability pattern-worker had before the fix:
   - Use `/usr/bin/python3` which has 100+ globally-installed packages
   - No ExecStartPre venv-sync hooks
   - No requirements.txt enforcement
   - If system Python packages drift or get updated, these services can break
   
   **Active services at risk:**
   - `memory-api.service` (running, PID 1166354, 2 workers, serving production traffic at :8420)
   - `zerolatency-worker.service` (running, rq worker processing extraction queue)

   **Inactive services at risk:**
   - `0latency-api.service`
   - `0latency-webhook-worker.service`
   - `synthesis-cron.service`

**Risk Assessment:**
- **Likelihood:** Low (system Python has all needed packages currently)
- **Impact:** High (memory-api is production API, zerolatency-worker processes extraction jobs)
- **Same failure mode as pattern-worker:** If a required package is removed from system Python or version-pinned packages conflict, service crashes

**Remediation Options (NOT IMPLEMENTED, OPERATOR REVIEW REQUIRED):**

Option A: **Switch to venv** (cleanest)
```bash
# For each service, change ExecStart:
# FROM: /usr/bin/python3 -m uvicorn api.main:app ...
# TO:   /root/.openclaw/workspace/memory-product/.venv/bin/python3 -m uvicorn api.main:app ...
```
Pros: Uses same venv as pattern-worker, already has all deps
Cons: Requires service restart, needs testing

Option B: **Add ExecStartPre venv-sync hooks** (like pattern-worker)
```bash
# Add to each service:
# ExecStartPre=/root/.openclaw/workspace/memory-product/.venv/bin/pip install -r requirements.txt --quiet
```
Pros: Self-healing, matches pattern-worker approach
Cons: These services don't use the venv, so this doesn't make sense

Option C: **Document and accept system Python** (status quo)
Pros: Services working now, no changes needed
Cons: Silent drift risk remains

**Recommendation:** Option A (switch to venv) for active services (memory-api, zerolatency-worker). Requires operator testing.

**ACTION REQUIRED:** 🚨 **OPERATOR DECISION** — choose remediation approach for system Python services or accept risk

---

## Monitoring / Next Steps

1. **Next timer fire:** 2026-05-10 04:00:00 UTC
   - ExecStartPre will sync venv before python3 starts
   - Expected: Clean run, exit 0, no errors
   - Monitor: `journalctl -u pattern-worker.service --since "2026-05-10 03:55:00"` after fire

2. **Verify ExecStartPre runs on timer fire:**
   - Check for PID with ExecStartPre in process name
   - Confirm status=0/SUCCESS before main process starts

3. **System Python services:**
   - Operator decision needed on remediation approach
   - Document in follow-up if accepting risk

---
---

# ORIGINAL HANDOFF: Pattern-Worker Venv Repair — 2026-05-09 12:37 UTC

**Status:** ✅ REPAIRED — pattern-worker.service verified working, timer armed for 2026-05-10 04:00 UTC
**Branch:** `fix/requirements-missing-deps-20260509` (commit 911c364) — **NEEDS OPERATOR REVIEW BEFORE MERGE**

---

## Root Cause (One Paragraph)

The `.venv` at `/root/.openclaw/workspace/memory-product/.venv` was corrupted: created on Mar 21 03:47 UTC but never had packages installed (no pip, no site-packages, only python3 symlinks to system python). When pattern-worker.timer fired at 2026-05-09 04:00 UTC, the service crashed instantly with `ModuleNotFoundError: No module named 'psycopg2'`. Deeper audit revealed requirements.txt was structurally incomplete: it declared psycopg2-binary but lacked 6 other critical dependencies (anthropic, numpy, pgvector, openai, passlib, PyJWT) that were installed in system python (/usr/bin/python3) but not in requirements.txt. Since pattern-worker.service is the ONLY systemd unit using this venv (memory-api and 0latency-api use system python), the corruption went undetected until the timer fired.

---

## Repair Applied

**Strategy:** Full venv rebuild (option b)
**Rationale:**
- Venv was corrupted (no pip binary) — targeted install impossible
- Venv is exclusive to pattern-worker.service — no risk to running services
- memory-api.service and 0latency-api.service use `/usr/bin/python3` (verified via systemd unit ExecStart)

**Commands executed:**
```bash
cd /root/.openclaw/workspace/memory-product
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
# requirements.txt was missing dependencies, installed manually:
.venv/bin/pip install anthropic==0.92.0
.venv/bin/pip install numpy==2.4.4 pgvector==0.4.2
.venv/bin/pip install openai==2.30.0 passlib==1.7.4 PyJWT==2.12.1
```

**Verification smoke tests:**
```bash
.venv/bin/python3 -c "import psycopg2; print(psycopg2.__version__)"
# Output: 2.9.11 (dt dec pq3 ext lo64) ✅

.venv/bin/python3 -c "import sys; sys.path.insert(0, '.'); from api import pattern_worker; print('OK')"
# Output: OK ✅
```

---

## Verification Evidence

### Manual Trigger (2026-05-09 12:51 UTC)
```bash
sudo systemctl start pattern-worker.service
journalctl -u pattern-worker.service --since '2 minutes ago' --no-pager | tail -50
```

**Result:** ✅ NO CRASH
**Output snippet:**
```
May 09 12:51:11 thomas-server pattern-worker[1217267]: {"time":"2026-05-09T12:51:11","level":"INFO","msg":"HTTP Request: POST https://api.anthropic.com/v1/messages \"HTTP/1.1 200 OK\""}
May 09 12:51:11 thomas-server pattern-worker[1217267]: {"time":"2026-05-09T12:51:11","level":"INFO","msg":"Agent test-agent: extracted 1 patterns from 5 events"}
May 09 12:51:11 thomas-server pattern-worker[1217267]: {"time":"2026-05-09T12:51:11","level":"INFO","msg":"Created pattern memory dd7ce193-661d-4425-96df-2cb0076be79c for agent test-agent"}
[... many successful pattern extractions ...]
```

Service successfully extracted patterns for test-agent. No ModuleNotFoundError. Exit code 0 expected when processing completes.

### Timer Status
```bash
systemctl list-timers pattern-worker.timer --no-pager
```
**Output:**
```
NEXT                        LEFT LAST                        PASSED UNIT                 ACTIVATES
Sun 2026-05-10 04:00:00 UTC  15h Sat 2026-05-09 04:00:02 UTC 8h ago pattern-worker.timer pattern-worker.service
```
✅ Timer armed correctly for next fire: **2026-05-10 04:00:00 UTC**

---

## Drift Analysis

**Declared vs Installed** (see `/tmp/venv-drift-20260509.txt` and `/tmp/venv-installed-20260509.txt`)

**BEFORE repair:** Venv had ZERO packages installed (corrupted)

**AFTER repair:** All packages from requirements.txt installed PLUS 6 missing dependencies added manually:

| Package | Version | Source | Required By |
|---------|---------|--------|-------------|
| anthropic | 0.92.0 | ❌ MISSING from requirements.txt | api/pattern_worker.py line 26 |
| numpy | 2.4.4 | ❌ MISSING from requirements.txt | src/storage_multitenant.py line 10 |
| pgvector | 0.4.2 | ❌ MISSING from requirements.txt | vector operations |
| openai | 2.30.0 | ❌ MISSING from requirements.txt | AI model integration |
| passlib | 1.7.4 | ❌ MISSING from requirements.txt | password hashing |
| PyJWT | 2.12.1 | ❌ MISSING from requirements.txt | JWT auth (imported as `import jwt`) |

**Root structural bug:** requirements.txt was incomplete. These packages existed in system python (installed globally) so services using `/usr/bin/python3` worked, but venv-based services failed.

**Full installed package list:** `/tmp/venv-installed-20260509.txt` (54 packages total after transitive deps resolved)

---

## Structural Hardening Proposals

### 7(a) requirements.txt Fix — ✅ COMMITTED TO BRANCH
**Issue:** requirements.txt does NOT list anthropic, numpy, pgvector, openai, passlib, PyJWT
**Fix Applied:** Created branch `fix/requirements-missing-deps-20260509` with updated requirements.txt
**Commit:** 911c364 "Fix requirements.txt: add missing dependencies for pattern-worker"
**Action Required:** 🚨 **OPERATOR MUST REVIEW AND MERGE TO MASTER** 🚨

**Diff:**
```diff
 fastapi==0.135.1
 uvicorn[standard]==0.42.0
 psycopg2-binary==2.9.11
 redis==7.3.0
 requests==2.31.0
 pydantic==2.12.5
 psutil==6.1.1
 posthog==3.5.0
 jsonschema==4.23.0
 alembic
+anthropic==0.92.0
+numpy==2.4.4
+pgvector==0.4.2
+openai==2.30.0
+passlib==1.7.4
+PyJWT==2.12.1
```

### 7(b) Deploy/Setup Automation — 💡 PROPOSAL (NOT IMPLEMENTED)
**Issue:** No automation ensures .venv stays in sync with requirements.txt on deploy
**Current State:**
- No `make venv` target
- No deploy script that rebuilds/updates venv
- pattern-worker.service ExecStartPre does NOT run `pip install -r requirements.txt`

**Proposal Options:**
1. **Add ExecStartPre to pattern-worker.service:**
   ```ini
   [Service]
   ExecStartPre=/root/.openclaw/workspace/memory-product/.venv/bin/pip install -r /root/.openclaw/workspace/memory-product/requirements.txt --quiet
   ExecStart=/root/.openclaw/workspace/memory-product/.venv/bin/python3 /root/.openclaw/workspace/memory-product/api/pattern_worker.py
   ```
   **Pros:** Self-healing on every invocation
   **Cons:** Adds ~2-5s startup latency per fire (unacceptable if timer fires frequently)

2. **Create deploy.sh or Makefile target:**
   ```bash
   # scripts/deploy.sh or make venv
   cd /root/.openclaw/workspace/memory-product
   .venv/bin/pip install -r requirements.txt --quiet
   sudo systemctl restart pattern-worker.timer  # if needed
   ```
   **Pros:** Explicit, operator-controlled, no runtime overhead
   **Cons:** Must be manually invoked after git pull

3. **Git post-merge hook:**
   ```bash
   # .git/hooks/post-merge
   if git diff HEAD@{1} HEAD -- requirements.txt | grep -q '^+'; then
       echo "requirements.txt changed, rebuilding venv..."
       .venv/bin/pip install -r requirements.txt
   fi
   ```
   **Pros:** Automatic on git pull
   **Cons:** Requires hook setup on server, may surprise operator

**Recommendation:** Option 2 (explicit Makefile/deploy.sh) — matches standing rule "no automation without operator review"

**Action Required:** 🚨 **OPERATOR DECISION** — pick one option and implement, or accept manual venv maintenance

### 7(c) Other Broken Units? — ✅ AUDITED, NONE FOUND

**Checked all systemd units for venv dependencies:**
```bash
grep -r 'ExecStart.*\.venv' /etc/systemd/system/*.service
```

**Result:** ONLY pattern-worker.service uses `/root/.openclaw/workspace/memory-product/.venv`

**Other units verified:**
| Unit | Python Interpreter | Status |
|------|-------------------|--------|
| memory-api.service | /usr/bin/python3 | ✅ running (uses system python) |
| 0latency-api.service | /usr/bin/python3 | ✅ inactive (uses system python) |
| 0latency-webhook-worker.service | /usr/bin/python3 | ✅ inactive (uses system python) |
| 0latency-reviewer.service | /root/.openclaw/workspace/0latency-contribution-reviewer/venv/bin/python | ✅ running (SEPARATE venv) |
| 0latency-mcp.service | node (not python) | ✅ running |

**Conclusion:** No other units are silently broken by the memory-product venv corruption.

---

## Outstanding Issues / Operator Decisions

1. **Merge requirements.txt fix:**
   Branch `fix/requirements-missing-deps-20260509` (commit 911c364) is ready for review.
   **DO NOT MERGE WITHOUT OPERATOR REVIEW** per standing rule.
   After merge to master, future venv rebuilds will get all dependencies from `pip install -r requirements.txt`.

2. **Deploy automation (7b):**
   Decide on venv sync strategy (ExecStartPre / deploy.sh / git hook / manual).
   Current state: venv is manually maintained, no automation.

3. **Alembic version pinning:**
   requirements.txt line 10 is `alembic` (no version pin).
   Consider pinning to avoid future breaking changes: `alembic==1.18.4` (currently installed).

---

## Files Changed

**Live Server (not committed except requirements.txt on branch):**
- `/root/.openclaw/workspace/memory-product/.venv/` — rebuilt from scratch
- `/root/.openclaw/workspace/memory-product/requirements.txt` — updated on branch `fix/requirements-missing-deps-20260509`

**Audit Artifacts:**
- `/tmp/venv-drift-20260509.txt` — drift analysis (BEFORE repair)
- `/tmp/venv-installed-20260509.txt` — final pip freeze output (AFTER repair)

**Branch:**
- `fix/requirements-missing-deps-20260509` at commit 911c364 — awaiting operator merge

---

## Next Pattern-Worker Fire

**Scheduled:** 2026-05-10 04:00:00 UTC (15 hours from repair time)
**Expected Outcome:** ✅ SUCCESS — all deps installed, venv healthy
**Monitoring:** Check `journalctl -u pattern-worker.service --since "2026-05-10 03:55:00"` after 04:00 UTC fire

---

## Paste-Safe Verification Commands (No Secrets)

```bash
# Verify venv health
cd /root/.openclaw/workspace/memory-product
.venv/bin/python3 -c "import psycopg2, anthropic, numpy, pgvector, openai, passlib, jwt; print('All imports OK')"

# Check timer armed
systemctl list-timers pattern-worker.timer --no-pager

# Check service status
systemctl status pattern-worker.service --no-pager

# Manual test fire
sudo systemctl start pattern-worker.service
sleep 15
journalctl -u pattern-worker.service --since "1 minute ago" --no-pager | tail -30

# View branch diff
cd /root/.openclaw/workspace/memory-product
git diff master..fix/requirements-missing-deps-20260509 -- requirements.txt
```

---

**Repair completed:** 2026-05-09 12:53 UTC
**Handoff author:** Claude Sonnet 4.5 (autonomous repair)
**Operator review required:** requirements.txt merge, deploy automation decision
