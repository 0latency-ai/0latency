# Stripe Webhook Test - Final Launch Blocker

**Goal:** Verify that when a user upgrades to Scale tier, the webhook fires and updates their account tier in the database.

**Time:** 5 minutes

---

## Test Procedure

### 1. Open Incognito Window
- Prevents cache/cookie issues
- Go to: https://0latency.ai

### 2. Create Test Account
- Click "Get Started" or "Sign Up"
- Email: `test-stripe-$(date +%s)@example.com` (unique timestamp)
- Password: anything (you won't need to remember it)
- Sign up

### 3. Verify Free Tier
- Dashboard should show: "Free Tier - 10,000 memory limit"
- Copy your API key (starts with `zl_live_...`)

### 4. Test Free Tier Works
Open terminal, run:
```bash
curl -X POST https://api.0latency.ai/v1/extract \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "stripe-test-agent",
    "text": "This is a test memory for Stripe webhook verification."
  }'
```

Should return 200 OK with memory_id.

### 5. Upgrade to Scale Tier
- Click "Upgrade to Scale" or "Pricing" → "Upgrade"
- Stripe checkout should open

### 6. Use Test Card
Stripe test card details:
- **Card number:** 4242 4242 4242 4242
- **Expiry:** Any future date (e.g., 12/28)
- **CVC:** Any 3 digits (e.g., 123)
- **ZIP:** Any 5 digits (e.g., 94111)
- **Name:** Test User

### 7. Complete Checkout
- Click "Subscribe" or "Pay $89"
- Should redirect to: https://0latency.ai/checkout-success.html
- Page should say: "Payment Successful - Your Scale tier is now active"

### 8. Verify Tier Upgrade
- Go back to dashboard: https://0latency.ai/dashboard.html
- Should now show: "Scale Tier - 100M memory limit"
- Tier badge should be orange/premium styled

### 9. Test Scale Tier Features
Run this API call (same key as before):
```bash
curl -X POST https://api.0latency.ai/v1/extract \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "stripe-test-agent",
    "text": "Palmer from ZeroClick is the Head of Engineering. He sold Honey to PayPal for $4 billion with Ryan Hudson."
  }'
```

Response should include:
```json
{
  "memory_id": "...",
  "entities_extracted": 3,  // Palmer, ZeroClick, Ryan Hudson
  "relationships_created": 2,  // Palmer -> ZeroClick, Palmer -> Ryan Hudson
  "sentiment_analyzed": true,
  "tier_features_used": ["entity_extraction", "relationship_graph", "sentiment_analysis"]
}
```

✅ **If you see entities/relationships/sentiment → webhook worked!**

### 10. Check Webhook Logs (Thomas Will Monitor)
While you're testing, I'll watch:
```bash
tail -f /var/log/0latency-api.log | grep webhook
```

I'll confirm:
- Webhook received from Stripe
- Tenant tier updated to "scale"
- No errors

---

## Expected Flow

1. User signs up → Free tier (tier=free, limit=10000)
2. User clicks Upgrade → Stripe checkout
3. User pays → Stripe fires webhook to https://api.0latency.ai/webhooks/stripe
4. Webhook handler updates DB: tier="scale", limit=100000000
5. User returns to dashboard → sees Scale tier
6. Next API call → features auto-enabled (entities, relationships, sentiment)

---

## What Could Go Wrong

### ❌ Webhook doesn't fire
**Symptom:** Tier still shows "Free" after payment  
**Cause:** Stripe webhook URL not configured  
**Fix:** Check Stripe dashboard → Webhooks → verify https://api.0latency.ai/webhooks/stripe is listed

### ❌ Webhook fires but tier doesn't update
**Symptom:** Webhook logs show event received, but tier unchanged  
**Cause:** Database update failed  
**Fix:** Check logs for SQL errors, verify tenant_id mapping

### ❌ Tier updates but features don't work
**Symptom:** Tier shows "Scale" but entities_extracted = 0  
**Cause:** Feature enablement logic broken  
**Fix:** Check /extract endpoint tier detection

---

## Rollback Plan

If webhook test fails:
1. **Don't launch yet**
2. Debug webhook locally (I'll help)
3. Fix the issue
4. Re-test with new test account
5. Only launch when webhook works 100%

**Webhook is non-negotiable.** If it doesn't work, paying customers get stuck on Free tier → instant churn.

---

## Success Criteria

✅ Payment completes  
✅ Redirect to /checkout-success.html  
✅ Dashboard shows "Scale Tier"  
✅ API call returns entities_extracted > 0  
✅ Webhook logs show successful tier update  

**When all 5 pass → YOU'RE LAUNCH READY**

---

## After Test Passes

1. Delete test account (or leave it for future testing)
2. Take screenshot of successful Scale tier dashboard
3. Post Show HN
4. Monitor for first real customer

---

**I'll be watching logs in real-time during your test. Run it when you're back and I'll confirm everything works.**
