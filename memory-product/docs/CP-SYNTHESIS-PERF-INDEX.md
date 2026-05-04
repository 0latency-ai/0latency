# CP-SYNTHESIS-PERF — Synthesis writer latency reduction

**Goal:** Bring per-cluster synthesis latency from ~173s to single-digit seconds, matching Mem0's published baseline.

**Phase 1 (this run):** Profile only. Add phase-boundary timing to orchestrator.run_synthesis_for_tenant(). Run one synthesis on user-justin. Report phase breakdown. Commit profiling instrumentation.

**Phase 2 (next chain):** Optimize the dominant phase based on Phase 1 data. Likely candidates: cluster-cache layer, async/batched DB writes, embedding-pipeline tuning, model swap. Each candidate becomes its own scoped task.

**Phase 3:** Re-benchmark. Lock in <10s/cluster as Phase-2 acceptance gate.
