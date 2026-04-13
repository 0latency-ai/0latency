# Troubleshooting Guide

## recall returning memories_used: 0

### Symptoms
- POST /recall always returns `memories_used: 0`
- Static agent profile block returns correctly
- But no actual memories are surfaced
- /memories/extract and search endpoints work fine

### Root Causes

#### 1. Expired API Keys in Systemd Service File
**Check:** Run `systemctl cat zerolatency-api.service`

If you see hardcoded `Environment=GOOGLE_API_KEY=...` or `Environment=OPENAI_API_KEY=...` lines, these keys may be expired or invalid.

**Fix:**
1. Ensure all API keys are in `.env` file only
2. Update systemd service to use `EnvironmentFile=/path/to/.env`
3. Never hardcode API keys in systemd service files
4. Rotate keys via dashboard when needed

**Correct systemd configuration:**
```ini
[Service]
EnvironmentFile=/root/.openclaw/workspace/memory-product/.env
ExecStart=/usr/bin/python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8420 --workers 2
```

#### 2. Wrong agent_id
**Check:** Verify the agent_id exists in your tenant's namespace.

```bash
curl -X GET "https://api.0latency.ai/memories?agent_id=your-agent-id&limit=5" \
  -H "X-API-Key: your_api_key"
```

If this returns an empty array `[]`, the agent_id has no memories stored yet.

**Fix:** Use the correct agent_id or store memories first before calling recall.

#### 3. Similarity Threshold Too Strict
**Check:** Open `src/recall.py` and look for the cosine distance threshold in the semantic search query.

Current threshold: `(embedding <=> %s::extensions.vector) < 0.75`

If this threshold is too low (e.g., 0.5), it may filter out relevant memories.

**Fix:** Adjust threshold in `src/recall.py` line ~149. Higher values (closer to 1.0) = stricter similarity required.

### Verification

After fixing, test recall:
```bash
curl -X POST https://api.0latency.ai/recall \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "thomas",
    "conversation_context": "your query here",
    "budget_tokens": 4000
  }'
```

**Expected:** `memories_used > 0` in the response.

---

## Health Check Reports "degraded"

### Symptoms
- `/health` endpoint returns `"status": "degraded"`
- `"embedding": "failed: <error>"` or `"embedding": "degraded: <reason>"`

### Root Causes

#### 1. Embedding API Failure
The health check now tests the embedding API by generating an embedding for "health check".

**Common errors:**
- `400 Bad Request`: Invalid or expired Google API key
- `401 Unauthorized`: Invalid or expired OpenAI API key
- `429 Too Many Requests`: Rate limit exceeded

**Fix:**
1. Check `.env` file for valid `GOOGLE_API_KEY` and `OPENAI_API_KEY`
2. Verify keys are not expired
3. Check rate limits in Google Cloud Console or OpenAI dashboard
4. Restart API: `systemctl restart zerolatency-api`

#### 2. Network Issues
If embedding API is unreachable due to network issues, health will report degraded.

**Fix:**
1. Check server internet connectivity
2. Verify firewall rules allow outbound HTTPS
3. Test manually: `curl https://generativelanguage.googleapis.com/`

---

## Canary Alerts Firing

### Symptoms
Receiving Telegram alerts:
- "⚠️ RECALL FAILURE: tenant getting 0 memories on recall"
- "❌ /health check failed with HTTP 500"

### What This Means
The canary cron (runs every 30 minutes) detected an issue:
- `/health` endpoint not responding
- `/recall` returning 0 memories despite database having memories

### Investigation Steps

1. **Check API status:**
   ```bash
   systemctl status zerolatency-api
   curl https://api.0latency.ai/health
   ```

2. **Check canary logs:**
   ```bash
   tail -50 /root/logs/canary_$(date +%Y-%m-%d).log
   ```

3. **Check API logs:**
   ```bash
   journalctl -u zerolatency-api -n 100 --no-pager
   ```

4. **Test recall manually:**
   ```bash
   curl -X POST https://api.0latency.ai/recall \
     -H "X-API-Key: zl_live_jk13qjxlpiltqs3t157rvfypsa6xa40o" \
     -d '{"agent_id":"thomas","conversation_context":"test","budget_tokens":2000}'
   ```

### Common Fixes
- Restart API: `systemctl restart zerolatency-api`
- Check embedding API keys in `.env`
- Verify database connectivity
- Check server disk space: `df -h`

---

## Zero-Recall Alert After 3 Consecutive Failures

### Symptoms
Telegram alert after multiple recall requests return 0 memories:
> ⚠️ RECALL FAILURE
> 
> Tenant 44c3080d... getting 0 memories on recall.
> 
> Consecutive failures: 3
> Possible embedding or index issue.

### What This Means
The API tracked 3+ recall requests returning `memories_used: 0` within 60 minutes for the same tenant.

This indicates a systemic issue, not just a one-off query problem.

### Investigation Steps

1. **Check embedding API status:**
   ```bash
   curl https://api.0latency.ai/health | jq .embedding
   ```
   Should return `"ok"`, not `"failed"` or `"degraded"`.

2. **Check if agent has memories:**
   ```bash
   curl "https://api.0latency.ai/memories?agent_id=thomas&limit=5" \
     -H "X-API-Key: your_key"
   ```

3. **Test embedding generation manually:**
   ```bash
   python3 << 'PYEOF'
   import os
   os.environ['GOOGLE_API_KEY'] = 'your_key_here'
   import sys
   sys.path.insert(0, '/root/.openclaw/workspace/memory-product/src')
   from storage_multitenant import _embed_text
   result = _embed_text("test embedding")
   print(f"Embedding length: {len(result)}")
   PYEOF
   ```

### Common Fixes
- Embedding API keys expired → rotate in `.env`
- Database connectivity issue → check Supabase dashboard
- Vector index corrupted → contact support
- Threshold too strict → adjust in `src/recall.py`

The alert auto-resets when the next successful recall (memories_used > 0) occurs.
