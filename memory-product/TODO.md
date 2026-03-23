# 0Latency Master TODO
**Last updated:** 2026-03-23 02:20 UTC

## 🔴 BLOCKING OUTREACH (do before Greg/Nate DM)

### Justin Must Do
- [ ] Create PyPI account (pypi.org/account/register) → generate API token → SSH add to ~/.pypirc
- [ ] Create Google OAuth "Web application" credential (GCP project: celtic-beacon-491018-m1, redirect: https://api.0latency.ai/auth/google/callback) → SSH add to .bashrc
- [ ] Add `www` CNAME in Cloudflare (www.0latency.ai → 0latency.ai)
- [ ] Set up Cloudflare email routing (hello@0latency.ai → jghiglia@gmail.com)
- [ ] Create 0Latency Twitter/X account

### Thomas Can Do Now
- [ ] Publish SDK to PyPI (once Justin creates account + token)
- [ ] One-pager consolidation (fold pricing + FAQ into homepage, strip nav)
- [ ] TypeScript SDK (Mem0 has one, we need one)
- [ ] Wire 0Latency into channel scanner (dogfood demo)
- [ ] Build /examples folder with 3+ real-world integration examples ✅ DONE
- [ ] Add CORS headers to API (frontend JS needs this)
- [ ] Add rate limiting enforcement on API (free tier abuse prevention)
- [ ] Add email verification on signup flow
- [ ] Add API error tracking (Sentry or simple log alerting)
- [ ] Automated database backups (pg_dump cron)
- [ ] API monitoring/alerting (beyond heartbeat script)
- [ ] OpenAPI spec downloadable from site
- [ ] Create 0Latency Discord server (even if empty — credibility signal)

### Claude Code Can Do
- [ ] One-pager consolidation (prompt ready — give to Claude Code)
- [ ] Full docs site (beyond Swagger — quickstart tutorial, auth guide, concepts explainer)
- [ ] Playground page (interactive web UI to test memory.add/recall in browser)
- [ ] Multi-level memory types (user/session/agent/org buckets like Mem0)
- [ ] Chrome extension for memory capture
- [ ] Audit logs on API operations

## 🟡 IMPORTANT BUT NOT BLOCKING

### Can Do This Week
- [ ] Load test the API (find the breaking point)
- [ ] Blog post #2: "How We Built a Memory Layer That Costs $0.93/User/Month"
- [ ] Blog post #3: "Mem0 vs 0Latency: An Honest Comparison"
- [ ] Startup program (3 months free Scale for companies <$5M — match Mem0)
- [ ] API versioning headers
- [ ] Status page (simple uptime monitor)
- [ ] API changelog page
- [ ] GitHub repo README: add badges (PyPI version, downloads, license)
- [ ] Steve site redesign with Ras Mic's Shadcn stack (Plus Jakarta Sans, Geist Sans, Newsreader, JetBrains Mono)

### Need Justin's Input
- [ ] Logo from Moheb → deploy as favicon + site assets
- [ ] Review light theme one-pager when ready
- [ ] Record 3-min Loom demo of Thomas using 0Latency
- [ ] Draft Greg Eisenberg DM
- [ ] Draft Nate B Jones community post / DM
- [ ] Decide: separate GitHub org (github.com/0latency) or keep under jghiglia2380?

## 🟢 NICE TO HAVE (Phase B+)

- [ ] SOC 2 compliance (expensive, months-long — roadmap item)
- [ ] HIPAA compliance (only if healthcare customers appear)
- [ ] Published benchmark (need real data first)
- [ ] Multiple vector backend options (Qdrant, Pinecone — currently PostgreSQL only)
- [ ] Self-host option (open-source core)
- [ ] Startup hunt / Product Hunt launch
- [ ] Conference presence

## ✅ DONE TODAY (March 22-23)
- [x] Site live with light theme across all pages
- [x] Stripe billing (Free / Pro $19 / Scale $99 / Enterprise)
- [x] GitHub OAuth working
- [x] Auth system (8 routes)
- [x] Dashboard page built
- [x] Pricing page with competitor comparison
- [x] Python SDK built + tested
- [x] 3 example scripts
- [x] Blog post
- [x] 5 integration pages
- [x] SEO (meta, OG, JSON-LD, sitemap, robots.txt, llms.txt)
- [x] Privacy policy + Terms of service
- [x] Scroll animations, hamburger nav, copy buttons, footer
- [x] Audit reports (function + form)
- [x] Channel scanner built + cron'd (11 YouTube channels)
- [x] "It just works" philosophy across all copy
- [x] Async extraction endpoint (202 + job_id)
- [x] HANDOFF.md symlinked for auto-injection (compaction fix)
- [x] Logo brief sent to Moheb
- [x] All audit fixes deployed
