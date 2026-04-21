# 0Latency Memory GPT - Publishing Guide

Complete step-by-step instructions for publishing to the GPT Store.

## Prerequisites

✅ OpenAI ChatGPT Plus or Enterprise account  
✅ Access to GPT Builder (available to Plus subscribers)  
✅ Logo image ready (512x512 or 1024x1024 PNG/SVG)  
✅ 0Latency API key for testing

## Step 1: Access GPT Builder

1. Go to https://chat.openai.com
2. Click your profile icon (bottom left)
3. Select **"My GPTs"**
4. Click **"Create a GPT"** (top right)

## Step 2: Configure Basic Settings

In the **Configure** tab:

### Name
```
0Latency Memory
```

### Description
```
Long-term memory for AI agents. Store and recall memories across conversations using the 0Latency API.
```

### Instructions
Copy and paste the entire contents of `gpt-instructions.md` into the Instructions field.

**File location:** `/root/.openclaw/workspace/memory-product/gpt-store/gpt-instructions.md`

### Conversation Starters
Add these four starters (from `conversation-starters.txt`):

1. `Store this memory: I prefer working with Python and FastAPI for backend development`
2. `Recall everything about my programming preferences`
3. `Search my memories for "Python"`
4. `Show me my recent memories from the past week`

### Logo/Profile Picture
Upload your 0Latency logo:
- Click the profile image placeholder
- Upload PNG or SVG (1024x1024 recommended)
- Ensure it's clear and recognizable at small sizes

## Step 3: Configure Actions

1. Scroll down to **"Actions"** section
2. Click **"Create new action"**
3. Click **"Import from URL"** or **"Import from file"**

### Option A: Import from URL (Recommended)
If you've hosted `actions-schema.json` at a public URL:
```
https://yourdomain.com/gpt-store/actions-schema.json
```

### Option B: Import from file
1. Click **"Import from file"**
2. Upload: `/root/.openclaw/workspace/memory-product/gpt-store/actions-schema.json`

### Configure Authentication

After importing the schema:

1. Scroll to **"Authentication"** section
2. Select **"API Key"**
3. Configure:
   - **Auth Type:** `API Key`
   - **API Key:** `Custom Header`
   - **Custom Header Name:** `X-API-Key`
4. Click **"Save"**

**Note:** Users will need to provide their own API key when they install the GPT. They get this from https://0latency.ai/dashboard.

## Step 4: Test Your GPT

Before publishing, test thoroughly:

### Get a Test API Key
1. Go to https://0latency.ai
2. Sign up or log in
3. Navigate to Dashboard
4. Copy your API key

### Add API Key to Your GPT
1. In GPT Builder, find the **"Actions"** section
2. Look for **"Privacy & Authentication"**
3. Click **"Add API Key"**
4. Paste your 0latency API key
5. Click **"Save"**

### Run Test Conversations

Test each core function:

**Test 1: Store a memory**
```
Store this memory: I prefer TypeScript for frontend work
```
Expected: GPT should call `/memories/extract` and confirm storage.

**Test 2: Recall memories**
```
What programming languages do I prefer?
```
Expected: GPT should call `/recall` and return the stored preference.

**Test 3: Search**
```
Search my memories for "TypeScript"
```
Expected: GPT should call `/memories/search?q=TypeScript` and show results.

**Test 4: List memories**
```
Show me all my stored memories
```
Expected: GPT should call `/memories?agent_id=...` and display the list.

**Test 5: Health check**
```
Is the API working?
```
Expected: GPT should call `/health` and report status.

### Verify API Calls

In the GPT Builder:
1. Open the **"Preview"** panel (right side)
2. Check the **"Actions"** log at the bottom
3. Confirm API calls are successful (200/202 responses)
4. Verify authentication headers are sent correctly

## Step 5: Add Knowledge Files (Optional)

You can upload additional reference documents:

1. In the **Configure** tab, scroll to **"Knowledge"**
2. Click **"Upload files"**
3. Upload these files from `/root/.openclaw/workspace/memory-product/gpt-store/`:
   - `quick-start.md` (if created)
   - `api-examples.md` (if created)
   - `use-cases.md` (if created)

**Note:** Max 20 files, 512MB total. Not required but helpful for context.

## Step 6: Set Capabilities

In the **Configure** tab:

- ✅ **Web Browsing:** OFF (not needed, we use Actions)
- ✅ **DALL·E Image Generation:** OFF
- ✅ **Code Interpreter:** OFF (unless you want users to analyze exports)

## Step 7: Publish

### Save as Draft
1. Click **"Save"** (top right)
2. Your GPT is now saved privately

### Submit for Review (Public Publishing)

**If publishing publicly to GPT Store:**

1. Click **"Publish"** (top right)
2. Select **"Everyone"** (public) or **"Anyone with a link"** (unlisted)
3. Review OpenAI's content policy
4. Click **"Confirm"**

**Publishing options:**
- **Only me:** Private, for testing
- **Anyone with a link:** Unlisted, shareable URL
- **Everyone:** Public in GPT Store (requires review)

### OpenAI Review Process
- Public GPTs go through content review (usually 1-3 business days)
- You'll receive email notification when approved
- Common rejection reasons: unclear instructions, broken Actions, policy violations

## Step 8: Post-Publishing

### Monitor Usage
1. Go to **"My GPTs"**
2. Click on **"0Latency Memory"**
3. View analytics (if published publicly)

### Update Your GPT
1. Click **"Edit GPT"**
2. Make changes (instructions, actions, etc.)
3. Click **"Update"** (no re-review needed for minor updates)

### Share Your GPT

**If unlisted or public:**
```
https://chat.openai.com/g/g-[YOUR-GPT-ID]
```

Share this link on:
- 0latency.ai website
- Documentation
- Social media (Twitter, LinkedIn)
- Developer communities

## Troubleshooting

### Common Issues

**Issue:** Actions not working  
**Fix:** 
- Verify API key is set correctly
- Check schema has correct `servers` URL
- Test endpoints directly with curl
- Check OpenAI logs for error messages

**Issue:** Authentication failing  
**Fix:**
- Ensure `X-API-Key` header is configured
- Verify API key is valid (test at https://0latency.ai/health)
- Check key hasn't been regenerated

**Issue:** GPT not calling actions  
**Fix:**
- Instructions should explicitly mention using the actions
- Use conversation starters that require API calls
- Verify schema operation IDs match instructions

**Issue:** Publishing rejected  
**Fix:**
- Review OpenAI content policy
- Ensure instructions don't violate policies
- Check that Actions don't access prohibited content
- Make description clear and accurate

### Testing Checklist

Before publishing, verify:

- [ ] All 4 conversation starters work
- [ ] Extract endpoint stores memories (202 response)
- [ ] Recall endpoint retrieves relevant memories
- [ ] Search works with keywords
- [ ] List memories returns results
- [ ] Delete memory works (if tested)
- [ ] Health check returns success
- [ ] Error messages are clear and helpful
- [ ] Instructions are accurate
- [ ] Logo displays correctly
- [ ] Description is compelling

## Maintenance

### Regular Updates

**Monthly:**
- Review user feedback
- Update instructions based on common questions
- Test all Actions still work
- Check for API changes

**As Needed:**
- Update schema if API adds endpoints
- Improve instructions based on user confusion
- Add new conversation starters
- Update knowledge files

### Version Control

Keep track of changes:
```bash
# In your workspace
cd /root/.openclaw/workspace/memory-product/gpt-store/
git init
git add .
git commit -m "Initial GPT Store configuration"
git tag v1.0.0
```

## Support Resources

- **0Latency Docs:** https://0latency.ai/docs
- **API Reference:** https://0latency.ai/api-docs.json
- **OpenAI GPT Builder:** https://platform.openai.com/docs/guides/gpts
- **GPT Actions Guide:** https://platform.openai.com/docs/actions

## Success Metrics

Track these after launch:

- Number of installs/uses
- API key activations (from 0latency.ai dashboard)
- User feedback in GPT reviews
- Support requests related to GPT
- API usage patterns from GPT users

---

## Quick Reference Commands

### Test API Key
```bash
curl -H "X-API-Key: YOUR_KEY" https://0latency.ai/health
```

### Export Current GPT Config
OpenAI doesn't provide export, but you can:
1. Copy instructions to `gpt-instructions.md`
2. Download action schema from Actions editor
3. Screenshot conversation starters

### Update Actions Schema
1. Edit `actions-schema.json` locally
2. In GPT Builder → Actions → Edit
3. Re-import updated schema
4. Test all endpoints
5. Click "Update"

---

**Ready to publish?** Follow the steps above in order. Test thoroughly before going public. Good luck! 🚀
