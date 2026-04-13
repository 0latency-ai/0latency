# 0Latency Chrome Extension

**Status:** In Development (ChatGPT core complete, Claude integration in progress)  
**Target Ship Date:** Early April 2026  
**Version:** 0.1.0 (Alpha)

---

## What's Built (ChatGPT + Core)

### ✅ Complete
- **Core Architecture**
  - Manifest V3 configuration
  - Background service worker
  - API client for 0Latency API
  - Authentication manager
  - Base message observer class

- **ChatGPT Integration**
  - Message extraction from chat.openai.com
  - Conversation ID detection
  - Real-time MutationObserver
  - Message queuing and batching

- **Popup UI**
  - API key input and validation
  - Connection status indicator
  - Platform toggle switches
  - Settings management

### 🚧 In Progress
- **Claude.ai Integration** (assigned to Claude Code)
- Chrome Web Store assets (icons, screenshots)
- Testing and polish

### ⏳ TODO
- Gemini integration
- Perplexity integration
- Extension icons (16x16, 48x48, 128x128)
- Chrome Web Store submission
- Error handling improvements
- Rate limiting logic

---

## Project Structure

```
0latency-chrome-extension/
├── manifest.json                 # Extension manifest (Manifest V3)
├── background/
│   ├── service-worker.js         # Main background script
│   ├── api-client.js             # 0Latency API wrapper
│   └── auth.js                   # API key management
├── content/
│   └── observer.js               # Base message observer class
├── popup/
│   ├── popup.html                # Extension popup UI
│   └── popup.js                  # Popup logic
├── platforms/
│   ├── chatgpt.js                # ChatGPT integration ✅
│   ├── claude.js                 # Claude integration 🚧
│   ├── gemini.js                 # Gemini integration ⏳
│   └── perplexity.js             # Perplexity integration ⏳
└── icons/
    ├── icon16.png                # 16x16 icon ⏳
    ├── icon48.png                # 48x48 icon ⏳
    └── icon128.png               # 128x128 icon ⏳
```

---

## How It Works

1. **Content Script Injection**
   - Extension injects `observer.js` + platform-specific module into chat pages
   - Detects platform (ChatGPT, Claude, etc.) based on URL

2. **Message Observation**
   - MutationObserver monitors DOM for new messages
   - Extracts message text, role (user/assistant), timestamp
   - Queues messages for batching

3. **Background Processing**
   - Content script sends messages to background service worker
   - Service worker formats messages for 0Latency API
   - API client handles authentication and uploads

4. **User Control**
   - Popup UI for API key configuration
   - Toggle individual platforms on/off
   - Real-time sync or batched mode

---

## Testing Locally

1. **Load unpacked extension:**
   ```bash
   cd /root/.openclaw/workspace/0latency-chrome-extension
   ```
   - Open Chrome → `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the extension directory

2. **Test ChatGPT:**
   - Navigate to https://chat.openai.com
   - Start a conversation
   - Check browser console for `[0Latency]` logs
   - Verify messages are being captured

3. **Configure API key:**
   - Click extension icon in toolbar
   - Enter 0Latency API key
   - Click "Connect"

---

## Next Steps

### For Thomas (Primary Focus)
1. ✅ Core architecture complete
2. ✅ ChatGPT integration complete
3. ⏳ Test ChatGPT end-to-end with real API key
4. ⏳ Create extension icons
5. ⏳ Prepare Chrome Web Store assets
6. ⏳ Integrate Claude.ai module (when Claude Code completes it)

### For Claude Code (Parallel Work)
**See: `/root/.openclaw/workspace/0latency-chrome-extension/CLAUDE_CODE_TASK.md`**

---

## Architecture Decisions

### Why Manifest V3?
- Chrome Web Store requires V3 for new extensions (as of 2024)
- Better security model
- Service workers instead of background pages

### Why MutationObserver?
- Chat interfaces are SPAs with dynamic content
- No official APIs available for ChatGPT/Claude/etc.
- MutationObserver is the most reliable DOM monitoring approach

### Why Batch Mode?
- Reduces API calls and rate limiting risk
- More efficient for long conversations
- User can toggle realtime vs batch

### Why Content Scripts Instead of Page Injection?
- Content scripts run in isolated context (more secure)
- Access to Chrome extension APIs
- Can't be blocked by page CSP

---

## Known Issues

1. **ChatGPT Selectors May Break**
   - OpenAI updates chat.openai.com UI frequently
   - Need fallback selectors and monitoring
   - Plan: Monthly maintenance for selector updates

2. **No API Key Validation Endpoint**
   - Current implementation assumes API key format is correct
   - Need actual validation endpoint from 0Latency API
   - Workaround: Try to store a test memory

3. **Rate Limiting Not Implemented**
   - No exponential backoff on 429 errors yet
   - Need to add retry logic with delays

4. **No Offline Queue**
   - If API is down, messages are lost
   - Should implement local queue with persistence

---

## API Integration

### 0Latency API Endpoints Used

**Store Single Memory:**
```
POST /v1/memories
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "text": "User: Hello\nAssistant: Hi there!",
  "metadata": {
    "platform": "chatgpt",
    "conversation_id": "abc-123",
    "message_id": "msg-1",
    "role": "assistant",
    "timestamp": "2026-03-28T22:00:00Z"
  }
}
```

**Store Multiple Memories (Batch):**
```
POST /v1/memories/batch
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "memories": [
    {
      "text": "...",
      "metadata": {...}
    },
    ...
  ]
}
```

**Validate API Key:**
```
GET /v1/auth/validate
Authorization: Bearer <api_key>
```

---

## Chrome Web Store Submission Checklist

- [ ] Extension icons created (16, 48, 128px)
- [ ] Screenshots (1280x800 or 640x400)
- [ ] Promotional images (1400x560)
- [ ] Privacy policy page (required for API key storage)
- [ ] Detailed description copy
- [ ] Category selection (Productivity)
- [ ] Pricing/monetization (Free)
- [ ] Permissions justification
- [ ] Test on Chrome, Edge, Brave
- [ ] Package .zip file
- [ ] Submit for review

---

## Timeline

**Current Date:** March 28, 2026

- **March 28:** Core + ChatGPT complete ✅
- **March 29-30:** Claude integration (Claude Code) + testing
- **March 31-April 1:** Gemini + Perplexity (if time) + assets
- **April 2-3:** Polish, testing, Chrome Web Store prep
- **April 7-11:** Submit + announce as Launch #2

**Estimated Total:** 2.5-3 focused days (as planned)

---

## License

Copyright © 2026 0Latency  
All rights reserved.
