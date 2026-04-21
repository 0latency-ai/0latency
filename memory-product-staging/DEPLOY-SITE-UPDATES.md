# Deploy Site Updates — Quick Guide

## What Changed

**File:** `/root/.openclaw/workspace/memory-product/site/index.html`

**Changes:**
1. "Get API Key" button: `https://api.0latency.ai/docs` → `https://0latency.ai/dashboard`
2. GitHub links: `github.com/jghiglia2380/0Latency` → `github.com/jghiglia2380`
3. MCP server link: GitHub repo → npm package URL

**Why:** Fixed 404 errors people were hitting when trying to download/sign up.

---

## How to Deploy

### If site is on Cloudflare Pages:

1. **Find the git repo** (wherever you push site changes from)
   
2. **Copy updated files from server:**
   ```bash
   scp root@164.90.156.169:/root/.openclaw/workspace/memory-product/site/index.html ~/your-repo/
   ```

3. **Commit + push:**
   ```bash
   git add index.html
   git commit -m "Fix: Update Get API Key button to point to dashboard, remove 404 GitHub links"
   git push origin main
   ```

4. **Cloudflare Pages auto-deploys** (usually takes 1-2 minutes)

5. **Verify:** Visit https://0latency.ai and click "Get API Key" → should go to dashboard

---

### If site is deployed manually:

1. **Copy all updated HTML files:**
   ```bash
   scp -r root@164.90.156.169:/root/.openclaw/workspace/memory-product/site/*.html ~/deploy-folder/
   ```

2. **Upload to host** (however you normally deploy)

3. **Verify:** Check the live site

---

### If site is on GitHub Pages:

1. **Find the repo** (probably something like `jghiglia2380.github.io` or `0latency-ai/0latency.github.io`)

2. **Copy updated files:**
   ```bash
   scp root@164.90.156.169:/root/.openclaw/workspace/memory-product/site/*.html ~/github-pages-repo/
   ```

3. **Commit + push:**
   ```bash
   git add .
   git commit -m "Fix: Site navigation and signup links"
   git push origin main
   ```

4. **Wait ~30 seconds** for GitHub Pages to rebuild

5. **Verify:** https://0latency.ai

---

## Quick Test After Deploy

1. Go to https://0latency.ai
2. Click "Get API Key" → should land on `/dashboard.html`
3. Click "Star on GitHub" → should go to `github.com/jghiglia2380` (not 404)
4. Scroll down to MCP install → should show npm command (not broken GitHub link)

All three should work without 404 errors.

---

## Files Updated on Server (all ready to deploy)

```
/root/.openclaw/workspace/memory-product/site/
├── index.html (main landing page - PRIORITY)
├── index-dark.html (theme variant)
├── index-light.html (theme variant)
├── pricing.html (updated feature lists)
├── case-study-thomas.html (github link fixed)
├── blog/*.html (github links fixed)
└── integrations/*.html (github links fixed)
```

**Priority:** Deploy `index.html` first — that's what most people will hit.

---

## Rollback (if something breaks)

**Cloudflare Pages:** Go to dashboard → Deployments → click "Rollback" on previous deployment

**Manual/GitHub Pages:** Revert the git commit:
```bash
git revert HEAD
git push origin main
```

---

**Estimated time:** 5 minutes

**Risk level:** Low (cosmetic fixes only, no functionality changes)

**Impact:** Fixes user signup flow + removes embarrassing 404s
