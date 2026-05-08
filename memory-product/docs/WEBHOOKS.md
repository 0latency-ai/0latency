# Webhooks Documentation

0Latency webhooks enable real-time notifications when important events occur in your memory system. This allows you to react to memory changes, invalidate caches, update downstream systems, and more.

## Overview

Webhooks are HTTP POST callbacks sent to URLs you configure. When a subscribed event occurs (e.g., a synthesis memory is replaced), 0Latency sends a signed JSON payload to your endpoint.

**Tier availability:**
- **Free/Pro**: Not available
- **Scale**: 1 webhook
- **Enterprise**: Up to 10 webhooks

## Supported Events

### `synthesis.replaced`

Fired when a synthesis memory is superseded by a new version (typically during redaction cascade resynthesis).

**Use cases:**
- Invalidate cached synthesis memories
- Trigger re-prompting of agents that referenced the old synthesis
- Update search indexes with new content
- Audit memory drift for compliance

## Setting Up a Webhook

### 1. Create a webhook endpoint

Your server must accept POST requests with a JSON body:

```bash
POST https://your-app.example.com/0latency-webhook
Content-Type: application/json
X-0Latency-Signature: t=1714000000,v1=abcdef...

{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "synthesis.replaced",
  "event_version": "1.0",
  "occurred_at": "2026-05-08T07:30:00.000Z",
  "tenant_id": "your-tenant-id",
  "agent_id": "your-agent",
  "synthesis": {
    "memory_id": "old-memory-uuid",
    "old_version": {
      "headline": "Original headline",
      "context": "Original context",
      "full_content": "Original full content",
      "created_at": "2026-05-01T00:00:00.000Z"
    },
    "new_version": {
      "memory_id": "new-memory-uuid",
      "headline": "Updated headline",
      "context": "Updated context",
      "full_content": "Updated full content",
      "created_at": "2026-05-08T07:30:00.000Z"
    },
    "change_reason": "Redaction cascade resynthesis",
    "audit_event_id": "audit-event-uuid"
  }
}
```

### 2. Register the webhook via API

```bash
curl -X POST https://api.0latency.ai/webhooks \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-cache-invalidator",
    "url": "https://your-app.example.com/0latency-webhook",
    "event_types": ["synthesis.replaced"]
  }'
```

**Response:**
```json
{
  "id": "webhook-uuid",
  "name": "prod-cache-invalidator",
  "url": "https://your-app.example.com/0latency-webhook",
  "secret": "64-char-hex-secret-SAVE-THIS",
  "event_types": ["synthesis.replaced"],
  "enabled": true,
  "created_at": "2026-05-08T07:00:00.000Z"
}
```

**IMPORTANT:** The `secret` is returned **only once** at creation. Save it securely. You'll need it to verify webhook signatures.

### 3. Verify webhook signatures

All webhook payloads are signed using HMAC SHA-256. The signature is sent in the `X-0Latency-Signature` header:

```
X-0Latency-Signature: t=1714000000,v1=abcdef...
```

Where:
- `t` = Unix timestamp when the signature was generated
- `v1` = HMAC SHA-256 signature (hex-encoded)

**Verification algorithm:**

```python
import hmac
import hashlib
import time

def verify_webhook(secret_hex: str, raw_body: bytes, signature_header: str) -> bool:
    """
    Verify a 0Latency webhook signature.

    Args:
        secret_hex: Your webhook secret (64-char hex string)
        raw_body: Raw request body bytes (do NOT parse JSON first)
        signature_header: Value of X-0Latency-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    # Parse header
    parts = dict(part.split("=") for part in signature_header.split(","))
    timestamp = int(parts["t"])
    received_sig = parts["v1"]

    # Reject if timestamp is too old (prevent replay attacks)
    if abs(time.time() - timestamp) > 300:  # 5 minutes
        return False

    # Compute expected signature
    msg = f"{timestamp}.".encode() + raw_body
    expected_sig = hmac.new(
        bytes.fromhex(secret_hex),
        msg,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected_sig, received_sig)


# Example usage
@app.post("/0latency-webhook")
async def handle_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-0Latency-Signature")

    if not verify_webhook(WEBHOOK_SECRET, raw_body, signature):
        raise HTTPException(401, "Invalid signature")

    payload = await request.json()

    # Process the event
    if payload["event_type"] == "synthesis.replaced":
        old_id = payload["synthesis"]["memory_id"]
        new_id = payload["synthesis"]["new_version"]["memory_id"]

        # Invalidate cache, update index, etc.
        cache.delete(f"memory:{old_id}")
        search_index.update(new_id, payload["synthesis"]["new_version"]["full_content"])

    return {"received": True}
```

### 4. Respond with 2xx status

Your endpoint must return a 2xx HTTP status code (e.g., 200, 201, 204) within 10 seconds to acknowledge receipt.

Non-2xx responses or timeouts trigger automatic retries.

## Retry Behavior

If your endpoint fails to respond with a 2xx status, 0Latency automatically retries with exponential backoff:

| Attempt | Delay | Cumulative Time |
|---------|-------|-----------------|
| 1       | 0s    | 0s              |
| 2       | 60s   | 1min            |
| 3       | 300s  | 6min            |
| 4       | 1500s | 31min           |
| 5       | 7200s | 2.5h            |
| 6 (final) | 43200s | 14.5h         |

After 5 failed attempts (covering ~14.5 hours), the delivery is marked as **dead-lettered** and no further retries occur.

**Same `event_id` is replayed** across all retry attempts. Use this for idempotency/deduplication.

## Auto-Disable

If a webhook accumulates **40 consecutive failures** across multiple events, it is automatically disabled to prevent further failures.

To re-enable:
```bash
curl -X PATCH https://api.0latency.ai/webhooks/{webhook-id} \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

## Managing Webhooks

### List webhooks
```bash
curl https://api.0latency.ai/webhooks \
  -H "X-API-Key: your-api-key"
```

### Update webhook
```bash
curl -X PATCH https://api.0latency.ai/webhooks/{webhook-id} \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "new-name",
    "url": "https://new-url.example.com/webhook",
    "enabled": false
  }'
```

### Rotate secret (Enterprise only)
```bash
curl -X POST https://api.0latency.ai/webhooks/{webhook-id}/rotate-secret \
  -H "X-API-Key: your-api-key"
```

Returns a new secret (shown **once only**). Old secret is immediately invalidated.

### Delete webhook
```bash
curl -X DELETE https://api.0latency.ai/webhooks/{webhook-id} \
  -H "X-API-Key: your-api-key"
```

Soft deletes the webhook. In-flight deliveries continue until they complete or exhaust retries.

## Security Best Practices

1. **Always verify signatures** - Never trust webhook payloads without HMAC verification
2. **Use HTTPS only** - Webhook URLs must use `https://`
3. **Reject stale timestamps** - Prevent replay attacks by checking `|now - t| < 300s`
4. **Store secrets securely** - Treat webhook secrets like API keys (environment variables, secret managers)
5. **Rate limit your endpoint** - Protect against accidentally creating duplicate webhooks
6. **Use idempotency keys** - Deduplicate events using `event_id`

## Troubleshooting

### Webhook not firing

1. Check webhook is enabled: `GET /webhooks` and verify `enabled: true`
2. Verify event type matches: `event_types` includes `synthesis.replaced`
3. Check consecutive failures: If `consecutive_failures >= 40`, webhook is auto-disabled

### Signature verification fails

1. Use raw request body (bytes), not parsed JSON
2. Verify secret is 64-character hex string (from initial webhook creation)
3. Check timestamp tolerance (must be within 5 minutes)
4. Ensure HMAC uses SHA-256 and hex encoding

### Deliveries timing out

1. Respond within 10 seconds
2. Process webhook asynchronously (return 200 immediately, process in background)
3. Check for long-running database queries or external API calls in your handler

## Support

For webhook issues or questions:
- Check delivery status via audit logs (Enterprise tier)
- Contact support@0latency.ai with webhook ID and event ID
