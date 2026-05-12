# State Log — 2026-05-12 Evening

## Shipped
- SimpleWorker switch (fork-after-psycopg2 hang fixed)
- Honest extraction error reporting (no more "No extraction model available" lies)
- 3-attempt retry with exponential backoff per provider
- Quote-stripping cleanup on env reads
- Tagged v0.2.1-simpleworker on master

## Verified
- 3 sequential single-extraction trials: 10.11s, 11.98s, 12.16s (all green)
- 4-way concurrent: 20.65s wall-clock (all 4 jobs completed cleanly)

## Deferred to AM
- Re-run Q3 benchmark when Anthropic edge healthy
- n=25 stratified smoke
- n=500 overnight (requires clean Q3 first)

## Known contamination tonight
- Anthropic API returned 502/520 repeatedly during Q3 attempt (~20:11 UTC)
- Benchmark runner hung for 13+ minutes polling for extraction completions
- Numbers tonight do NOT represent code performance, represent upstream degradation
- Worker logs clean (no errors in extraction workers)
- System healthy: 0 pending, 0 failed jobs in RQ queue

## Root cause diagnosis completed
- "No extraction model available" error was misleading
- Actual cause: Transient DNS failures (errno -3) on May 12 09:25 and 09:39
- Both ANTHROPIC_API_KEY and OPENAI_API_KEY were present (verified via DEBUG log)
- Both providers failed due to network issues, not missing configuration
- Fix applied: Honest error messages that distinguish missing keys from API failures

## Next session
- Run Q3 when Anthropic status is fully operational
- If clean, proceed to n=25 and n=500
- Expect 9-12s single extraction latency when upstream healthy
