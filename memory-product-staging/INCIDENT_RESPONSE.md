# Incident Response Playbook - 0Latency API

## Incident Classification

### Severity Levels

**P0 - Critical (Production Down)**
- API completely unavailable
- Database unreachable
- Data corruption detected
- Security breach
- **Response time:** Immediate
- **Notification:** Telegram alert + phone call if >15 min

**P1 - High (Major Degradation)**
- Error rate >20% across all endpoints
- Latency >10s on critical endpoints
- Stripe payments failing
- Memory/disk >95%
- **Response time:** Within 15 minutes
- **Notification:** Telegram alert

**P2 - Medium (Service Degradation)**
- Error rate 10-20% on specific endpoints
- Latency spike 2-10s
- Slow database queries
- Memory/disk 85-95%
- **Response time:** Within 1 hour
- **Notification:** Telegram alert (throttled)

**P3 - Low (Minor Issues)**
- Error rate 5-10% on non-critical endpoints
- Anomaly detected but no user impact
- Resource usage trending upward
- **Response time:** Next business day
- **Notification:** Daily summary

---

## Alert Response Procedures

### 1. Database Connection Failure (P0)

**Symptoms:**
- Telegram alert: "🔥 Database Connection Failed"
- All API endpoints returning 500

**Immediate Actions:**
1. Check database status
   ```bash
   curl https://fuojxlabvhtmysbsixdn.supabase.co/rest/v1/
   ```
2. Check API logs
   ```bash
   tail -100 /var/log/0latency-api.log | grep -i "database\|connection"
   ```
3. Restart API if stale connection pool
   ```bash
   /root/scripts/start_0latency_api.sh
   ```
4. Check Supabase dashboard for incidents
5. If Supabase is down: Post status update, estimate recovery time

**Recovery Steps:**
- API auto-reconnects on restart
- Verify health: `curl https://api.0latency.ai/health`
- Monitor error rate for 10 minutes
- Send all-clear notification

**Escalation:**
- If issue persists >30 min: Contact Supabase support
- If data loss suspected: Trigger backup restore procedure

---

### 2. High Error Rate (P1)

**Symptoms:**
- Telegram alert: "⚠️ High Error Rate Detected"
- Error rate >10/minute

**Immediate Actions:**
1. Check error breakdown
   ```bash
   curl -s https://api.0latency.ai/observability/errors/stats?hours=1 | jq
   ```
2. Identify top error groups
   ```bash
   cd /root/.openclaw/workspace/memory-product && python3 -c "
   from observability import get_error_stats
   stats = get_error_stats(hours=1)
   print(stats.get('top_errors', []))
   "
   ```
3. Check if specific to one tenant
4. Review recent deployments (was code just pushed?)

**Recovery Steps:**
- If deployment-related: Roll back immediately
- If tenant-specific: Investigate tenant data/usage
- If 3rd party API (Stripe/OpenAI): Wait for recovery, post status
- Monitor until error rate <5/minute for 15 minutes

**Prevention:**
- Add error pattern to test suite
- Update validation logic if user input issue
- Add rate limiting if abuse detected

---

### 3. Latency Spike (P1-P2)

**Symptoms:**
- Telegram alert: "⚠️ High Error Rate on Endpoint" (>5s)
- Slow user reports

**Immediate Actions:**
1. Check slow query log
   ```bash
   cd /root/.openclaw/workspace/memory-product && python3 -c "
   from observability.metrics import get_metrics_summary
   metrics = get_metrics_summary()
   print(metrics.get('database', {}).get('slow_queries', []))
   "
   ```
2. Check system resources
   ```bash
   top -b -n 1 | head -20
   free -h
   df -h
   ```
3. Check for unusual traffic patterns (DDoS?)
   ```bash
   tail -1000 /var/log/0latency-api.log | grep -E "POST|GET" | cut -d' ' -f1 | sort | uniq -c | sort -rn | head -10
   ```

**Recovery Steps:**
- If database slow: Restart connection pool (restart API)
- If resource exhaustion: Scale up server or add caching
- If attack: Add rate limiting, block IP ranges
- Monitor until latency p95 <2s for 10 minutes

**Prevention:**
- Add query optimization
- Implement caching for hot paths
- Add circuit breakers for external APIs

---

### 4. High Memory Usage (P2)

**Symptoms:**
- Telegram alert: "⚠️ High Memory Usage" (>90%)

**Immediate Actions:**
1. Check process memory
   ```bash
   ps aux --sort=-%mem | head -10
   ```
2. Check for memory leaks
   ```bash
   systemctl status 0latency-api  # if using systemd
   # or check process uptime - long uptime + high mem = leak
   ps -eo pid,etime,pmem,cmd | grep uvicorn
   ```

**Recovery Steps:**
- Restart API to clear memory
- Check for leaked connections or cached data
- Monitor for 1 hour - if memory grows steadily = leak

**Prevention:**
- Investigate memory leak if pattern repeats
- Add memory profiling
- Consider connection pool limits

---

### 5. Anomaly Detected (P2-P3)

**Symptoms:**
- Sudden traffic spike/drop
- Unusual error pattern
- Latency deviation from baseline

**Immediate Actions:**
1. Review anomaly details
   ```bash
   cd /root/.openclaw/workspace/memory-product && python3 -c "
   from observability import get_recent_anomalies
   print(get_recent_anomalies(hours=1, severity='high'))
   "
   ```
2. Correlate with:
   - Recent deployments
   - Marketing campaigns
   - External events (HN/Reddit launch)
   - Time of day patterns

**Recovery Steps:**
- If expected (launch traffic): Scale resources, monitor
- If unexpected drop: Investigate outage or user churn
- If error pattern: Follow error rate procedure

---

## Monitoring Commands Cheat Sheet

```bash
# Check API health
curl https://api.0latency.ai/health | jq

# View recent errors
curl -s https://api.0latency.ai/observability/errors/stats?hours=1 | jq '.top_errors'

# View metrics summary
curl -s https://api.0latency.ai/observability/metrics | jq

# View recent anomalies
curl -s https://api.0latency.ai/observability/anomalies?hours=24 | jq

# Tail live logs
tail -f /var/log/0latency-api.log

# Check system resources
htop  # or: top, free -h, df -h

# Restart API
/root/scripts/start_0latency_api.sh

# Test database connection
psql "$MEMORY_DB_CONN" -c "SELECT 1"

# Check cron jobs
crontab -l | grep 0latency
```

---

## Communication Templates

### Status Update (Telegram)

```
🚨 Incident Update: <Title>

Status: <Investigating|Identified|Monitoring|Resolved>
Impact: <Description>
ETA: <Time estimate>

Actions taken:
- <Action 1>
- <Action 2>

Next steps:
- <Step 1>
```

### Post-Mortem Template

```markdown
# Incident Post-Mortem: <Date> - <Title>

## Summary
- **Duration:** X minutes
- **Impact:** Y users affected
- **Root cause:** Z

## Timeline
- HH:MM - Incident detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Monitoring confirmed resolution

## Root Cause Analysis
<What happened and why>

## Action Items
- [ ] Immediate fix: <description>
- [ ] Monitoring improvement: <description>
- [ ] Prevention: <description>

## Lessons Learned
<What we learned>
```

---

## Escalation Contacts

**Primary On-Call:** Justin Ghiglia (Telegram: 8544668212)

**Service Providers:**
- Supabase: Dashboard → https://supabase.com/dashboard/project/fuojxlabvhtmysbsixdn
- Stripe: Dashboard → https://dashboard.stripe.com
- DigitalOcean: Support → https://cloud.digitalocean.com/support

**External Support:**
- Anthropic API issues: Check status page
- OpenAI API issues: status.openai.com

---

## Recovery Procedures

### Full API Restart
```bash
# Stop all API processes
fuser -k 8420/tcp

# Wait for cleanup
sleep 3

# Start fresh
cd /root/.openclaw/workspace/memory-product
nohup /root/scripts/start_0latency_api.sh >> /var/log/0latency-api-restart.log 2>&1 &

# Verify
sleep 6
curl https://api.0latency.ai/health
```

### Database Connection Reset
```bash
# API restart handles this automatically
/root/scripts/start_0latency_api.sh
```

### Full System Reboot (Last Resort)
```bash
# Only if: process hangs, file descriptor exhaustion, kernel issues
sudo reboot

# After reboot: API auto-starts if configured in systemd
# If not, manually start:
/root/scripts/start_0latency_api.sh
```

---

## Post-Incident Checklist

- [ ] All-clear notification sent
- [ ] Incident logged in daily memory file
- [ ] Root cause identified
- [ ] Monitoring gaps identified
- [ ] Action items created
- [ ] Post-mortem written (if P0 or P1)
- [ ] Team debriefed
- [ ] Prevention measures implemented

---

**Last Updated:** 2026-03-26
**Owner:** Thomas (thomas-server)
**Next Review:** After first P0/P1 incident
