# CP9.1.8 Cross-Repo Audit Report

**Date:** 2026-05-10  
**Auditor:** Claude Code (CC)  
**Task:** Pre-Phase-1-close audit across all 0Latency repositories  
**Scope:** Read-only (no merges, no pushes, no fixes)

---

## Executive Summary

**STATUS: 2 BLOCKERS FOUND**

Two critical issues block CP9 Phase 1 closure:
1. **SDK version triple-mismatch** — git tag v0.2.2, `__init__.py` shows 0.1.0, PyPI has 0.2.1
2. **Branch cleanup needed** — `fix-tenant-role-seed-drift` already merged to master (by other CC running CP9.1.5b), but local + remote branches still exist

Both are fixable in <10 minutes. Otherwise all repos are in good shape for Phase 1 close.

---

## REPO 1: memory-product (Server API)

**Location:** `/root/.openclaw/workspace/memory-product`  
**Branch:** master (up to date with origin/master)  
**Latest tag:** v0.2.2

### Branch Status

**Total branches:** 36 (18 local, 18 remote)

**Recent merges to master:**
```
4199af6 Merge CP9.1.5b: atomic tenant+role provisioning + backfill
f7eca96 merge cp9-1-4-mcp-init: init wizard v0.2.2
358959f Merge CP9.1.2: POST /atoms endpoint for CLI wrapper verbatim capture
```

**Orphan branches (merged, ready for deletion):**

| Branch | Status | Evidence |
|--------|--------|----------|
| `cp9-1-2-atoms-endpoint` | ✅ Merged to master (358959f) | Local only, no remote — safe to delete |
| `fix-tenant-role-seed-drift` | ✅ Merged to master (4199af6) | **JUST MERGED** by other CC running CP9.1.5b. Local + remote both exist — both deletable |

**Active branches (do NOT delete):**
- `cp9-1-4-mcp-init` — keep for reference (already merged but might need patch)
- All `cp-p5-*` branches — Phase 5 work-in-progress
- All `cp-p10-*` branches — Phase 10 work-in-progress

### Git Status

**Uncommitted changes:** None (clean working tree)  
**Untracked files:**
- `CP9-1-6-AUDIT.md` (this session's output)
- `mcp-server/0latency-mcp-server-0.2.2.tgz` (npm pack artifact)
- `mcp-server/test-end-to-end-timing.mjs` (dev test file)

**Assessment:** Normal dev artifacts, not blocking.

### Summary Table

| Metric | Status | Notes |
|--------|--------|-------|
| Latest tag | v0.2.2 | ✅ |
| Master clean | ✅ Yes | Up to date with origin |
| Orphan branches | ⚠️ 2 found | cp9-1-2-atoms-endpoint, fix-tenant-role-seed-drift |
| Uncommitted changes | ✅ None | Untracked files are dev artifacts |

**Action required:** Delete 2 orphan branches after Phase 1 closes.

---

## REPO 2: zerolatency-py (Python SDK)

**Location:** `/root/.openclaw/workspace/sdk`  
**Git tag:** v0.2.2  
**Published version (PyPI):** 0.2.1  
**Code version (`__init__.py`):** 0.1.0

### VERSION MISMATCH BLOCKER 🚨

**Critical inconsistency:**
```
Git tag:        v0.2.2
PyPI published: 0.2.1
__init__.py:    0.1.0
```

**Impact:**
- Users installing from PyPI get 0.2.1
- Git repo is tagged 0.2.2 (never published?)
- Code still reports 0.1.0 when imported
- Confusing for debugging ("what version am I running?")

**Root cause analysis:**
- v0.2.0 was yanked from PyPI (correct — it had /v1/ endpoint bug)
- v0.2.1 was published to replace 0.2.0
- v0.2.2 tag was created in git but never published to PyPI
- `__init__.py` was never updated from 0.1.0

**Verification:**
```bash
$ pip index versions zerolatency
zerolatency (0.2.1)
Available versions: 0.2.1, 0.1.0
  INSTALLED: 0.2.0  # local install, not from PyPI
  LATEST:    0.2.1
```

✅ **0.2.0 successfully yanked** (not in available versions)

### CHANGELOG Status

**File exists:** ❌ No `CHANGELOG.md` found

**Impact:** Users cannot see version history or breaking changes.

**Recommendation:** Create CHANGELOG.md documenting:
- 0.1.0: Initial release
- 0.2.0: (yanked) API endpoint bug
- 0.2.1: Fixed API endpoints (removed /v1/ prefix)

### Summary Table

| Metric | Status | Notes |
|--------|--------|-------|
| Tag pushed | ⚠️ v0.2.2 | Tag exists but never published to PyPI |
| Published version | ⚠️ 0.2.1 | Mismatch with git tag (0.2.2) |
| Code version | 🚨 0.1.0 | `__init__.py` never updated |
| 0.2.0 yanked | ✅ Yes | Correctly removed from PyPI |
| CHANGELOG exists | ❌ No | Missing |

**Blocker:** Version triple-mismatch must be resolved before Phase 1 close.

**Suggested fix (NOT applied in this audit):**
1. Update `__init__.py` to `__version__ = "0.2.1"` (match PyPI)
2. Either:
   - **Option A:** Delete v0.2.2 tag (it was never published)
   - **Option B:** Publish v0.2.2 to PyPI and update `__init__.py` to 0.2.2
3. Create CHANGELOG.md

---

## REPO 3: @0latency/mcp-server (npm)

**Location:** `/root/.openclaw/workspace/memory-product/mcp-server`  
**Git tag:** v0.2.2  
**Package version (`package.json`):** 0.2.2  
**Published version (npm):** 0.2.2

### Version Consistency

✅ **All versions aligned:**
```
Git tag:        v0.2.2
package.json:   0.2.2
npm published:  0.2.2
```

**npm registry verification:**
```json
[
  "0.1.0",
  "0.1.1",
  "0.1.4",
  "0.2.0",
  "0.2.1",
  "0.2.2"  ← latest
]
```

### CHANGELOG Status

**File exists:** ✅ Yes  
**Latest entry:** 0.2.2 (2026-05-10)  
**Content:** Documents init wizard feature comprehensively

**Excerpt:**
```markdown
## [0.2.2] - 2026-05-10

### Added
- **`init` subcommand** for one-command MCP setup
  - Interactive CLI wizard to configure Claude Desktop, Cursor, Windsurf, or Claude Code
  - Auto-detects OS and generates correct config file paths
  - Memory write+recall verification to confirm working setup
  - Target: <60s end-to-end with existing API key
  - Usage: `npx @0latency/mcp-server init`
```

### Git Status

**Untracked files:**
- `0latency-mcp-server-0.2.2.tgz` (npm pack artifact)
- `test-end-to-end-timing.mjs` (dev test)

**Assessment:** Normal dev artifacts.

### Summary Table

| Metric | Status | Notes |
|--------|--------|-------|
| Tag pushed | ✅ v0.2.2 | |
| Published version | ✅ 0.2.2 | Matches git tag |
| package.json version | ✅ 0.2.2 | Aligned |
| CHANGELOG current | ✅ Yes | Reflects init wizard feature |
| Uncommitted changes | ✅ Clean | Untracked files are dev artifacts |

**Status:** ✅ **READY FOR PHASE 1 CLOSE**

---

## REPO 4: 0latency-cli (PyPI wrapper)

**Location:** `/root/0latency-cli`  
**Git tag:** v0.3.0  
**Code version (`__init__.py`):** 0.3.0  
**Published version (PyPI):** 0.3.0

### Version Consistency

✅ **All versions aligned:**
```
Git tag:        v0.3.0
__init__.py:    0.3.0
PyPI published: 0.3.0
```

**PyPI verification:**
```bash
$ pip index versions 0latency-cli
0latency-cli (0.3.0)
Available versions: 0.3.0
  LATEST:    0.3.0
```

### CHANGELOG Status

**File exists:** ❌ No `CHANGELOG.md` found

**Impact:** Users cannot see what changed between 0.1.0 → 0.3.0.

**Recommendation:** Create CHANGELOG.md documenting:
- 0.1.0: Initial release
- 0.2.0: (inferred) Added profiles support
- 0.3.0: /atoms endpoint integration, soak testing

### README Status — /atoms Endpoint

**Searched for:** "atoms", "POST /atoms", "/atoms endpoint"

**Finding:** README mentions "verbatim CLI capture wrapper" and "atoms" conceptually, but does NOT explicitly document the `/atoms` endpoint integration as a feature.

**Excerpt found:**
> "Verbatim CLI capture wrapper for Claude Code, Codex, Gemini CLI, and Aider. Captures all user inputs and agent outputs as role-tagged atoms, stored locally or synced to the 0Latency cloud memory platform."

**Assessment:** Functional description present, but technical implementation detail (POST /atoms) not documented.

### Git Status

**Uncommitted changes:**
```
 D dist/0latency_cli-0.1.0-py3-none-any.whl
 D dist/0latency_cli-0.1.0.tar.gz
 M src/zerolatency_cli/__pycache__/*.pyc (multiple)
 D tests/__pycache__/*.pyc (multiple)
?? dist/0latency_cli-0.3.0-py3-none-any.whl
?? dist/0latency_cli-0.3.0.tar.gz
?? SOAK-COMPLETION-CHECKLIST.md
?? SOAK-MONITOR-STATUS.md
?? monitor_soak.sh
?? tests/soak_*.{sh,log,py}
```

**Assessment:**
- Deleted old 0.1.0 dist files (normal cleanup)
- Modified `__pycache__` files (normal Python artifact)
- New 0.3.0 dist files (build artifacts)
- Soak test infrastructure (dev files)

**Impact:** No blocking issues. These are normal dev/build artifacts.

### Summary Table

| Metric | Status | Notes |
|--------|--------|-------|
| Tag pushed | ✅ v0.3.0 | |
| Published version | ✅ 0.3.0 | Matches git tag |
| Code version | ✅ 0.3.0 | Aligned |
| CHANGELOG exists | ❌ No | Missing |
| README reflects /atoms | ⚠️ Partial | Mentions atoms conceptually, not endpoint technically |
| Uncommitted changes | ⚠️ Yes | Build artifacts and soak test files (not blocking) |

**Status:** ✅ **READY FOR PHASE 1 CLOSE** (CHANGELOG absence is non-blocking)

---

## REPO 5: Website (/var/www/0latency/)

**Location:** `/var/www/0latency/`  
**Key file:** `quickstart.html` (CP9.1.5 deliverable)

### URL Accessibility

**Both routes tested:**
```
/quickstart       → 200 ✅
/quickstart.html  → 200 ✅
```

**Assessment:** Both URLs work. No routing issues.

### PostHog Tracking

**Search:** `grep -i posthog quickstart.html`

**Found:**
```javascript
// Track in PostHog if available
if (window.posthog) {
    posthog.capture('quickstart_first_memory', {
        elapsed_seconds: elapsed,
        install_method: currentInstall,
        gate_passed: elapsed <= 60
    });
}
```

**Assessment:** ✅ PostHog event tracking present for funnel analysis.

### Site Nav Component

**Search:** `grep site-nav quickstart.html`

**Found:**
```html
<script src="/components/site-nav.js?v=12" defer></script>
<site-nav></site-nav>
```

**Assessment:** ✅ Site nav component referenced with cache-buster (`?v=12`).

### Cache-Buster Versions

**Search:** `grep -oE '?v=[0-9]+' quickstart.html`

**Found:** `?v=12`

**Assessment:** ✅ Single cache-buster version used consistently.

### Summary Table

| Metric | Status | Notes |
|--------|--------|-------|
| /quickstart accessible | ✅ 200 | Both /quickstart and /quickstart.html work |
| PostHog tracking | ✅ Present | Event: `quickstart_first_memory` |
| site-nav component | ✅ Referenced | With ?v=12 cache buster |
| Cache-buster version | ✅ v=12 | Consistent across assets |

**Status:** ✅ **READY FOR PHASE 1 CLOSE**

---

## REPO 6: docs.0latency.ai

**URL:** https://docs.0latency.ai  
**Status:** Accessible (200 OK)

### Install Path References

**Checked for:** Current published versions vs placeholders ("coming soon", "0.1.x", "beta")

**Findings:**
- References `npm install -g @0latency/mcp-server` ✅
- References `npx -y @0latency/mcp-server` ✅
- References `from zerolatency import Memory` ✅
- No "coming soon" language found ✅
- No placeholder version strings found ✅

**Code snippets found:**
```bash
npm install -g @0latency/mcp-server
npx -y @0latency/mcp-server
export ZEROLATENCY_API_KEY=zl_live_...
```

```python
from zerolatency import Memory
```

**Assessment:** Docs reference current packages without hardcoded version numbers (good — auto-updates as packages publish).

### Hardcoded Version Audit

**Searched for:** `v?0\.[0-9]\.[0-9]+`, version-specific patterns

**Result:** No hardcoded version numbers found in install examples.

**Assessment:** ✅ Docs are version-agnostic (best practice).

### Summary Table

| Metric | Status | Notes |
|--------|--------|-------|
| Site accessible | ✅ 200 | |
| Install paths current | ✅ Yes | References latest packages |
| Placeholder language | ✅ None | No "coming soon" or "beta" warnings |
| Hardcoded versions | ✅ None | Version-agnostic (good) |

**Status:** ✅ **READY FOR PHASE 1 CLOSE**

---

## Cross-Repo Summary Tables

### Version Alignment Audit

| Repo | Git Tag | Published Version | Code Version | Aligned? |
|------|---------|-------------------|--------------|----------|
| memory-product | v0.2.2 | N/A (API) | N/A | ✅ |
| zerolatency-py | v0.2.2 | 0.2.1 (PyPI) | 0.1.0 (`__init__`) | 🚨 **NO** |
| mcp-server | v0.2.2 | 0.2.2 (npm) | 0.2.2 (`package.json`) | ✅ |
| 0latency-cli | v0.3.0 | 0.3.0 (PyPI) | 0.3.0 (`__init__`) | ✅ |

### CHANGELOG Audit

| Repo | CHANGELOG Exists | Current? | Notes |
|------|------------------|----------|-------|
| memory-product | N/A | N/A | API repo, no user-facing package |
| zerolatency-py | ❌ No | N/A | Missing |
| mcp-server | ✅ Yes | ✅ Yes | Documents 0.2.2 init wizard |
| 0latency-cli | ❌ No | N/A | Missing |

### Branch Cleanup Audit

| Repo | Orphan Branches | Deletable? | Notes |
|------|-----------------|------------|-------|
| memory-product | 2 found | ✅ Yes | cp9-1-2-atoms-endpoint, fix-tenant-role-seed-drift |
| zerolatency-py | Not checked | N/A | Single-dev repo |
| mcp-server | Not checked | N/A | Subdir of memory-product |
| 0latency-cli | Not checked | N/A | Single-dev repo |

---

## BLOCKERS FOR PHASE 1 CLOSE

### BLOCKER 1: SDK Version Triple-Mismatch 🚨

**Repo:** `zerolatency-py` (Python SDK)

**Issue:**
- Git tag: v0.2.2
- PyPI published: 0.2.1
- `__init__.py`: 0.1.0

**Impact:**
- Users installing from PyPI get 0.2.1
- Code reports 0.1.0 when imported (`import zerolatency; print(zerolatency.__version__)`)
- Git tag v0.2.2 was never published
- Debugging confusion ("I installed 0.2.1 but it says 0.1.0")

**Required fix (choose ONE):**

**Option A (recommended):** Align to PyPI 0.2.1
1. Update `__init__.py` to `__version__ = "0.2.1"`
2. Delete git tag v0.2.2 (never published, orphan)
3. Commit: "Fix version: align __init__.py with published PyPI version 0.2.1"

**Option B:** Publish 0.2.2 to PyPI
1. Update `__init__.py` to `__version__ = "0.2.2"`
2. Build and publish to PyPI: `python -m build && twine upload dist/*`
3. Update docs/quickstart to reference 0.2.2

**Estimated fix time:** 5 minutes

---

### BLOCKER 2: Orphan Branches Already Merged 🚨

**Repo:** `memory-product`

**Issue:** 2 branches merged to master but not deleted:

1. **`cp9-1-2-atoms-endpoint`**
   - Merged: commit 358959f (CP9.1.2)
   - Local only (no remote)
   - Safe to delete: `git branch -d cp9-1-2-atoms-endpoint`

2. **`fix-tenant-role-seed-drift`**
   - **JUST MERGED** by other CC running CP9.1.5b (commit 4199af6)
   - Exists: local + remote
   - Safe to delete both:
     ```bash
     git branch -d fix-tenant-role-seed-drift
     git push origin --delete fix-tenant-role-seed-drift
     ```

**Impact:** Clutters branch list, confuses future audits ("is this still active?")

**Required fix:**
```bash
cd /root/.openclaw/workspace/memory-product
git branch -d cp9-1-2-atoms-endpoint
git branch -d fix-tenant-role-seed-drift
git push origin --delete fix-tenant-role-seed-drift
```

**Estimated fix time:** 2 minutes

---

## NON-BLOCKING FINDINGS

### Missing CHANGELOGs

**Repos affected:** `zerolatency-py`, `0latency-cli`

**Impact:** Users cannot see version history.

**Recommendation:** Create CHANGELOG.md for both repos documenting version history.

**Priority:** Low (Phase 2 hygiene work)

---

### CLI README — /atoms Endpoint Not Documented

**Repo:** `0latency-cli`

**Finding:** README mentions "atoms" conceptually but does not document the `/atoms` endpoint as a technical integration point.

**Impact:** Developers debugging wrapper behavior won't know where atoms are sent.

**Recommendation:** Add technical section to README:
```markdown
## Architecture

The wrapper captures all CLI I/O as role-tagged atoms and POSTs them to:
- **Local mode:** `~/.0latency/local.db` (SQLite)
- **Cloud mode:** `https://api.0latency.ai/atoms` (authenticated)
```

**Priority:** Low (Phase 2 docs polish)

---

### Uncommitted Dev Artifacts

**Repos:** `0latency-cli`, `mcp-server`

**Files:**
- Build artifacts (`dist/*.whl`, `*.tar.gz`, `*.tgz`)
- Test files (`test-*.mjs`, `soak_*.sh`)
- Python cache (`__pycache__/*.pyc`)

**Impact:** None (normal dev environment state)

**Recommendation:** Add to `.gitignore` if not already present. Not blocking.

**Priority:** Low

---

## FINAL ASSESSMENT

### Phase 1 Close Readiness

**Current status:** 🚨 **NOT READY — 2 blockers**

**Blockers:**
1. SDK version triple-mismatch (5 min fix)
2. Orphan branch cleanup (2 min fix)

**Total fix time:** ~7 minutes

**After fixes applied:** ✅ **READY TO CLOSE**

### Post-Fix Checklist

After blockers are resolved:

- [ ] SDK `__init__.py` version matches PyPI (0.2.1 or 0.2.2)
- [ ] SDK git tag matches published version
- [ ] cp9-1-2-atoms-endpoint branch deleted (local)
- [ ] fix-tenant-role-seed-drift branch deleted (local + remote)
- [ ] Re-run this audit to verify clean state

### Phase 2 Hygiene Queue (Non-Blocking)

- [ ] Create CHANGELOG.md for `zerolatency-py`
- [ ] Create CHANGELOG.md for `0latency-cli`
- [ ] Document /atoms endpoint in CLI README
- [ ] Clean up uncommitted dev artifacts

---

## NOTES FOR CP9.1.7 TESTER PASS

**Parallel work context:** This audit ran concurrently with another CC running CP9.1.5b drift-fix close-out. That CC successfully merged `fix-tenant-role-seed-drift` to master (commit 4199af6) during this audit session.

**Safe to proceed with testing:** Yes, but tester should verify:
1. SDK version mismatch (users will report "wrong version" bugs if not fixed)
2. All install paths reference correct published versions

**No merge conflicts expected:** This audit made zero code changes.

---

**End of audit.**
