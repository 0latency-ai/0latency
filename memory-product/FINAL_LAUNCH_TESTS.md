# Final Launch Tests - 0Latency API

**Before launch checklist - systematic verification of all critical paths.**

---

## Test 1: Data Isolation (CRITICAL)

**Purpose:** Verify different accounts can't see each other's memories.

### Setup
You need two separate accounts. You currently have:
- ✅ `jghiglia@gmail.com` - exists, has 2 memories
- ❌ `justin@startupsmartup.com` - doesn't exist (account creation failed earlier)

### Steps

**A. Create second account properly:**
1. Go to https://0latency.ai/login.html
2. Click "Create Account"
3. Email: `justin@startupsmartup.com`
4. Password: (at least 8 characters)
5. Should succeed and show dashboard with NEW API key

**B. Test isolation:**

**Account 1 (jghiglia@gmail.com):**
1. Open Claude Desktop
2. Current key should be: `zl_Live_bn-RvZbdRcINn__rkt4v5LctabsoIRPQ`
3. Ask: "Use 0latency to remember: My dog's name is Max"
4. Verify it stores successfully

**Account 2 (justin@startupsmartup.com):**
1. Open a NEW Claude Desktop window (or logout/login)
2. Update config with the NEW API key from justin@startupsmartup.com
3. Restart Claude Desktop
4. Ask: "What do you remember about my pets?"
5. **Expected:** Should say it has NO memories about pets
6. Ask: "Use 0latency to remember: My cat's name is Luna"
7. Verify it stores successfully

**Back to Account 1:**
1. Restart Claude Desktop with jghiglia@gmail.com key
2. Ask: "What do you remember about my pets?"
3. **Expected:** Should ONLY know about "Max the dog", NOT Luna the cat

**✅ PASS CRITERIA:** Each account only sees its own memories.

---

## Test 2: Memory Limit Enforcement (CRITICAL)

**Purpose:** Verify the database trigger prevents exceeding limits.

### Steps

**A. Check current memory count:**
```bash
curl https://api.0latency.ai/memories \
  -H "X-Api-Key: zl_live_lg5ojpbea291wh5i41pcv8n7qgnhi9q3" \
  | jq '.memories | length'
```

**B. Test limit (free tier = 10,000):**

If you're under 9,995 memories, this is hard to test. Instead, verify the trigger exists:

```bash
PGPASSWORD=jcYlwEhuHN9VcOuj psql \
  -h aws-1-us-east-1.pooler.supabase.com \
  -U postgres.fuojxlabvhtmysbsixdn \
  -d postgres \
  -c "SELECT trigger_name, event_object_table FROM information_schema.triggers WHERE trigger_name = 'enforce_memory_limit';"
```

**Expected:** Should show 1 row with `enforce_memory_limit` on `memories` table.

**✅ PASS CRITERIA:** Trigger exists in database.

---

## Test 3: API Key Regeneration (HIGH)

**Purpose:** Verify old keys stop working immediately after regeneration.

### Steps

**A. Store a memory with current key:**
```bash
curl -X POST https://api.0latency.ai/extract \
  -H "X-Api-Key: zl_live_lg5ojpbea291wh5i41pcv8n7qgnhi9q3" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test",
    "human_message": "Test before regen",
    "agent_message": ""
  }'
```

**Expected:** Returns `{"memories_stored": ...}`

**B. Regenerate key on dashboard:**
1. Go to https://0latency.ai/dashboard
2. Click "Regenerate" button (twice to confirm)
3. Copy NEW key

**C. Test old key is dead:**
```bash
curl -X POST https://api.0latency.ai/extract \
  -H "X-Api-Key: zl_live_lg5ojpbea291wh5i41pcv8n7qgnhi9q3" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test",
    "human_message": "Test after regen",
    "agent_message": ""
  }'
```

**Expected:** Returns `{"detail": "Invalid API key"}`

**D. Test new key works:**
```bash
curl -X POST https://api.0latency.ai/extract \
  -H "X-Api-Key: <NEW_KEY_HERE>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test",
    "human_message": "Test with new key",
    "agent_message": ""
  }'
```

**Expected:** Returns `{"memories_stored": ...}`

**✅ PASS CRITERIA:** Old key fails, new key works.

---

## Test 4: Rate Limiting (MEDIUM)

**Purpose:** Verify API doesn't accept unlimited requests.

### Steps

**A. Check rate limit headers:**
```bash
curl -I https://api.0latency.ai/health \
  -H "X-Api-Key: <YOUR_KEY>"
```

**Expected:** Look for headers like:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

**B. Rapid-fire test (10 requests in <1 second):**
```bash
for i in {1..10}; do
  curl -s https://api.0latency.ai/health \
    -H "X-Api-Key: <YOUR_KEY>" &
done
wait
```

**Expected:** All should succeed (health endpoint is usually not rate-limited)

**C. Check extraction rate limit:**
```bash
for i in {1..5}; do
  curl -X POST https://api.0latency.ai/extract \
    -H "X-Api-Key: <YOUR_KEY>" \
    -H "Content-Type: application/json" \
    -d "{\"agent_id\":\"test\",\"human_message\":\"Test $i\",\"agent_message\":\"\"}" &
done
wait
```

**Expected:** All succeed (free tier: 100 req/min, so 5 should be fine)

**✅ PASS CRITERIA:** Rate limiting exists and is documented.

---

## Test 5: CORS Configuration (MEDIUM)

**Purpose:** Verify production CORS is locked down.

### Steps

**A. Check CORS from 0latency.ai (should work):**

Open browser console on https://0latency.ai and run:
```javascript
fetch('https://api.0latency.ai/health')
  .then(r => r.json())
  .then(console.log)
```

**Expected:** Returns `{status: "ok", ...}`

**B. Check CORS from random domain (should fail):**

Open browser console on https://google.com and run:
```javascript
fetch('https://api.0latency.ai/health')
  .then(r => r.json())
  .then(console.log)
```

**Expected:** CORS error in console: `Access-Control-Allow-Origin`

**C. Verify environment config:**
```bash
grep "CORS origins configured" /var/log/uvicorn* | tail -1
```

**Expected:** Should show `env=production` and NOT include localhost or IP addresses.

**✅ PASS CRITERIA:** CORS allows 0latency.ai, blocks other origins.

---

## Test 6: Error Handling (LOW)

**Purpose:** Verify errors don't leak sensitive info.

### Steps

**A. Invalid API key:**
```bash
curl https://api.0latency.ai/extract \
  -H "X-Api-Key: zl_live_fakekeyfakekeyfakekeyfakekey" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","human_message":"x","agent_message":""}'
```

**Expected:** `{"detail": "Invalid API key"}` (no DB schema or stack traces)

**B. Malformed JSON:**
```bash
curl https://api.0latency.ai/extract \
  -H "X-Api-Key: <YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","human_message"'
```

**Expected:** Generic validation error (no internal paths)

**C. SQL injection attempt:**
```bash
curl -X POST https://api.0latency.ai/extract \
  -H "X-Api-Key: <YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test",
    "human_message": "My password is '\"''; DROP TABLE memories;--",
    "agent_message": ""
  }'
```

**Expected:** Stores as normal text (parameterized queries prevent injection)

**D. Verify table still exists:**
```bash
PGPASSWORD=jcYlwEhuHN9VcOuj psql \
  -h aws-1-us-east-1.pooler.supabase.com \
  -U postgres.fuojxlabvhtmysbsixdn \
  -d postgres \
  -c "SELECT COUNT(*) FROM memory_service.memories;"
```

**Expected:** Returns count (table not dropped)

**✅ PASS CRITERIA:** Errors are generic, SQL injection blocked.

---

## Test 7: End-to-End MCP Flow (CRITICAL)

**Purpose:** Verify the full user experience works.

### Steps

**A. Fresh account setup:**
1. Sign up at https://0latency.ai/login.html
2. Copy API key from dashboard
3. Update Claude Desktop config
4. Restart Claude Desktop

**B. Store memory:**
Ask Claude: "Use 0latency to remember that I prefer dark mode"

**Expected:** Claude calls `0latency_remember` tool and confirms storage

**C. Recall memory (same session):**
Ask Claude: "What theme do I prefer?"

**Expected:** Claude recalls "dark mode" from 0latency

**D. Recall memory (new session):**
1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. Start NEW conversation
4. Ask: "What theme do I prefer?"

**Expected:** Claude still recalls "dark mode" (persistent memory)

**✅ PASS CRITERIA:** Memory persists across sessions.

---

## Test 8: Backup System (LOW)

**Purpose:** Verify backup script works.

### Steps

**A. Run backup manually:**
```bash
/root/scripts/backup-0latency.sh
```

**Expected:** Creates `/root/backups/0latency/0latency-YYYYMMDD.sql.gz`

**B. Verify backup file:**
```bash
ls -lh /root/backups/0latency/
```

**Expected:** Shows compressed SQL file

**C. Check cron job:**
```bash
crontab -l | grep backup-0latency
```

**Expected:** Shows `0 2 * * * /root/scripts/backup-0latency.sh`

**✅ PASS CRITERIA:** Backup runs and creates file.

---

## Summary Checklist

Before launch, ALL CRITICAL tests must pass:

- [ ] **Test 1: Data Isolation** - Different accounts isolated
- [ ] **Test 2: Memory Limit** - Trigger exists
- [ ] **Test 3: Key Regeneration** - Old keys invalidated
- [ ] **Test 5: CORS** - Production lockdown working
- [ ] **Test 7: MCP Flow** - End-to-end working

Nice-to-have (not blockers):

- [ ] **Test 4: Rate Limiting** - Documented
- [ ] **Test 6: Error Handling** - No leaks
- [ ] **Test 8: Backup** - Script works

---

## If Any Test Fails

1. Document the failure
2. Fix the issue
3. Re-run the test
4. Do NOT launch until all CRITICAL tests pass

**Good luck! 🚀**
