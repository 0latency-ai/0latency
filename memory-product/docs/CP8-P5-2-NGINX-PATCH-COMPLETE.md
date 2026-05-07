# CP8 P5.2 Nginx Patch COMPLETE

Date: 2026-05-07
Branch: cp-p5-2-nginx-patch
Tier: 1 (infra config change, no schema/code)

## Summary

Added nginx routing for GET /audit/events endpoint to make it accessible via https://mcp.0latency.ai/audit/events.

## Problem

P5.2 merged to master (c4bc846) but endpoint returned 404 at https://mcp.0latency.ai/audit/events despite working locally on 127.0.0.1:8420.

Root cause: mcp.0latency.ai subdomain had existing nginx config (/etc/nginx/sites-available/mcp.0latency.ai) that proxied all requests to localhost:3100 (MCP server), not to memory API backend at 127.0.0.1:8420.

## Solution

Added location block for /audit/events in existing mcp.0latency.ai nginx config:

```nginx
# Audit events endpoint - proxy to memory API backend
location /audit/events {
    proxy_pass http://127.0.0.1:8420/audit/events;
    proxy_http_version 1.1;
    
    # Standard proxy headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Timeouts
    proxy_connect_timeout 30s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

Inserted before the catch-all location / block to ensure /audit/events routes to memory API backend while other paths continue to MCP server.

## Files Changed

- /etc/nginx/sites-available/mcp.0latency.ai (production file)
- infra/nginx/mcp.0latency.ai.conf (version-controlled copy in repo)

## Verification

1. Config test: `nginx -t` passed
2. Reload: `systemctl reload nginx` successful
3. Endpoint routing: `curl https://mcp.0latency.ai/audit/events` returned 401 (was 404)
4. Smoke test with enterprise key: returned 3 events, has_more: true

Sample response:
```json
{
  "returned": 3,
  "has_more": true,
  "sample_event_type": "read"
}
```

## Deployment Notes

The modified nginx config is active in production immediately (applied via systemctl reload nginx).

To deploy to another environment:
1. Copy infra/nginx/mcp.0latency.ai.conf to /etc/nginx/sites-available/mcp.0latency.ai
2. Ensure symlink exists: ln -s /etc/nginx/sites-available/mcp.0latency.ai /etc/nginx/sites-enabled/
3. Test: nginx -t
4. Reload: systemctl reload nginx

## Notes

- Tier 1: infra config only, no schema/code changes
- No migration needed
- Config is version-controlled in infra/nginx/ for deployment reproducibility
- Change is backward compatible (existing MCP server routes unaffected)

NOT MERGED to master. Awaits operator review.
