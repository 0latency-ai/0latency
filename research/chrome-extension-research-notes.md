# Chrome Extension Research - 0Latency Integration

## Research Date: 2026-03-28

### Target Platforms

#### 1. Web-Based Chat Interfaces (Chrome Extension Approach)
- **ChatGPT** (chat.openai.com)
- **Claude** (claude.ai)
- **Gemini** (gemini.google.com)
- **Perplexity** (perplexity.ai)

#### 2. Desktop IDE Coding Assistants (Extension/Plugin Approach)
- **Cursor** (cursor.com) - VSCode fork
- **Windsurf** (windsurf.com) - VSCode-based by Codeium

---

## Technical Findings

### Web Chat Platforms (Chrome Extensions)

**Common Architecture:**
- Content script injection into chat pages
- DOM observation (MutationObserver) to detect new messages
- Message extraction via CSS selectors
- Background script for 0Latency API calls
- Popup UI for settings/auth

**Technical Stack:**
- Manifest V3 (Chrome/Edge/Brave compatible)
- Shared core module (auth, API, storage)
- Platform-specific selector configs
- localStorage for API keys/settings

**Key Challenges:**
- Each platform has different DOM structures
- SPA/dynamic content requires MutationObserver
- Rate limiting on API calls
- Message threading/context extraction

**Feasibility:** HIGH - Standard chrome extension pattern

---

### Desktop IDEs (Cursor/Windsurf)

**Cursor:**
- VSCode fork (Electron-based)
- Likely supports VSCode extension API
- Extensions installed via marketplace or .vsix
- Access to conversation history via extension API

**Windsurf:**
- VSCode-based (confirmed from docs)
- Can import VSCode extensions (confirmed in onboarding)
- Cascade chat interface (their agentic assistant)
- Extension marketplace support mentioned

**Extension Approach:**
- Build as VSCode extension (.vsix)
- Use VSCode extension API for:
  - Chat message hooks
  - Workspace context
  - Settings/configuration
  - Background tasks
- Deploy to both platforms via .vsix sideload

**Key Challenges:**
- Need to reverse-engineer chat APIs (if proprietary)
- May need separate extensions for Cursor vs Windsurf chat systems
- Desktop app authentication flow
- Rate limiting on 0Latency API

**Feasibility:** MEDIUM-HIGH - VSCode extension API is well-documented, but chat integration may be platform-specific

---

## Next Steps for Full Plan

1. ✅ Confirm VSCode extension compatibility (both support it)
2. ⏳ Check if Cursor/Windsurf expose chat/conversation APIs
3. ⏳ Research existing examples (ChatGPT chrome extensions as reference)
4. ⏳ Prototype selector discovery for each web platform
5. ⏳ Assess marketplace publishing vs private distribution

