# CP-architecture-1 — MCP Server Stateless-Edge Refactor

**Type:** Autonomy scope doc for CC (Sonnet)
**Priority:** P0 — blocks further CP8 Phase 2 work
**Created:** 2026-05-03 (amended 2026-05-03 to add rotation runbook page)
**Trigger:** 2026-05-02 cascade (8 hours of misdiagnosis traceable to MCP credential validation gaps)
**Estimated execution:** 1–2 hours wall clock at current chained-autonomy pacing

---

## Problem statement

The MCP server at `/root/0latency-mcp-unified/src/server-sse.ts` performs cosmetic-only validation of API keys (`startsWith("zl_")`) before passing them to a tenant lookup. The pre-validation log line `[MCP POST/GET] Request from <ip> with valid API key` fires on the cosmetic check and not on actual validation, making the log misleading. When a key is invalid (revoked, rotated, malformed), the log says "valid API key" while the downstream tenant lookup silently fails, producing 401-class cascade failures with no visible signal at the connector layer.

This is a stateless-edge violation. The MCP server should not pretend to validate. It should forward the client-provided key to REST and return REST's verdict — clear success or clear failure with a meaningful message.

## Goal

Make the MCP server a stateless edge service that:
1. Forwards client-provided API keys to REST without prefix-based gatekeeping.
2. Returns REST's actual auth verdict to the client.
3. Logs honestly — no "valid API key" messaging until validation has actually succeeded.

After this ships, the only surface that knows whether a key is valid is the REST API talking to the DB. The MCP server becomes pass-through.

## Non-goals

- Not implementing API key versioning / multi-key tenants (that's CP8 Phase 2 v3 Task 12 — separate scope).
- Not changing the REST API's auth logic.
- Not changing the MCP tool schemas or the 14-tool surface area.
- Not republishing Smithery listing (separate follow-up after this lands).

---

## Pre-flight gates (run before starting)

```bash
# 1. Confirm we're on master, clean tree, latest pull
cd /root/.openclaw/workspace/memory-product
git status
git rev-parse HEAD
# Expected: HEAD = 4eb70ab (or later if other commits have landed)

# 2. Confirm MCP server source location
ls -la /root/0latency-mcp-unified/src/server-sse.ts
# Expected: file exists

# 3. Confirm REST API auth endpoint exists and works
set -a && source .env && set +a
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ZEROLATENCY_API_KEY" http://localhost:8420/agents
# Expected: 200

# 4. Capture baseline for revert if needed
cp /root/0latency-mcp-unified/src/server-sse.ts /tmp/server-sse.ts.pre-arch1
```

If any gate fails, stop and report.

---

## Current code (audit findings 2026-05-03)

In `/root/0latency-mcp-unified/src/server-sse.ts`:

```typescript
// Line 432 (POST handler)
const apiKey = extractApiKey(req);
console.log(`[MCP POST] Request from ${req.ip}`, apiKey ? "with valid API key" : "MISSING API KEY");

if (!apiKey || !apiKey.startsWith("zl_")) {
  // 401 response
}

// Line 449 (GET handler)
const apiKey = extractApiKey(req);
console.log(`[MCP GET] Request from ${req.ip}`, apiKey ? "with valid API key" : "MISSING API KEY");

if (!apiKey || !apiKey.startsWith("zl_")) {
  // 401 response
}

const tenantId = await getTenantId(apiKey);  // ← real validation happens here
```

**Note:** earlier handoff suggested `MCP_API_KEY` env var was being held against. Live audit found no such env var in the source. The actual issue is the cosmetic prefix check + lying log, not a cached env var.

---

## Required changes

### Change 1: Remove cosmetic `startsWith("zl_")` gate

In both POST handler (line 434) and GET handler (line 452), simplify the validation to existence-only:

```typescript
// BEFORE
if (!apiKey || !apiKey.startsWith("zl_")) {
  return res.status(401).json({ error: "Missing or invalid API key" });
}

// AFTER
if (!apiKey) {
  return res.status(401).json({ error: "Missing API key" });
}
```

The prefix check provides no security value (anyone can prefix `zl_`) and falsely signals validation.

### Change 2: Fix the misleading log lines

In both POST handler (line 432) and GET handler (line 450), replace the dishonest "valid API key" log with a presence-only log:

```typescript
// BEFORE
console.log(`[MCP POST] Request from ${req.ip}`, apiKey ? "with valid API key" : "MISSING API KEY");

// AFTER
console.log(`[MCP POST] Request from ${req.ip}`, apiKey ? "with API key (validation pending)" : "MISSING API KEY");
```

Apply same change to the GET handler line 450.

### Change 3: Surface tenant-lookup failure clearly

After `getTenantId(apiKey)` returns (line 457 in GET handler — confirm same pattern in POST handler), the failure path needs explicit logging and a clear 401 with a message that distinguishes "key not found" from other failure modes.

Find the existing `getTenantId` failure handling and ensure:
- A 401 is returned with body `{"error": "API key not recognized. If you recently rotated keys, update your client configuration."}`
- A log line fires: `[MCP {METHOD}] Auth FAILED for ${req.ip}: tenant lookup returned no match for key suffix ${apiKey.slice(-4)}` — log only the last 4 characters of the key, never the full key.

If `getTenantId` currently throws or returns null silently, wrap it explicitly:

```typescript
const tenantId = await getTenantId(apiKey);
if (!tenantId) {
  console.log(`[MCP GET] Auth FAILED for ${req.ip}: tenant lookup returned no match for key suffix ${apiKey.slice(-4)}`);
  return res.status(401).json({ error: "API key not recognized. If you recently rotated keys, update your client configuration." });
}
```

Apply equivalent pattern in the POST handler.

### Change 4: Add a short rotation note to existing docs

Find the existing docs structure under `/var/www/0latency/docs/` (or wherever the docs site sources content). Identify the most natural existing page for a "key rotation" note — likely an authentication or getting-started page. If no such page exists, append the note to the most-trafficked docs index page.

Add a short paragraph (3–5 sentences) at a stable URL that covers:

- After rotating a key, update any client that holds it: Claude.ai connector, Claude Desktop / Claude Code `.mcp.json`, Chrome extension, `.env` files, CI secrets.
- A one-line verification curl: `curl -H "Authorization: Bearer YOUR_NEW_KEY" https://api.0latency.ai/agents` should return 200.
- A forward-looking note that key versioning with a grace window is on the roadmap.

The exact URL of the resulting anchor (e.g. `https://0latency.ai/docs/getting-started#key-rotation`) is what the 401 message in Change 3 points at. Update the error string in Change 3 to use the actual URL produced:

```typescript
return res.status(401).json({
  error: "API key not recognized. If you recently rotated keys, see <ROTATION_DOCS_URL> for what to update."
});
```

Apply equivalent change in the POST handler. Replace `<ROTATION_DOCS_URL>` with the real URL once the doc snippet is placed.

### Change 5: Build, deploy, smoke test

```bash
cd /root/0latency-mcp-unified
npm run build  # or whatever the existing build command is — check package.json scripts

# Deploy: existing pattern is cp -r dist/ to wherever the running service reads from
# Confirm by inspecting how the service is currently started (systemctl or pm2 or similar)
systemctl status 0latency-mcp 2>/dev/null || pm2 list 2>/dev/null || ps aux | grep -i mcp
```

After deployment, run smoke tests:

```bash
# Test 1: missing key returns 401 with clear message
curl -s -w "\nHTTP %{http_code}\n" https://mcp.0latency.ai/mcp

# Test 2: bogus key returns 401 with "not recognized" message (tests Change 3)
curl -s -w "\nHTTP %{http_code}\n" "https://mcp.0latency.ai/mcp?key=zl_bogus_does_not_exist"

# Test 3: real key works
curl -s -w "\nHTTP %{http_code}\n" "https://mcp.0latency.ai/mcp?key=$ZEROLATENCY_API_KEY"

# Test 4: log line is honest — should say "validation pending" not "valid API key"
journalctl -u 0latency-mcp --since "1 minute ago" | tail -20
# OR
pm2 logs 0latency-mcp --lines 20
```

---

## Functional gates (must all pass before commit)

1. **Gate 1:** Missing key request → 401 with body containing `"Missing API key"`.
2. **Gate 2:** Bogus key (random `zl_xxxxx` not in DB) → 401 with body containing `"not recognized"` and a URL pointing at the rotation note, and log line containing `"Auth FAILED"` and key suffix only (last 4 chars).
3. **Gate 3:** Real production key → 200 with valid MCP response.
4. **Gate 4:** Log lines no longer contain the string `"with valid API key"`. Search the new build:
   ```bash
   grep -rn "with valid API key" /root/0latency-mcp-unified/dist/ /root/0latency-mcp-unified/src/
   # Expected: no matches
   ```
5. **Gate 5:** All 14 MCP tools still callable from a connected Claude session (smoke via `list_agents` from the session that has the connector configured).
6. **Gate 6:** Full key value never appears in any log line. Verify:
   ```bash
   journalctl -u 0latency-mcp --since "5 minutes ago" | grep -E "zl_[a-zA-Z0-9_]{20,}" | head -5
   # Expected: no matches (only suffix logging is permitted)
   ```
7. **Gate 7:** The rotation note URL referenced in the 401 message returns 200.

---

## Commit pattern

```bash
cd /root/0latency-mcp-unified
git add src/server-sse.ts
git commit -m "CP-architecture-1: stateless edge refactor

Drop cosmetic startsWith(\"zl_\") validation. Rely on REST tenant
lookup as single source of truth. Fix misleading 'valid API key'
log line that fired before any actual validation.

Surfaces auth failure clearly with key suffix only (never full key).
Resolves silent 401 cascade pattern from 2026-05-02.
"

# Per ops standard: commit locally; push from root SSH if claude user lacks creds
```

If a separate `dist/` deploy artifact pattern is in use and is git-tracked, include the rebuilt artifact in the same commit.

---

## Out of scope follow-ups (do NOT touch)

- Smithery republish without `?key=` URL embedding — separate task after this lands
- API key versioning (`api_keys` table replacing single `api_key_live` column) — CP8 P2 T12, separate scope
- Build/deploy hygiene rework (`/root/0latency-mcp-sse/dist/` git tracking, rollback mechanism) — separate task
- T8 `docs/VERBATIM-GUARANTEE.md` — fold this into the same execution session if time permits, but author it as a separate commit. Scope: 4-write-path audit (atom write, import-thread, resume/async, seed) confirming raw atoms are stored before any extraction; ~1 page of markdown.

---

## Rollback plan

If smoke tests fail after deployment:

```bash
cp /tmp/server-sse.ts.pre-arch1 /root/0latency-mcp-unified/src/server-sse.ts
cd /root/0latency-mcp-unified && npm run build
# Redeploy via the same path
systemctl restart 0latency-mcp  # or pm2 restart, whichever is in use
```

Capture the failure mode in a comment on the commit before reverting, so the next attempt has the data.

---

## Done criteria

- All 6 functional gates pass.
- Commit lands on master.
- 5-minute observation period after deploy: no 5xx errors in `journalctl`, MCP traffic continuing as normal.
- Update memory: rotation lesson is now obsolete (DB is single source of truth post-fix). Smithery listing flagged as needing republish in P1 queue.
