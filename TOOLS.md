# TOOLS.md - Local Notes & Capabilities Manifest

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## ⚡ CAPABILITIES MANIFEST (READ ON EVERY SESSION START — NON-NEGOTIABLE)

**Rule: NEVER tell Justin you can't do something without TESTING FIRST. NEVER narrate that you're about to use a capability. Just use it.**

### What I Can Do — Direct Access

| Capability | How | Notes |
|---|---|---|
| **Read/send email** | Microsoft Graph API (OAuth2 client credentials) | PFL Academy + Startup Smartup mailboxes. Search, read full bodies, send. |
| **Search the web** | `web_fetch` (DuckDuckGo HTML, direct URLs) | Brave API key not configured — use DDG or direct URL fetch. |
| **Read/write/edit files** | Direct filesystem access | Full server access. `/root/` and all subdirs. |
| **Run any shell command** | `exec` tool | Root access. Python3, Node, curl, git, pdftotext, ffmpeg, etc. |
| **Send Telegram messages** | `message` tool, channel=telegram | Target: 8544668212 (Justin). Can send media, polls, buttons. |
| **Query databases** | Supabase REST API + psql | Thomas schema (memory), Atlas schema (metrics). See creds below. |
| **Spawn sub-agents** | `sessions_spawn` | Research, coding, parallel tasks. Respect spawn discipline rules. |
| **Manage cron/scheduled tasks** | System crontab | 11 active cron jobs. Can add/edit/remove. |
| **Analyze PDFs** | `pdftotext` CLI (most reliable) or `pdf` tool | Download first, then extract. |
| **Analyze images** | `image` tool | Screenshots, documents, photos. |
| **YouTube transcripts** | Supadata API | Always use this first, not yt-dlp. |
| **TTS / voice** | `tts` tool | For storytelling, summaries. |
| **Browser automation** | `browser` tool | Screenshots, navigation, form filling. |
| **HubSpot** | API access | 6,211 contacts, deals, pipeline data. |
| **Apollo** | API (X-Api-Key header) | Contact/company search. api_search endpoint. |
| **ZeroBounce** | Email verification API | ~4,721 credits. Check master registry before any run. |

### Email Accounts (Graph API)

| Mailbox | Tenant | Use |
|---|---|---|
| justin@pflacademy.co | PFL | Primary business email |
| info@pflacademy.co | PFL | General inquiries |
| justin@startupsmartup.com | SS | Startup Smartup |
| contact@startupsmartup.com | SS | SS general |

### Behavioral Rules for Capabilities
1. **If Justin asks you to check/do something → just do it.** Don't say "let me check if I have access" — you do.
2. **Never announce the tool you're about to use.** Wrong: "Let me use the Graph API to..." Right: just pull the emails and report.
3. **If something fails, troubleshoot silently.** Only tell Justin if you genuinely can't resolve it after trying.
4. **Default assumption: you CAN do it.** Only say you can't after you've actually tried and failed.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

### Gmail (jghiglia@gmail.com)
- **Status: BROKEN** — refresh token expired/revoked as of March 20, 2026
- **OAuth credentials exist** in /root/.bashrc (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN)
- **Needs:** Justin to re-authorize OAuth flow to generate fresh refresh token
- **Impact:** Can't read personal Gmail, can't access forwarded emails (e.g., Waterbar schedule from David Hanna)

### Denis (Curriculum/Content)
- Confirmed Kentucky curriculum built (60 chapters, 120 hours, 1.0 credit)
- Confirmed Texas updated for both pathways: §113.49 (PFL) and §113.76 (PFLE)
- Need to document role/contact info

### Supabase (Thomas Memory System)

- **Schema:** `thomas` (not public)
- **REST API:** Use RPC functions prefixed `thomas_*` via Supabase REST
- **Direct DB (psql):** `postgresql://postgres.fuojxlabvhtmysbsixdn:[pw]@aws-1-us-east-1.pooler.supabase.com:5432/postgres` (Session Pooler, IPv4)
- **Direct DB does NOT work** via `db.*.supabase.co` — IPv6 only, server has no IPv6
- **pgvector** lives in `extensions` schema, not `public`
- **Env vars** in `/root/.bashrc` (not auto-loaded in non-interactive shells — hardcode fallbacks in scripts)

### RPC Functions (public schema, query thomas schema)

- `thomas_get_agents()` — all agents
- `thomas_get_p0_facts()` — P0 memory records
- `thomas_get_latest_checkpoint()` — most recent checkpoint
- `thomas_get_open_blockers()` — open/in-progress blockers
- `thomas_get_active_tasks()` — pending/in-progress tasks
- `thomas_query(table, filter, limit)` — generic thomas.* query
- `thomas_log_event(...)` — append to event_log
- `thomas_save_memory(...)` — upsert agent_memory
- `thomas_save_decision(...)` — insert decision
- `thomas_save_blocker(...)` — insert blocker
- `thomas_save_task(...)` — insert task
- `thomas_create_checkpoint(...)` — create checkpoint

### Supadata (YouTube Transcript API)
- **API:** `https://api.supadata.ai/v1/youtube/transcript?url=<YOUTUBE_URL>&text=true`
- **Header:** `x-api-key: $SUPADATA_API_KEY`
- **Key:** `sd_0cd8dcc58cc1f4b60c6e42e4385e895d`
- **USE THIS FIRST for any YouTube video analysis.** Do NOT try yt-dlp, Invidious, web scraping, or any other method. Supadata exists for exactly this purpose.

### Claude Code Constraints (thomas-server)
- **Server runs as root.** `claude --permission-mode bypassPermissions` WILL NOT WORK as root. Don't try it.
- For coding tasks on this server: either edit files directly (preferred for <10 file changes) or find a non-root execution path.
- Don't burn tokens on spawn attempts that will fail due to known environment constraints.

### Scripts

- `/root/scripts/bootstrap_thomas.sh` — Resume validation gate (run on session start)
- Logs to `/var/log/thomas_bootstrap.log`
- State file: `/root/scripts/.thomas_resume_state.json`

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
