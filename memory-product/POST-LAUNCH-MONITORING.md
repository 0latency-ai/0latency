# Post-Launch Monitoring Guide

**After you launch, watch these things.**

---

## Hour 1: Immediate Checks

**Every 15 minutes:**

```bash
# 1. Check API health
curl https://api.0latency.ai/health

# 2. Check error logs
ssh root@164.90.156.169
tail -f /var/log/0latency-api.log | grep ERROR

# 3. Check database connections
psql [connection-string] -c "SELECT count(*) FROM memory_service.memories WHERE created_at > NOW() - INTERVAL '1 hour';"
```

**Watch for:**
- 500 errors (server crashes)
- Database connection failures
- Slow response times (>1s)

---

## Hours 2-4: User Onboarding

**Check dashboard signups:**

```bash
ssh root@164.90.156.169
psql [connection-string] -c "SELECT COUNT(*) FROM memory_service.tenants WHERE created_at > NOW() - INTERVAL '4 hours';"
```

**Check MCP installs:**
```bash
# npm downloads (updated hourly)
npm view @0latency/mcp-server --json | jq '.downloads'
```

**Watch for:**
- Signup rate (goal: 10+ in first 4 hours)
- MCP install rate (goal: 5+ in first 4 hours)
- High bounce rate (signups but no API usage = onboarding problem)

---

## Day 1: Engagement Metrics

**Check API usage:**

```bash
psql [connection-string] -c "
SELECT 
  tenant_id,
  COUNT(*) as api_calls,
  COUNT(DISTINCT agent_id) as agents
FROM memory_service.memories 
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY tenant_id
ORDER BY api_calls DESC
LIMIT 10;
"
```

**Check feature adoption:**

```bash
# How many users are using Scale features?
psql [connection-string] -c "
SELECT 
  COUNT(DISTINCT tenant_id) as scale_users
FROM memory_service.graph_relationships
WHERE created_at > NOW() - INTERVAL '24 hours';
"
```

**Watch for:**
- Active users (goal: 20+ making API calls)
- Scale feature usage (goal: 2+ using graph/sentiment)
- Stale accounts (signups with 0 API calls)

---

## Week 1: Growth & Iteration

**Daily checks:**

1. **Error rate** — Should be <1% of requests
   ```bash
   tail -1000 /var/log/0latency-api.log | grep ERROR | wc -l
   ```

2. **Response time** — p95 should be <200ms
   ```bash
   # Check nginx access log
   tail -10000 /var/log/nginx/access.log | awk '{print $NF}' | sort -n | tail -50
   ```

3. **Signups** — Should be growing (not flat or declining)
   ```bash
   psql [connection-string] -c "
   SELECT 
     DATE(created_at) as day,
     COUNT(*) as signups
   FROM memory_service.tenants
   WHERE created_at > NOW() - INTERVAL '7 days'
   GROUP BY DATE(created_at)
   ORDER BY day;
   "
   ```

4. **Churn** — How many users stop after first day?
   ```bash
   # Users who made 1 API call and never returned
   psql [connection-string] -c "
   SELECT COUNT(DISTINCT tenant_id)
   FROM memory_service.memories m1
   WHERE created_at < NOW() - INTERVAL '48 hours'
   AND NOT EXISTS (
     SELECT 1 FROM memory_service.memories m2
     WHERE m2.tenant_id = m1.tenant_id
     AND m2.created_at > m1.created_at + INTERVAL '24 hours'
   );
   "
   ```

---

## Alerts to Set Up

**Critical (immediate response):**

1. **API down** — Health check fails
   ```bash
   # Cron every 5 min
   */5 * * * * curl -sf https://api.0latency.ai/health || openclaw message send --channel telegram --target 8544668212 --message "🚨 API HEALTH CHECK FAILED"
   ```

2. **Database connection lost**
   ```bash
   # Check in API logs
   */5 * * * * grep "database connection" /var/log/0latency-api.log | tail -1 | grep ERROR && openclaw message send --channel telegram --target 8544668212 --message "🚨 DATABASE CONNECTION ERROR"
   ```

3. **High error rate** — >5% of requests returning 500
   ```bash
   # Check error rate every 15 min
   */15 * * * * /root/scripts/check_error_rate.sh
   ```

**Important (review daily):**

1. **Slow queries** — p95 >500ms
2. **Memory leaks** — API process using >2GB RAM
3. **Zero signups** — No new users in 6+ hours

---

## Community Monitoring

**Reddit (r/ClaudeCode):**
- Check comments every 2-4 hours for first 24 hours
- Respond to questions quickly
- Fix bugs mentioned in comments

**Hacker News (if posted):**
- Check every hour for first 4 hours
- Respond to technical questions
- Don't get defensive (HN can be harsh)

**Twitter/X:**
- Monitor @0latencyai mentions
- Reply to questions
- RT positive feedback

**Email (hello@0latency.ai):**
- Check 2x per day minimum
- Respond within 12 hours
- Forward bugs to yourself with [BUG] prefix

---

## Success Metrics (First Week)

| Metric | Goal | Stretch |
|--------|------|---------|
| **Signups** | 100 | 250 |
| **Active users (made 5+ API calls)** | 20 | 50 |
| **Pro upgrades** | 2 | 5 |
| **Scale upgrades** | 1 | 3 |
| **MCP installs** | 50 | 100 |
| **GitHub stars** | 10 | 25 |
| **Reddit upvotes** | 50 | 150 |
| **HN front page** | No | Yes |

---

## Common Issues & Fixes

### "Dashboard won't load"
**Fix:** Check Cloudflare deployment, verify DNS

### "MCP tools not showing in Claude"
**Fix:** 
1. User needs to restart Claude Desktop (fully quit)
2. Clear npx cache: `rm -rf ~/.npm/_npx`
3. Check config syntax in `claude_desktop_config.json`

### "Getting 403 on graph features"
**Fix:**
1. Check user's plan in database
2. Verify feature gating logic in `src/graph_sentiment.py`
3. If Free tier, tell them to upgrade

### "Memory extraction is slow (>10s)"
**Fix:**
1. Check OpenAI API status
2. Switch to Gemini fallback if OpenAI is down
3. Increase timeout in `api/main.py`

### "Recall returns no results"
**Fix:**
1. Check embeddings are being generated
2. Verify pgvector extension is installed
3. Check similarity threshold (lower if needed)

---

## When to Pivot

**If after 7 days:**

- **<20 signups:** Marketing problem. Launch didn't reach audience.
  - Fix: Post to more communities, reach out to influencers

- **<5 active users:** Product problem. People sign up but don't use it.
  - Fix: Improve onboarding, add examples, simplify setup

- **0 paid upgrades:** Pricing problem. Free tier is good enough.
  - Fix: Add more value to paid tiers or restrict free tier more

- **High churn (>80%):** UX problem. People try once and quit.
  - Fix: Find out why (email churned users), fix onboarding

---

## Emergency Contacts

**If something breaks badly:**

1. **Revert API deployment**
   ```bash
   ssh root@164.90.156.169
   cd /root/.openclaw/workspace/memory-product
   git checkout [previous-commit]
   sudo systemctl restart 0latency-api
   ```

2. **Rollback database migration**
   ```bash
   psql [connection-string] < migrations/rollback_007.sql
   ```

3. **Take API offline temporarily**
   ```bash
   # Stop API
   sudo systemctl stop 0latency-api
   
   # Put up maintenance page
   # (update nginx config to serve static "Down for maintenance" page)
   ```

4. **Post update**
   - Tweet: "Experiencing technical issues. Investigating. ETA 30 min."
   - Reddit: Edit launch post with update
   - Email: Send to all users who signed up today

---

## Daily Checklist (First Week)

**Morning (30 min):**
- [ ] Check error logs
- [ ] Check signups overnight
- [ ] Respond to Reddit/HN comments
- [ ] Check email
- [ ] Review metrics (active users, API calls)

**Evening (30 min):**
- [ ] Check error logs again
- [ ] Review day's metrics
- [ ] Respond to any urgent questions
- [ ] Plan tomorrow's fixes/improvements

---

**Remember:** First week is about learning what users need, not hitting arbitrary metrics. Pay attention to feedback. Iterate quickly. Fix bugs fast.

**Good luck!** 🚀
