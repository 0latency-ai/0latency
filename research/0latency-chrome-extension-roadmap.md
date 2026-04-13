# 0Latency Extension Roadmap & Priority List

**Research Date:** March 28, 2026  
**Author:** Thomas  
**Status:** Planning Phase

---

## Executive Summary

**Objective:** Build browser/IDE extensions to automatically capture and store conversation history from AI chat platforms (ChatGPT, Claude, Gemini, Perplexity, Cursor, Windsurf) to 0Latency memory API.

**Total Effort:** 20-27 hours (2.5-3 focused days)  
**Recommended Approach:** Build in 3 phases, starting with highest-ROI web platforms  
**Key Insight:** Web platforms share 80% of code. Desktop IDEs require separate approach but leverage VSCode extension API.

---

## Platform Research Summary

### Web-Based Chat Platforms

| Platform | User Base (Est.) | DOM Complexity | API Access | Feasibility | Priority |
|---|---|---|---|---|---|
| **ChatGPT** | ~200M users | Medium | None (scraping) | HIGH | **P0** |
| **Claude** | ~10M users | Medium | None (scraping) | HIGH | **P0** |
| **Gemini** | ~50M users | Medium | None (scraping) | HIGH | **P1** |
| **Perplexity** | ~5M users | Low-Medium | None (scraping) | HIGH | **P1** |

**Technical Approach:**
- Manifest V3 chrome extension
- Content script injection
- MutationObserver for real-time message detection
- Background service worker for 0Latency API calls
- Shared core module (80% code reuse)
- Platform-specific selector configs (20% unique)

**Challenges:**
- Each platform has different DOM structure
- SPA/dynamic content requires robust observers
- Rate limiting considerations
- Thread/context extraction logic

### Desktop IDE Coding Assistants

| Platform | User Base (Est.) | Extension Support | API Access | Feasibility | Priority |
|---|---|---|---|---|---|
| **Cursor** | ~2M devs | VSCode extensions | Partial | MEDIUM-HIGH | **P2** |
| **Windsurf** | ~500K devs | VSCode extensions | Partial | MEDIUM-HIGH | **P2** |

**Technical Approach:**
- VSCode extension (.vsix)
- Extension API for workspace hooks
- May need proprietary chat API reverse-engineering
- Separate builds for Cursor vs Windsurf (different chat systems)

**Challenges:**
- Chat conversation APIs may be proprietary/undocumented
- Desktop authentication flow
- Platform-specific quirks despite VSCode base
- Requires installation flow (not just browser click)

---

## Architecture Overview

### Phase 1: Core Chrome Extension (Web Platforms)

**Shared Core Module:**
```
├── background/
│   ├── api-client.js          # 0Latency API integration
│   ├── auth.js                # User auth + API key mgmt
│   └── storage.js             # Chrome storage wrapper
├── content/
│   ├── observer.js            # MutationObserver base class
│   ├── extractor.js           # Message extraction logic
│   └── ui-overlay.js          # In-page status indicator
├── popup/
│   ├── settings.html          # Extension settings UI
│   ├── dashboard.html         # Memory stats/preview
│   └── auth-flow.html         # OAuth/API key setup
└── manifest.json              # Extension manifest (V3)
```

**Platform-Specific Configs:**
```
├── platforms/
│   ├── chatgpt.js             # OpenAI selectors + logic
│   ├── claude.js              # Anthropic selectors + logic
│   ├── gemini.js              # Google selectors + logic
│   └── perplexity.js          # Perplexity selectors + logic
```

### Phase 2: Desktop IDE Extensions

**VSCode Extension Structure:**
```
├── extension/
│   ├── extension.js           # Main extension entry
│   ├── chat-monitor.js        # Chat message hook
│   ├── workspace-context.js   # Codebase context capture
│   └── api-client.js          # 0Latency API (reused)
├── platform-adapters/
│   ├── cursor-adapter.js      # Cursor-specific hooks
│   └── windsurf-adapter.js    # Windsurf-specific hooks
└── package.json               # VSCode extension manifest
```

---

## Phased Rollout Plan

### **Phase 1: Web Platforms - Core Build (P0)**
**Duration:** 12-15 hours  
**Deliverables:**
- ✅ ChatGPT extension (fully functional)
- ✅ Claude extension (fully functional)
- ✅ Shared core + popup UI
- ✅ Chrome Web Store listing (pending review)
- ⏳ Gemini integration (stretch goal if time permits)

**Why start here:**
- Largest user base (200M+ ChatGPT, 10M+ Claude)
- Shared architecture = faster iteration
- Easier testing (no desktop install required)
- Chrome Web Store distribution = instant reach

**Milestones:**
1. **Hours 0-4:** Core architecture + ChatGPT integration
2. **Hours 5-8:** Claude integration + shared module refactor
3. **Hours 9-12:** Popup UI + auth flow
4. **Hours 13-15:** Testing, polish, Chrome Web Store submission

### **Phase 2: Web Platforms - Expansion (P1)**
**Duration:** 4-6 hours  
**Deliverables:**
- ✅ Gemini extension (if not in Phase 1)
- ✅ Perplexity extension
- ✅ Edge/Brave compatibility testing

**Why second:**
- Incremental reach (50M+ Gemini, 5M+ Perplexity)
- Minimal new code (platform config only)
- Market validation from Phase 1 first

**Milestones:**
1. **Hours 0-2:** Gemini selector discovery + integration
2. **Hours 3-4:** Perplexity selector discovery + integration
3. **Hours 5-6:** Cross-browser testing

### **Phase 3: Desktop IDEs (P2)**
**Duration:** 8-12 hours  
**Deliverables:**
- ✅ Cursor VSCode extension
- ✅ Windsurf VSCode extension
- ⏳ Marketplace listing (if allowed) OR private distribution

**Why third:**
- Smaller user base (2.5M combined)
- Higher implementation risk (API unknowns)
- Requires Phase 1/2 learnings first
- Market validation signal before investing

**Milestones:**
1. **Hours 0-3:** VSCode extension scaffold + API research
2. **Hours 4-6:** Cursor chat integration
3. **Hours 7-9:** Windsurf chat integration
4. **Hours 10-12:** Testing + distribution setup

---

## Priority Ranking (Final)

### **Tier 0 (Launch Blockers):**
1. **ChatGPT** — 200M users, market leader, must-have
2. **Claude** — 10M users, technical audience, early adopters

**Launch with these two. Validate market fit before continuing.**

### **Tier 1 (Post-Launch):**
3. **Gemini** — 50M users, Google ecosystem
4. **Perplexity** — 5M users, research-focused users

**Add after Phase 1 validates demand. Low effort, incremental reach.**

### **Tier 2 (Market Validation Required):**
5. **Cursor** — 2M devs, coding-focused memory use case
6. **Windsurf** — 500K devs, emerging platform

**Only build if Phase 1 shows strong adoption. Different use case (coding vs chat).**

---

## Time Estimates by Phase

| Phase | Platform(s) | Hours | Cumulative | Status |
|---|---|---|---|---|
| **1A** | ChatGPT | 6-8h | 6-8h | 🔴 Not Started |
| **1B** | Claude | 4-5h | 10-13h | 🔴 Not Started |
| **1C** | UI + Polish | 2-3h | 12-15h | 🔴 Not Started |
| **2A** | Gemini | 2-3h | 14-18h | 🔴 Not Started |
| **2B** | Perplexity | 2-3h | 16-21h | 🔴 Not Started |
| **3A** | Cursor | 4-6h | 20-27h | 🔴 Not Started |
| **3B** | Windsurf | 4-6h | 24-33h | 🔴 Not Started |

**Recommendation:** Ship Phase 1 (ChatGPT + Claude) as MVP, measure adoption, then decide on Phase 2/3.

---

## Technical Risks & Mitigation

### Risk 1: Platform UI Changes Break Extension
**Likelihood:** High  
**Impact:** High (extension stops working)  
**Mitigation:**
- Semantic selectors over brittle class names
- Fallback selectors (try 3+ approaches)
- Auto-reporting when selectors fail (telemetry)
- Monthly maintenance budget for selector updates

### Risk 2: Rate Limiting on 0Latency API
**Likelihood:** Medium  
**Impact:** Medium (delayed syncs)  
**Mitigation:**
- Client-side batching (sync every 5 messages, not per-message)
- Exponential backoff on 429 errors
- Local queue with retry logic
- User-configurable sync frequency

### Risk 3: Cursor/Windsurf APIs Are Proprietary
**Likelihood:** High  
**Impact:** High (can't ship Phase 3)  
**Mitigation:**
- Research first before committing hours
- Fallback: manual export/import flow
- Community feedback: ask users if they'd pay for it

### Risk 4: Chrome Web Store Review Rejection
**Likelihood:** Low-Medium  
**Impact:** High (can't distribute)  
**Mitigation:**
- Follow all Manifest V3 guidelines strictly
- Clear privacy policy (data goes to user's 0Latency account)
- Manual distribution via GitHub releases (backup plan)
- Edge Add-ons + Firefox Add-ons as alternatives

---

## Market Sizing

### Total Addressable Market
- **ChatGPT users:** ~200M
- **Claude users:** ~10M
- **Gemini users:** ~50M
- **Perplexity users:** ~5M
- **Cursor devs:** ~2M
- **Windsurf devs:** ~500K

**Total:** ~267.5M potential users

### Serviceable Available Market (Realistic)
- Assume 5% of users care about memory/history: **13.4M**
- Assume 10% of those install extensions: **1.34M**
- Assume 1% convert to 0Latency paid: **13,400 customers**

**Revenue potential (at $10/mo avg):** $134K MRR = $1.6M ARR

---

## Open Questions

1. **Chrome Web Store approval timeline?** (Typically 1-3 days, can be weeks)
2. **Do we want browser-local storage fallback?** (For users who don't auth immediately)
3. **Should we support conversation export (JSON)?** (Good for migration, low effort)
4. **Freemium model?** (Free extension, paid API tier?) — YES per current 0Latency model
5. **Telemetry?** (Anonymous usage stats to track selector breakage) — Need privacy review

---

## Next Steps (After Approval)

1. ✅ **Justin reviews + approves roadmap**
2. ⏳ Set up Chrome extension boilerplate (Manifest V3)
3. ⏳ ChatGPT selector discovery (open chat.openai.com, inspect DOM)
4. ⏳ Build core observer + extractor logic
5. ⏳ 0Latency API client (reuse SDK if available)
6. ⏳ Build + test ChatGPT integration
7. ⏳ Repeat for Claude
8. ⏳ Build popup UI
9. ⏳ Packaging + Chrome Web Store submission

**ETA for Phase 1 MVP:** 2-3 focused days after kickoff

---

## Distribution Strategy

### Phase 1 (Web Extensions)
- **Chrome Web Store** (primary)
- **Edge Add-ons** (Chromium-compatible, easy port)
- **Firefox Add-ons** (requires Manifest V2 backport OR V3 support)
- GitHub releases (manual .crx sideload for power users)

### Phase 2 (Desktop Extensions)
- VSCode Marketplace (if Cursor/Windsurf allow it)
- Direct .vsix distribution via 0latency.ai
- GitHub releases

---

## Competitive Analysis

### Existing Solutions
- **None found** for 0Latency-style API memory storage
- Some chrome extensions for ChatGPT history export (local JSON)
- No unified multi-platform memory solution

**Opportunity:** First-mover advantage for cross-platform AI memory

---

## Success Metrics

### Phase 1 (30 days post-launch)
- 1,000+ installs (ChatGPT + Claude combined)
- 100+ active users (using 0Latency API)
- <5% uninstall rate
- <10 selector breakage reports

### Phase 2 (60 days post-launch)
- 5,000+ installs (all 4 web platforms)
- 500+ active users
- 50+ paying 0Latency customers attributed to extensions

### Phase 3 (90 days post-launch)
- 10,000+ total installs
- 1,000+ active users
- 100+ paying customers
- Positive ROI on development time

---

## Budget Summary

**Development Time:**
- Phase 1: 12-15 hours ($0 internal)
- Phase 2: 4-6 hours ($0 internal)
- Phase 3: 8-12 hours ($0 internal)

**Ongoing Costs:**
- Chrome Web Store developer fee: $5 (one-time)
- Monthly maintenance: 2-4 hours/month (selector updates)

**Revenue Opportunity:** $1.6M ARR potential (best case)

---

## Appendix: Technical Specs

### Chrome Extension Permissions Required
```json
{
  "permissions": [
    "storage",           // Store API keys + settings
    "activeTab",         // Inject into chat pages
    "https://*.openai.com/*",
    "https://*.anthropic.com/*",
    "https://*.google.com/*",
    "https://*.perplexity.ai/*"
  ],
  "host_permissions": [
    "https://api.0latency.ai/*"  // 0Latency API calls
  ]
}
```

### VSCode Extension Capabilities
```json
{
  "contributes": {
    "commands": [
      {
        "command": "0latency.syncConversation",
        "title": "0Latency: Sync Current Conversation"
      }
    ],
    "configuration": {
      "title": "0Latency",
      "properties": {
        "0latency.apiKey": {
          "type": "string",
          "description": "Your 0Latency API key"
        },
        "0latency.autoSync": {
          "type": "boolean",
          "default": true,
          "description": "Automatically sync conversations"
        }
      }
    }
  }
}
```

---

**Status:** Awaiting approval to proceed with Phase 1 build.

