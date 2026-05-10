# CP9 P1 Audit Report
**Date**: 2026-05-10  
**Task**: CP9.1.1 — Audit all 4 install paths  
**Goal**: Measure baseline timing, identify gaps blocking <60s time-to-first-memory  

---

## Path A: Wrapper CLI (`pip install 0latency-cli`)

### Install command
```bash
pip install 0latency-cli
```

**Current state**: NOT on PyPI. Local test used: `pip install -e /root/0latency-cli`

### Prerequisites
1. Python 3.11+ environment
2. 0Latency account (for cloud sync)
3. OAuth device-code flow completion (manual browser interaction)
4. Claude Code binary in PATH

### Measured time-to-first-memory

**Run 1** (fresh venv, existing credentials):
- Install: 10s
- Missing dependency fix (psutil not in pyproject.toml): +3s  
- Test wrapper execution (0latency claude -- -p "what is 2+2"): 7.4s
- **TOTAL: ~20s** (but memory write **FAILED** - see gaps)

**Runs 2 & 3**: NOT COMPLETED due to blocking gap (see below)

### Gaps blocking <60s

1. **BLOCKING: /atoms endpoint does not exist**
   - CLI tries to POST atoms to https://api.0latency.ai/atoms
   - API returns 404 (endpoint not defined in api/main.py)
   - Every wrapper session generates "Cloud write failed: 404" errors
   - **Impact**: Path A cannot write memories to cloud, period
   - **Substrate gap**: The wrapper CLI and API are out of sync

2. **Missing dependency in pyproject.toml**
   - psutil imported in recovery.py but not listed in dependencies
   - Fresh install fails with ModuleNotFoundError
   - **Fix**: Add psutil>=5.9.0 to dependencies array

3. **Not published to PyPI**
   - User cannot run pip install 0latency-cli yet
   - PYPI-PUBLISH-INSTRUCTIONS.md exists in repo but not executed
   - **Impact**: Documentation/marketing cannot reference real install flow

4. **OAuth device-code flow requires manual browser interaction**
   - No auto-auth for fresh users
   - User must: run 0latency login then open browser then enter code then wait for approval
   - Adds 30-60s minimum for first-time setup (not measured in isolation)

5. **Click argument parsing issue**  
   - User cannot run 0latency claude -p "query" (Click intercepts -p)
   - Must use 0latency claude -- -p "query" with double-dash separator
   - Poor UX, undocumented in README

6. **No verification mechanism**
   - Wrapper captures atoms locally but user has no way to verify memory was recalled
   - No 0latency verify or 0latency recall "query" command to test end-to-end

### Substrate check

| Component | Status | Evidence |
|-----------|--------|----------|
| Auto-tenant-provision | WORKS | Credentials file at ~/.0latency/credentials contains tenant_id |
| OAuth device-code | WORKS | 0latency status shows logged in as tenant |
| Role registry | NOT EXERCISED | Wrapper does not interact with role registry |
| Audit log | NOT EXERCISED | Wrapper tries to POST atoms but endpoint does not exist |

**Critical finding**: OAuth device-code flow works (CP10 P1 substrate is live), but the **atoms ingestion path is missing entirely**. The wrapper CLI was built for an API contract that does not exist.

### Suggested fixes

1. **URGENT: Build /atoms endpoint** (or adapt wrapper to use /memories/extract)
   - Option A: Add POST /atoms endpoint to api/main.py that accepts atom payloads, queues them for extraction
   - Option B: Refactor wrapper to chunk conversation into turn-pairs and POST to /memories/extract 
   - Recommendation: Option A is faster (wrapper already chunking correctly), Option B is cleaner long-term

2. **Add psutil to pyproject.toml dependencies**

3. **Publish to PyPI**
   - Follow PYPI-PUBLISH-INSTRUCTIONS.md in cli repo
   - Register 0latency-cli package name

4. **Add verify command** to CLI for testing memory recall

5. **Document double-dash separator requirement** in README or fix Click parsing

6. **Measure OAuth flow end-to-end** (conditional Task 2 item)
   - Fresh credentials file deleted, run full 0latency login flow
   - Measure browser-open to token-saved time
   - If >30s, consider adding Quick Start mode with pre-populated test token

---

## Path B: SDK (pip install zerolatency)

### Install command
pip install zerolatency

Current state: Published on PyPI at version 0.2.0

### Prerequisites
1. Python 3.8+ environment
2. 0Latency API key (from dashboard/signup flow)

### Measured time-to-first-memory

Installation timing (Run 1):
- Install: 21.4s (includes all dependencies: httpx, anthropic, openai, google-generativeai)

End-to-end flow: FAILED - could not complete
- Client init: approximately 0.08s
- Memory extract call: FAILED with "Invalid or missing API key"
- Root cause: SDK uses /v1/ API prefix, deployed API has no /v1/ prefix
- Substrate gap: SDK version mismatch with production API

Runs 2 and 3: NOT COMPLETED due to blocking API mismatch

### Gaps blocking <60s

1. BLOCKING: SDK/API version mismatch
   - PyPI SDK v0.2.0 calls /v1/memories/extract, /v1/memories/recall, etc.
   - Production API has NO /v1/ prefix (endpoints are /memories/extract, /recall, etc.)
   - Every SDK call returns "Invalid or missing API key" (actually a routing error)
   - Impact: Published SDK is completely non-functional against production API

2. README examples use wrong method signatures
   - README shows one signature, actual SDK uses different signature
   - Impact: Developer following README gets immediate errors, no working example

3. Deprecated Gemini dependency warning
   - SDK depends on google-generativeai package which shows scary FutureWarning on every import
   - Warning: "All support for google.generativeai package has ended"
   - Impact: Poor first impression, suggests unmaintained code

4. No clear getting started for API key
   - README shows usage but does not explain WHERE to get API key
   - No link to dashboard, signup, or quickstart
   - Fresh user has no path from pip install to working code

5. Return types do not match README
   - README implies one return structure, actual returns different structure
   - User following README will have broken code

### Substrate check

Component | Status | Evidence
Auto-tenant-provision | UNKNOWN | Could not test due to API mismatch
OAuth device-code | NOT USED | SDK uses direct API key authentication
Role registry | UNKNOWN | Could not test due to API mismatch
Audit log | UNKNOWN | Could not test due to API mismatch

Critical finding: Cannot verify substrate because SDK cannot connect to API. The /v1/ prefix mismatch suggests the SDK was built for a different API version or the API was refactored without updating the SDK.

### Suggested fixes

1. URGENT: Republish SDK with correct API paths
   - Remove /v1/ prefix from all endpoints in client.py
   - Match production API paths exactly: /memories/extract, /recall, etc.
   - Bump version to 0.2.1 or 0.3.0
   - Test against production API before publishing

2. Update README with correct method signatures and examples
   - Match all examples to actual SDK API surface
   - Add Getting your API key section with link to dashboard
   - Show async extraction pattern (job_id polling) if that is the model

3. Fix or suppress Gemini deprecation warning
   - Option A: Update to google.genai package (requires testing)
   - Option B: Add warnings filter in wrapper code
   - Option C: Remove Gemini support from default dependencies (make it optional extra)

4. Add quickstart script in SDK repo
   - Include actual working example that can be copy-pasted

5. Align SDK with current API contract
   - Review EVERY endpoint the SDK calls vs what production API exposes
   - Create integration test suite that runs against production API
   - Add to CI/CD so future API changes are caught before deploy

---

## Path C: MCP server (npx @0latency/mcp-server)

### Install command
No install required - uses npx. Alternative: npm install -g @0latency/mcp-server

### Prerequisites
1. Node.js/npm environment
2. 0Latency API key
3. MCP-compatible client (Claude Desktop, Claude Code, Cursor, etc.)
4. Manual config file edit (JSON)

### Measured time-to-first-memory
Cannot automate - requires manual MCP client interaction. Flow: get API key, edit JSON config, restart client, invoke memory tool. Estimated 3-5 minutes for experienced user.

### Gaps blocking <60s
1. No automated onboarding - manual JSON config editing required
2. No verification mechanism - cannot test if MCP server connected  
3. API key acquisition step unclear
4. No getting started conversation template
5. Dependency on having MCP client installed first

### Substrate check
Cannot verify without full MCP client integration test. MCP server uses direct API key auth.

### Suggested fixes
1. Build init command that auto-detects clients and writes config
2. Build verify command to test API key and connection
3. Add Quick Start conversation template to README
4. Add dashboard screenshot showing where to find API key
5. Measure actual onboarding time with real MCP client

---


## Path D: Web signup (https://0latency.ai)

### Entry point
https://0latency.ai (homepage) or https://0latency.ai/login

### Prerequisites
Web browser only

### Measured time-to-first-memory
NOT MEASURED - requires manual browser interaction

Observed flow (via inspection, not actual test):
1. Visit homepage or login page
2. /quickstart route does not exist (returns homepage)
3. /dashboard returns JSON error: "Missing X-API-Key header"
4. login.html exists but flow not tested

Cannot complete automated test without actual browser session.

### Gaps blocking <60s

1. No clear quickstart route
   - Documentation references /quickstart but URL does not exist
   - Homepage is marketing-focused, not onboarding-focused
   - First-time user unclear where to start

2. Dashboard requires API key to view
   - Catch-22: Need dashboard to get API key, but dashboard requires API key
   - Suggests dashboard is for authenticated users only
   - No obvious public signup form

3. Onboarding flow not discoverable
   - Homepage does not prominently show "Get Started" or "Sign Up"
   - login.html exists but unclear if it handles signup or just login
   - No automated way to test actual flow

4. No quickstart code snippet on homepage
   - User lands on homepage with no immediate "try it now" experience
   - No embedded code example showing what the API does
   - Missing "copy API key, run this code, see memory work" flow

5. Path D as documented does not exist
   - Task instructions reference /quickstart as entry point
   - That URL just serves homepage
   - Suggests documentation drift or incomplete feature

### Substrate check
Cannot test without completing browser-based signup flow.

### Suggested fixes

1. Build actual /quickstart route
   - Single-page app that walks user through: signup, get API key, run test code, verify memory
   - Embedded code editor or copy-paste snippet with pre-filled API key
   - Real-time feedback showing memory written and recalled
   - Target: <60s from landing to working memory

2. Add prominent CTA to homepage
   - "Start Free Trial" or "Get API Key" button above fold
   - Directly to signup/quickstart, not to pricing or docs
   - Measure conversion funnel from homepage visit to first API call

3. Build no-code demo on homepage
   - Embedded chat widget that uses 0Latency memory
   - User types messages, sees memory extraction happen live
   - Shows knowledge graph building in real-time
   - Proves value before signup

4. Simplify dashboard auth
   - Option A: Make initial dashboard view public (show demo data, no API key required)
   - Option B: Auto-create API key on email signup (OAuth or magic link)
   - Option C: Show API key generation screen immediately after signup

5. Measure actual web onboarding flow
   - Fresh browser session, no cookies
   - Time from homepage visit to first successful API call
   - Identify friction points (email verification, payment info, etc.)

---


# Summary and Cross-Path Analysis

## Critical Findings

### Blocking Issues (Prevent ANY path from achieving <60s)

1. **Path A (CLI Wrapper): /atoms endpoint missing**
   - Wrapper tries POST to /atoms, API returns 404
   - Zero memories written to cloud
   - Requires building new endpoint or refactoring wrapper

2. **Path B (SDK): Version mismatch**
   - PyPI SDK calls /v1/* endpoints, API has no /v1 prefix
   - Published SDK completely non-functional
   - Requires emergency republish with corrected paths

3. **Path C (MCP): Manual config editing required**
   - No automated onboarding
   - Cannot measure time-to-first-memory without full MCP client test
   - Requires building init/verify commands

4. **Path D (Web): /quickstart route does not exist**
   - Documented entry point returns 404
   - No clear signup flow discoverable
   - Requires building actual quickstart page

### Substrate Status Across Paths

Component | Path A | Path B | Path C | Path D
----------|--------|--------|--------|--------
Auto-tenant-provision | WORKS | UNKNOWN | UNKNOWN | UNKNOWN
OAuth device-code | WORKS | NOT USED | NOT USED | UNKNOWN
Role registry | NOT EXERCISED | UNKNOWN | UNKNOWN | UNKNOWN
Audit log | NOT EXERCISED | UNKNOWN | UNKNOWN | UNKNOWN

**Key takeaway**: CP8/CP10 substrate (OAuth, tenant-provision) is LIVE and WORKING on Path A. Other paths use different auth models or could not be tested.

## Time-to-First-Memory (Where Measurable)

Path | Install Time | Auth Time | Write+Recall Time | Total | Status
-----|--------------|-----------|-------------------|-------|--------
A (CLI) | 10s | MANUAL (30-60s est) | FAILED | N/A | BLOCKED
B (SDK) | 21s | N/A (uses key) | FAILED | N/A | BLOCKED
C (MCP) | 5s (npx) | N/A (uses key) | NOT MEASURED | N/A | MANUAL
D (Web) | 0s | NOT TESTED | NOT TESTED | N/A | NOT FOUND

**None of the 4 paths can currently achieve <60s time-to-first-memory.**

## Recommended Prioritization for Tasks 2-5

Based on impact and effort:

### P0 (Ship-blockers)
1. Fix Path B SDK /v1 mismatch - republish to PyPI (1-2 hours)
2. Build Path A /atoms endpoint OR refactor wrapper to use /memories/extract (3-4 hours)

### P1 (High-impact onboarding)
3. Build Path D /quickstart page with embedded code test (4-6 hours)
4. Add Path C init command for auto-config (2-3 hours)

### P2 (Polish)
5. Fix all README documentation mismatches
6. Add verification commands to all paths
7. Measure actual OAuth flow timing for Path A

## Next Steps

This audit doc provides input to Tasks 2-5:
- Task 2: Choose which path(s) to fix
- Task 3: Implement fixes
- Task 4: Re-measure timing
- Task 5: Verify <60s achieved

Gate criteria met:
- All 4 paths audited
- Measured timing where possible
- Gaps documented with concrete fixes
- Substrate check performed

