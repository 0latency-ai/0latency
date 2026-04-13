# Deployment Checklist

Complete guide for deploying to production.

## Pre-Deployment

### Infrastructure
- [ ] Server provisioned (min: 2GB RAM, 2 vCPU, 20GB storage)
- [ ] PostgreSQL 12+ installed and running
- [ ] Python 3.8+ installed
- [ ] Port 8765 open in firewall
- [ ] SSL certificate configured (recommended: nginx reverse proxy)
- [ ] Domain/subdomain configured (e.g., `contributions.0latency.ai`)

### Credentials
- [ ] Stripe API key (production)
- [ ] 0Latency API key (production)
- [ ] GitHub webhook secret generated
- [ ] SMTP credentials configured
- [ ] Database password set
- [ ] Mission Control API key (if using)

### Accounts
- [ ] Stripe account with products created:
  - [ ] Pro 3-month plan
  - [ ] Scale 6-month plan
  - [ ] Scale 12-month plan
- [ ] 0Latency account active
- [ ] Email account for sending rewards

## Deployment Steps

### 1. Clone Repository
```bash
cd /opt
sudo git clone <repo-url> 0latency-contribution-reviewer
cd 0latency-contribution-reviewer
sudo chown -R www-data:www-data .
```

### 2. Run Setup
```bash
sudo -u www-data bash setup.sh
```

### 3. Configure Environment
```bash
sudo -u www-data cp .env.template .env
sudo -u www-data nano .env
```

Fill in all production values.

### 4. Initialize Database
```bash
sudo -u postgres psql -c "CREATE DATABASE zerolatency_contributions;"
sudo -u postgres psql -d zerolatency_contributions -f schema.sql
```

### 5. Configure Stripe Products
```bash
# Note product/price IDs in Stripe dashboard
# Update config.yaml with correct price IDs
```

### 6. Install systemd Service
```bash
sudo cp scripts/0latency-reviewer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable 0latency-reviewer
sudo systemctl start 0latency-reviewer
```

### 7. Configure nginx (Recommended)
```nginx
server {
    listen 443 ssl http2;
    server_name contributions.0latency.ai;

    ssl_certificate /etc/letsencrypt/live/contributions.0latency.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/contributions.0latency.ai/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 8. Configure GitHub Webhook
- Repository: `0latency/0latency`
- Payload URL: `https://contributions.0latency.ai/contribution-review`
- Content type: `application/json`
- Secret: (from `.env`)
- Events: Issues, Pull requests
- Active: ✓

### 9. Test Deployment
```bash
curl https://contributions.0latency.ai/health
bash scripts/test_webhook.sh https://contributions.0latency.ai
```

### 10. Monitor First Events
```bash
sudo journalctl -u 0latency-reviewer -f
```

## Post-Deployment

### Monitoring Setup
- [ ] Set up log aggregation (e.g., Papertrail, Logtail)
- [ ] Configure alerts for service failures
- [ ] Set up uptime monitoring (e.g., UptimeRobot)
- [ ] Database backup automation

### Validation
- [ ] Submit test bug report
- [ ] Submit test PR
- [ ] Verify auto-approval works
- [ ] Verify manual review flagging
- [ ] Verify promo code generation
- [ ] Verify email delivery
- [ ] Check Mission Control integration

### Documentation
- [ ] Update internal wiki with webhook URL
- [ ] Document override procedure for team
- [ ] Add Stripe product IDs to team docs
- [ ] Update contributor rewards page

## Configuration Tuning

### After First Week
Review metrics and adjust `config.yaml`:

```yaml
# If too many false positives (auto-approving low quality)
thresholds:
  pr_auto_approve_confidence: 0.90  # Increase threshold

# If too many false negatives (rejecting good contributions)
thresholds:
  pr_auto_approve_confidence: 0.80  # Decrease threshold
```

### After First Month
Analyze override patterns:

```bash
# Check override stats
psql -d zerolatency_contributions -c "
  SELECT 
    original_recommendation,
    override_recommendation,
    COUNT(*) as count
  FROM review_overrides
  GROUP BY original_recommendation, override_recommendation;
"
```

Adjust scoring weights in `app/reviewer.py` based on patterns.

## Backup & Recovery

### Database Backups
```bash
# Daily backup
sudo -u postgres pg_dump zerolatency_contributions > backup_$(date +%Y%m%d).sql

# Add to crontab
0 2 * * * sudo -u postgres pg_dump zerolatency_contributions > /backups/contributions_$(date +\%Y\%m\%d).sql
```

### Restore Procedure
```bash
sudo -u postgres psql -c "CREATE DATABASE zerolatency_contributions;"
sudo -u postgres psql zerolatency_contributions < backup_20260331.sql
sudo systemctl restart 0latency-reviewer
```

## Scaling

### If Processing >100 contributions/day:
1. Add database connection pooling
2. Consider Redis queue for async processing
3. Scale to multiple workers with load balancer
4. Add caching for contributor history lookups

### If Database >10GB:
1. Set up read replicas
2. Implement table partitioning by date
3. Archive old reviews to cold storage

## Security Hardening

- [ ] Enable firewall (only SSH, HTTP/S, PostgreSQL)
- [ ] Configure fail2ban
- [ ] Set up SSH key-only authentication
- [ ] Regular security updates
- [ ] Rotate secrets quarterly
- [ ] Enable database encryption at rest
- [ ] Implement rate limiting on webhook endpoint
- [ ] Set up HTTPS-only (HSTS)

## Rollback Plan

If deployment fails:

```bash
# Stop service
sudo systemctl stop 0latency-reviewer

# Restore database from backup
sudo -u postgres psql -d zerolatency_contributions < last_good_backup.sql

# Revert code
cd /opt/0latency-contribution-reviewer
git checkout <previous-commit>

# Restart
sudo systemctl start 0latency-reviewer
```

## Support Contacts

- **Infrastructure:** DevOps team
- **Stripe Issues:** billing@0latency.ai
- **0Latency API:** support@0latency.ai
- **GitHub Webhook:** github-admin@0latency.ai

## Success Metrics

Track after deployment:

- **Auto-approval rate:** Target 60-70%
- **False positive rate:** <5% (wrong auto-approvals)
- **False negative rate:** <10% (wrong rejections)
- **Average review time:** <2 minutes
- **Promo code redemption rate:** >80%

## Maintenance Schedule

- **Daily:** Check logs for errors
- **Weekly:** Review pending manual reviews
- **Monthly:** Analyze override patterns, tune thresholds
- **Quarterly:** Update dependencies, rotate secrets
- **Yearly:** Review and optimize database schema
