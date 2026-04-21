# Chrome Extension Guide

## Status: ✅ Functional

The 0Latency Chrome Extension is fully functional and ready for production use.

## Overview

The Chrome extension automatically captures web content and stores it as memories in your 0Latency account. It intelligently extracts information from pages you visit and makes it available for recall in your AI agents.

## Installation

1. Download the latest release: `0latency-ext-v3.zip`
2. Extract the ZIP file
3. Open Chrome and go to `chrome://extensions`
4. Enable "Developer mode" (top right)
5. Click "Load unpacked"
6. Select the extracted extension folder
7. The 0Latency icon should appear in your toolbar

## Configuration

### Initial Setup

1. Click the 0Latency icon in your toolbar
2. Go to **Settings**
3. Configure the following fields:

**API Key** (required)
- Get from: https://0latency.ai/dashboard
- Format: `zl_live_...` or `zl_test_...`
- Stores securely in Chrome sync storage

**Agent ID** (required)
- Default: `justin`
- This determines which memory namespace your captures write to
- Examples: `justin`, `thomas`, `research-agent`, `personal`

**API Endpoint** (optional)
- Default: `https://api.0latency.ai`
- Only change if using self-hosted instance

### Agent ID Field

**What it does:** Routes all captured memories to a specific agent_id namespace.

**Default behavior:**
```
agent_id: "justin"
```
All web captures → Justin's personal memory namespace

**Custom routing:**
```
agent_id: "research-assistant"
```
All web captures → research-assistant namespace

**Best practices:**
- Use your name for personal browsing: `justin`, `alice`
- Use project names for focused research: `pfl-academy`, `memory-product`
- Use role names for specialized work: `researcher`, `writer`, `analyst`

**Important:** Once you set an agent_id, all memories are written to that namespace. If you change it later, previous captures remain under the old agent_id.

### Which Namespace Do Captures Land In?

All captures write to the `agent_id` configured in extension settings.

**Example flow:**
1. You browse to https://example.com/article
2. Extension captures interesting content
3. Sends to: `POST /memories/extract`
4. Stored with: `agent_id: "justin"` (or your configured value)
5. Available for recall: `POST /recall` with `agent_id: "justin"`

**Multiple agents:** If you have multiple AI agents (e.g., writer, researcher, analyst), decide which one should receive browser captures. Change the agent_id in settings when switching contexts.

## Features

### Automatic Capture

**What gets captured:**
- Page title and URL
- Main content (articles, blog posts, documentation)
- Code snippets (from GitHub, Stack Overflow, etc.)
- Key quotes and excerpts
- Metadata (timestamps, authors, sources)

**What gets filtered out:**
- Navigation elements
- Ads and promotional content
- Boilerplate text
- Cookie banners and popups

### Manual Capture

**Text selection:**
1. Highlight any text on a page
2. Right-click
3. Select "Save to 0Latency Memory"
4. Extension captures the selected text with context

**Full page capture:**
1. Click extension icon
2. Click "Capture This Page"
3. Extension extracts and stores page content

### Capture Status

**Visual feedback:**
- 🔄 Processing: Blue spinner icon
- ✅ Success: Green checkmark
- ❌ Error: Red X (click for details)

**View capture history:**
1. Click extension icon
2. Go to "Recent Captures"
3. See last 20 captures with timestamps

## Endpoints Used

### Primary: /memories/extract

**Endpoint:** `POST https://api.0latency.ai/memories/extract`

**Payload:**
```json
{
  "agent_id": "justin",
  "content": "Captured content here...",
  "metadata": {
    "source": "chrome-extension",
    "url": "https://example.com",
    "title": "Page Title",
    "captured_at": "2026-03-31T23:00:00Z"
  }
}
```

**Response:**
```json
{
  "job_id": "b799ef48-e1d5-4b87-a3e6-7443b8de4c08",
  "status": "accepted"
}
```

**Note:** This is an async endpoint. Extraction happens in background. Use `/memories/extract/{job_id}` to check status.

### Batch: /extract/batch

**Endpoint:** `POST https://api.0latency.ai/extract/batch`

Used when capturing multiple items simultaneously (e.g., tabbed pages, bulk imports).

**Payload:**
```json
{
  "agent_id": "justin",
  "items": [
    {
      "content": "First item...",
      "metadata": {...}
    },
    {
      "content": "Second item...",
      "metadata": {...}
    }
  ]
}
```

**Response:**
```json
{
  "batch_id": "batch_abc123",
  "jobs": [
    {"job_id": "job1", "status": "accepted"},
    {"job_id": "job2", "status": "accepted"}
  ]
}
```

## Usage Patterns

### Personal Knowledge Base

**Setup:**
```
agent_id: "justin"
```

**Use cases:**
- Save articles you read
- Capture research findings
- Store documentation for later reference
- Build personal knowledge graph

**Recall:**
```python
client.recall(
    agent_id="justin",
    conversation_context="What did I read about vector databases?"
)
```

### Project-Specific Research

**Setup:**
```
agent_id: "pfl-academy-research"
```

**Use cases:**
- Focused research for specific project
- Isolated memory namespace
- Easy to export/share with team
- Clean separation from personal browsing

**Recall:**
```python
client.recall(
    agent_id="pfl-academy-research",
    conversation_context="California education standards"
)
```

### Team Shared Memory

**Setup:**
```
agent_id: "team-engineering"
```

**Use cases:**
- Team members share same agent_id
- Collective knowledge base
- Everyone's captures contribute to shared memory
- Useful for onboarding new team members

**Recall:**
```python
client.recall(
    agent_id="team-engineering",
    conversation_context="Deployment procedures"
)
```

## Troubleshooting

### Extension Not Capturing

**Check:**
1. API key is valid and not expired
2. Agent ID is set (not empty)
3. Page content is accessible (not blocked by CORS)
4. Extension has permission for current site

**Fix:**
```
1. Click extension icon
2. Go to Settings
3. Click "Test Connection"
4. Should show: ✅ Connected successfully
```

### Captures Not Appearing in Recall

**Check:**
1. Correct agent_id in recall request
2. Wait 5-10 seconds for extraction to complete
3. Verify capture succeeded (check extension popup)

**Test:**
```bash
# List recent memories for your agent_id
curl "https://api.0latency.ai/memories?agent_id=justin&limit=10" \
  -H "X-API-Key: your_api_key"
```

### Rate Limit Errors

**Symptoms:**
- Extension shows "429 Too Many Requests"
- Captures failing frequently

**Cause:** Exceeding your tier's rate limit (Free: 20 RPM, Pro: 100 RPM)

**Fix:**
1. Upgrade tier if needed
2. Reduce capture frequency (change settings)
3. Use batch endpoint for bulk captures

### CORS Errors

**Symptoms:**
- Extension shows "Network error"
- Console shows CORS policy error

**Cause:** API endpoint not allowing extension origin

**Fix:** This should not happen with production API. If it does, contact support.

## Privacy and Security

### What Gets Captured

- Only visible content from pages you actively visit
- Selected text when you explicitly right-click → Save
- Metadata: URL, title, timestamp (for context)

### What Does NOT Get Captured

- Passwords or authentication tokens
- Private API keys or credentials
- Credit card numbers (filtered out)
- Social security numbers (filtered out)
- Personal identifying information (filtered by default)

### Data Storage

- Encrypted in transit (HTTPS)
- Stored in tenant-isolated database
- No cross-tenant data leakage
- GDPR compliant

### API Key Security

- Stored in Chrome sync storage (encrypted)
- Never transmitted except in API calls
- Never logged or cached
- Revocable from dashboard

## Updates

### Checking for Updates

Chrome automatically updates extensions from the Chrome Web Store.

For manual installs:
1. Visit: https://github.com/0latency/chrome-extension/releases
2. Download latest version
3. Replace extension files
4. Reload extension in `chrome://extensions`

### Version History

- **v3** (Current): Fixed syntax errors, improved error handling, batch support
- **v2**: Added manual capture, context menus, settings UI
- **v1**: Initial release with automatic capture

## Feedback and Support

**Report issues:**
- GitHub: https://github.com/0latency/chrome-extension/issues
- Email: support@0latency.ai

**Feature requests:**
- Submit via GitHub issues
- Tag with `enhancement`

**Documentation:**
- API Reference: https://0latency.ai/docs
- Best Practices: See BEST_PRACTICES.md
- Troubleshooting: See TROUBLESHOOTING.md
