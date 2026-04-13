# Chrome Extension Sprint Plan — Week of April 7, 2026

**Status:** Scheduled (pending core product launch)  
**Duration:** 2.5-3 focused days  
**Target Ship Date:** Friday, April 11, 2026  
**Launch Moment:** "Launch #2" — Second wave of HN/Twitter traffic

---

## Pre-Sprint Checklist (Complete before kickoff)

- [ ] Core product (API/SDKs/MCP) launched and stable
- [ ] Week 1 feedback collected and triaged
- [ ] Chrome Developer account set up ($5 one-time fee)
- [ ] Extension privacy policy drafted (required for Chrome Web Store)
- [ ] Extension icons/assets prepared (128x128, 48x48, 16x16 PNG)
- [ ] 0Latency API endpoint for extension traffic confirmed

---

## Day 1: Foundation + ChatGPT (6-8 hours)

### Morning (0-4 hours)
**Goal:** Scaffold core extension + ChatGPT integration

1. **Set up project structure**
   - `manifest.json` (Manifest V3)
   - `background/` (service worker)
   - `content/` (injection scripts)
   - `popup/` (settings UI)
   - `platforms/` (platform configs)

2. **Build shared core**
   - `api-client.js` — 0Latency API wrapper
   - `auth.js` — API key storage + validation
   - `storage.js` — Chrome storage wrapper
   - `observer.js` — MutationObserver base class

3. **ChatGPT selector discovery**
   - Open chat.openai.com
   - Inspect message elements
   - Document selectors (conversation, messages, user/assistant roles)
   - Test across: new chat, existing chat, regenerate flows

### Afternoon (4-8 hours)
**Goal:** ChatGPT integration working end-to-end

4. **Build ChatGPT platform module**
   - `platforms/chatgpt.js` with selectors
   - Message extraction logic
   - Thread/context capture
   - Real-time observer integration

5. **Test ChatGPT integration**
   - Load unpacked extension
   - Verify message capture
   - Verify 0Latency API calls
   - Check edge cases (code blocks, images, regenerate)

6. **Build minimal popup UI**
   - API key input
   - Status indicator (connected/disconnected)
   - Manual sync button

**Milestone:** ChatGPT extension functional, syncing to 0Latency

---

## Day 2: Claude + UI Polish (4-5 hours)

### Morning (0-3 hours)
**Goal:** Claude integration

1. **Claude selector discovery**
   - Open claude.ai
   - Inspect message structure
   - Document selectors (different from ChatGPT)

2. **Build Claude platform module**
   - `platforms/claude.js`
   - Test message extraction
   - Verify thread context

3. **Refactor shared core**
   - Abstract platform-specific logic
   - Ensure clean separation

### Afternoon (3-5 hours)
**Goal:** UI polish + Chrome Web Store prep

4. **Enhanced popup UI**
   - Dashboard: recent memories, sync status
   - Settings: auto-sync toggle, sync frequency
   - Visual polish (CSS, icons)

5. **Prepare Chrome Web Store assets**
   - Screenshots (ChatGPT + Claude in action)
   - Promotional images (1400x560)
   - Description copy
   - Privacy policy link

6. **Testing across both platforms**
   - ChatGPT + Claude simultaneously
   - Edge cases, error handling
   - Rate limiting behavior

**Milestone:** Both platforms working, UI polished, ready for submission

---

## Day 3: Gemini (Stretch) + Submission (2-3 hours)

### Morning (0-2 hours)
**Goal:** Gemini integration (if time permits)

1. **Gemini selector discovery** (gemini.google.com)
2. **Build Gemini platform module** (`platforms/gemini.js`)
3. **Test integration**

**If tight on time:** Skip Gemini, ship with ChatGPT + Claude only

### Afternoon (2-3 hours)
**Goal:** Chrome Web Store submission + announcement prep

4. **Final testing**
   - Load unpacked extension
   - Full flow: install → auth → sync
   - Cross-browser check (Chrome, Edge, Brave)

5. **Package extension**
   - Create .zip for Chrome Web Store
   - Create .crx for manual distribution (GitHub releases)

6. **Chrome Web Store submission**
   - Upload .zip
   - Complete store listing (description, screenshots, privacy policy)
   - Submit for review (typically 1-3 days)

7. **Prepare Launch #2 announcement**
   - HN post title: "0Latency Chrome Extension: Automatic Memory for ChatGPT, Claude, and Gemini"
   - Show HN post text (problem, solution, demo GIF)
   - Twitter announcement thread
   - Update 0latency.ai homepage (add Chrome Extension section back)

**Milestone:** Extension submitted, announcement ready to go live

---

## Launch #2 Announcement (Friday, April 11)

### HN Post Template
```
Title: 0Latency Chrome Extension: Automatic Memory for ChatGPT, Claude, and Gemini

Body:
We launched 0Latency last week [link to Launch #1] — an API for persistent memory across AI agents and chats.

Today we're shipping a Chrome extension that automatically captures your ChatGPT, Claude, and Gemini conversations and stores them to your 0Latency memory graph.

Why this matters:
- AI chats are ephemeral. When the session ends, context is lost.
- 0Latency gives your conversations a memory layer that persists across platforms.
- Works with the same API your agents use — everything in one unified memory.

What it does:
- Monitors your ChatGPT/Claude/Gemini conversations in real-time
- Extracts messages, context, and metadata
- Stores to your 0Latency account via API
- Enables semantic search, graph relationships, and recall across all platforms

Tech stack:
- Manifest V3 Chrome extension
- MutationObserver for real-time capture
- 80% shared core, 20% platform-specific selectors
- Open to feedback on other platforms (Perplexity, Cursor, etc.)

Download: [Chrome Web Store link]
GitHub: [link to repo if open-source]
Docs: https://docs.0latency.ai/integrations/chrome-extension

Happy to answer questions!
```

### Twitter Thread
```
🧠 0Latency Chrome Extension is live

Automatically capture your ChatGPT, Claude, and Gemini conversations and store them to a persistent memory layer.

Why? AI chats are ephemeral. When the tab closes, context is gone.

🧵 1/5
```

---

## Post-Launch Monitoring (Week 3)

### Metrics to Track
- Installs (Chrome Web Store analytics)
- Active users (API usage from extension user-agent)
- Error reports (Sentry or similar)
- Selector breakage reports (platforms update their UIs)

### Maintenance Plan
- Monitor platform UI changes (ChatGPT/Claude/Gemini)
- Update selectors as needed (~2-4 hours/month)
- Add Perplexity if demand is clear

---

## Contingencies

### If Chrome Web Store Review Rejected
- Distribute via GitHub releases (.crx manual install)
- Submit to Edge Add-ons (less strict review)
- Fix issues and resubmit

### If Selectors Break During Testing
- Fallback selectors (try 3+ approaches per platform)
- User-reported breakage flow (in-extension feedback button)

### If Timeline Slips
- Ship ChatGPT-only first, add Claude/Gemini in follow-up releases
- Still a valid Launch #2 with single platform

---

## Technical Debt / Future Work

### Phase 2 (Post-validation)
- Perplexity integration
- Firefox Add-ons (requires Manifest V2 backport)
- Edge Add-ons (easy, Chromium-compatible)

### Phase 3 (If demand proven)
- Cursor VSCode extension
- Windsurf VSCode extension
- Conversation export (JSON)
- Browser-local storage fallback

---

## Files to Reference During Sprint

- **Architecture:** `/root/.openclaw/workspace/research/0latency-chrome-extension-roadmap.md`
- **Research notes:** `/root/.openclaw/workspace/research/chrome-extension-research-notes.md`
- **0Latency API docs:** https://docs.0latency.ai/api
- **Manifest V3 guide:** https://developer.chrome.com/docs/extensions/mv3/

---

**Status:** Ready to execute on Week of April 7. No further planning needed — just run this playbook.
