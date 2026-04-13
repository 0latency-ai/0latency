# Claude Code Task: Claude.ai Integration

**Assigned:** March 28, 2026  
**Priority:** HIGH  
**Estimated Time:** 4-5 hours  
**Dependencies:** Core modules complete (api-client, auth, observer)

---

## Mission

Build the `platforms/claude.js` module to capture conversations from claude.ai and integrate with the 0Latency Chrome extension.

---

## Context

### What's Already Built

**Core Infrastructure (by Thomas):**
- ✅ `manifest.json` — Extension manifest configured for Claude
- ✅ `background/api-client.js` — 0Latency API wrapper
- ✅ `background/auth.js` — API key management
- ✅ `background/service-worker.js` — Background script handles API uploads
- ✅ `content/observer.js` — Base `MessageObserver` class
- ✅ `popup/` — UI for API key + settings

**Platform Reference:**
- ✅ `platforms/chatgpt.js` — Fully functional ChatGPT integration (use as template)

### Your Job

Build `platforms/claude.js` following the same pattern as `chatgpt.js` but adapted for Claude.ai's DOM structure.

---

## Technical Requirements

### File Location
`/root/.openclaw/workspace/0latency-chrome-extension/platforms/claude.js`

### Module Structure (Required)

```javascript
const ClaudePlatform = {
  id: 'claude',        // Platform ID (must match manifest)
  name: 'Claude',      // Display name

  /**
   * Extract conversation ID from URL or page
   * Claude URLs: https://claude.ai/chat/[conversation-id]
   */
  extractConversationId() {
    // TODO: Implement
  },

  /**
   * Extract all messages currently on the page
   * Returns array of message objects
   */
  extractMessages() {
    // TODO: Implement
  },

  /**
   * Extract messages from a specific DOM node
   * (for MutationObserver - new messages added dynamically)
   */
  extractMessagesFromNode(node) {
    // TODO: Implement
  },

  /**
   * Extract single message from a DOM element
   */
  extractMessageFromElement(element, index) {
    // TODO: Implement
    // Return format:
    // {
    //   id: string,           // Unique message ID
    //   role: string,         // 'user' or 'assistant'
    //   text: string,         // Message content
    //   timestamp: string,    // ISO 8601 timestamp
    //   platform: 'claude',
    //   metadata: {
    //     index: number,
    //     hasCodeBlocks: boolean,
    //     hasImages: boolean
    //   }
    // }
  }
};

// Initialize observer when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const observer = new window.MessageObserver(ClaudePlatform);
    observer.init();
  });
} else {
  const observer = new window.MessageObserver(ClaudePlatform);
  observer.init();
}
```

---

## Step-by-Step Instructions

### 1. Selector Discovery (1-2 hours)

**Open claude.ai in Chrome:**
1. Navigate to https://claude.ai
2. Start a new conversation
3. Send a few messages back and forth
4. Open DevTools (F12) → Elements tab

**Find Message Containers:**
- Look for parent elements that wrap each conversation turn
- Identify attributes that distinguish user vs assistant messages
- Common patterns:
  - `data-testid="user-message"` / `data-testid="assistant-message"`
  - `role="user"` / `role="assistant"`
  - Class names like `.message-user`, `.message-assistant`
  - Parent divs with specific structure

**Document Your Findings:**
- Main message container selector
- User vs assistant differentiation
- Text content location
- Message ID attribute (if available)
- Timestamp element (if visible)

**Example (hypothetical):**
```javascript
// Claude message structure (example - verify with actual page):
// <div data-role="user" data-message-id="abc123">
//   <div class="message-content">
//     Hello, Claude!
//   </div>
// </div>

const userMessages = document.querySelectorAll('[data-role="user"]');
const assistantMessages = document.querySelectorAll('[data-role="assistant"]');
```

### 2. Implement `extractConversationId()` (15 minutes)

**Claude URL Structure:**
- Typically: `https://claude.ai/chat/[conversation-id]`
- Example: `https://claude.ai/chat/a1b2c3d4-e5f6-7890`

**Implementation:**
```javascript
extractConversationId() {
  // Extract from URL
  const match = window.location.pathname.match(/\/chat\/([a-f0-9-]+)/);
  if (match) {
    return match[1];
  }
  
  // Fallback: generate from timestamp
  return `claude-${Date.now()}`;
}
```

### 3. Implement `extractMessages()` (1-2 hours)

**Goal:** Extract all messages currently visible on the page

**Steps:**
1. Query all message elements
2. Loop through each
3. Extract text, role, timestamp
4. Return array of message objects

**Reference `chatgpt.js` lines 29-45 for pattern**

**Tips:**
- Use `querySelectorAll()` to find all messages
- Check for both user and assistant messages
- Handle edge cases (empty messages, code blocks, images)
- Use `innerText` for text content (preserves line breaks)

### 4. Implement `extractMessagesFromNode()` (30 minutes)

**Goal:** Extract messages from a newly added DOM node (for MutationObserver)

**Steps:**
1. Check if node itself is a message
2. Query node's children for messages
3. Return array of message objects

**Reference `chatgpt.js` lines 50-70**

### 5. Implement `extractMessageFromElement()` (1 hour)

**Goal:** Extract single message data from a DOM element

**Required Fields:**
- `id` — Unique identifier (from attribute or generate)
- `role` — 'user' or 'assistant'
- `text` — Message content
- `timestamp` — ISO 8601 format
- `platform` — Always 'claude'
- `metadata` — Object with extra info

**Reference `chatgpt.js` lines 75-109**

**Tips:**
- Use `getAttribute()` for data attributes
- Use `querySelector()` to find child elements
- Use `innerText` or `textContent` for text
- Handle null cases gracefully (return null if invalid)

### 6. Testing (1 hour)

**Load Extension:**
1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select `/root/.openclaw/workspace/0latency-chrome-extension`

**Test Claude.ai:**
1. Navigate to https://claude.ai
2. Start a conversation
3. Open DevTools → Console
4. Look for `[0Latency]` logs
5. Verify messages are being captured

**Debug:**
- Check console for errors
- Verify selectors still work
- Test edge cases (code blocks, long messages, images)

**Report Back:**
- Number of messages captured
- Any errors encountered
- Edge cases found
- Selectors used (document for future updates)

---

## Success Criteria

✅ `platforms/claude.js` file created and functional  
✅ Messages extracted from claude.ai  
✅ Conversation ID detected correctly  
✅ Both user and assistant messages captured  
✅ No console errors  
✅ Integration tested end-to-end with loaded extension  
✅ Code documented with comments  

---

## Deliverables

1. **`platforms/claude.js`** — Fully functional module
2. **Test Report** — Document:
   - Selectors used
   - Test results (how many messages captured?)
   - Edge cases found
   - Any issues or limitations

3. **Selector Documentation** — Write down:
   - What selectors you used
   - Why they were chosen
   - Fallback selectors (if any)
   - Notes for future maintenance

---

## Common Pitfalls

❌ **Claude updates their UI frequently** — Use semantic selectors when possible  
❌ **Messages may load asynchronously** — MutationObserver handles this  
❌ **Code blocks have special formatting** — Use `innerText`, not `innerHTML`  
❌ **Empty messages** — Check for null/empty and skip  
❌ **Regenerated messages** — May have same ID, need deduplication  

---

## Reference Files

**Must Read:**
- `/root/.openclaw/workspace/0latency-chrome-extension/platforms/chatgpt.js` — Template to follow
- `/root/.openclaw/workspace/0latency-chrome-extension/content/observer.js` — Base class you're extending

**Context:**
- `/root/.openclaw/workspace/research/chrome-extension-sprint-plan.md` — Overall plan
- `/root/.openclaw/workspace/0latency-chrome-extension/README.md` — Project overview

---

## Questions?

- Check existing code first (chatgpt.js is your template)
- Console.log() everything while debugging
- Test incrementally (don't wait until the end)
- Report blockers ASAP

---

## When Complete

Report back to Justin with:
1. ✅ "Claude.ai integration complete"
2. 📊 Test results (messages captured, no errors)
3. 📝 Selector documentation
4. 🐛 Any issues or limitations found

**Estimated completion:** 4-5 hours from start

Good luck! 🚀
