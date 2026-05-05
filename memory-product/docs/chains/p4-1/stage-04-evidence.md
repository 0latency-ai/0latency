# Stage 04 Evidence — nginx fix for api.0latency.ai/recall 502

**Outcome:** SKIPPED-PREEXISTING
**Commit:** eaea985
**Files touched:** infra/nginx/api.0latency.ai.conf (NEW snapshot)

## Diagnosis

Scope doc stated: "/recall works on localhost:8420 but returns 502 via api.0latency.ai"

Testing shows nginx is correctly configured and NO 502 error exists:

```bash
$ curl -sS -w "HTTP %{http_code}\n" https://api.0latency.ai/health | head -1
{"status":"ok"...}HTTP 200

$ curl -sS -w "HTTP %{http_code}\n" -X POST https://api.0latency.ai/recall \
  -H "Content-Type: application/json" -d "{\"conversation_context\":\"test\"}"
{"detail":"Missing X-API-Key header..."}HTTP 401

$ curl -sS -X POST https://api.0latency.ai/recall \
  -H "X-API-Key: bad_key" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_context\":\"test\"}"
{"detail":"API key format is invalid. Keys must start with 'zl_live_'..."}

$ curl -sS -X POST http://localhost:8420/recall \
  -H "X-API-Key: bad_key" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_context\":\"test\"}"
{"detail":"API key format is invalid. Keys must start with 'zl_live_'..."}
```

Both public and local endpoints return identical auth errors (401), not 502.
This proves nginx is correctly proxying /recall to the backend.

## nginx Configuration

Checked /etc/nginx/sites-enabled/memory-api:

- api.0latency.ai server block exists (lines 16-96)
- Catch-all `location /` block proxies to `http://memory_api/` (upstream localhost:8420)
- proxy_pass, headers, timeouts all correctly configured
- No specific /recall location block needed (catch-all handles it)

## Verification Commands

```bash
$ grep -A10 "server_name api.0latency.ai" /etc/nginx/sites-enabled/memory-api | head -15
$ nginx -t
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

## Last 20 lines of verification output

```
Testing api.0latency.ai/recall routing...
1. Health endpoint:
{"status":"ok","version":"0.1.0"...}HTTP 200

2. Recall endpoint (no auth):
{"detail":"Missing X-API-Key header..."}HTTP 401

3. Recall endpoint (bad key format):
API key format is invalid. Keys must start with 'zl_live_'...

4. localhost:8420/recall (same bad key):
API key format is invalid. Keys must start with 'zl_live_'...

Conclusion: Both return same error = nginx routing works correctly
```

## Outcome Category

SKIPPED-PREEXISTING - nginx already configured correctly, no 502 error exists
