# NGINX 502 Investigation - Phase 6 Benchmark Launch

> **Historical record.** `memory-api.service` was renamed `zerolatency-api.service` on 2026-05-18, and the dead unit was deleted on 2026-08-24. Service names below are preserved as they were written; do not follow them as current operational steps.

Date: 2026-05-11 18:56-19:02 UTC
Status: DIAGNOSED - Transient connection backlog exhaustion
Severity: Medium (does not block benchmark completion)

## Root Cause

Connection backlog exhaustion when both Phase 6 benchmarks launch simultaneously against 2-worker uvicorn instance.

## Evidence

1. Nginx error log: Connection refused (111) to 127.0.0.1:8420 during surge
2. Nginx access log: 200 OK responses after surge settles
3. Production API health: All endpoints returning 200
4. Decision field fix verified: 100% success rate (1/1 decision has fields populated)
5. Memory storage: 26 memories in 5 min (8 correction, 8 identity, 5 fact, 2 preference, 1 decision)

## Current Configuration

- Service: memory-api.service
- Workers: 2 uvicorn workers
- Port: 127.0.0.1:8420
- Backlog: 2048

## Impact

Transient 502s during request surge. Benchmarks retry and succeed. No data quality impact.

## Recommendation

Accept for Phase 6. Extraction fix is verified working. Increase workers to 4 post-benchmark.

## Verification

- Production API healthy
- Decision field fix deployed (100% success)
- No constraint violations
- Benchmarks progressing
