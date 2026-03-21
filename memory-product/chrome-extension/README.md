# 0Latency Chrome Extension

Automatically capture AI conversations from ChatGPT, Claude, Gemini, and Perplexity into your 0Latency memory layer.

## Install (Developer Mode)

1. Clone or download this repo
2. Open `chrome://extensions` in Chrome
3. Enable **Developer mode** (top right toggle)
4. Click **Load unpacked**
5. Select this `chrome-extension` folder

## Setup

1. Click the 0Latency icon in your Chrome toolbar
2. Enter your API key (`zl_live_...`)
3. Set your Agent ID (default: `chrome-extension`)
4. Toggle auto-capture ON

## How It Works

The extension watches your AI conversations using DOM observers:

- **ChatGPT** — Detects `[data-message-author-role]` elements
- **Claude** — Detects `[data-testid="user-message"]` and `[data-testid="ai-message"]`
- **Gemini** — Detects query/response containers
- **Perplexity** — Detects question/answer pairs

When a new conversation turn completes (2s debounce after streaming finishes), the extension sends the human message + agent response to your 0Latency API for memory extraction.

## Features

- 🔄 **Auto-capture** — conversations are captured as they happen
- ⚡ **Rate limited** — max 1 extraction per 10 seconds per tab
- 🔒 **Your API key stays local** — stored in Chrome sync storage
- 📊 **Badge counter** — shows memories captured per turn
- 🌐 **4 platforms** — ChatGPT, Claude, Gemini, Perplexity

## Privacy

- The extension only activates on supported AI chat sites
- Conversation data is sent only to your configured API endpoint
- No data is sent to any third party
- Your API key is stored locally in Chrome's sync storage
