# MEMORY.md — Thomas Long-Term Memory

## API Hygiene Rules (NON-NEGOTIABLE — added March 23, 2026)
- **NEVER ask for or accept API keys, tokens, passwords, or any secret as plaintext chat messages.** Not Telegram, not Discord, not any messaging surface. Period.
- **Acceptable methods for secrets:** SSH onto server, JSON file attachments, one-time secret links (onetimesecret.com), or directly in the platform's UI.
- **If Justin sends a secret as plaintext:** Immediately warn him, do NOT store/repeat it, and tell him to rotate the key.
- **File attachments (JSON, etc.) ARE acceptable** — Justin confirmed this is fine and corrected Thomas for over-correcting.
- This rule exists because Thomas asked Justin to paste a PyPI token in Telegram plaintext. That was wrong. Never again.

## TODO Verification Rule (NON-NEGOTIABLE — added March 23, 2026)
- **NEVER present a TODO/action item as open without verification.**
- Before surfacing tasks to Justin: run `python3 /root/scripts/verify_todos.py` — it cross-references open TODOs against daily notes + session transcripts and flags stale items.
- Only present items from the `open` list in the output. Items in `likely_done` are stale until proven otherwise.
- Output lives at `/root/scripts/.verified_todos.json` — check it before any "what should I work on" type question.
- If you can't run the script, run memory_search manually — but the script is the primary gate.
- This is the exact failure mode 0Latency solves. Don't be your own counter-example.

## Communication Rules (NON-NEGOTIABLE)
- **NEVER ask Justin to paste API keys, secrets, tokens, or credentials into Telegram/chat.** He practices clean API key hygiene. Always provide terminal/SSH instructions to store credentials directly on the server. No exceptions. (Added March 22, 2026 — Justin called this out twice.)
- **NEVER say** "I want to be straight with you," "to be honest," "I'll be honest," "let me be real," or any variant. Justin despises this framing — it implies you might otherwise be dishonest. Just say the thing. No preamble.
- **NEVER announce your capabilities before using them.** Don't say "Let me use the Graph API" or "I have access to email." Just do the thing. Justin set up all integrations weeks ago — narrating them wastes his time and signals you don't know your own tools.
- **NEVER say you can't do something without testing first.** Default assumption: you CAN. Try it. If it actually fails after trying, then report the failure. (Added March 18, 2026 — Justin called this out directly.)
- **NEVER default to suggesting Justin stop working or "call it a night."** His default is GO. Don't build passiveness into the operating model. Only suggest stopping if there's a genuine technical reason. (Added March 18, 2026 — Justin corrected this directly.)

## Output Redundancy Rule (NON-NEGOTIABLE — added March 20, 2026)
- Say it ONCE. Don't explain something in prose and then re-list it as bullets. Don't summarize what you just showed. Pick one format and commit.
- This is the same root cause as the screenshot play-by-play: generating volume instead of being precise.

## Sub-Agent Delegation Rules (NON-NEGOTIABLE — added March 23, 2026 after 7-min outage)
- **Main session = conversation + coordination ONLY.** Execution → sub-agents.
- Mandatory delegate: >2 files, web fetches, research, code gen >50 lines, tasks >30 sec, multi-step debugging
- **Acknowledge-first:** Respond to Justin within 1 tool call. NEVER run >2 tool calls before first reply.
- Token awareness: 80k+ = aggressive delegation. 120k+ = EMERGENCY, zero inline work, write checkpoint immediately.
- Only inline: read 1-2 small files, single quick commands, sending messages, spawning agents, writing memory.
- Root cause of March 23 outage: inline work bloated tokens 120k→202k in 2 hours → compaction crash → 7 min blackout.

## Capabilities Awareness (NON-NEGOTIABLE — added March 18, 2026)
- On every session start, read the **Capabilities Manifest** in `TOOLS.md`. It lists every integration, API, and tool I have access to.
- This exists because context compaction kills capability awareness. The manifest is the fix.
- If Justin asks me to do something and I'm not sure I can: **try it first, report results.** Don't ask permission or announce the attempt.

## Identity
- I am Thomas, Chief of Staff & Consigliere. Named after Justin's deceased uncle.
- I manage Steve (CMO), Scout (Sales Ops), Sheila (Startup Smartup), and Atlas (CDO, pending).
- Justin is a full-time founder. Night job 2-3 days/week. 40-50+ hours/week on businesses. No competing priorities. The constraint isn't time — it's distribution efficiency. 300 cold calls/emails a day is possible but pointless. Every action needs to be high-leverage.

## Media Batching Rule (NON-NEGOTIABLE — added March 20, 2026, Gap Analysis #3)
When receiving 3+ media messages (images, files, screenshots) within 60 seconds:
1. Send ONE acknowledgment ("Got them, keep sending — I'll review everything together.")
2. Do NOT analyze individual images as they arrive
3. Wait for a natural pause (>30s silence) or explicit signal
4. Give ONE comprehensive, summative response connecting all media
5. If >10 items, organize by theme, not by image order
- Born from: 30-screenshot barrage on March 20 where Thomas wrote play-by-play commentary on each image, consumed 15K+ tokens, triggered compaction, lost all working context
- A human would wait for all images, digest them together, then respond once. Do that.

## Compaction Defense Rules (NON-NEGOTIABLE — added March 20, 2026, Gap Analysis #3)
- **Pre-compaction checkpoint:** When context exceeds 70%, IMMEDIATELY write checkpoint to HANDOFF.md + today's daily notes. Do this before next response.
- **Post-compaction protocol:** If context feels thin or recent conversation is missing: (1) Read HANDOFF.md, (2) Read today's daily notes, (3) Read RECALL.md, (4) THEN respond. Never respond to a message you don't have context for.
- **Long-running work:** Any task requiring >5 sequential tool calls → spawn as sub-agent. Main session stays responsive. Exception: only inline if Justin is actively directing each step.
- **File naming hierarchy:** MEMORY.md (curated, permanent) > RECALL.md (auto-generated daemon recall, was MEMORY_CONTEXT.md) > HANDOFF.md (session state). Names are intentionally distinct to avoid confusion post-compaction.

## File Ingestion Rule (NON-NEGOTIABLE)
Any file over 5KB received via Telegram MUST be:
1. Written to disk immediately (`/root/incoming/` with timestamp prefix)
2. NEVER ingested inline into the conversation context
3. Processed in chunks (max 4KB per chunk read)
4. Checkpoint between chunks (write partial results to `/root/logs/` dated file)
5. Final summary only goes into the conversation — raw content stays on disk
This prevents context blowout from large file drops.

## Main Thread Responsiveness Rule (NON-NEGOTIABLE — added March 22, 2026)
- **If a task requires more than 3 sequential tool calls and doesn't need real-time user input, SPAWN A SUB-AGENT.** Stay in the main thread. Tell Justin what you kicked off. Relay results when they land.
- The main session is a CONVERSATION THREAD, not a build pipeline. Never go silent for >2 minutes during active chat.
- Background work examples that MUST be delegated: site deployments, API restarts, file conversions, bulk edits, research tasks.
- This rule exists because on March 22, 2026, Justin was left waiting 10+ minutes during active conversation while Thomas chained 15+ tool calls for deployment work. That's unacceptable.

## Spawn Discipline Rules (NON-NEGOTIABLE — added March 13, 2026)
1. **Spawn budget rule:** Before spawning any sub-agent, estimate token cost vs doing it directly. If the task is under ~15 minutes of direct work, just do it. Don't delegate for the sake of delegating.
2. **Pre-flight checklist:** Before every spawn, verify: (a) Will the execution environment work? (b) Is the scope right-sized for the timeout? (c) Is the timeout sufficient? Do NOT spawn until all three are confirmed.
3. **Batch sizing:** Never give Reed/research agents more than 6 entities per batch. Write partial results after every 2 entities. A completed batch of 6 beats a timed-out batch of 12 every time.
4. **Re-discovery tax:** Every spawn has a startup cost (reading context, orienting). If an agent already failed on a task, diagnose WHY before respawning. Don't just retry blindly.
5. **Track spawn failures:** Log every failed spawn in the daily memory file — what was attempted, why it failed, tokens wasted. Review weekly for patterns.
6. **Polling overhead:** No agent polls more frequently than hourly unless there's an active reason. Default: hourly. Exception: only if Justin explicitly requests faster.
7. **Right tool for the job:** 3 file edits = direct edit. Research on 6 states = sub-agent. Full app build = coding agent. Match the tool to the scope.

## Responsiveness Rule (NON-NEGOTIABLE — added March 23, 2026)
- **ANY debug, fix, or investigation task estimated over 60 seconds MUST be spawned as a sub-agent.**
- The main session stays responsive to Justin at all times. No exceptions.
- Justin flagged this directly: 6 minutes of silence while debugging OAuth/Stripe was unacceptable.
- Pattern: spawn agent → confirm to Justin it's being handled → stay available for conversation.

## Non-Negotiable Operating Rules
0. **Verify Before Claiming (added March 16, 2026 — after Justin rightfully called this out):** NEVER tell Justin something is broken, unavailable, or not working based on old notes or assumptions. TEST IT FIRST. If you have credentials, make the API call. If you have a path, check the file. If you have a URL, hit it. Report what you ACTUALLY FOUND, not what you remember reading. Stale memory ≠ current state. This applies to everything — integrations, APIs, services, tools, access. No exceptions.
1. **Background Jobs Rule:** Any task estimated to take longer than 60 seconds MUST be launched as a background job using `nohup`, with output written to a dated file in `/root/logs/`. Never run long-running tasks inline. Check results on next heartbeat or incoming message.
2. **Task Queue:** On every session startup (Step 0, before bootstrap), check `/root/scripts/task_queue.json` for anything that was running or queued when the session last went dark. Update status and resume or report.
3. **Never migrate the gateway process manager while running on it.** Systemd manages the gateway. PM2 manages Mission Control. Don't touch the gateway's process manager from inside the gateway session.
4. **Heartbeat:** `/root/scripts/heartbeat.sh` runs every 30 min (7 AM - midnight Pacific). Checks gateway, task queue, Mission Control. Alerts Justin via Telegram if gateway is down.

## Architecture
- **Server:** DigitalOcean thomas-server, IP 164.90.156.169, Ubuntu 24.04
- **Previous server:** AWS, lost all data early March 2026. Rebuilt from scratch March 8, 2026.
- **Memory system:** Supabase PostgreSQL + pgvector, schema `thomas`, 12 tables
- **DB connection:** Session Pooler at aws-1-us-east-1 (no IPv6 on server, direct DB won't work)
- **REST API key:** sb_secret_Es9Slvb-intR7NKadDUoLQ_7RFbYQYf
- **Apollo API:** Header auth (X-Api-Key), use api_search endpoint (old one deprecated)
- **Telegram:** openclaw message send --channel telegram --target 8544668212
- **Scripts:** /root/scripts/ (bootstrap, pulse, stale check, checkpoint, save_*, reindex)

## Businesses
- **PFL Academy** (pflacademy.co, NOT .com) — Primary revenue focus. $16/student legacy, $20/student new. 36 states, 34 deployed.
- **Startup Smartup** (startupsmartup.com) — Three programs forming a K-18 pathway:
  - **Project Explore** (K-4, ages 5-10): Animated episode series teaching financial literacy through storytelling. 8 seasons × 12 episodes. 4 reading tiers. English + Spanish (192 scripts natively composed in Spanish, v5 methodology, 3.81/4.0 back-translation audit). Characters: Layla, Riley, Ellis, Benny + Mr. Mason. Aligned to CEE/Jump$tart, Common Core ELA, CA ELA/ELD. **Daytime instruction UI NOW BUILT** (React/TypeScript on startup-smartup-gateway, deployed GitHub Pages). Targets ELA/reading adoptions, financial literacy mandates, and dual language/bilingual funding (Title III, state DL grants). Remaining: extend PFL SSO/LMS infrastructure, ~1 day dev for "mark class complete" (Sebastian).
  - **Project Pioneer** (ages 9-12): Team-based creative project learning. **Strictly enrichment** (after-school, clubs, extracurricular — NOT daytime instruction). $5,000/site (can split $2,500/trimester but not lower than $1,600). 12 chapters per module. Four stages: Inspire → Create → Connect → Launch. NOT entrepreneurship yet — foundational skills.
  - **Project Launchpad** (ages 13-18): Real entrepreneurship and venture creation. **Strictly enrichment** (after-school, clubs, extracurricular — NOT daytime instruction). $7,500/site (can split $2,500/trimester based on ~25 students × 12 classes = $8.33/student/class). Business planning, CRM, sales, marketing, financial modeling, "Shark Tank" pitches. Financial literacy embedded throughout.
  - **Enrichment pipeline spans K-18:** Explore → Pioneer → Launchpad (all enrichment today)
  - **Daytime instruction today:** PFL Academy only. Explore daytime version is a future product.
  - Full pipeline: Explore → Pioneer → Launchpad → PFL Academy
- **Loop Marketing** — Not a separate business. Marketing philosophy across both.

## Key Facts
- ICAP/ILP via Standard 15 is the moat. No competitor has it.
- Paying customers: Dale PS ($1,600), Clinton PS ($2,400). Mustang PS tier unknown. Muldrow PS not in platform.
- Confirmed ARR: $4,000 (Dale + Clinton only)
- PFL pricing: $16/student legacy, $20/student new contracts. Floor 100 students, increments of 25.
- Justin's goal: $1M ARR, first milestone $200K-$300K
- 34 of 36 states sales-ready (only NY + OH need corrections)
- Total addressable: ~$42M+ across all 36 states at $16/student

## 36 State Priority Tiers (March 2026)
- **Tier 1 (Flagship):** Colorado ($1.1M TAM, HB25-1192, ICAP), Kentucky ($720K, HB 342, 1.0 credit, HARD STOP until curriculum rebuilt), Texas ($6.8M, HB 27, ESC channel)
- **Tier 2 (High-Priority):** California ($6.6M, AB 2927, CDE shut us down via Jeff — lead w/ Jump$tart), Oklahoma ($500K, foundation state, paying customer), Florida ($3.2M, SB 1054, active since 2023-24)
- **Tier 3 (Near-Term):** Ohio* ($2.4M, needs minor corrections), Pennsylvania ($2.0M), Virginia ($1.4M), Wisconsin ($900K), Connecticut ($600K), Michigan ($1.8M), New Jersey ($1.5M)
- **Tier 4 (Steady-State):** AL, NC, GA, LA, IN, MO, TN, MS, SC, MD, MN, DE
- **Tier 5 (Backlink/Long-Term):** OR, KS, IA, NE, NY* ($3.2M, needs major rewrite), UT, RI, WV, NH, ME, IL ($2.0M)
- Key contacts: Stephanie Hartman (CO CDE), Sharon Collins (KY KDE), Joshua Brady (CA CDE)
- Doc: /home/ubuntu/scout/36_state_priority.md
- Platform stats: 157 students, 25 teachers across all districts
- PFL uses separate Supabase: oizzivklbsfqgickluti.supabase.co (anon key only, no service role)

## PFL Academy — Deep Architecture (from Complete Product Brief, March 2026)
- **What it is:** Full-credit, standards-mapped K-12 financial literacy platform. Not supplemental. Not elective add-on.
- **Two-Day Model:** Day 1 = concept intro via COST framework (slide deck + teacher guide + skill builders). Day 2 = Learning Lab (4-5 stations, portfolio artifacts, podcast bridge EN+ES). This is the foundational architecture — not optional.
- **COST Framework:** Concept → Operationalize → Situate → Transfer. 100% implementation across all 71 slide decks.
- **Chapter System:** L-01 to L-45 (core), L-46 to L-72 (extended). L-71 (Estate Planning) and L-72 (Understanding Health Insurance) built March 11, 2026. LC-36 (combined gambling L-36+L-37), LC-39 (combined philanthropy L-39+L-40). ~26 states use combined chapters. L-41 to L-45 = ILP/Career Readiness — NEVER call "Standard 15" externally.
- **Free Resources:** 6 PDFs per chapter per state (slide deck + student workbook + teacher guide × EN + ES). 4,700+ PDFs generated. Pipeline: JSON → HTML → state variable replacement → Puppeteer PDF.
- **State Variables:** 86+ variables across 8 categories. 8 chapters need full replacement. Rest get {{STATE_NAME}} only.
- **Paid Platform Features:** Interactive teacher guide (62,975-line LTeacherGuide.ts), contextual AI assistant, live SME chat, 90+ skill builders, 3-tier IEP scaffolding (Clean/Guided/Complete, DB-backed per student per assignment), instructor dashboard, Canvas/Schoology grade passback, Clever/Infinite Campus SSO.
- **Podcast Summaries:** Each Day 2 has audio podcast bridging Day 1 → Day 2. English + Spanish.
- **AI Interviews (In Dev):** 8 chapters — job negotiation, car purchase, banking, apartment lease, roommate, landlord. Quote from Sebastian.
- **Progressive Financial Life Simulator (Future):** Isometric Sim-Town. Unique financial state per student. Decisions compound. Anti-cheat by design. Assessment alternative.
- **Research Foundation:** Backward Design (Wiggins & McTighe), PCK (Shulman), Experiential Learning (Kolb), Improvement Science (Bryk), UDL (CAST). Feb 2026 audit: 196 files analyzed, 100% COST/differentiation/facilitation.
- **Competitor moat:** Implementation architecture, not content volume. ICAP/ILP integration. No competitor has this depth of teacher support infrastructure.
- **GitHub repos:** all-chapters-english, slide-deck-templates, pfl-academy-sync-90, state-data-variables, -state--simple-data-2026, json-files-46-69
- **Docs:** /home/ubuntu/pfl-academy/product-docs/ (brief, research foundation, quantitative audit)
- **Kentucky:** 1.0 credit = 120 hours = 60 chapters. 6 Strands (not Standards). L-71 replaces L-68. Only 4 platforms nationally can deliver this.
- **Never expose:** L-XX codes in state-facing materials. Never call L-41-L-45 "Standard 15" outside Oklahoma.

## Course Configuration Rules (NON-NEGOTIABLE)
- **Every state configuration = exactly 45 chapters = 90 hours** (2 days per chapter)
- No 44. No 46. Always 45.
- **Exception: Kentucky** — full 1.0 credit mandate requires 120-hour program (60 chapters)
- This is a marketing and product constraint: "90-hour program" is the core pitch
- PFL chapters are shared between PFL-only and PFL+Econ courses — the economics chapters are what differentiate

## Reed Universal Operating Rules (NON-NEGOTIABLE — apply to ALL research tasks regardless of project)
1. **Chunk decomposition:** Before starting any task, decompose into chunks under 10 minutes each and write all chunks to `task_queue.json` first.
2. **Partial results:** Write partial results to a dated file in `/root/logs/` after every completed chunk — never hold in memory.
3. **Parallel execution:** Any task covering more than 3 entities OR estimated over 20 minutes must spawn parallel sub-sessions. Reed coordinates, sub-sessions execute.
4. **Timeout recovery:** On timeout, immediately write `partial_complete` status to `task_queue.json` with output file location.
5. **Single-thread rule:** Never start a new research task while a previous one shows "running" status.
These rules apply whether Reed is scraping state DOE directories, researching competitors, building contact lists, or anything else.

## Texas TEKS — Authoritative Standards (from TEA TAC Chapter 113C PDF, verified by dual audit March 11 2026)
- **§113.49 (Personal Financial Literacy)**: HB 2662 (2013), adopted 2016. OLDER standalone PFL elective. 16 K&S statements: (c)(1)-(c)(16). Earning/spending (4), saving/investing (3), credit/borrowing (3), insuring/protecting (4), college/postsecondary (2). No economics content.
- **§113.76 (Personal Financial Literacy & Economics / PFLE)**: SB 1063 (2021), adopted August 1, 2022. NEWER combined course fulfilling economics graduation credit. 10 K&S statements: (d)(1)-(d)(10). Includes economics fundamentals + macro (d)(1)-(d)(2) requiring L-48–L-55, L-58, L-70.
- **Both coexist** — neither phased out. Districts must still offer §113.49 as elective. Students can't earn credit for both.
- **HB 27 (2023)**: Requires ALL students to complete PFL instruction. Uses §113.49 standards framework.
- **Estate planning required by both**: §113.49(c)(14) wills/guardianship/POA/living will/medical directive. §113.76(d)(9)(K) same coverage. L-71 is load-bearing for both TX configs.
- Repo previously said 10 standards for §113.49, outreach templates said 11 — both wrong. Authoritative source is TEA Chapter 113C PDF.
- **Marketing/compliance**: cite TEKS K&S count (16 for §113.49, 10 for §113.76). **Platform**: uses pedagogical groupings (8 categories).
- TEA PDF saved: `/root/.openclaw/workspace/ch113c.pdf`
- Sebastian needs to reconcile platform display with actual TEKS structure.
- DOE backlink spec updated: 8 chapters with real state-specific data (not just L-06).

## Distribution Strategy (March 12, 2026)
- Cold email campaigns declared dead for K-12. 35% bounce rate on CO campaign. Can't reach thousands of districts via automation.
- New strategy: distributors/channel partners who already have district relationships
- PFL is ALREADY listed in Jump$tart Clearinghouse — don't recommend applying again
- BOCES in CO are NOT purchasers. Districts buy directly. Don't recommend BOCES as procurement.
- EVERFI is NOT a viable partner/comparison. Basic supplemental content vs PFL's implementation architecture. Different league.
- Key targets: Discovery Education (corporate partnership model), CEE, NGPF (complement not competitor), state cooperatives (TX ESCs, FL consortia, KY cooperatives, OH ESCs)
- Justin's margin thesis: COGS is effectively zero. Even giving distributors 30-40% cut, 10x volume beats direct sales.
- Both pflacademy.co and startupsmartup.com scored 9.5/10 on mail-tester — domains intact but NO MORE cold sending from them
- Third-party sending services: MCH Strategic Data, Agile Education Marketing worth exploring for any future outbound

## Communication Heuristics
- Be direct. No jargon. No filler.
- Never say content was sent unless visibly present in Telegram chat.
- Prefer prose over lists unless structure helps.
- No bullet point emojis. No staged scene-setting.
- **BANNED PHRASES (makes Justin physically recoil):** "Let me be straight with you," "Here's the honest assessment," "I need to be honest," "Let me be real," "Here's the thing," or any formulaic AI throat-clearing that signals "I'm about to say something important." Just say the thing. No preamble. No performative candor. If you're being honest, you don't need to announce it.
- **NEVER tell Justin to rest, take a break, call it a night, or comment on his work hours.** He's a founder. He decides when he works. My job is to execute, not babysit. If he's here, there's work to do. Do the work.
- Inter font is NOT acceptable. Use Plus Jakarta Sans / Geist Sans / Newsreader / JetBrains Mono.
- Ras Mic (@rasmic) is design north star. Cody Schneider (@codyschneiderx) is GTM north star.

## Writing Rules (ALL agents, ALL writing — locked March 11, 2026)
Source: `/home/ubuntu/pfl-academy/product-docs/writing_rules.md` (full doc). Copies in every agent dir.

**COLD EMAIL RULES (first-touch outreach):**
- Always introduce yourself — name, title, company. No stranger wants to read past line 1 without knowing who's writing.
- Never fabricate social proof — "I keep hearing from districts..." is a lie if you haven't heard it. Never claim experiences Justin hasn't had.
- Don't be chummy with strangers. Professional, direct, respectful. Not a blog post, not a conversation with a friend.
- Structure: introduce → lead with what resonates for their role → specifics → free resources → pricing → CTA
- Include phone number and domain at bottom
- The v1 structure was correct; the AI voice was wrong. Don't overcorrect structure when fixing voice.

**BANNED PATTERNS — no exceptions, any medium:**
- Staccato proclamation: "The mandate is clear. The challenge is implementation." — most recognizable AI signal
- Rhetorical question-answer: "The problem? Implementation. The solution? Infrastructure." — banned entirely
- AI formulaic openers: "The problem?", "The catch?", "It's not about X, it's about Y"
- Marketing language: "game-changer", "revolutionary", "unprecedented"
- Buffering/validation: "You're right," "Absolutely," "Great point," "That's a great question"
- Honesty qualifiers: "honest," "honestly," "to be honest," "I'll be honest"
- Empty expertise claims without specifics
- False urgency / manufactured crisis language
- Formulaic intro-problem-solution-conclusion structure

**EMBRACE:**
- Analytical depth — break down complex challenges
- Lived expertise — reference specific implementation patterns
- Systems perspective — connect individual issues to structural causes
- Evidence-based reasoning grounded in data and real-world experience
- Generous critique — identify problems while offering paths forward
- Start with specific, concrete observations that illuminate larger patterns
- Layer analysis: immediate context → structural analysis → implementation lens → forward implications

## K-4 Bilingual ELA Market Intelligence (March 2026)
- **Source:** Gemini Deep Research, March 13, 2026
- **Full reports:** `/root/.openclaw/workspace/research/gemini_k2_literacy_full_report.md` + `gemini_dual_language_competitive_analysis.md`
- **US supplemental instructional materials market:** $4.73B (2024), projected $5.11B by 2027
- **US DLI market:** $1.5B (2023), projected $14B by 2032 (25% CAGR)
- **Global DLI market:** $4.3B (2025), projected $13.9B by 2035 (12.9% CAGR)
- **5.3M English Learners** in US public schools (10.6%), 76.4% Spanish-speaking
- **Big Three states:** TX (20.2% EL), CA (18.9%), FL (~10.5%). Fastest growth in Midwest/Southeast "new destination" states.
- **Title III funding:** Flows from federal → SEAs → LEAs. Districts have 27 months to spend (Tydings Amendment). Supplements, not supplants.

### Competitor Pricing Benchmarks
- Amplify Caminos: $25-32/student/year, classroom kits $2,999-3,999
- Savvas miVisión: intervention workbooks ~$195-255
- McGraw Hill Maravillas: foundational skill enhancements ~$670/grade
- Benchmark Adelante: mid-range basal, digital bundled with print
- HMH Arriba la Lectura: basal rates, bundles include 25 sets consumables

### Competitor Architecture (Translation vs Parallel)
- **Amplify Caminos:** Parallel build, respects syllable-based Spanish phonics. No Sound Cards. Uses read-alouds + authentic literature as bridge.
- **Savvas miVisión:** Parallel, heavily print-integrated with Realize platform
- **McGraw Hill Maravillas:** Parallel, gradual release model
- **Benchmark Adelante:** Parallel, created as Spanish partner to Benchmark Advance
- **HMH Arriba la Lectura:** Parallel
- **Lexia English:** Digital supplemental only, AI-adaptive, NOT teacher-led
- **Imagine Español:** Digital supplemental, remedial focus
- **Istation Español:** Digital CAI, minimal teacher-led component

### Four Market Gaps (ALL addressable by Project Explore)
1. **"Basal Burnout"** — teachers want narrative coherence, not fragmented weekly skills
2. **Lack of technical rigor in immersion** — "socially fluent but academically behind"
3. **Bilingual teacher shortage** — programs assume fluency teachers don't have
4. **Financial literacy void in K-4** — nobody integrating FL into ELA at this level

### State Adoption Windows
- **CA:** 2026 ELA/ELD Follow-up Adoption. Program Type 3 Biliteracy. Fee: $8K/grade (small publisher reduction available <$10M revenue). SBE action Nov 2026. March 11 deadline PASSED but exploring late entry.
- **TX:** Proclamation 2027. NEW 5-level ELPS (up from 4) launching 2026-2027. HB 1605 Literary Works List requirement.
- **FL:** B.E.S.T. Standards. Social Studies adoption ITB June 1, 2026. FL encouraging K-8 financial literacy integration.

### K-2 Delivery Model (Industry Standard)
- K-2 = teacher-mediated, physical manipulatives, "We Screen" (NAEYC). No student digital interaction.
- Grade 3 = universal transition point for independent digital interaction
- Assessment: observation-based, teacher-administered during small-group time
- Spanish literacy: syllable-based (transparent orthography), NOT phoneme-based like English

### Daytime Explore Architecture (Claude, March 13 2026)
- **LEAPS Framework:** Launch → Explore → Practice → Share
- **Template:** 5 PDFs per chapter (Teacher Guide + 4 tier student packs)
- **Pilot:** S3 CH05 "The Potter's Valley" (FL level None — proves pure literacy value)
- **Phase 1:** PDFs behind a button (days, not weeks). 48 chapters × 5 PDFs × 2 languages = 480 files
- **Phase 2:** Teacher dashboard (Seb clones PFL infra, 1-2 weeks)
- **Phase 3:** Grade 3-4 student platform (later, when districts ask)
- **Full architecture doc:** `/root/.openclaw/workspace/research/` (from Claude.ai)
- **Key decisions pending:** English-first vs parallel bilingual passage generation. Decodable text strategy for FL SoR compliance. Platform: separate product vs startupsmartup.com extension.

## Oklahoma Adoption — Active Bid (March 2026)
- **Subject code:** 1451 (Personal Financial Literacy)
- **Intent to Bid:** Open March 6 - April 10, 2026. Form: https://airtable.com/appxqQsu43AsSItCZ/pagDIVRFcr1oX07TE/form
- **Process:** Intent to Bid (March) → Justification letter (April/May) → STC June vote → Materials review July
- **Submission type:** Out of Cycle
- **Publisher registration:** Complete (fully digital platform)
- **Data Privacy Attestation:** Generated, awaiting Justin's signature
- **Key contacts:** Carolynn Bristow (405-522-1904, carolynn.bristow@sde.ok.gov, Project Manager Educational Materials) — out until March 23. Brenda Chapman (405-522-3523, brenda.chapman@sde.ok.gov, PM Social Studies & PFL) — extremely responsive.
- **Shea McCrary:** OK instructor who piloted PFL, serves on RFP evaluation team. Met at CCOSA Conference summer 2025.

## CDE California — Carrie Marovich Contact
- **Full name:** Carrie Marovich, Education Programs Consultant, Standards and Curricular Guidance Unit, CFIRD
- **Direct:** cmarovich@cde.ca.gov, 916-327-1023
- **Status:** PF Curriculum Guide adopted March 11-12 by State Board. CDE does NOT review instructional materials. Jump$tart pathway is the indirect route. Asked for intro to ELA/ELD adoption team for Project Explore.
- **Key quote:** "curriculum providers are encouraged to make their presence known to school districts"

## Project Explore — Status (updated March 18, 2026)

### Spanish Transcreation — COMPLETE
- All 192 scripts across 4 seasons composed natively in Spanish using v5 methodology
- NOT translated or transadapted — original Spanish compositions anchored to Latin American literary voices
- v5 methodology: T1 = picture book warmth w/ diminutives, T2 = children's lit style, T3 = middle-grade analytical, T4 = literary precision
- Uses emotional vocabulary palettes (not cognate defaults), natural Spanish discourse markers and word order
- Back-translation audit: 3.81/4.0 on original composition scale — auditors couldn't tell which language came first
- S3-CH05 finalized March 18. All committed to git.

### Daytime Instruction UI — BUILT
- React/TypeScript app (Vite + Tailwind + Framer Motion), deployed on GitHub Pages
- Built on existing **startup-smartup-gateway** repo
- **Video Library (ExploreDashboard):** 12-chapter grid, tier switcher (T1 K-1, T2 Gr2, T3 Gr3, T4 Gr4), season selector, EN/ES toggle
- **Daytime Instruction Page:** Two-panel layout — left: thumbnail + video + 5-day lesson arc; right: 5-tab document hub
- **5-tab document hub per chapter:**
  - Teacher Materials: Full guide, Quick Reference Card, Vocabulary Word Cards (4 Launch + 1 Apply)
  - Student Packs: Activity Booklet, Read-Aloud Backup Script (K-1 oral-first/teacher-led)
  - Assessment: Observation Checklist (5 observable behaviors, no grading required)
  - Family Connection: Bilingual EN/ES letter
  - Standards: CCSS ELA, CA ELD, Jump$tart, CEE badges with standard codes
- Each doc card has Preview, Download PDF, Print actions

### Next Steps
- Extend PFL Academy infrastructure (Clever/ClassLink SSO, Canvas/Schoology grade passback) to Explore
- Only new dev: teacher-side "mark class complete" for K-2 whole-class delivery (~1 day, Sebastian)
- LMS integration is REQUIRED for district deployment — not optional (for-credit daytime program)
- Strategy: direct district sales + self-certification one-pager mapping to CA rubric. $40K state submission deferred.
- Build brief + references: `/root/.openclaw/workspace/explore-daytime/build-brief/`

## Memory Product (NEW — March 18, 2026)
- **What:** AI agent memory layer — framework-agnostic service for persistent, intelligent memory
- **Why:** NemoClaw (Nvidia, GTC March 2026) addressed security but punted on memory. Nobody solves this well.
- **Product shape:** Option B (Memory API) that can grow into C (Agent OS)
- **Status:** Phases 0-3 COMPLETE. Extraction, Storage, Recall all built and tested.
  - Extraction: Gemini Flash 2.0, 6 memory types, tiered L0/L1/L2 content
  - Storage: `memory_service` schema on Supabase, pgvector embeddings, decay, reinforcement, corrections
  - Recall: composite scoring (semantic + recency + importance + access), budget-aware tiered loading
- **Test agent "Echo":** @MemoryTestAgent_bot on Telegram. OpenClaw agent memory-test, workspace /root/.openclaw/workspace-memory-test
- **Competitors analyzed:** OpenViking (ByteDance), Mem0 (YC), Zep/Graphiti, Letta, LangChain, CrewAI
- **Our differentiation:** Proactive + budget-aware + temporally-weighted recall. Nobody does all three.
- **Unit economics:** Power user costs ~$0.93/mo, pricing $19/mo = 95% margin. Break-even: 3 users.
- **Domains possibly available:** synaptic.dev, mnemonic.dev, agentrecall.dev
- **All docs:** `/root/.openclaw/workspace/memory-product/` (ROADMAP.md, competitive-teardown.md, unit-economics.md, privacy-architecture.md, design-decisions.md)
- **Code:** `/root/.openclaw/workspace/memory-product/src/` (extraction.py, storage.py, recall.py)
- **Next:** Phase 4 — wire Echo to memory service, Justin tests it

## 0Latency Product Philosophy (Codified March 22, 2026)
- **"It just works. Zero latency. No configuration."** — Steve Jobs philosophy applied to agent memory
- API is 3 lines: `Memory(api_key)`, `.add()`, `.recall()` — no config knobs
- Three architectural rules: (1) Recall always sync/fast sub-100ms, (2) Extraction accepts instantly processes in background, (3) Partial results beat blocking
- Nobody configures latency tolerance. We decide how memory works. Developer's job is to build their agent.
- Async extraction is an architectural principle, not a feature toggle
- New endpoints: POST /memories/extract (202 Accepted + job_id), GET /memories/extract/{job_id}
- Brand name: **0Latency** (no space), statement descriptor: **0LATENCY**
- Justin dissolved Startup Smartup LLC (bankrupt). New Stripe account as sole proprietor under his name.
- Stripe email: jghiglia+0latency@gmail.com
- **Obsidian opportunity:** "Obsidian is your second brain. 0Latency is your agent's." — complementary, not competitive. Integration page planned.

## CABE 2026 Conference Research (March 18, 2026)
- Compiled district contact list for dual language outreach: `/root/.openclaw/workspace/research/cabe_2026_district_contacts.md`
- 9 co-sponsor districts identified (SFUSD, Oakland USD, Oak Grove, Palmdale, Salinas City ESD, Salinas Union HSD, Los Banos USD, John Swett USD, Santa Clara COE)
- Confirmed contacts: Olga Simms (Sacramento City USD), Bianca Barquin & Edward Bustamante (Santa Ana USD), Rachel Latta & Jennifer Brouhard (Oakland USD), Eva Kellogg (SFUSD)
- For both Project Explore (K-4 bilingual) and PFL Academy (HS financial literacy)
- Vista Higher Learning (Justin emailed Arturo Castillon) was Silver sponsor at CABE 2026
- CABE 2027 in Long Beach — plan for exhibitor/presenter presence

## Gemini Distributor Analysis (March 18, 2026)
- Justin had Gemini run report on dual language distributors
- Top recommendation: Vista Higher Learning (acquired Santillana 2018) for Project Explore
- Also: Imagine Learning, Savvas, Wayside Publishing, Everfi, Participate Learning
- Justin emailed Arturo Castillon at Vista Higher Learning re: partnerships (from SS inbox)

## 0Latency Product (Memory-as-a-Service) — Status as of March 21, 2026
- **Domain:** 0latency.ai (Cloudflare, SSL active)
- **API:** api.0latency.ai (42 endpoints, live)
- **Repo:** github.com/jghiglia2380/0Latency (private)
- **GitHub creds:** ~/.netrc on thomas-server (jghiglia2380)
- **Audit score:** 7.5/10 → fixing criticals brought it higher, re-audit pending
- **Tests:** 147 passing (86 core + 61 feature parity)
- **Chrome extension:** Built, not yet on Chrome Web Store ($5 dev account needed)
- **SDKs:** Python + TypeScript both built
- **Landing page:** Live at 0latency.ai with feature comparison vs mem0
- **Scaling:** Stateless, Docker + fly.toml ready. Current droplet handles 10 concurrent. fly.io for production auto-scaling.
- **Key files:** ARCHITECTURE.md, GAP_ANALYSIS_5.md, memory-product/
- **Next:** Seb review, Chrome Web Store publish, fly.io production deploy, pricing model (Gemini analysis pending)

## 0Latency — Product & Strategy (as of March 23, 2026)
- **Status:** Pre-launch, 92% production-ready. 47 API endpoints, 147 tests, 6,840 lines of code, 2 SDKs, 3 blog posts, Stripe billing, Google/GitHub OAuth
- **Memory count:** 624 (this IS the marketing story)
- **API:** api.0latency.ai (FastAPI, uvicorn, port 8420 behind Cloudflare)
- **Site:** 0latency.ai (static HTML on nginx, /var/www/0latency/)
- **Repo:** github.com/jghiglia2380/0Latency (private, master branch)
- **Pricing:** Free (10K/5 agents/20 RPM) → Pro $19 (100K/25/100) → Scale $89 (1M/∞/500/graph) → Enterprise custom
- **MCP server:** @0latency/mcp-server, built but NOT on npm yet. Needs publishing for Claude Desktop distribution.
- **Sebastian Lucaciu (sebbuilds):** Reviewing codebase, few days. Found OAuth + billing issues (both fixed).
- **Strategic pivot:** Claude thread memory as prosumer go-to-market. Same product, MCP delivery. TAM: 6.4M Claude power users.
- **Dual track:** Dev API (Nate/Greg/HN) + Claude prosumer (r/ClaudeAI, r/ClaudeCode, Product Hunt)
- **Competitive moat:** Temporal decay, negative recall, cross-platform portability (Anthropic won't build this), sub-100ms recall
- **Platform risk:** Anthropic Memory Beta is basic now but will improve. Window is finite. Move fast.
- **Openclaw Labs (@Openclawlabs):** YouTube educator, introduced Justin to mem0. Potential distribution partner. Reach out AFTER product polished.
- **Key insight from Gemini:** Gate on velocity (RPM) and intelligence (graph memory), not storage. "Unlimited Claude Memory" framing for prosumer.

## Loop — Expanded Role (Queued, March 24 2026)
When Loop comes online, her responsibilities include:
- **Daily channel monitoring:** Reddit (r/ClaudeAI, r/ClaudeCode, r/AI_Agents, r/LocalLLaMA), GitHub (stars/forks/issues on Mem0, Zep, Hindsight, MCP repos), X/Twitter (MCP memory, Claude memory complaints, @0latencyai), HN, Anthropic Discord MCP channels
- **PFL Academy monitoring (lighter cadence):** r/teachers, r/financialliteracy, state DOE procurement boards
- **Daily digest:** Volume, sentiment, key threads across all channels
- **Real-time alerts:** Flag posts/conversations where 0Latency should participate, with suggested responses
- **Competitive intel:** New features, pricing changes, launches from Mem0/Zep/Hindsight/others
- **Automated engagement:** Thoughtful replies where appropriate (not spam)
- Justin's directive: "Loop stays informed and alerts us to posts or conversations we should be a part of"

## Agent Status (as of March 9, 2026)
- **Thomas:** Active. Memory system certified. All 6 phases complete.
- **Steve:** Active. Both deliverables done (case study + spotlight spec). Two reference pillars loaded (Cody + Ras Mic).
- **Scout:** Active. 250 contacts staged (201 CO, 49 KY). Nothing sent. Awaiting morning review.
- **Sheila:** Active. Full spinup complete. HubSpot recon done: 6,211 contacts, 1,158 warm/SS-relevant. Reconnect list staged.
- **Atlas:** Active. CDO fully initialized. atlas schema (4 tables), 21 metric definitions, week 1 baseline captured. Sunday night snapshot + Monday briefing crons set.

## Cron Schedule (11 jobs)
- `*/5 * * * *` — Heartbeat (every 5 min)
- `*/5 * * * *` — Context monitor (token usage watchdog, warns 150k, kills 175k)
- `0 13 * * *` — Daily session reset (6 AM Pacific)
- `0 15 * * *` — Thomas pulse (8 AM Pacific)
- `0 */6 * * *` — Thomas stale check
- `0 2 * * 0` — Embedding reindex (Sunday 2 AM UTC)
- `30 14 * * *` — Morning report (7:30 AM Pacific, sentinel-guarded)
- `0 6 * * 1` — Atlas Sunday night snapshot capture (11 PM Pacific Sunday)
- `15 15 * * 1` — Atlas Monday briefing (8:15 AM Pacific)
- `30 14 * * 1-5` — CO outreach scheduler (8:30 AM Mountain)

## Schemas
- `thomas` — 12 tables, Thomas memory system
- `atlas` — 4 tables (weekly_snapshots, metric_definitions, events, agent_performance), 5 RPC functions

## HubSpot Discovery
- 6,211 total contacts (Startup Smartup era, 2020-2021)
- 32 deals: $74K closed-won historical, $231K stale pipeline
- PFL Academy revenue NOT in HubSpot — needs separate tracking
- 228 existing customers, 206 SQLs, 1,158 warm/SS-relevant for Sheila

## ZeroBounce Protocol (NON-NEGOTIABLE — added after wasting 541 credits March 12, 2026)
- **Master registry:** `/root/.openclaw/workspace/research/zerobounce-master-registry.json` — 1,677 unique emails verified
- **Before ANY ZeroBounce job:** Cross-reference against master registry. Skip already-verified emails. Report exact NEW credit cost to Justin and get explicit approval before running.
- **After every run:** Update master registry with new results.
- **Credits remaining:** ~4,721 (as of March 12, 2026)
- **This is real money.** No duplicate verifications. No exceptions.

## Key People — Moheb
- **Moheb** — Egyptian artist/designer. Does ALL artwork for Project Explore (Startup Smartup). Character art, episode illustrations. Justin trusts his creative work. Potential for 0Latency logo design.
