# 0Latency Contribution Reviewer

Automated GitHub contribution review agent for 0Latency reward claims. Evaluates bug reports, pull requests, and Build & Share submissions, then automatically approves or flags for manual review.

## Architecture

### Components

1. **Webhook Endpoint** (`app/webhook.py`)
   - FastAPI server receiving GitHub webhooks
   - Validates webhook signatures
   - Routes events to appropriate reviewers

2. **Review Agent** (`app/reviewer.py`)
   - Core evaluation logic for contributions
   - Scores based on quality heuristics
   - Auto-approves high-confidence submissions

3. **0Latency Integration** (`app/zerolatency_client.py`)
   - Stores all review decisions as memories
   - Tracks contributor history
   - Learns from human overrides

4. **Mission Control Integration** (`app/mission_control.py`)
   - Creates TODO items for manual review
   - Provides full context for human decisions

5. **Promo Code Generator** (`app/promo.py`)
   - Generates Stripe promo codes
   - Sends reward emails to contributors
   - Logs all redemptions

6. **Database** (`schema.sql`)
   - PostgreSQL schema for review tracking
   - Contributor statistics
   - Override history for learning

## Contribution Types

### 🐛 Bug Reports
- **Criteria:** Reproduction steps, not duplicate, actual bug (not feature request)
- **Auto-approve threshold:** 80% confidence
- **Reward:** Pro 3-month

### 🔧 Pull Requests
- **Criteria:** Merged, >10 meaningful lines, adds value
- **Auto-approve threshold:** 85% confidence
- **Reward:** Scale 6-month

### 🏗️ Build & Share
- **Criteria:** Quality demonstration (always manual review)
- **Auto-approve:** Never (requires human judgment)
- **Reward:** Scale 12-month

## Installation

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Stripe account
- 0Latency API account
- Mission Control instance (optional)

### Setup

1. **Clone and install:**
```bash
cd /root/.openclaw/workspace/0latency-contribution-reviewer
bash setup.sh
```

2. **Configure environment:**
Edit `.env` with your credentials:
```bash
cp .env.template .env
nano .env
```

Required variables:
- `STRIPE_API_KEY` - Stripe secret key
- `GITHUB_WEBHOOK_SECRET` - GitHub webhook secret
- `DB_*` - PostgreSQL connection details
- `ZEROLATENCY_API_KEY` - 0Latency API key
- `SMTP_*` - Email credentials for promo code delivery

3. **Initialize database:**
```bash
psql -h localhost -U postgres -d 0latency -f schema.sql
```

4. **Start service:**
```bash
# Development
python main.py

# Production (systemd)
sudo systemctl start 0latency-reviewer
sudo systemctl enable 0latency-reviewer
```

## GitHub Webhook Configuration

1. Go to your repository settings → Webhooks → Add webhook
2. Configure:
   - **Payload URL:** `http://your-server:8765/contribution-review`
   - **Content type:** `application/json`
   - **Secret:** (value from `GITHUB_WEBHOOK_SECRET`)
   - **Events:** Select "Issues" and "Pull requests"
   - **Active:** ✓

3. Test with:
```bash
curl http://localhost:8765/health
# Should return: {"status":"healthy","service":"contribution-reviewer"}
```

## Configuration

Edit `config.yaml` to tune thresholds and rewards:

```yaml
thresholds:
  bug_auto_approve_confidence: 0.80  # 80% confidence for auto-approve
  pr_auto_approve_confidence: 0.85   # 85% confidence for auto-approve
  build_share_always_manual: true    # Always require manual review

rewards:
  bug_report: "pro-3mo"
  pull_request: "scale-6mo"
  build_share: "scale-12mo"
```

## Workflow

### Automatic Flow

1. **Webhook received** → GitHub issue labeled or PR merged
2. **Review agent evaluates** → Scores contribution quality
3. **High confidence?**
   - ✅ Yes → Auto-approve, generate promo code, send email
   - ❌ No → Create Mission Control TODO for Justin

### Manual Override

For flagged reviews, Justin can:

1. Check Mission Control TODO
2. Review contribution details
3. Override decision:
```bash
python scripts/admin_override.py pr-123 approve "Great fix" justin
```

The system learns from overrides and adjusts future scoring.

## Learning System

The agent improves over time by:

1. **Storing all decisions** in 0Latency memory
2. **Tracking contributor history** (repeat contributors get higher scores)
3. **Learning from overrides** (when Justin approves/rejects recommendations)
4. **Pattern analysis** (identifies what "valuable PR" means over time)

## API Endpoints

- `POST /contribution-review` - GitHub webhook endpoint
- `GET /health` - Health check
- `GET /stats` - Review statistics

## Database Schema

### Tables

- `contribution_reviews` - All review decisions
- `review_overrides` - Human overrides for learning
- `contributor_stats` - Contributor history tracking
- `mission_control_todos` - Mission Control task references

## Admin Scripts

### Override a Decision
```bash
python scripts/admin_override.py <contribution_id> <decision> <reason> <admin>
```

Example:
```bash
python scripts/admin_override.py pr-456 approve "Excellent bug fix" justin
```

## Monitoring

### Logs
```bash
# Systemd logs
sudo journalctl -u 0latency-reviewer -f

# Service status
sudo systemctl status 0latency-reviewer
```

### Statistics
```bash
curl http://localhost:8765/stats
```

## Security

- GitHub webhook signature verification (HMAC-SHA256)
- Environment-based secrets (never committed)
- Database connection pooling
- Rate limiting (TODO: add if needed)

## Development

### Run tests
```bash
source venv/bin/activate
pytest
```

### Local development
```bash
python main.py
# Server runs on http://localhost:8765
```

### Test webhook locally
```bash
# Use ngrok or similar for GitHub to reach localhost
ngrok http 8765
# Update GitHub webhook URL to ngrok URL
```

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u 0latency-reviewer -n 50

# Verify environment
cat .env

# Test database connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;"
```

### Promo codes not sending
- Check SMTP credentials in `.env`
- Verify contributor email exists in GitHub payload
- Check Stripe API key is valid

### Webhook not receiving events
- Verify webhook URL is accessible from internet
- Check webhook secret matches `.env`
- Review GitHub webhook delivery logs

## Support

For issues or questions:
- Email: support@0latency.ai
- Documentation: https://0latency.ai/docs

## License

Proprietary - 0Latency, Inc.
