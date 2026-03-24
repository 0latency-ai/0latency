# 0Latency Explainer Video — Script v2 (Real Story)
## 75 seconds | Screen recordings + minimal animation

---

### SHOT 1: The Reality (0:00 - 0:10)
**Visual:** Real Telegram screenshot — Thomas delivering detailed work. Busy, productive conversation. Zoom slowly into the chat.

**Narration:** "This is Thomas. An AI agent managing a product launch — writing specs, analyzing competitors, deploying code. 175,000 tokens of context. Hours of accumulated work."

---

### SHOT 2: The Crash (0:10 - 0:20)
**Visual:** Screenshot of 🚨 CONTEXT LIMIT HIT. Red warning. Session reset message. The screen goes dark briefly.

**Narration:** "Then this happens. Context limit. Session reset. Every LLM has a ceiling. When you hit it, your agent starts over. Everything it learned — gone."

**Text overlay:** "175,000 tokens. Wiped."

---

### SHOT 3: The Recovery (0:20 - 0:35)
**Visual:** Screenshot of Thomas coming back immediately after reset — delivering the full site facelift summary without missing a beat. Highlight the seamless continuation.

**Narration:** "Unless it has a memory layer. Watch — session resets, and the agent picks up exactly where it left off. No re-explaining. No lost context. It remembers the gap analysis, the design decisions, the competitor research. All of it."

---

### SHOT 4: The Depth (0:35 - 0:50)
**Visual:** Screenshot showing "76 messages found" for gap analysis. Scroll through the search results — Saturday, Sunday, Monday. Days of accumulated context.

**Narration:** "76 conversations. Three days of work. Strategy, architecture, competitive analysis — all instantly recallable. Not stored in a token window. Stored in persistent memory that survives every session reset, every crash, every context limit."

---

### SHOT 5: How It Works (0:50 - 1:00)
**Visual:** Clean terminal. Three lines of code:

```python
from zerolatency import ZeroLatency
zl = ZeroLatency(api_key="your_key")
zl.store("User prefers dark mode")
results = zl.recall("What does the user prefer?")
# → 47ms, relevance: 0.94
```

**Narration:** "Three lines of code. Sub-100 millisecond recall. Your agent stores what matters and gets it back instantly — ranked by relevance, weighted by recency."

---

### SHOT 6: The Proof (1:00 - 1:10)
**Visual:** Text animation on dark background:

"We built this entire AI startup on 624 memories."

Then below it:

"You get 10,000 free."

**Narration:** "We built this entire product — five AI agents, a 36-state deployment, a full launch — on 624 memories. You get ten thousand. Free."

---

### SHOT 7: CTA (1:10 - 1:17)
**Visual:** 0Latency landing page. Orange glow. Logo.

**Text on screen:**
```
pip install zerolatency
0latency.ai
```

**Narration:** "Zero latency. Zero configuration. Give your agent a memory."

**[END]**

---

## Production Notes

### What We Already Have:
- Screenshots 1, 2, 3 (Justin sent today — the Telegram compaction sequence)
- These ARE the video. Real product, real context, real recovery.

### What Justin Records:
1. **Voiceover** — Read the narration. Quiet room. Natural pace. Phone voice memo is fine.
2. **Terminal demo** (Shot 5 only) — Clean dark terminal, type the 4 lines of Python. 30 seconds of footage.

### What We Build in Canva:
- Shot 1: Slow zoom on screenshot + subtle vignette
- Shot 2: Red flash / glitch effect on the context limit warning
- Shot 5: Terminal mockup or real recording
- Shot 6: Text animation (simple fade-in, orange accent)
- Shot 7: Landing page + logo

### Style:
- **Dark theme throughout** (#0a0a0a background)
- **Orange accent** (#f97316) for highlights and text
- **Music:** Low, ambient tech. Tension builds in shots 1-2, resolves at shot 3.
- **Pacing:** Let the screenshots breathe. Don't rush. The story sells itself.

### Why This Version Is Better:
- v1 was a generic product demo. Any memory API could make that video.
- v2 shows a REAL agent doing REAL work, hitting a REAL limit, and recovering seamlessly.
- The screenshots are the proof. No synthetic demos. No fake data.
- Developer audience respects authenticity over polish.
