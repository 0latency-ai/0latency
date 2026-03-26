# Launch Checklist — 0Latency

**When you get home, run through this list. ~35 minutes total.**

---

## Step 1: Publish MCP 0.1.4 to npm (5 min)

**On your Mac:**

```bash
# Copy the built package from server
scp -r root@164.90.156.169:/root/.openclaw/workspace/memory-product/mcp-server ~/0latency-mcp-temp

cd ~/0latency-mcp-temp

# Verify version is 0.1.4
cat package.json | grep version

# Login to npm (if not already)
npm login
# Username: jghiglia
# Email: your-email@example.com

# Publish
npm publish --access public

# Verify it's live
npm view @0latency/mcp-server version
# Should show: 0.1.4

# Clean up
cd ~ && rm -rf ~/0latency-mcp-temp
```

**Expected output:**
```
+ @0latency/mcp-server@0.1.4
```

---

## Step 2: Deploy Site Updates (5 min)

**Find your site deployment repo** (Cloudflare Pages source):

```bash
# Copy updated files from server
scp root@164.90.156.169:/root/.openclaw/workspace/memory-product/site/index.html ~/your-site-repo/
scp root@164.90.156.169:/root/.openclaw/workspace/memory-product/site/pricing.html ~/your-site-repo/

cd ~/your-site-repo/

# Verify changes
git diff index.html
# Should show: "Get API Key" button changed from /docs to /dashboard

git diff pricing.html
# Should show: Scale tier features updated

# Commit and push
git add index.html pricing.html
git commit -m "Fix: Update Get API Key button, add Scale tier features to pricing"
git push origin main
```

**Cloudflare Pages will auto-deploy** (usually 1-2 minutes)

**Verify deployment:**
1. Go to https://0latency.ai
2. Click "Get API Key" → should go to `/dashboard` (not `/docs`)
3. Go to https://0latency.ai/pricing
4. Check Scale tier lists: graph, sentiment, confidence, versioning, entities

---

## Step 3: Test MCP 0.1.4 in Claude Desktop (10 min)

**Clear npx cache:**
```bash
rm -rf ~/.npm/_npx
```

**Update Claude Desktop config:**
```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Ensure it looks like this:**
```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server@0.1.4"],
      "env": {
        "ZERO_LATENCY_API_KEY": "zl_live_synwdojae2ois01oi01mmzdqh791hfek"
      }
    }
  }
}
```

**Restart Claude Desktop** (fully quit, not just close window)

**Test in Claude Desktop:**

1. Open Claude Desktop
2. Start a new conversation
3. Type: "Use the 0latency remember tool to store that my favorite color is blue"
4. Claude should call the `remember` tool → Success message
5. Type: "What's my favorite color?"
6. Claude should call `memory_search` or `memory_recall` → "Blue"

**Test graph tools (Scale tier):**

7. Type: "Use the memory_graph_traverse tool to explore related memories"
8. Claude should call the tool → Returns graph data (or empty if no relationships yet)

**If any errors:** Check `~/.claude/logs/mcp*.log` for details

---

## Step 4: Final Smoke Test (5 min)

**API endpoints:**

```bash
# 1. Core memory works
curl -X POST https://api.0latency.ai/extract \
  -H "X-API-Key: zl_live_synwdojae2ois01oi01mmzdqh791hfek" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"final-test","human_message":"I prefer Vim over Emacs","agent_message":"Noted"}'

# Should return: {"memories_stored":1,"memory_ids":["..."]}

# 2. Graph endpoint works
curl "https://api.0latency.ai/memories/entities?agent_id=final-test&limit=10" \
  -H "X-API-Key: zl_live_synwdojae2ois01oi01mmzdqh791hfek"

# Should return: {"agent_id":"final-test","entities":[...],"total":...}

# 3. Dashboard works
# Open https://0latency.ai/dashboard in browser
# Should show your API key and usage stats
```

**If everything passes:** You're ready to launch.

---

## Step 5: Review Launch Posts (10 min)

**Reddit post:**
```bash
cat /root/.openclaw/workspace/memory-product/launch/reddit-claude-code-post.md
```

**X/Twitter thread:**
```bash
cat /root/.openclaw/workspace/memory-product/launch/x-launch-thread.md
```

**Hacker News post:**
```bash
cat /root/.openclaw/workspace/memory-product/launch/hackernews-show-hn.md
```

**Edits needed?** Tell Thomas, I'll update them.

---

## Step 6: Launch Sequence (when ready)

**Option A: Soft launch (test the waters)**
1. Post to r/ClaudeCode first
2. Monitor response for 2-4 hours
3. Fix any issues that come up
4. Then post to X and HN

**Option B: Full launch (all at once)**
1. Post to r/ClaudeCode
2. Post X/Twitter thread
3. Submit to Hacker News (Show HN)
4. Send outreach to Palmer (ZeroClick)
5. Send outreach to Nate (YouTube)
6. Send outreach to Greg Isenberg

**Recommendation:** Option A (soft launch via Reddit first)

---

## Step 7: Outreach (after launch stable)

**Palmer (ZeroClick):**
- Draft ready in conversation history (March 25, 4:43 AM UTC)
- Platform: LinkedIn or email (if you have it)

**Nate (YouTube):**
- Draft angles prepared in `/root/.openclaw/workspace/memory/2026-03-25.md`
- Platform: X DM, YouTube comment, or email

**Greg Isenberg:**
- Outreach drafted in MEMORY.md (March 24 notes)
- Platform: X DM or YouTube comment on Firecrawl video

---

## Rollback Plan (if something breaks)

**MCP issues:**
```bash
# Tell users to install 0.1.3
npx @0latency/mcp-server@0.1.3
```

**API issues:**
```bash
# Revert migration on server
ssh root@164.90.156.169
cd /root/.openclaw/workspace/memory-product
psql [connection-string] < migrations/rollback_007.sql
```

**Site issues:**
```bash
# Cloudflare Pages → Deployments → Rollback to previous
```

---

## Success Metrics (First 24 Hours)

**Traffic:**
- [ ] 100+ API signups
- [ ] 10+ Scale tier upgrades
- [ ] 50+ MCP installs (npm downloads)

**Engagement:**
- [ ] Reddit post >50 upvotes
- [ ] HN front page (if submitted)
- [ ] 5+ GitHub stars (when repos go live)

**Revenue:**
- [ ] First paid customer (Pro or Scale)

**Outreach:**
- [ ] Response from Palmer, Nate, or Greg

---

## Post-Launch Tasks (Day 2+)

- [ ] Monitor error logs for issues
- [ ] Respond to comments/questions on Reddit/HN
- [ ] Set up Discord community
- [ ] Create GitHub repos (push code)
- [ ] Record demo video
- [ ] Load test under real traffic
- [ ] Iterate based on feedback

---

## Current Status

**Ready to ship:**
- ✅ API features tested and working
- ✅ MCP 0.1.4 built
- ✅ Site updates ready
- ✅ Launch posts drafted
- ✅ Documentation complete

**Waiting on you:**
- [ ] npm publish (Step 1)
- [ ] Site deploy (Step 2)
- [ ] MCP test in Claude Desktop (Step 3)
- [ ] Final smoke test (Step 4)
- [ ] Launch approval (Step 5-6)

**Time estimate:** 35 minutes from start to launch-ready

---

**You're 35 minutes away from launching a production-ready memory API. Let's go.**
