# Phase 6 Execution Blocker - LongMemEval Full Benchmark

**Date**: 2026-05-11 06:20 UTC  
**Status**: BLOCKED - API authentication issues preventing benchmark execution  
**Context Usage**: 113k / 200k tokens (58%)

---

## Executive Summary

Phase 6 objective was to run two full LongMemEval benchmarks (n=500 each):
- Run 1: Production tier (Haiku extraction + Sonnet recall)
- Run 2: Enterprise tier (Sonnet extraction + Sonnet recall)

**Blocker**: API key generation/validation failures preventing benchmark from authenticating with the 0Latency API service.

---

## Exact Error Encountered

### Primary Issue: API Key Hash Format Mismatch

**Symptom**: Benchmark fails with 401 Unauthorized when calling /extract endpoint

**Root Cause**: Mismatch between how API keys are hashed during creation vs validation

**Database Schema**:
- key_hash column type: text (not bytea)
- Expected format: hex string

**Generated Keys**:
1. zl_live_ir_RKqGNThcgCSS0hedVpA7CIx-ifIUF - Created with bytea hash (wrong format)
2. zl_live_KrffFsr58sA9LleX_PaRSCq6M_m8P23M - Created with hex hash (correct format)

### Secondary Issue: Service Environment Variables

**Symptom**: Direct Python tests show _anthropic_key() returns empty string

**Cause**: Environment file not loaded in systemd service worker processes

### Tertiary Issue: 500 Errors After Auth

API returns 200 but extraction fails with EXTRACTION_FAILED error.

**Investigation**: Anthropic API works directly, but service workers don't see ANTHROPIC_API_KEY

---

## What Was Tried

- API key generation (3 attempts with different hash formats)
- Service restarts to reload environment
- Direct extraction tests (failed - no API key visible)
- Direct Anthropic API test (succeeded - proves API works)

---

## Current State of Scripts

### run1_production.sh - READY
Location: /root/.openclaw/workspace/memory-product/benchmarks/longmemeval/run1_production.sh
Status: Script correct, blocked by API auth

### run2_enterprise.sh - READY  
Location: /root/.openclaw/workspace/memory-product/benchmarks/longmemeval/run2_enterprise.sh
Status: Script correct, blocked by API auth

### Supporting Scripts - READY
- purge_benchmark_data.sh
- monitor_run.sh

---

## What's Still Needed

### Critical Path

1. Fix API Key Authentication
   - Option A: Use existing working key from different tenant
   - Option B: Debug systemd environment loading
   - Option C: Bypass API, call extract_memories() directly

2. Verify Extraction Works End-to-End
   - Test API returns 200 with memories_stored > 0

3. Launch Runs in tmux
   - Run 1: 4-6 hours
   - Run 2: 4-6 hours after purging data

---

## Code Changes Made

### src/extraction.py - MODIFIED
Line 131: Changed to use EXTRACTION_MODEL variable
Backup: src/extraction.py.backup-pre-model-config

### .env.benchmark - UPDATED
API Key: zl_live_KrffFsr58sA9LleX_PaRSCq6M_m8P23M
Tenant: 382faaf1-5cbf-49a1-b689-5ffef8918d10
WARNING: May not be working

---

## Technical Context

### Timeout Configuration - VERIFIED
- Extraction: 90s (commit 4bc1b8f)
- Recall: 30s (commit 4bc1b8f)

### Available Models
- claude-haiku-4-5-20251001
- claude-sonnet-4-20250514

### Known Good State
Earlier validation proved:
- Timeout fix works (20% -> 40% accuracy)
- Extraction quality sufficient
- Recall with type boosting works
- Infrastructure fundamentally sound

Issue is authentication/environment only.

---

## Budget Status

**API Spend**: $100-120 estimated (within $175 budget)
**Context**: 113k / 200k tokens used (58%)

---

## Files Ready

- run1_production.sh (READY)
- run2_enterprise.sh (READY)
- purge_benchmark_data.sh (READY)
- monitor_run.sh (READY)
- run_benchmark.py (READY - 90s timeout)
- .env.benchmark (API KEY MAY NOT WORK)

---

**Handoff complete. Next operator: debug authentication and launch runs.**
