# Outreach: Auto Dream Video Creator

**YouTube Channel:** (check video for channel name)  
**Video:** https://youtu.be/OnQ4BGN8B-s  
**Audience:** Claude Code power users  

---

## X/Twitter DM

Hey [name],

Just watched your Auto Dream breakdown — great explanation of what Anthropic built.

I built something similar but cross-platform: memory consolidation that works with Claude, GPT, Cursor, any agent framework. Basically Auto Dream as a public API, not locked to Claude Code.

Shipped today: https://0latency.ai

Would love your feedback. Happy to give you Scale tier access if you want to try it.

Justin  
https://0latency.ai

---

## YouTube Comment

Great breakdown of Auto Dream! 

I built something similar but cross-platform — works with Claude Code, ChatGPT, Cursor, custom agents. Basically "Auto Dream for everyone else."

API is live: https://0latency.ai

If anyone here uses multiple AI tools (not just Claude Code), would love feedback.

---

## Email (if available)

Subject: Auto Dream for any AI framework (not just Claude)

Hey [name],

Watched your Auto Dream video — you did a great job explaining why memory consolidation matters.

I built the cross-platform version. Instead of being locked to Claude Code, it works everywhere:
- Claude Code ✓
- ChatGPT ✓
- Cursor ✓
- Custom agents (LangChain, CrewAI, etc.) ✓

Think of it as "Auto Dream as a public API."

Launched today: https://0latency.ai

Would love to send you Scale tier access if you want to try it. Your audience (Claude Code power users) is exactly who needs this — especially if they use multiple tools.

Let me know if you're interested.

Thanks,  
Justin  
Founder, 0Latency  
https://0latency.ai

---

## Follow-up (if positive response)

Awesome! Just upgraded your account to Scale tier (free, indefinitely).

API key: [generate one for them]

Install:
```bash
npx @0latency/mcp-server@latest
```

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "0latency": {
      "command": "npx",
      "args": ["-y", "@0latency/mcp-server@latest"],
      "env": {
        "ZERO_LATENCY_API_KEY": "your_key_here"
      }
    }
  }
}
```

Test it:
1. Tell Claude to remember something: "Use the 0latency remember tool to store that I prefer React"
2. New session, ask: "What frontend framework do I prefer?"
3. Claude recalls it instantly

Works with GPT, Cursor, any framework via the API too.

Let me know what you think!

---

## Why This Creator Matters

**Audience:**
- Claude Code power users
- Early adopters of Auto Dream
- People who will IMMEDIATELY understand why cross-platform memory matters

**Value prop for him:**
- His audience needs this (multi-tool users)
- Good content angle ("Auto Dream vs 0Latency")
- He covers AI agent features aggressively

**Timing:**
- His video is fresh (posted today)
- Auto Dream is still beta/unannounced
- We're first-to-market with public cross-platform version

**Goal:**
Get him to try it, tweet about it, or make a follow-up video comparing Auto Dream vs 0Latency.
