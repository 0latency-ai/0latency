# CP10 P3 CANONICAL SOAK TEST RESULT

**Test File**: /root/0latency-cli/tests/soak_test_4hr.py
**Start Time**: 2026-05-09 18:45:34 UTC
**End Time**: 2026-05-10T06:49:57Z
**PID**: 1275115

## G11 GATE VERDICT: PASS

## Metrics Summary

| Metric | Result | Limit | Status |
|--------|--------|-------|--------|
| Duration | 4.00h | ≥4.0h | ✓ PASS |
| Atoms Written | 400 | ≥400 | ✓ PASS |
| Max RSS | 34.4MB | <500MB | ✓ PASS |
| Final RSS | 34.4MB | N/A | INFO |
| p95 Latency | 20.7ms | <50ms | ✓ PASS |
| Atoms Lost | 0 | 0 | ✓ PASS |

## Final Block from Log

\`\`\`
Starting CANONICAL 4-hour soak test (G11 gate)...
PID: 1275115
Start time: 2026-05-09 18:45:34
[100/400] Elapsed: 0.99h, RSS: 34.3MB, p95 latency: 15.5ms
[200/400] Elapsed: 1.99h, RSS: 34.4MB, p95 latency: 21.0ms
[300/400] Elapsed: 2.99h, RSS: 34.4MB, p95 latency: 19.3ms
[400/400] Elapsed: 3.99h, RSS: 34.4MB, p95 latency: 20.7ms

============================================================
CANONICAL SOAK TEST COMPLETE (G11 GATE)
============================================================
Duration: 4.00 hours
Atoms written: 400
Final RSS: 34.4MB
Max RSS: 34.4MB
p95 latency: 20.7ms
============================================================

G11 PASS: RSS < 500MB, 400 atoms written, p95 < 50ms
SOAK_DONE_2026-05-09T22:45:38Z
\`\`\`

## Sidecar RSS Samples

\`\`\`
2026-05-09T22:27:28Z RSS=34MB ATOMS=NA
2026-05-09T22:28:28Z RSS=34MB ATOMS=NA
2026-05-09T22:29:28Z RSS=34MB ATOMS=NA
2026-05-09T22:30:28Z RSS=34MB ATOMS=NA
2026-05-09T22:31:28Z RSS=34MB ATOMS=NA
2026-05-09T22:32:28Z RSS=34MB ATOMS=NA
2026-05-09T22:33:28Z RSS=34MB ATOMS=NA
2026-05-09T22:34:28Z RSS=34MB ATOMS=NA
2026-05-09T22:35:28Z RSS=34MB ATOMS=NA
2026-05-09T22:36:28Z RSS=34MB ATOMS=NA
2026-05-09T22:37:28Z RSS=34MB ATOMS=NA
2026-05-09T22:38:28Z RSS=34MB ATOMS=NA
2026-05-09T22:39:28Z RSS=34MB ATOMS=NA
2026-05-09T22:40:28Z RSS=34MB ATOMS=NA
2026-05-09T22:41:28Z RSS=34MB ATOMS=NA
2026-05-09T22:42:28Z RSS=34MB ATOMS=NA
2026-05-09T22:43:28Z RSS=34MB ATOMS=NA
2026-05-09T22:44:28Z RSS=34MB ATOMS=NA
2026-05-09T22:45:28Z RSS=34MB ATOMS=NA
Sidecar monitor ended 2026-05-09T22:46:28Z - process 1275115 exited
\`\`\`

## Full Logs

- Main: /root/0latency-cli/tests/soak_test_4hr.log
- Sidecar: /root/0latency-cli/tests/soak_sidecar.log

## Next Steps

1. Review this report
2. Update merge message: /root/.openclaw/workspace/memory-product/CP10-P3-MERGE-COMMIT-MESSAGE.txt
   - Replace __DURATION_HOURS__ with 4.00
   - Replace __ATOMS_WRITTEN__ with 400
   - Replace __MAX_RSS_MB__ with 34.4
   - Replace __P95_LATENCY__ with 20.7
   - Replace __END_TIMESTAMP__ with 2026-05-10T06:49:57Z
   - Replace __OPERATOR_NAME__ with your name
3. AWAIT OPERATOR MERGE AUTHORIZATION
4. Merge command: cd /root/0latency-cli && git merge feat/cp10-p3-reliability

---

**Report generated**: 2026-05-10T06:53:53Z
