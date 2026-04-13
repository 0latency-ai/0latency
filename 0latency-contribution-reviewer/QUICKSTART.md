# Quick Start Guide

Get the 0Latency Contribution Reviewer running in 5 minutes.

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] PostgreSQL 12+ running
- [ ] Stripe API key
- [ ] 0Latency API key
- [ ] SMTP credentials (Gmail, SendGrid, etc.)

## 1. Install

```bash
cd /root/.openclaw/workspace/0latency-contribution-reviewer
bash setup.sh
```

## 2. Configure

Edit `.env` with your credentials:

```bash
nano .env
```

**Minimum required:**
```env
STRIPE_API_KEY=sk_live_...
GITHUB_WEBHOOK_SECRET=your_secret_here
ZEROLATENCY_API_KEY=your_key_here
DB_PASSWORD=your_db_password
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

## 3. Initialize Database

```bash
source venv/bin/activate
psql -h localhost -U postgres -d 0latency -f schema.sql
```

## 4. Start Service

### Development (foreground):
```bash
python main.py
```

### Production (systemd):
```bash
sudo systemctl start 0latency-reviewer
sudo systemctl enable 0latency-reviewer
```

## 5. Configure GitHub Webhook

1. Go to: `https://github.com/your-org/your-repo/settings/hooks`
2. Click "Add webhook"
3. Fill in:
   - **Payload URL:** `http://your-server:8765/contribution-review`
   - **Content type:** `application/json`
   - **Secret:** Same as `GITHUB_WEBHOOK_SECRET` in `.env`
   - **Events:** Check "Issues" and "Pull requests"
4. Click "Add webhook"

## 6. Test

```bash
# Health check
curl http://localhost:8765/health

# Should return:
# {"status":"healthy","service":"contribution-reviewer"}

# Check stats
curl http://localhost:8765/stats
```

## 7. Monitor

```bash
# View logs
sudo journalctl -u 0latency-reviewer -f

# Check service status
sudo systemctl status 0latency-reviewer
```

## Next Steps

- Label an issue as "bug" to test bug report review
- Merge a PR to test pull request review
- Check Mission Control for flagged reviews
- Review first auto-approvals to calibrate thresholds

## Tuning

Edit `config.yaml` to adjust:
- Auto-approve confidence thresholds
- Reward tiers
- Review criteria weights

## Troubleshooting

**Service won't start:**
```bash
sudo journalctl -u 0latency-reviewer -n 50
```

**Database connection fails:**
```bash
psql -h localhost -U postgres -d 0latency -c "SELECT 1;"
```

**Promo codes not sending:**
- Verify SMTP credentials
- Check contributor email exists
- Review service logs for errors

## Support

Questions? Email support@0latency.ai
