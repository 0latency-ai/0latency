# MEMORY_REFERENCE.md — Business & Product Reference Data
# This file is NOT loaded on session startup. Read on demand when needed.
# Moved from MEMORY.md on April 3, 2026 to reduce bootstrap token cost.

## PFL Academy — Deep Architecture (from Complete Product Brief, March 2026)
- **What it is:** Full-credit, standards-mapped K-12 financial literacy platform. Not supplemental.
- **Two-Day Model:** Day 1 = concept intro via COST framework. Day 2 = Learning Lab (4-5 stations, portfolio artifacts, podcast bridge EN+ES).
- **COST Framework:** Concept → Operationalize → Situate → Transfer. 100% implementation across all 71 slide decks.
- **Chapter System:** L-01 to L-45 (core), L-46 to L-72 (extended). LC-36 (combined gambling), LC-39 (combined philanthropy). ~26 states use combined chapters. L-41 to L-45 = ILP/Career Readiness — NEVER call "Standard 15" externally.
- **Free Resources:** 6 PDFs per chapter per state. 4,700+ PDFs generated. Pipeline: JSON → HTML → state variable replacement → Puppeteer PDF.
- **State Variables:** 86+ variables across 8 categories.
- **Paid Platform Features:** Interactive teacher guide (62,975-line LTeacherGuide.ts), contextual AI assistant, live SME chat, 90+ skill builders, 3-tier IEP scaffolding, instructor dashboard, Canvas/Schoology grade passback, Clever/Infinite Campus SSO.
- **Podcast Summaries:** Each Day 2 has audio podcast bridging Day 1 → Day 2. English + Spanish.
- **AI Interviews (In Dev):** 8 chapters. Quote from Sebastian.
- **Progressive Financial Life Simulator (Future):** Isometric Sim-Town.
- **Research Foundation:** Backward Design, PCK, Experiential Learning, Improvement Science, UDL.
- **Competitor moat:** Implementation architecture, not content volume. ICAP/ILP integration.
- **Kentucky:** 1.0 credit = 120 hours = 60 chapters. 6 Strands. Only 4 platforms nationally can deliver this.
- **Never expose:** L-XX codes in state-facing materials. Never call L-41-L-45 "Standard 15" outside Oklahoma.

## Course Configuration Rules (NON-NEGOTIABLE)
- Every state config = exactly 45 chapters = 90 hours (Exception: Kentucky = 60 chapters = 120 hours)

## Texas TEKS — Authoritative Standards
- **§113.49 (PFL)**: HB 2662 (2013), 16 K&S statements: (c)(1)-(c)(16). Standalone PFL elective.
- **§113.76 (PFLE)**: SB 1063 (2021), 10 K&S statements: (d)(1)-(d)(10). Combined PFL + Economics course.
- **Both coexist.** HB 27 (2023) requires ALL students to complete PFL instruction using §113.49 framework.
- Estate planning required by both. L-71 is load-bearing for both TX configs.
- TEA PDF: `/root/.openclaw/workspace/ch113c.pdf`

## 36 State Priority Tiers (March 2026)
- **Tier 1:** CO ($1.1M), KY ($720K), TX ($6.8M)
- **Tier 2:** CA ($6.6M), OK ($500K), FL ($3.2M)
- **Tier 3:** OH ($2.4M), PA ($2.0M), VA ($1.4M), WI ($900K), CT ($600K), MI ($1.8M), NJ ($1.5M)
- **Tier 4:** AL, NC, GA, LA, IN, MO, TN, MS, SC, MD, MN, DE
- **Tier 5:** OR, KS, IA, NE, NY ($3.2M), UT, RI, WV, NH, ME, IL ($2.0M)
- Key contacts: Stephanie Hartman (CO CDE), Sharon Collins (KY KDE), Joshua Brady (CA CDE)
- Platform stats: 157 students, 25 teachers across all districts

## Distribution Strategy (March 12, 2026)
- Cold email campaigns dead for K-12. 35% bounce rate. New strategy: distributors/channel partners.
- PFL already in Jump$tart Clearinghouse. BOCES in CO are NOT purchasers. EVERFI is NOT a viable comparison.
- Key targets: Discovery Education, CEE, NGPF, state cooperatives (TX ESCs, FL consortia, KY cooperatives, OH ESCs)
- Third-party sending: MCH Strategic Data, Agile Education Marketing

## K-4 Bilingual ELA Market Intelligence (March 2026)
- US supplemental instructional materials: $4.73B (2024). US DLI market: $1.5B → $14B by 2032 (25% CAGR).
- 5.3M English Learners in US public schools, 76.4% Spanish-speaking.
- Big Three states: TX (20.2% EL), CA (18.9%), FL (~10.5%).
- Competitor pricing: Amplify Caminos $25-32/student, Savvas ~$195-255, McGraw Hill ~$670/grade.
- Four market gaps: basal burnout, lack of technical rigor, bilingual teacher shortage, financial literacy void in K-4.
- State adoption windows: CA 2026 ELA/ELD, TX Proclamation 2027, FL B.E.S.T. ITB June 2026.
- Full reports: `/root/.openclaw/workspace/research/`

## Oklahoma Adoption — Active Bid (March 2026)
- Subject code: 1451 (PFL). Intent to Bid open March 6 - April 10, 2026.
- Process: Intent → Justification letter → STC June vote → Materials review July
- Contacts: Carolynn Bristow (405-522-1904), Brenda Chapman (405-522-3523)
- Shea McCrary: OK instructor, piloted PFL, serves on RFP evaluation team.

## CDE California — Carrie Marovich
- Education Programs Consultant, CFIRD. cmarovich@cde.ca.gov, 916-327-1023
- CDE does NOT review instructional materials. Jump$tart pathway is indirect route.

## Project Explore — Status (March 18, 2026)
- Spanish Transcreation COMPLETE: 192 scripts, v5 methodology, 3.81/4.0 back-translation audit.
- Daytime Instruction UI BUILT: React/TypeScript on startup-smartup-gateway, GitHub Pages.
- Next: extend PFL SSO/LMS infrastructure, ~1 day dev for "mark class complete" (Sebastian).

## CABE 2026 Conference Research
- 9 co-sponsor districts identified. Contacts compiled at `/root/.openclaw/workspace/research/cabe_2026_district_contacts.md`
- CABE 2027 in Long Beach — plan for exhibitor/presenter presence.

## Gemini Distributor Analysis (March 18, 2026)
- Top recommendation: Vista Higher Learning for Project Explore. Justin emailed Arturo Castillon.

## Reed Universal Operating Rules
1. Chunk decomposition: <10 min chunks, write to task_queue.json first.
2. Partial results: Write after every completed chunk.
3. Parallel execution: >3 entities or >20 min → spawn parallel sub-sessions.
4. Timeout recovery: Write partial_complete status immediately.
5. Single-thread rule: Never start new task while previous shows "running".

## Writing Rules (ALL agents)
Source: `/home/ubuntu/pfl-academy/product-docs/writing_rules.md`

**COLD EMAIL RULES:** Always introduce yourself. Never fabricate social proof. Don't be chummy with strangers. Include phone + domain.

**BANNED PATTERNS:** Staccato proclamation, rhetorical question-answer, AI formulaic openers, marketing language ("game-changer"), buffering/validation, honesty qualifiers, empty expertise claims, false urgency, formulaic structure.

**EMBRACE:** Analytical depth, lived expertise, systems perspective, evidence-based reasoning, generous critique, specific concrete observations, layered analysis.

## Communication Heuristics
- Inter font NOT acceptable. Use Plus Jakarta Sans / Geist Sans / Newsreader / JetBrains Mono.
- Ras Mic (@rasmic) = design north star. Cody Schneider (@codyschneiderx) = GTM north star.
