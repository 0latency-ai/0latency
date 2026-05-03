# CP8 Phase 2 Tasks 5 + 6 — Autonomous Scope: Manual Trigger Endpoint + Cron Schedule

**Task:** Ship `POST /synthesis/run` (tier-gated manual trigger) AND a cron entry that runs the synthesis writer at tenant-local 03:00 daily.
**Mode:** Autonomous (CC in `--dangerously-skip-permissions`).
**Protocol:** Per `docs/AUTONOMY-PROTOCOL.md`.
**Predecessor commit:** T3 commit (validation wired into writer).
**Estimated wall-clock:** 25–45 min for CC.
**Chain position:** Chain B, task 3 of 4 (T2 → T3 → **T5+T6** → T11-fix).

**Combining T5 and T6 because** they share the same orchestration code path. The manual trigger and the cron worker both wrap T2's `synthesize_cluster` in a T4 job lifecycle — only the entry point differs (HTTP vs systemd timer).

---

## Goal

One sentence: Add `POST /synthesis/run` to the FastAPI app and a systemd timer-driven cron that both call a shared `run_synthesis_for_tenant` orchestrator that wraps T2's writer in T4's job lifecycle.

This is the first time synthesis can be **triggered**. Before this task, synthesis logic exists but only runs from a Python REPL.

---

## In scope

**Files to create:**
- `src/synthesis/orchestrator.py` — NEW (the shared run-synthesis-for-tenant function)
- `scripts/run_synthesis_cron.py` — NEW (cron entry script)
- `scripts/synthesis-cron.service` — NEW (systemd service unit)
- `scripts/synthesis-cron.timer` — NEW (systemd timer unit)
- `tests/synthesis/test_orchestrator.py` — NEW
- `tests/api/test_synthesis_run_endpoint.py` — NEW

**Files to modify:**
- `api/main.py` — register `POST /synthesis/run` route (≤30 lines added)
- `docs/ENDPOINTS.md` — append `/synthesis/run` entry (≤20 lines)

**Files to read (do not modify):**
- `src/synthesis/clustering.py`, `writer.py`, `jobs.py`
- `src/tier_gates.py` — quota and tier resolution
- `api/main.py` — for existing endpoint patterns (auth, error shapes)
- `docs/MCP-TOOLS.md` — to NOT break the existing MCP path; this task adds REST only

**Database:** Reads atom rows for clustering, writes synthesis rows + audit + jobs (all via T2/T4 modules). No migrations.

---

## Out of scope (DO NOT TOUCH)

- Any migration file
- The `memory_synthesize` MCP tool — that's Phase 4, not here. T5 only adds the REST endpoint; the MCP wrapper is later.
- Modifications to `src/synthesis/writer.py` beyond what was changed in T2/T3
- Recall path
- Any change to `mcp-server/` repo
- The `analytics_events` schema-qualifier bug — known follow-up, separate scope
- Webhook firing on synthesis_written — Phase 5
- Decision-journal writes — Phase 5

---

## Component contracts

### `src/synthesis/orchestrator.py`

```python
def run_synthesis_for_tenant(
    tenant_id: str,
    agent_id: str,
    role_scope: str = "public",
    force: bool = False,
    max_clusters: int = 5,  # cost ceiling per run
    triggered_by: str = "cron",  # 'cron' | 'manual_api' | 'manual_mcp'
) -> dict:
    """
    Orchestrate one synthesis run for a tenant:
    1. Create a synthesis_jobs row (status='queued') via jobs.create_job
    2. Mark started; find_clusters; iterate up to max_clusters
    3. For each cluster: synthesize_cluster (sync), accumulate results
    4. Mark job succeeded/failed; populate result blob
    5. Return summary dict

    Cost discipline:
    - Pre-check: skip the run entirely if zero clusters meet criteria
      (the v3 spec's cron pre-check gate)
    - Hard ceiling: max_clusters per invocation
    - Each synthesize_cluster call is independently rate-limited; partial
      runs leave already-written rows in place
    """
```

Returns:

```python
{
    "job_id": "<uuid>",
    "status": "succeeded" | "failed" | "skipped",
    "clusters_found": <int>,
    "clusters_synthesized": <int>,
    "synthesis_ids": [<uuid>, ...],
    "rate_limited": <bool>,            # True if any cluster hit quota mid-run
    "tokens_used_total": <int>,
    "duration_ms": <int>,
}
```

### `POST /synthesis/run` endpoint

```
POST /synthesis/run
Headers: X-API-Key: <tenant_api_key>
Body: {
  "agent_id": "user-justin",
  "role_scope": "public",      // optional, defaults to "public"
  "force": false,              // optional, defaults to false; bypasses recency-pre-check
  "max_clusters": 5            // optional, default 5, capped at 10
}

Response 200: <orchestrator return dict>
Response 401: missing/invalid X-API-Key
Response 403: tenant tier does not permit synthesis
                (Free tier returns this; Pro/Scale/Enterprise pass)
Response 422: malformed body
Response 429: rate-limit exceeded for current period
                (Pro tier hit 10/month, Scale hit 200/month, etc.)
```

**Tier gate:** call `tier_gates.check_synthesis_quota(tenant_id)` before any work. Free → 403. Quota exceeded → 429.

**Idempotency:** none for v1 (caller's responsibility). Phase 5 adds an idempotency-key header.

### Systemd timer + service

`scripts/synthesis-cron.service`:

```ini
[Unit]
Description=0Latency synthesis cron worker
After=memory-api.service postgresql.service
Requires=memory-api.service

[Service]
Type=oneshot
User=root
WorkingDirectory=/root/.openclaw/workspace/memory-product
EnvironmentFile=/root/.openclaw/workspace/memory-product/.env
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/memory-product/scripts/run_synthesis_cron.py
StandardOutput=journal
StandardError=journal
```

`scripts/synthesis-cron.timer`:

```ini
[Unit]
Description=0Latency synthesis cron timer (daily 03:00 UTC)

[Timer]
OnCalendar=*-*-* 03:00:00 UTC
RandomizedDelaySec=600
Persistent=true

[Install]
WantedBy=timers.target
```

Note: v3 scope says "tenant-local 03:00, configurable per tenant" — for v1, single timer at 03:00 UTC for all tenants is fine. Per-tenant scheduling is Phase 5 polish.

`scripts/run_synthesis_cron.py`:

```python
#!/usr/bin/env python3
"""Cron entry: iterate active tenants, call run_synthesis_for_tenant for each."""
import sys
from src.synthesis.orchestrator import run_synthesis_for_tenant
from src.storage_multitenant import _db_execute_rows

def main():
    # Find tenants on Pro+ tier (Free tier blocked at orchestrator level anyway)
    tenants = _db_execute_rows(
        "SELECT id::text AS tenant_id FROM memory_service.tenants WHERE tier IN ('pro', 'scale', 'enterprise')"
    )
    for row in tenants:
        try:
            # For now, run on each tenant's default agent. Multi-agent per tenant: Phase 5.
            result = run_synthesis_for_tenant(
                tenant_id=row["tenant_id"],
                agent_id="default",  # placeholder; resolve via tenant config in Phase 5
                triggered_by="cron",
            )
            print(f"[cron] tenant={row['tenant_id']} status={result['status']} "
                  f"synth={result['clusters_synthesized']}")
        except Exception as e:
            print(f"[cron] tenant={row['tenant_id']} FAILED: {e}", file=sys.stderr)
            # Continue to next tenant; don't let one tenant's failure block the cron

if __name__ == "__main__":
    main()
```

**Cron pre-check is inside `run_synthesis_for_tenant`**: if `clusters_found == 0`, the orchestrator returns `status='skipped'` without calling LLM. That's the cost gate.

---

## Steps

### Step 1 — Verify tier_gates surface for `check_synthesis_quota`

```bash
cd /root/.openclaw/workspace/memory-product
grep -n "def check_synthesis_quota\|def get_tenant_tier" src/tier_gates.py
```

**Gate G2:** both functions exist (or equivalents). Note the exact return shape — orchestrator and endpoint both consume them.

### Step 2 — Implement `src/synthesis/orchestrator.py`

Per contract above. Module imports T1's `find_clusters`, T2's `synthesize_cluster`, T4's `create_job/start_job/complete_job/fail_job`, and `tier_gates`.

Module docstring documents:
- Cost-ceiling design (max_clusters, pre-check skip)
- Triggered-by tagging for downstream analytics
- Partial-run semantics (already-written rows persist if a later cluster fails)

### Step 3 — Add `POST /synthesis/run` to `api/main.py`

Find the existing route registration pattern. Add:

```python
@app.post("/synthesis/run")
async def synthesis_run(request: Request, body: SynthesisRunRequest):
    tenant = await authenticate_tenant(request)  # use existing auth helper
    quota = tier_gates.check_synthesis_quota(tenant["id"])
    if quota["tier"] == "free":
        raise HTTPException(403, detail="Synthesis requires Pro tier or above")
    if quota["allowed"] is False:
        raise HTTPException(429, detail=f"Quota exceeded: {quota['reason']}")
    result = run_synthesis_for_tenant(
        tenant_id=tenant["id"],
        agent_id=body.agent_id,
        role_scope=body.role_scope or "public",
        force=body.force or False,
        max_clusters=min(body.max_clusters or 5, 10),
        triggered_by="manual_api",
    )
    return result
```

Define `SynthesisRunRequest` Pydantic model in the same file alongside other request models.

### Step 4 — Implement `scripts/run_synthesis_cron.py`

Per contract above. Make it executable: `chmod +x scripts/run_synthesis_cron.py` after writing.

### Step 5 — Implement systemd unit files

Write `scripts/synthesis-cron.service` and `scripts/synthesis-cron.timer` per contract. **Do NOT install or enable them yet** — that's Step 9 (manual review).

### Step 6 — Tests

`tests/synthesis/test_orchestrator.py` — six tests:
1. `test_zero_clusters_returns_skipped` — fresh tenant; status='skipped', no LLM call
2. `test_normal_run_creates_job_and_synthesis` — real cluster; job row exists with status='succeeded'; synthesis_ids non-empty
3. `test_max_clusters_caps_run` — cluster count 8, max_clusters=3; only 3 synthesized
4. `test_rate_limited_mid_run_marks_partial` — quota allows 2; first 2 synthesized, 3rd hits limit; result has rate_limited=True and partial synthesis_ids list
5. `test_writer_failure_marks_job_failed` — inject a failing validator; orchestrator marks job failed, error captured
6. `test_triggered_by_propagates_to_audit` — check synthesis_audit_events row has triggered_by in payload

`tests/api/test_synthesis_run_endpoint.py` — six tests:
1. `test_endpoint_200_on_pro_tier` — fixture tenant on Pro; POST returns 200 with orchestrator dict
2. `test_endpoint_403_on_free_tier` — fixture tenant on Free; POST returns 403
3. `test_endpoint_429_on_quota_exceeded` — Pro tenant at quota; POST returns 429
4. `test_endpoint_401_missing_key` — no X-API-Key; returns 401
5. `test_endpoint_422_malformed_body` — missing agent_id; returns 422
6. `test_endpoint_caps_max_clusters_at_10` — body has max_clusters=999; orchestrator called with 10

Mark integration. Cleanup fixtures.

### Step 7 — Test gate (G3)

```bash
pytest tests/synthesis/test_orchestrator.py tests/api/test_synthesis_run_endpoint.py -v --tb=short 2>&1 | tee /tmp/t5t6-test-output.txt
grep -q "passed" /tmp/t5t6-test-output.txt && ! grep -q "failed" /tmp/t5t6-test-output.txt && echo 'T5+T6 GATE PASS'
```

### Step 8 — Restart memory-api, smoke test endpoint

```bash
systemctl restart memory-api
sleep 3
systemctl is-active memory-api  # → "active"
curl -sS -X POST http://localhost:8420/synthesis/run \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "user-justin", "max_clusters": 1}' \
  | tee /tmp/t5-smoke.json
```

**Gate G1:** response is a JSON dict with `status` field. If `status: "succeeded"` and `clusters_synthesized: 1`, T5 works end-to-end.

### Step 9 — **HALT for human review of systemd installation**

Write `CP8-P2-T5T6-CRON-INSTALL-REVIEW.md`:

```markdown
# CP8 P2 T5+T6 — Cron units ready for installation

**Status:** Endpoint shipped + tested. Cron unit files written but NOT installed.

**To install cron (manual, one-time):**

  cp scripts/synthesis-cron.service /etc/systemd/system/
  cp scripts/synthesis-cron.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now synthesis-cron.timer
  systemctl list-timers | grep synthesis-cron

**To verify cron will fire:**

  systemctl status synthesis-cron.timer
  # Look for: Trigger: <next 03:00 UTC>

**To dry-run cron once manually before letting timer fire:**

  python3 /root/.openclaw/workspace/memory-product/scripts/run_synthesis_cron.py
  journalctl -u synthesis-cron.service --since "5 minutes ago"

**To rollback (if needed):**

  systemctl disable --now synthesis-cron.timer
  rm /etc/systemd/system/synthesis-cron.{service,timer}
  systemctl daemon-reload
```

CC commits the code/units (Step 10), then exits cleanly. Justin installs the timer at his own discretion. **The endpoint works without the timer being installed.**

### Step 10 — Commit

```bash
git add src/synthesis/orchestrator.py \
  scripts/run_synthesis_cron.py \
  scripts/synthesis-cron.service scripts/synthesis-cron.timer \
  api/main.py docs/ENDPOINTS.md \
  tests/synthesis/test_orchestrator.py tests/api/test_synthesis_run_endpoint.py
git status
git diff --cached --stat
```

Commit message:

```
CP8 Phase 2 T5+T6: POST /synthesis/run + cron timer

T5: tier-gated manual trigger endpoint
- POST /synthesis/run; 200/403/422/429 responses
- Free tier blocked at 403; quota exceeded at 429
- max_clusters capped at 10 server-side regardless of body

T6: systemd timer-driven cron
- scripts/run_synthesis_cron.py iterates Pro+ tenants
- scripts/synthesis-cron.timer fires daily 03:00 UTC
- scripts/synthesis-cron.service is the oneshot worker
- Per-tenant scheduling deferred to Phase 5; v1 is single UTC slot

Both share src/synthesis/orchestrator.py:
- run_synthesis_for_tenant wraps T2 writer in T4 job lifecycle
- Cost gates: clusters_found==0 → status='skipped' (no LLM)
- Hard ceiling: max_clusters per run (default 5)
- Partial-run semantics: rate-limit mid-run leaves earlier rows in place

Cron units written but NOT installed; manual install per
CP8-P2-T5T6-CRON-INSTALL-REVIEW.md.

Verification receipts:
[CC fills in: test pass, smoke endpoint hit with status=succeeded,
 synthesis_ids count]

Files:
  src/synthesis/orchestrator.py (NEW),
  scripts/run_synthesis_cron.py (NEW, executable),
  scripts/synthesis-cron.service (NEW),
  scripts/synthesis-cron.timer (NEW),
  api/main.py (+~30 lines, 1 endpoint + 1 request model),
  docs/ENDPOINTS.md (+~20 lines, /synthesis/run entry),
  tests/synthesis/test_orchestrator.py (NEW, 6 tests),
  tests/api/test_synthesis_run_endpoint.py (NEW, 6 tests)
```

```bash
git commit -F /tmp/cp8-p2-t5t6-commit-msg.txt
git log -1 --stat
git push origin master
```

### Step 11 — Verify no regression

```bash
journalctl -u memory-api --since "10 minutes ago" --no-pager | grep -E "ERROR|CRITICAL" | grep -v "analytics_events"
```

**Gate G2:** clean.

---

## Halt conditions (specific to this task)

1. **`memory-api` fails to restart** in step 8. Halt — endpoint code broke service. Revert via `git reset --hard HEAD~1` and restart.
2. **Endpoint returns 500** on smoke test. Halt — orchestrator path is broken in production-like settings even if tests pass.
3. **`scripts/` directory doesn't exist.** Halt — repo layout has changed; may need a different location.
4. **`docs/ENDPOINTS.md` doesn't exist.** Halt — manually re-locate the endpoint reference doc, do not invent a new one.

---

## Definition of done

1. `POST /synthesis/run` works end-to-end against prod with real tenant key.
2. All 12 tests pass.
3. Cron unit files written; install paused for human review.
4. `memory-api` restarted cleanly post-deploy.
5. Single commit pushed with real receipts.
6. No `CP8-P2-T5T6-BLOCKED.md`.
7. `journalctl` clean.

**Deploy required** (memory-api restart) — handled in Step 8 before commit.
