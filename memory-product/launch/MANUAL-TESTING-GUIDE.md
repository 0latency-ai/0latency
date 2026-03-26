# 🧪 Manual Testing Guide - 0Latency Launch

**Tester:** Justin  
**Date:** March 26, 2026  
**Base URL:** https://0latency.ai  
**API Base:** https://api.0latency.ai

---

## 🔐 Authentication Testing (5 tests)

### ✅ Test 1: Sign Up with Email/Password
**URL:** https://0latency.ai/signup

**Steps:**
1. Navigate to signup page
2. Enter email: `justin+test1@pflacademy.co`
3. Enter password: `TestPass123!`
4. Submit form
5. Check email for confirmation (if required)

**Expected:**
- Account created successfully
- Redirects to dashboard or onboarding
- No errors in browser console

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 2: Sign Up with GitHub OAuth
**URL:** https://0latency.ai/signup

**Steps:**
1. Click "Sign up with GitHub"
2. Authorize the app (if first time)
3. Redirected back to 0latency.ai

**Expected:**
- Account created with GitHub profile
- Redirects to dashboard
- Email matches GitHub email

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 3: Sign Up with Google OAuth
**URL:** https://0latency.ai/signup

**Steps:**
1. Click "Sign up with Google"
2. Select Google account
3. Grant permissions
4. Redirected back to 0latency.ai

**Expected:**
- Account created with Google profile
- Redirects to dashboard
- Email matches Google email

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 4: Login with All 3 Methods
**URL:** https://0latency.ai/login

**Steps:**
1. Log out
2. Log in with email/password
3. Log out
4. Log in with GitHub
5. Log out
6. Log in with Google

**Expected:**
- All 3 methods work
- Session persists across pages
- Logout clears session

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 5: Password Reset Flow
**URL:** https://0latency.ai/forgot-password

**Steps:**
1. Click "Forgot Password"
2. Enter email: `justin+test1@pflacademy.co`
3. Check email inbox
4. Click reset link
5. Enter new password
6. Submit
7. Try logging in with new password

**Expected:**
- Reset email arrives within 2 min
- Link works (not expired)
- Password updates successfully
- Can log in with new password

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

## 📊 Dashboard Testing (2 tests)

### ✅ Test 6: Dashboard Loads
**URL:** https://0latency.ai/dashboard

**Steps:**
1. Log in
2. Navigate to each dashboard page:
   - Overview
   - Memories
   - API Keys
   - Settings
   - Billing

**Expected:**
- All pages load without errors
- No 404s or 500s
- UI renders correctly on desktop
- No console errors

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 7: API Key Generation
**URL:** https://0latency.ai/dashboard/api-keys

**Steps:**
1. Click "Generate New API Key"
2. Copy the key
3. Try to regenerate
4. Revoke the key
5. Confirm revocation

**Expected:**
- Key generates successfully
- Shows once, then hides (security)
- Regenerate creates new key, invalidates old
- Revoke works instantly

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

## 🔌 API Testing (2 tests)

### ✅ Test 8: API Call with SDK (Python)
**Location:** Local machine or server

**Steps:**
1. Install SDK: `pip install zerolatency`
2. Create test script:

```python
from zerolatency import ZeroLatency

client = ZeroLatency(api_key="YOUR_API_KEY")

# Add a memory
result = client.add_memory(
    agent_id="test_agent",
    content="Justin tested the Python SDK on March 26, 2026",
    metadata={"test": True}
)
print("Added:", result)

# Recall memories
memories = client.recall(
    agent_id="test_agent",
    query="When did Justin test the SDK?"
)
print("Recalled:", memories)
```

3. Run the script
4. Check dashboard for new memory

**Expected:**
- SDK installs without errors
- API calls succeed
- Memory appears in dashboard
- Recall returns relevant result

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 9: API Call with cURL
**Location:** Terminal

**Steps:**
```bash
# Add a memory
curl -X POST https://api.0latency.ai/v1/memories \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "curl_test",
    "content": "Testing with cURL on March 26, 2026",
    "metadata": {"method": "curl"}
  }'

# Recall memories
curl -X POST https://api.0latency.ai/v1/recall \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "curl_test",
    "query": "cURL test"
  }'
```

**Expected:**
- Both requests return 200 OK
- JSON responses are valid
- Memory ID returned on add
- Recall returns the memory

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

## 💳 Stripe Testing (3 tests)

### ✅ Test 10: Stripe Checkout Flow
**URL:** https://0latency.ai/dashboard/billing

**Steps:**
1. Click "Upgrade to Pro"
2. Redirected to Stripe Checkout
3. Use test card: `4242 4242 4242 4242`
4. Expiry: any future date, CVC: any 3 digits
5. Complete payment

**Expected:**
- Stripe checkout loads
- Test payment succeeds
- Redirects back to dashboard
- Shows success message

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 11: Stripe Webhook
**Location:** Server logs + database

**Steps:**
1. After completing checkout, wait 30 seconds
2. Check webhook logs:
   ```bash
   tail -f /var/log/0latency-monitor.log | grep webhook
   ```
3. Check database:
   ```sql
   SELECT * FROM users WHERE email = 'your_test_email' ORDER BY updated_at DESC LIMIT 1;
   ```

**Expected:**
- Webhook received from Stripe
- User tier updated to 'pro'
- Stripe customer ID saved
- Subscription ID saved

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 12: Pro Features Unlock
**URL:** https://0latency.ai/dashboard

**Steps:**
1. After upgrading, check dashboard
2. Try accessing:
   - Knowledge graph view
   - Memory consolidation
   - Advanced analytics
3. Check API limits (50K memories, not 100)

**Expected:**
- Pro badge shows on dashboard
- Pro features are accessible (not grayed out)
- Free tier restrictions lifted
- Billing page shows active subscription

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

## 🚫 Limits & Data Testing (3 tests)

### ✅ Test 13: Hit Free Tier Limit
**Location:** Script on server or local

**Steps:**
1. Create new free account
2. Run script to add 101 memories (over 100 limit):

```python
from zerolatency import ZeroLatency

client = ZeroLatency(api_key="FREE_TIER_API_KEY")

for i in range(101):
    try:
        client.add_memory(
            agent_id="limit_test",
            content=f"Test memory {i}"
        )
        print(f"Added memory {i}")
    except Exception as e:
        print(f"Failed at {i}: {e}")
        break
```

**Expected:**
- First 100 succeed
- 101st returns 429 error
- Error message suggests upgrade
- Dashboard shows "100/100 memories used"

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 14: Data Export
**URL:** https://0latency.ai/dashboard/settings

**Steps:**
1. Navigate to Settings
2. Click "Export My Data"
3. Wait for download
4. Open JSON file
5. Verify contents

**Expected:**
- Export triggers download
- JSON is valid
- Contains all memories, metadata, timestamps
- No sensitive data leaked (API keys, passwords)

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 15: Account Deletion
**URL:** https://0latency.ai/dashboard/settings

**Steps:**
1. Scroll to "Danger Zone"
2. Click "Delete Account"
3. Confirm deletion
4. Check database:
   ```sql
   SELECT * FROM users WHERE email = 'your_test_email';
   ```

**Expected:**
- Confirmation modal appears
- Account deleted after confirm
- Redirects to homepage
- User record removed from DB
- All memories purged

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

## ⚙️ Infrastructure (8 tests)

### ✅ Test 16: Reddit API Keys Added
**Location:** Server environment

**Steps:**
```bash
ssh root@164.90.156.169
echo $REDDIT_CLIENT_ID
echo $REDDIT_CLIENT_SECRET
```

**Expected:**
- Both env vars exist
- Values are non-empty

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 17: GitHub API Token Added
**Location:** Server environment

**Steps:**
```bash
ssh root@164.90.156.169
echo $GITHUB_TOKEN
```

**Expected:**
- Token exists
- Has repo permissions

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 18: Support Email Working
**Steps:**
1. Send test email to: support@0latency.ai
2. Check Justin's inbox

**Expected:**
- Email arrives within 2 min
- Forwards to justin@pflacademy.co or jghiglia@gmail.com

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 19: Legal Email Working
**Steps:**
1. Send test email to: legal@0latency.ai
2. Check Justin's inbox

**Expected:**
- Email arrives within 2 min
- Forwards to justin@pflacademy.co or jghiglia@gmail.com

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 20: Analytics Table Migrated
**Location:** Supabase dashboard

**Steps:**
```bash
ssh root@164.90.156.169
psql $DATABASE_URL -c "\dt analytics_events;"
```

**Expected:**
- Table exists
- Has columns: id, event_type, user_id, metadata, created_at

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 21: Monitoring Cron Running
**Location:** Server

**Steps:**
```bash
ssh root@164.90.156.169
crontab -l | grep 0latency
cat /var/log/0latency-monitor.log | tail -20
```

**Expected:**
- Cron job exists (runs every 15 min)
- Log file shows recent entries
- No critical errors

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 22: Error Alerting Tested
**Location:** Server

**Steps:**
```bash
ssh root@164.90.156.169
# Trigger a test alert
curl -X POST http://localhost:8000/trigger-test-alert
```

**Expected:**
- Telegram message arrives within 1 min
- Alert includes error details
- Sent to Justin's Telegram (8544668212)

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

### ✅ Test 23: Backups Confirmed
**Location:** Supabase dashboard

**Steps:**
1. Log in to Supabase: https://supabase.com/dashboard
2. Navigate to project settings
3. Check backup schedule

**Expected:**
- Daily backups enabled
- Retention period: 7 days minimum
- Last backup succeeded

**Result:** [ ] PASS / [ ] FAIL  
**Notes:**

---

## 📝 Summary

**Total Tests:** 23  
**Passed:** ___  
**Failed:** ___  
**Blocked:** ___

**Critical Issues Found:**
- 

**Minor Issues Found:**
- 

**Ready to Launch?** [ ] YES / [ ] NO

**Notes:**


---

**Completed by:** Justin  
**Date:** March 26, 2026  
**Time Spent:** ___ hours
