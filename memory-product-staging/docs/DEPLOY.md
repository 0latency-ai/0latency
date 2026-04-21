# Zero Latency Memory — Deployment Guide

## Prerequisites

- Ubuntu 22.04+ (tested on 24.04)
- Python 3.11+
- PostgreSQL 15+ with pgvector (Supabase recommended)
- Redis 6+
- nginx

## Quick Deploy

```bash
# 1. Clone and install
cd /opt
git clone <repo> zerolatency
cd zerolatency
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your values

# 3. Database setup
# Run the SQL in docs/schema.sql against your Postgres instance
# This creates the memory_service schema, tables, RLS policies, and functions

# 4. Redis
apt install redis-server
systemctl enable redis-server --now

# 5. Systemd service
cat > /etc/systemd/system/zerolatency-api.service << EOF
[Unit]
Description=Zero Latency Memory API
After=network.target redis.service

[Service]
Type=simple
WorkingDirectory=/opt/zerolatency
Environment=MEMORY_DB_CONN=postgresql://user:pass@host:5432/db
Environment=MEMORY_ADMIN_KEY=your_secret
Environment=GOOGLE_API_KEY=your_key
Environment=CORS_ORIGINS=https://your-domain.com
ExecStart=/opt/zerolatency/.venv/bin/python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8420 --workers 2 --access-log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl enable zerolatency-api --now

# 6. nginx
# Copy docs/nginx.conf to /etc/nginx/sites-enabled/memory-api
# Update server_name with your domain
nginx -t && systemctl reload nginx

# 7. SSL (requires domain)
certbot --nginx -d your-domain.com

# 8. Create first tenant
curl -X POST http://127.0.0.1:8420/api-keys \
  -H "X-Admin-Key: your_secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "plan": "pro"}'

# 9. Verify
curl https://your-domain.com/health
python3 tests/test_api_full.py
```

## Architecture

```
Internet → nginx (443, TLS) → /api/v1/* → uvicorn:8420 (2 workers)
                                              ↓
                                         psycopg2 pool (2-10)
                                              ↓
                                         PostgreSQL + pgvector
                                              ↓
                                         RLS per tenant

                                         Redis 6379
                                         ├── Rate limiting (rl:{tenant_id})
                                         └── Cache invalidation (zl:cache_bust)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| MEMORY_DB_CONN | Yes | PostgreSQL connection string |
| MEMORY_ADMIN_KEY | Yes | Admin API key |
| GOOGLE_API_KEY | Yes | Gemini API (embeddings + extraction) |
| CORS_ORIGINS | No | Comma-separated allowed origins |
| MEMORY_DB_PASSWORD | No | For backup script (psql) |
| OPENAI_API_KEY | No | Fallback extraction model |
| ANTHROPIC_API_KEY | No | Fallback extraction model |

## Operations

### Logs
```bash
journalctl -u zerolatency-api -f          # Live logs
journalctl -u zerolatency-api --since "1h ago" | grep '"req='  # Structured request logs
```

### Backup
```bash
export MEMORY_DB_CONN="postgresql://..."
bash scripts/backup.sh
# Outputs to /root/backups/memory-api/YYYY-MM-DD_HHMM/
```

### Health Check
```bash
curl http://127.0.0.1:8420/health
# Returns: status, DB connectivity, pool stats, Redis status, memory count
```

### Key Rotation
```bash
# Rotate (old key immediately invalid)
curl -X POST http://127.0.0.1:8420/admin/rotate-key/{tenant_id} \
  -H "X-Admin-Key: $ADMIN_KEY"

# Revoke (disable tenant)
curl -X POST http://127.0.0.1:8420/admin/revoke-key/{tenant_id} \
  -H "X-Admin-Key: $ADMIN_KEY"
```

### Tests
```bash
python3 tests/test_api_full.py
# Runs 70+ checks: auth, CRUD, SQL injection, tenant isolation, key lifecycle, etc.
```

## Monitoring

The `/health` endpoint returns:
- `status`: "ok" or "degraded"
- `memories_total`: total active memories
- `db_pool`: connection pool min/max
- `redis`: "connected" or "unavailable"

Point your uptime monitor at `https://your-domain/health` and alert on non-200 or `status != "ok"`.

## Scaling Notes

- **Workers**: Default 2. Increase for more concurrent requests. Each worker has its own memory caches.
- **DB pool**: Default 2-10. Scale with workers (2 per worker minimum).
- **Redis**: Single instance sufficient to 10K RPM. 
- **Embedding latency**: ~500ms per call to Gemini. Cached for 5 minutes per unique query.
- **Auth latency**: ~280ms cold, <3ms cached (30s TTL, cross-worker invalidation).
