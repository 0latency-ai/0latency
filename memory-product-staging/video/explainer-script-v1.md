# 0Latency Explainer Video — Script v1
## 90 seconds | Animated + Screen Recording Hybrid

---

### SHOT 1: Hook (0:00 - 0:05)
**Visual:** Dark screen. Text types out like a terminal cursor.
**Text on screen:** "Your AI agent forgets everything."
**Narration (Justin):** "Your AI agent forgets everything between sessions."

---

### SHOT 2: The Problem (0:05 - 0:20)
**Visual:** Split screen animation — left side shows a chat with an AI agent. Right side shows the agent's "memory" as a bucket that empties every time the session ends. Each new session starts blank.

**Narration:** "Every conversation starts from zero. Your agent doesn't remember what it learned yesterday, what the user prefers, or what it already tried. Context compaction wipes it clean. You lose work. Your users repeat themselves. Your agent looks dumb."

---

### SHOT 3: The Solution (0:20 - 0:35)
**Visual:** Terminal screen. Clean, dark theme. Type out:

```
pip install zerolatency
```

Then show the code:

```python
from zerolatency import ZeroLatency

zl = ZeroLatency(api_key="zl_live_abc123")
zl.store("User prefers dark mode and metric units")
```

**Narration:** "0Latency gives your agent persistent memory in three lines of code. Install the SDK. Store a memory. That's it."

---

### SHOT 4: The Recall (0:35 - 0:50)
**Visual:** Continue in terminal. Type:

```python
results = zl.recall("What are the user's preferences?")
print(results)
```

Output appears instantly (emphasize speed):

```json
{
  "content": "User prefers dark mode and metric units",
  "relevance": 0.94,
  "latency_ms": 47
}
```

**Narration:** "When your agent needs context, it recalls. Sub-100 millisecond retrieval. The right memory, ranked by relevance, with temporal awareness. Not a vector dump — an active cognitive layer."

---

### SHOT 5: The Differentiator (0:50 - 1:05)
**Visual:** Animated comparison. Left: competitor logo (generic) with "10M tokens stored, 800ms retrieval, stale results." Right: 0Latency logo with "624 memories, 47ms retrieval, built an entire startup."

**Text overlay:** "We built this entire AI startup on 624 memories."

**Narration:** "Other platforms give you massive storage because their retrieval is slow and imprecise. We built an entire AI startup — five agents, 36 state deployments, a full product launch — on just 624 memories. It's not about how much you store. It's about how fast and accurately you get it back."

---

### SHOT 6: Features Flash (1:05 - 1:15)
**Visual:** Quick animated cards flipping in, one per second:
- ⚡ Sub-100ms recall
- 🧠 Temporal decay (recent > stale)
- 🔗 Graph memory (relationship traversal)
- 🚫 Negative recall (knows what to forget)
- 🔒 Multi-tenant isolation
- 🛡️ Built-in secret detection

**Narration:** "Temporal decay. Graph memory. Negative recall. Secret detection. Multi-tenant isolation. Everything your agent needs to think, not just remember."

---

### SHOT 7: CTA (1:15 - 1:25)
**Visual:** Clean landing page hero shot. Orange gradient. The pricing tiers fade in briefly.

**Text on screen:** 
```
10,000 memories free.
pip install zerolatency
0latency.ai
```

**Narration:** "Ten thousand memories. Free. Start building agents that actually remember."

**[END]**

---

## Production Notes

### What Justin Records:
1. **Terminal demo** (Shots 3 & 4) — Real terminal, dark theme, type out the commands live. Use a large font (20pt+). Record at 1920x1080. Pause briefly after each command so we can trim timing in edit.
2. **Voiceover** — Record narration separately in a quiet room. Phone voice memo is fine if the room is quiet. Read slowly and naturally — we can speed up in edit but can't fix rushed delivery.

### What We Build in Canva/After Effects:
- Shot 1: Typing text animation
- Shot 2: Memory bucket emptying animation
- Shot 5: Side-by-side comparison
- Shot 6: Feature cards
- Shot 7: Landing page reveal + CTA

### Style Guide:
- **Colors:** Dark background (#0a0a0a), orange accent (#f97316), white text
- **Font:** JetBrains Mono for code, Inter/Jakarta Sans for UI text
- **Music:** Subtle, techy ambient. Try Uppbeat or Pixabay (both free for commercial use). Something like "Chill Technology" or "Digital Innovation" — not EDM, not corporate.
- **Pacing:** Unhurried but not slow. Each shot earns its seconds.

### File Naming:
- `shot-3-4-terminal-demo.mov` — Screen recording of pip install + code
- `voiceover-full.m4a` — Complete narration
- `voiceover-shot-1.m4a` through `voiceover-shot-7.m4a` — Individual shots (easier to edit)
