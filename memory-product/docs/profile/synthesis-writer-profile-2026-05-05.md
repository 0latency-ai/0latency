# Synthesis Writer Profile Report

**Date:** 2026-05-05 06:28:16
**Cluster ID:** 6af31b14-900a-4c64-8031-6a7b5a1ea5b3
**Cluster Size:** 12 memories
**Synthesis ID:** 03a08dbb-52fb-4935-ab51-a900d092d937
**Model:** claude-sonnet-4-6
**Tokens Used:** 1421

## Summary

- **Total wall-clock:** 5899ms (5.9s)
- **Total accounted:** 5241ms (88.8% coverage)
- **Phases recorded:** 4

## Phase Breakdown

| Phase | Duration (ms) | % of Total | Metadata |
|-------|--------------|-----------|----------|
| llm_call | 4445 | 75.4% | synthesis_id=None, tokens_used=1421 |
| tenant_load | 404 | 6.8% | synthesis_id=None, cluster_size=12 |
| embedding | 311 | 5.3% | synthesis_id=None |
| db_write | 81 | 1.4% | synthesis_id=03a08dbb-52fb-4935-ab51-a900d092d937 |

## Before / After Comparison (CP-SYNTHESIS-PERF S2.B)

| Phase | Stage 1 (cold) | Stage 2.B (preloaded) | Improvement |
|-------|---------------|----------------------|-------------|
| embedding | 12585ms | 311ms | **40.5x faster** |
| llm_call | 4261ms | 4445ms | ~same |
| db_write | 416ms | 81ms | 5.1x faster |
| tenant_load | 98ms | 404ms | slower (variance) |
| **wall_clock** | **17457ms** | **5899ms** | **3.0x faster** |

**Startup cost:** SentenceTransformer preload adds ~20s to memory-api startup (10.8s model load + warmup in profile script).  
This is a one-time cost paid at boot, not per-synthesis.

**Steady state:** Second consecutive run: 5899ms wall-clock (embedding 311ms).  
Model stays loaded between synthesis calls in the same process.

**Fix details:**
- Modified  to run warmup inference after model load
- Modified  startup event to preload and log model load time
- Modified  to preload model before profiling (excludes cold-load from timing)
- Embedding phase dropped from 72% of wall-clock to 5%
- LLM call is now the dominant phase (75% of wall-clock)

**Verification gates:**
- ✓ Gate A: embedding < 1000ms (actual: 311ms)
- ✓ Gate B: wall_clock < 6000ms (actual: 5899ms)
- ✓ Gate C: steady state < 6000ms (actual: 5899ms)

## Before / After Comparison (CP-SYNTHESIS-PERF S2.B)

| Phase | Stage 1 (cold) | Stage 2.B (preloaded) | Improvement |
|-------|---------------|----------------------|-------------|
| embedding | 12585ms | 311ms | **40.5x faster** |
| llm_call | 4261ms | 4445ms | ~same |
| db_write | 416ms | 81ms | 5.1x faster |
| tenant_load | 98ms | 404ms | slower (variance) |
| **wall_clock** | **17457ms** | **5899ms** | **3.0x faster** |

**Startup cost:** SentenceTransformer preload adds ~20s to memory-api startup.
This is a one-time cost paid at boot, not per-synthesis.

**Steady state:** Second consecutive run: 5899ms wall-clock (embedding 311ms).
Model stays loaded between synthesis calls in the same process.

**Fix details:**
- Modified src/storage_multitenant.py _get_local_model() to run warmup inference after model load
- Modified api/main.py startup event to preload and log model load time
- Modified scripts/profile_synthesis.py to preload model before profiling
- Embedding phase dropped from 72% of wall-clock to 5%
- LLM call is now the dominant phase (75% of wall-clock)

**Verification gates:**
- Gate A: embedding < 1000ms (actual: 311ms) PASS
- Gate B: wall_clock < 6000ms (actual: 5899ms) PASS
- Gate C: steady state < 6000ms (actual: 5899ms) PASS
