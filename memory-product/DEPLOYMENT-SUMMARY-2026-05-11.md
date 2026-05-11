# Memory Extraction Regression Fix - Deployment Summary

**Date**: 2026-05-11 05:26 UTC
**Commits**: 225fdcf, 0b91e6e
**Status**: DEPLOYED TO MASTER

## Problem (Commit ed6343d)
- Confidence filter raised from 0.3 to 0.5
- Prompt demanded EXHAUSTIVE extraction with 3-5+ facts per turn
- Result: 0 memories extracted from simple inputs like "User prefers blue mode"
- 289 memories created in last 12hr all from MCP, zero from extract API

## Fix Applied

### Part 1 - Extraction Regression (src/extraction.py)
- Reverted confidence filter from 0.5 back to 0.3
- Removed "EXHAUSTIVE EXTRACTION REQUIRED" framing
- Restored importance/confidence ranges to 0.0-1.0
- Restored raw_turn fallback storage
- Added debug logging for LLM responses and filtering

### Part 2 - Quickstart Direct-Insert
- Updated /var/www/0latency/quickstart.html to use /memories/seed
- Changed from probabilistic extraction to deterministic insertion
- Perfect for quickstart onboarding

## Verification
- Test: extract_memories("User prefers blue mode") returns 1 memory
- MCP conversation flow: 374 memories in last 24hr, still flowing
- API service restarted successfully
- All changes pushed to origin/master

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
