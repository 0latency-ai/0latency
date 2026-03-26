# Observability & Error Tracking System

Production-grade monitoring, error tracking, and alerting for the 0Latency API.

## Overview

The observability system provides comprehensive visibility into:
- **Error Tracking**: Capture, group, and analyze all exceptions
- **Performance Monitoring (APM)**: Track latency, throughput, and resource usage
- **Alerting**: Real-time notifications for critical issues via Telegram
- **Health Checks**: Continuous monitoring of all system components
- **Status Page**: Public status dashboard at status.0latency.ai

## Components

### 1. Error Tracker (`observability/error_tracker.py`)

Captures all exceptions with full context and groups similar errors for analysis.

#### Features
- **Error Taxonomy**: CRITICAL, ERROR, WARNING, INFO, DEBUG levels
- **Stack Trace Capture**: Full exception traces with context
- **Deduplication**: Groups similar errors by stack trace hash
- **Tenant Impact**: Tracks which tenants are affected by each error
- **Frequency Tracking**: Monitors error rates (errors/minute)
- **Context Capture**: Logs tenant_id, request_id, user_agent, IP, endpoint

#### Usage

**Decorator (recommended):**
```python
from observability import track_error, ErrorLevel

@track_error(level=ErrorLevel.CRITICAL, alert=True)
async def critical_endpoint(...):
    # Your code here
    pass
```

**Manual logging:**
```python
from observability import log_error, ErrorLevel

try:
    # Your code
except Exception as e:
    log_error(
        e,
        level=ErrorLevel.ERROR,
        tenant_id=tenant_id,
        endpoint="/memories/add",
        extra_context={"some": "data"}
    )
    raise
```

**Query error statistics:**
```python
from observability import get_error_stats

stats = get_error_stats(hours=24, level=ErrorLevel.CRITICAL)
# Returns: total_errors, unique_error_groups, error_rate_per_minute, top_errors
```

#### Database Schema

**error_logs** - Individual error occurrences
- `id`, `error_hash`, `error_type`, `error_message`, `stack_trace`
- `level`, `tenant_id`, `request_id`, `user_agent`, `ip_address`
- `endpoint`, `context`, `occurred_at`

**error_groups** - Aggregated error groups
- `error_hash` (PK), `error_type`, `sample_message`, `sample_stack_trace`
- `first_seen`, `last_seen`, `occurrence_count`, `affected_tenants`
- `level`, `resolved`, `resolved_at`, `resolved_by`

### 2. Metrics Collector (`observability/metrics.py`)

Tracks API performance, database queries, and system resources.

#### Features
- **Request Latency**: p50, p95, p99 percentiles per endpoint
- **Database Performance**: Query latency tracking and slow query detection
- **Embedding API Monitoring**: OpenAI API call latency
- **System Metrics**: Memory, disk, CPU usage
- **Endpoint Stats**: Request count, error rate, throughput

#### Usage

**Decorator (automatic tracking):**
```python
from observability import track_performance

@track_performance(endpoint="POST /memories/add")
async def add_memory_endpoint(...):
    # Automatically tracks duration and status
    pass
```

**Manual tracking:**
```python
from observability.metrics import _metrics_collector

# Track request
_metrics_collector.track_request(
    endpoint="POST /memories/add",
    duration_ms=234.5,
    status_code=200,
    tenant_id=tenant_id
)

# Track database query
_metrics_collector.track_database_query(
    duration_ms=45.2,
    query="SELECT * FROM memories..."
)

# Track embedding API call
_metrics_collector.track_embedding_api(
    duration_ms=1250.0,
    provider="openai"
)
```

**Get metrics:**
```python
from observability import get_metrics_summary, get_endpoint_stats

# Full summary
summary = get_metrics_summary()
# Returns: endpoints, database, embedding_api, system

# Specific endpoint
stats = get_endpoint_stats("POST /memories/add")
# Returns: request_count, error_rate, latency percentiles
```

#### Key Thresholds
- **Slow Query**: >5 seconds (configurable)
- **High Memory**: >90% usage
- **High Disk**: >90% usage

### 3. Alert Manager (`observability/alerts.py`)

Intelligent alerting with rate limiting and multi-level severity.

#### Features
- **Telegram Integration**: Sends alerts to configured chat
- **Smart Throttling**: Prevents alert spam with cooldown periods
- **Severity Levels**: INFO, WARNING, ERROR, CRITICAL
- **Multi-Check**: Monitors error rates, database, system health, endpoints
- **Alert History**: All alerts logged to database

#### Cooldown Periods
- **CRITICAL**: 5 minutes
- **ERROR**: 15 minutes
- **WARNING**: 30 minutes
- **INFO**: 1 hour

#### Usage

**Send manual alert:**
```python
from observability import send_alert

send_alert(
    "Database connection lost",
    level="critical",
    alert_type="database_failure"
)
```

**Run all checks:**
```python
from observability import check_alert_thresholds

results = check_alert_thresholds()
# Runs all health checks and sends alerts if thresholds exceeded
```

#### Alert Thresholds
- **Error Rate**: >10 errors/minute
- **Endpoint Error Rate**: >20% on any endpoint
- **Slow Queries**: >10 queries exceeding 5s
- **Memory Usage**: >90%
- **Disk Usage**: >90%

### 4. Health Endpoint (`/health`)

Public health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2024-03-25T22:00:00Z",
  "memories_total": 15234,
  "db_pool": {
    "pool_min": 5,
    "pool_max": 20
  },
  "redis": "connected"
}
```

**Status Values:**
- `ok` - All systems operational
- `degraded` - Some non-critical issues
- `down` - Critical failure

### 5. Status Page (`/var/www/0latency/status.html`)

Public-facing status dashboard that polls `/health` endpoint every 30 seconds.

**Features:**
- Real-time status updates
- Visual health indicators (✓ / ⚠ / ✗)
- System metrics display
- Auto-refresh every 30 seconds

**Deployment:**
Serve via nginx at status.0latency.ai

## Installation & Setup

### 1. Run Migration

```bash
cd /root/.openclaw/workspace/memory-product
psql $DATABASE_URL < migrations/011_error_logs_table.sql
```

### 2. Configure Environment

Add to `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=8544668212
```

### 3. Import in main.py

Add to `api/main.py`:
```python
from observability import (
    track_error, ErrorLevel,
    track_performance,
    send_alert, check_alert_thresholds
)

# Apply decorators to endpoints
@track_error(level=ErrorLevel.CRITICAL, alert=True)
@track_performance()
async def critical_endpoint(...):
    pass
```

### 4. Schedule Periodic Checks

Add to crontab:
```bash
# Run health checks every 5 minutes
*/5 * * * * cd /root/.openclaw/workspace/memory-product && python3 -c "from observability import check_alert_thresholds; check_alert_thresholds()" >> /var/log/0latency-alerts.log 2>&1

# Persist metrics snapshot every 15 minutes
*/15 * * * * cd /root/.openclaw/workspace/memory-product && python3 -c "from observability.metrics import _metrics_collector; _metrics_collector.persist_metrics()" >> /var/log/0latency-metrics.log 2>&1
```

## Integration Examples

### Wrapping Existing Endpoints

```python
# Before:
@app.post("/memories/add")
async def add_memory(req: AddMemoryRequest, tenant: dict = Depends(require_api_key)):
    # ... implementation
    pass

# After:
@app.post("/memories/add")
@track_error(level=ErrorLevel.ERROR, alert=True)
@track_performance(endpoint="POST /memories/add")
async def add_memory(req: AddMemoryRequest, tenant: dict = Depends(require_api_key)):
    # ... implementation
    pass
```

### Database Query Tracking

```python
from observability.metrics import _metrics_collector
import time

def execute_query(query, params):
    start = time.time()
    try:
        result = cursor.execute(query, params)
        return result
    finally:
        duration_ms = (time.time() - start) * 1000
        _metrics_collector.track_database_query(duration_ms, query)
```

### Custom Alert Conditions

```python
from observability import send_alert

# Monitor custom business metric
if tenant_signup_rate < 5:
    send_alert(
        f"Low signup rate: {tenant_signup_rate} signups/hour",
        level="warning",
        alert_type="low_signups"
    )
```

## Monitoring Dashboards

### Error Dashboard

Query recent errors:
```sql
SELECT * FROM recent_errors LIMIT 50;
```

Get errors by tenant:
```python
from observability.error_tracker import _error_tracker

errors = _error_tracker.get_tenant_errors(tenant_id, hours=24)
```

### Performance Dashboard

```python
from observability import get_metrics_summary

metrics = get_metrics_summary()

print(f"Endpoints:")
for ep in metrics['endpoints']:
    print(f"  {ep['endpoint']}: {ep['latency_ms']['p95']:.0f}ms p95")

print(f"\nDatabase:")
print(f"  p95 latency: {metrics['database']['latency_ms']['p95']:.0f}ms")
print(f"  Slow queries: {metrics['database']['slow_query_count']}")

print(f"\nSystem:")
print(f"  Memory: {metrics['system']['memory']['percent']:.1f}%")
print(f"  Disk: {metrics['system']['disk']['percent']:.1f}%")
```

## Log Rotation

Error logs and metrics can grow large. Set up log rotation:

```bash
# /etc/logrotate.d/0latency
/var/log/0latency-*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
}
```

## Disaster Recovery

### Replay Failed Requests

All errors are logged with full context. To replay a failed request:

```python
from observability.error_tracker import _error_tracker

# Get error details
details = _error_tracker.get_error_details(error_hash)

for occurrence in details['recent_occurrences']:
    context = occurrence['context']
    # Extract original request data and retry
```

### Export Error Data

```sql
-- Export errors for analysis
COPY (
    SELECT * FROM error_logs 
    WHERE occurred_at > NOW() - INTERVAL '7 days'
) TO '/tmp/error_export.csv' WITH CSV HEADER;
```

## Best Practices

1. **Always use decorators** - Wrap all API endpoints with `@track_error` and `@track_performance`
2. **Set appropriate levels** - Use CRITICAL only for true emergencies
3. **Include context** - Add tenant_id, request_id whenever possible
4. **Monitor alert noise** - Adjust thresholds if too many false positives
5. **Review errors weekly** - Check error_groups for patterns
6. **Archive old logs** - Move logs >30 days to S3 or delete

## Architecture Decisions

### Why In-Memory + Database?
- **In-memory**: Fast, low-latency metrics collection (no DB overhead per request)
- **Database**: Persistent storage, historical analysis, audit trail
- **Periodic persistence**: Balance between real-time and durability

### Why Stack Trace Hashing?
Groups errors by *pattern* rather than exact match. Different line numbers or variable names = same error group.

### Why Cooldown Periods?
Prevents alert fatigue. If database is down, you want 1 alert, not 100.

## Performance Impact

- **Error tracking**: ~1-2ms overhead per request (database insert)
- **Metrics collection**: <0.1ms (in-memory deque append)
- **Health checks**: Run async, no endpoint impact
- **Alert checks**: Run via cron, no endpoint impact

## Future Enhancements

- [ ] Prometheus metrics export
- [ ] Grafana dashboards
- [ ] Sentry integration (5K free events/month)
- [ ] Automated incident reports
- [ ] Tenant-specific error dashboards
- [ ] Anomaly detection (ML-based)
- [ ] PagerDuty integration for on-call

## Support

For issues or questions:
- Email: justin@0latency.ai
- Docs: https://0latency.ai/docs
- Status: https://status.0latency.ai
