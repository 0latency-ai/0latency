# Quickstart Direct-Insert Fix (2026-05-11)

## Problem
Quickstart page submitted trivial single-fact inputs through , which uses probabilistic extraction. The regression in ed6343d caused extraction to return 0 memories for simple inputs like "User prefers blue mode".

## Solution
Updated  Step 3 to use  instead of .

- **Before**:  with 
- **After**:  with 

## Rationale
-  bypasses extraction (deterministic)
- Writes exactly one memory atomically
- Perfect for quickstart onboarding where users expect immediate, predictable results
-  stays for real conversational ingestion (MCP, SDK, agent traces)

## Files Changed
-  (production, not in git)
  - Updated testMemory() function
  - Updated curl example

## Test
Submit "User prefers blue mode" via quickstart form → exactly 1 memory created with matching headline.
