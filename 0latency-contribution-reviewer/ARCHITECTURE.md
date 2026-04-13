# Architecture Overview

## System Diagram

```
┌──────────────┐
│   GitHub     │
│  Repository  │
└──────┬───────┘
       │ Webhook (issue labeled, PR merged)
       │
       ▼
┌─────────────────────────────────────────────────┐
│         FastAPI Webhook Endpoint                │
│              (app/webhook.py)                   │
│  • Verify signature                             │
│  • Parse payload                                │
│  • Route to reviewer                            │
└──────┬──────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────┐
│         Contribution Reviewer                   │
│            (app/reviewer.py)                    │
│  • Score contribution quality                   │
│  • Check contributor history                    │
│  • Query 0Latency for past contributions        │
│  • Make recommendation                          │
└──────┬──────────────────────────────────────────┘
       │
       ├─────────────────┬─────────────────┬───────┐
       │                 │                 │       │
       ▼                 ▼                 ▼       ▼
┌──────────┐     ┌──────────────┐  ┌─────────┐ ┌──────────┐
│PostgreSQL│     │  0Latency    │  │ Mission │ │  Stripe  │
│ Database │     │     API      │  │ Control │ │   API    │
│          │     │              │  │   API   │ │          │
│• Reviews │     │• Store       │  │• Create │ │• Generate│
│• Stats   │     │  memories    │  │  TODO   │ │  promo   │
│• History │     │• Learn from  │  │• Track  │ │  codes   │
│• Overrides│    │  overrides   │  │  status │ │• Coupons │
└──────────┘     └──────────────┘  └─────────┘ └──────────┘
       │                                  │
       │                                  ▼
       │                          ┌──────────────┐
       │                          │ Email (SMTP) │
       └──────────────────────────┤• Send promo  │
                                  │  to contrib. │
                                  └──────────────┘
```

## Component Details

### 1. Webhook Endpoint (`app/webhook.py`)
**Responsibility:** Accept and validate GitHub webhooks

**Key Functions:**
- `verify_github_signature()` - HMAC-SHA256 validation
- `webhook_handler()` - Route events to reviewers
- `process_review_decision()` - Orchestrate decision flow

**Endpoints:**
- `POST /contribution-review` - Main webhook receiver
- `GET /health` - Health check
- `GET /stats` - System statistics

### 2. Review Agent (`app/reviewer.py`)
**Responsibility:** Evaluate contribution quality and make recommendations

**Key Classes:**
- `ContributionReviewer` - Main reviewer logic

**Methods:**
- `review_bug_report()` - Score bug reports
- `review_pull_request()` - Score PRs
- `review_build_and_share()` - Handle manual reviews

**Scoring Criteria:**

**Bug Reports:**
- Reproduction steps present (+15%)
- Expected vs actual behavior (+10%)
- Detailed description (+10%)
- Not a feature request (base)
- Not duplicate (critical)
- Contributor history (+5%)

**Pull Requests:**
- Meaningful size >10 lines (+5-15%)
- Good description (+10%)
- Includes tests (+10%)
- Includes docs (+5%)
- Not trivial (-20% if typo/whitespace)
- Contributor history (+10%)

### 3. Database Layer (`app/database.py`)
**Responsibility:** Persist all review data

**Key Tables:**
- `contribution_reviews` - All decisions
- `contributor_stats` - Historical performance
- `review_overrides` - Learning data
- `mission_control_todos` - Task tracking

**Key Methods:**
- `save_review()` - Store decision
- `get_contributor_history()` - Lookup past contributions
- `save_override()` - Record human corrections

### 4. 0Latency Integration (`app/zerolatency_client.py`)
**Responsibility:** Memory storage and learning

**Key Methods:**
- `store_review_decision()` - Save to memory API
- `store_override()` - Save corrections for learning
- `search_contributor_history()` - Query past memories
- `learn_from_overrides()` - Analyze patterns

**Memory Structure:**
```json
{
  "text": "Contribution review for alice: approve with 87% confidence...",
  "context": "GitHub pull_request review",
  "metadata": {
    "contribution_id": "pr-456",
    "contributor": "alice",
    "recommendation": "approve",
    "confidence": 0.87
  }
}
```

### 5. Promo Generator (`app/promo.py`)
**Responsibility:** Generate and deliver rewards

**Key Methods:**
- `generate_promo_code()` - Create Stripe coupon + promo code
- `_send_email()` - SMTP delivery

**Flow:**
1. Create Stripe coupon (100% off, X months)
2. Create promo code from coupon
3. Send HTML email to contributor
4. Update database with code

### 6. Mission Control (`app/mission_control.py`)
**Responsibility:** Queue manual reviews

**Key Methods:**
- `create_review_task()` - Add TODO for Justin
- `update_task_status()` - Mark resolved

**Task Format:**
```
🔍 Review PR: alice
Agent recommends: APPROVE (85% confidence)
Reason: Substantial PR (120 lines). Good PR description. Includes tests.
```

## Data Flow

### Auto-Approval Flow
```
GitHub Event → Webhook → Reviewer → High Confidence (>85%)
  → Save to DB
  → Store in 0Latency
  → Generate Promo Code
  → Send Email
  ✅ Done
```

### Manual Review Flow
```
GitHub Event → Webhook → Reviewer → Medium Confidence (40-85%)
  → Save to DB
  → Store in 0Latency
  → Create Mission Control TODO
  ⏸️ Awaits Human Review
```

### Override Learning Flow
```
Justin Overrides → admin_override.py
  → Update DB (review_overrides table)
  → Store in 0Latency (tagged as "correction")
  → Future reviews learn from pattern
  🧠 System Improves
```

## Decision Logic

```python
if confidence >= auto_approve_threshold:
    if contributor_email:
        generate_promo_code()
        send_email()
        status = "auto_approved"
    else:
        create_todo()
        status = "review_needed"

elif confidence < reject_threshold:
    status = "rejected"
    reason = "Does not meet quality criteria"

else:
    create_todo()
    status = "manual_review"
```

## Configuration Hierarchy

```
config.yaml               # Main config
  ├── thresholds          # Confidence thresholds
  ├── rewards             # Tier mappings
  ├── stripe              # API keys, product IDs
  ├── github              # Webhook secret
  ├── database            # Connection params
  ├── zerolatency         # API config
  ├── mission_control     # Integration config
  └── email               # SMTP settings
```

## Error Handling

### Webhook Processing
- Invalid signature → 401 Unauthorized
- Invalid JSON → 400 Bad Request
- Unknown event → 200 OK (ignored)

### Review Processing
- Database error → Retry 3x, then log failure
- 0Latency API error → Log, continue (non-blocking)
- Stripe API error → Fall back to manual review
- SMTP error → Log, continue (admin can retry)

## Security Model

### Authentication
- **GitHub webhook:** HMAC-SHA256 signature verification
- **0Latency API:** Bearer token
- **Mission Control:** API key
- **Stripe:** Secret API key

### Data Protection
- Secrets in environment variables (never committed)
- Database credentials in `.env`
- PostgreSQL over TLS (production)
- HTTPS for all external APIs

### Rate Limiting
- GitHub webhooks: ~100/hour (per repo)
- 0Latency API: 10,000/minute (Enterprise)
- Stripe API: 100/second
- SMTP: Depends on provider

## Performance Characteristics

### Latency
- Webhook processing: <100ms
- Review scoring: <500ms
- Database write: <50ms
- 0Latency storage: <100ms (async, non-blocking)
- Total response time: <1 second

### Throughput
- Expected: 10-50 contributions/day
- Tested: 100 contributions/hour
- Max theoretical: 1000/hour (with scaling)

### Resource Usage
- Memory: ~200MB base, +50MB per worker
- CPU: <5% (idle), <30% (processing)
- Database: ~10MB/1000 reviews
- Network: <1KB per webhook

## Scaling Strategy

### Horizontal Scaling
```
Load Balancer
  ├── Reviewer Instance 1
  ├── Reviewer Instance 2
  └── Reviewer Instance 3
       ↓
  Shared PostgreSQL
  Shared Redis Queue (optional)
```

### Vertical Scaling
- Increase worker threads in uvicorn
- Add database connection pooling
- Cache contributor history in Redis

## Monitoring Points

### Health Checks
- `/health` - Service alive
- `/stats` - Pending reviews count
- Database connectivity
- 0Latency API reachability

### Metrics to Track
- Reviews processed per hour
- Auto-approval rate
- Manual review rate
- Rejection rate
- Average confidence score
- Override rate (learning indicator)
- Email delivery success rate

### Logs to Collect
- Webhook events received
- Review decisions made
- Auto-approvals sent
- Manual reviews created
- Errors and exceptions
- Override actions

## Dependencies

### Runtime
- Python 3.8+
- FastAPI + Uvicorn
- PostgreSQL 12+
- psycopg2 (database driver)

### External Services
- GitHub (webhooks)
- Stripe (promo codes)
- 0Latency (memory API)
- SMTP server (email)
- Mission Control (optional)

### Development
- pytest (testing)
- black (formatting)
- mypy (type checking)
