# Testing Guide

## Manual Testing Workflow

### 1. Health Check

```bash
curl http://localhost:8765/health
```

Expected response:
```json
{"status":"healthy","service":"contribution-reviewer"}
```

### 2. Stats Check

```bash
curl http://localhost:8765/stats
```

Expected response:
```json
{"pending_reviews":0,"status":"operational"}
```

### 3. Test Bug Report Review

Create a test issue in your GitHub repo:

**Title:** "App crashes when clicking submit button"

**Body:**
```
Steps to reproduce:
1. Open the form
2. Fill in all fields
3. Click submit button
4. App crashes

Expected: Form should submit successfully
Actual: App crashes with error

Environment: Chrome 120, macOS 14
```

**Label:** `bug`

**Expected:** Agent should auto-approve (high confidence) or flag for review

### 4. Test PR Review

Create and merge a test PR:

**Title:** "Fix validation bug in user registration"

**Body:**
```
This PR fixes a bug where user registration would fail with invalid email formats.

Changes:
- Updated email validation regex
- Added unit tests
- Updated documentation
```

**Metrics:** 150+ lines changed, 3+ files

**Expected:** Agent should auto-approve (substantial, tested, documented)

### 5. Test Low-Quality PR (Should Reject)

**Title:** "fix typo"

**Body:** (empty or minimal)

**Metrics:** 2 lines changed, 1 file

**Expected:** Agent should reject (trivial change)

### 6. Test Webhook Signature Validation

```bash
# Valid signature
bash scripts/test_webhook.sh

# Invalid signature (should fail)
curl -X POST http://localhost:8765/contribution-review \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-Hub-Signature-256: sha256=invalid" \
  -d '{"action":"labeled"}'

# Expected: 401 Unauthorized
```

### 7. Test Manual Override

```bash
# Override a review decision
python scripts/admin_override.py pr-123 approve "Excellent fix after manual review" justin

# Check database
psql -d 0latency -c "SELECT * FROM review_overrides ORDER BY overridden_at DESC LIMIT 1;"
```

### 8. Verify 0Latency Memory Storage

After processing a review:

```bash
# Check that memory was stored
# (Use your 0Latency dashboard or API to verify)
```

### 9. Verify Email Delivery

After auto-approval:

1. Check SMTP logs
2. Verify email received by test contributor
3. Confirm promo code is valid in Stripe

### 10. Verify Mission Control Integration

After a "review" recommendation:

1. Check Mission Control dashboard
2. Verify TODO item was created
3. Confirm it includes all context

## Database Queries for Verification

### Check recent reviews
```sql
SELECT 
  contribution_id, 
  contributor, 
  type, 
  recommendation, 
  confidence, 
  created_at 
FROM contribution_reviews 
ORDER BY created_at DESC 
LIMIT 10;
```

### Check contributor stats
```sql
SELECT * FROM contributor_stats ORDER BY total_contributions DESC;
```

### Check overrides (learning data)
```sql
SELECT 
  ro.*, 
  cr.contribution_id, 
  cr.contributor 
FROM review_overrides ro 
JOIN contribution_reviews cr ON ro.review_id = cr.id 
ORDER BY ro.overridden_at DESC;
```

### Check promo code usage
```sql
SELECT 
  contribution_id,
  contributor,
  promo_code,
  promo_tier,
  promo_sent_at
FROM contribution_reviews
WHERE promo_code IS NOT NULL
ORDER BY promo_sent_at DESC;
```

## Load Testing

### Simulate multiple webhooks

```bash
for i in {1..10}; do
  bash scripts/test_webhook.sh &
done
wait
echo "Load test complete"
```

### Monitor performance

```bash
# Watch system resources
htop

# Monitor database connections
psql -d 0latency -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '0latency';"

# Check API response times
time curl http://localhost:8765/health
```

## Troubleshooting Tests

### Webhook not received
- Check firewall: `sudo ufw status`
- Verify port open: `netstat -tulpn | grep 8765`
- Check GitHub webhook delivery logs

### Database errors
- Verify schema: `psql -d 0latency -c "\dt"`
- Check permissions: `psql -d 0latency -c "\du"`
- Test connection: `psql -h localhost -U postgres -d 0latency -c "SELECT 1;"`

### Email not sending
- Test SMTP: `curl -v telnet://smtp.gmail.com:587`
- Check credentials in `.env`
- Review service logs: `sudo journalctl -u 0latency-reviewer -n 50`

### 0Latency API errors
- Verify API key: `echo $ZEROLATENCY_API_KEY`
- Test API: `curl -H "Authorization: Bearer $ZEROLATENCY_API_KEY" https://api.0latency.ai/v1/health`

## Continuous Testing

Set up automated testing with cron:

```bash
# Add to crontab (every hour)
0 * * * * /root/.openclaw/workspace/0latency-contribution-reviewer/scripts/test_webhook.sh > /tmp/reviewer-test.log 2>&1
```

## Expected Behavior Summary

| Contribution Type | Quality | Expected Decision | Auto-Approve? |
|------------------|---------|-------------------|---------------|
| Bug report with reproduction | High | approve | ✅ Yes (>80%) |
| Bug report without details | Low | reject | ❌ No |
| Bug report moderate quality | Medium | review | ❌ No |
| PR >100 lines with tests | High | approve | ✅ Yes (>85%) |
| PR <10 lines trivial | Low | reject | ❌ No |
| PR moderate changes | Medium | review | ❌ No |
| Build & Share | Any | review | ❌ Never |

## Success Criteria

✅ All webhooks processed without errors
✅ High-quality contributions auto-approved
✅ Low-quality contributions rejected
✅ Medium-quality flagged for manual review
✅ Promo codes generated and sent
✅ Memories stored in 0Latency
✅ Mission Control TODOs created
✅ Database records accurate
✅ Override learning working
