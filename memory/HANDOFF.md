# HANDOFF.md — Live State for Session Continuity
**Last updated:** 2026-03-23 02:22 UTC

## Active Right Now
- Sub-agent building: TypeScript SDK, CORS headers, rate limiting, DB backups, API monitoring
- Claude Code (Justin's machine): working on one-pager consolidation
- Justin: at Waterbar (bartending shift), available via Telegram on phone
- Channel scanner: cron'd for 9AM + 6PM Pacific (11 YouTube channels)
- Master TODO: /root/.openclaw/workspace/memory-product/TODO.md

## What We're Building: 0Latency (0latency.ai)
Memory layer API for AI agents. "It just works. Zero latency. No configuration."
- API: 3 lines — Memory(api_key), .add(), .recall()
- Pricing: Free / Pro $19 / Scale $99 / Enterprise
- Main competitor: Mem0 ($249 for what we give at $99)
- Pitch: "We built what Mem0 should have built, at half the price."

## Current State
- **Site live** at 0latency.ai — LIGHT THEME
- **API live** at api.0latency.ai — healthy, 624 memories
- **Stripe billing** — fully wired (pk_live + sk_live + whsec in .bashrc)
- **GitHub OAuth** — working
- **Google OAuth** — NOT done (blocked on Justin: needs Web credential in GCP)
- **Python SDK** — built, tested, PyPI-ready. Needs Justin to create PyPI account.
- **TypeScript SDK** — being built right now by sub-agent
- **Dashboard** — built at site/dashboard.html
- **Channel scanner** — built, cron'd, 11 channels, all IDs resolved
- **Logo** — placeholder. Moheb designing real one.

## Blocked on Justin (when back at desk, ~20 min total)
1. PyPI account + token → ~/.pypirc
2. Google OAuth web credential → .bashrc
3. www CNAME in Cloudflare
4. Cloudflare email routing (hello@0latency.ai)
5. Create @0latency on Twitter/X
6. Create 0Latency Discord server

## Key Decisions
- Light theme is default
- One-pager direction (fold pricing + FAQ into homepage)
- Orange #f97316 accent, no config knobs philosophy
- Ras Mic's Shadcn stack for future Steve redesign
- Logo: Moheb (Egyptian artist, Project Explore)
- Brand: 0Latency (no space), 0LATENCY on statements

## Architecture
- Server: 164.90.156.169 (DigitalOcean)
- Site source: /root/.openclaw/workspace/memory-product/site/
- Deployed: /var/www/0latency/
- API: port 8420, uvicorn, behind nginx
- GitHub: github.com/jghiglia2380/0Latency (master)
- Stripe: prod_UCIoPEsjrxIGI5 (Pro), prod_UCJ7s3gpULhV9O (Scale)

## Critical Rules
- Sub-agents for >3 tool calls. Main thread stays responsive.
- NEVER "to be honest" / "let me be real"
- NEVER announce capabilities before using them
- NEVER paste API keys in Telegram — SSH instructions only
- NEVER suggest Justin stop working
