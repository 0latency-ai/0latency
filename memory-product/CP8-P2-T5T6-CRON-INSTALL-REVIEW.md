# CP8 Phase 2 T5+T6 — Cron Installation Review

## Summary

Implementation of manual synthesis trigger endpoint (T5) and automated cron schedule (T6) is COMPLETE.

**Manual Trigger Endpoint:** ✅ WORKS  
**Systemd Units Created:** ✅ READY FOR INSTALLATION  
**Tests:** ✅ ALL PASSING (6/6 orchestrator tests)

## What Was Built

### 1. Orchestrator Logic (`src/synthesis/orchestrator.py`)
- Shared function `run_synthesis_for_tenant()` for both manual and cron triggers
- Job lifecycle management (create → running → succeeded/failed)
- Handles rate limiting mid-run
- Returns structured result dict

### 2. Manual Trigger Endpoint (`api/main.py`)
- **POST /synthesis/run**
- Tier-gated: Free tier blocked (403), Pro+ rate-limited (429)
- Input: `{agent_id, max_clusters (1-10), force, role_scope}`
- Output: `{job_id, status, clusters_found, clusters_synthesized, synthesis_ids, rate_limited, tokens_used_total, duration_ms}`
- **Performance:** ~3 minutes for 1 cluster synthesis (includes clustering + LLM call + DB writes)

### 3. Cron Worker (`scripts/run_synthesis_cron.py`)
- Executable Python script
- Iterates Pro+ tenants
- Calls orchestrator for each tenant
- Continues on individual failures
- Exit code 0 even if some tenants fail

### 4. Systemd Units (NOT YET INSTALLED)

**synthesis-cron.service:**
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

**synthesis-cron.timer:**
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

## Test Results

**Orchestrator Tests:** 6/6 PASSED (18 minutes runtime)
```
tests/synthesis/test_orchestrator.py::test_zero_clusters_returns_skipped PASSED
tests/synthesis/test_orchestrator.py::test_normal_run_creates_job_and_synthesis PASSED
tests/synthesis/test_orchestrator.py::test_max_clusters_caps_synthesis PASSED
tests/synthesis/test_orchestrator.py::test_rate_limited_midrun_stops_early PASSED
tests/synthesis/test_orchestrator.py::test_result_has_duration PASSED
tests/synthesis/test_orchestrator.py::test_job_id_is_uuid PASSED
```

**Endpoint Smoke Test:** ✅ PASSED
```bash
curl -X POST http://localhost:8420/synthesis/run \
  -H "X-API-Key: $ZEROLATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d {agent_id: user-justin, max_clusters: 1}
  
# Response (after ~3 min):
{
  "job_id": "73595b16-940b-4d1f-9c3e-c433651c01f9",
  "status": "succeeded",
  "clusters_found": 117,
  "clusters_synthesized": 1,
  "synthesis_ids": ["9cbe65bd-301f-444e-9bf3-f814b4f6d5ca"],
  "rate_limited": false,
  "tokens_used_total": 1415,
  "duration_ms": 173958
}
```

## Installation Instructions (Step 9 — MANUAL REVIEW REQUIRED)

### Prerequisites
- Memory API service must be running
- PostgreSQL database accessible
- .env file with MEMORY_DB_CONN configured

### Installation Steps

1. **Copy systemd units to system directory:**
```bash
sudo cp scripts/synthesis-cron.service /etc/systemd/system/
sudo cp scripts/synthesis-cron.timer /etc/systemd/system/
```

2. **Reload systemd daemon:**
```bash
sudo systemctl daemon-reload
```

3. **Enable and start the timer:**
```bash
sudo systemctl enable synthesis-cron.timer
sudo systemctl start synthesis-cron.timer
```

4. **Verify timer is active:**
```bash
systemctl status synthesis-cron.timer
systemctl list-timers --all | grep synthesis
```

5. **Test manual trigger (optional):**
```bash
sudo systemctl start synthesis-cron.service
journalctl -u synthesis-cron.service -f
```

### Uninstallation (if needed)
```bash
sudo systemctl stop synthesis-cron.timer
sudo systemctl disable synthesis-cron.timer
sudo rm /etc/systemd/system/synthesis-cron.{service,timer}
sudo systemctl daemon-reload
```

## Performance Characteristics

- **Endpoint latency:** ~3 minutes for 1 cluster
- **Cron runtime estimate:** ~5-30 minutes depending on tenant count and cluster availability
- **Resource usage:** Moderate CPU during clustering, LLM calls handled by Anthropic API

## Known Issues / Notes

1. **Long Response Times:** Synthesis operations take 2-3 minutes due to clustering and LLM calls. Clients should use timeouts ≥180 seconds.

2. **Async/Sync Fix:** Endpoint was changed from `async def` to `def` because all operations are synchronous (connection pools, orchestrator calls).

3. **Clustering Module:** Fixed module-level connection pool initialization that was causing import errors. Now uses lazy loading.

## Files Changed

**New Files:**
- `src/synthesis/orchestrator.py` (170 lines)
- `scripts/run_synthesis_cron.py` (94 lines, executable)
- `scripts/synthesis-cron.service`
- `scripts/synthesis-cron.timer`
- `tests/synthesis/test_orchestrator.py` (6 tests)

**Modified Files:**
- `api/main.py` (+55 lines: SynthesisRunRequest model + POST /synthesis/run endpoint)
- `src/synthesis/clustering.py` (fixed module-level pool init → lazy loading)

## Next Steps

**After manual review and approval:**
1. Install systemd units (commands above)
2. Commit all changes with test verification receipts
3. Run full regression test (journalctl check)
4. Proceed to T11 (Contract test fix) — final task in Chain B

---

**Status:** READY FOR INSTALLATION ✅  
**Blocker:** None  
**Review Date:** 2026-05-03
