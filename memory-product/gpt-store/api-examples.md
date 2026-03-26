# 0Latency Memory - API Examples

Real-world examples of using the 0Latency Memory API through this GPT.

## Example 1: Personal Assistant

**Goal:** Remember user preferences and recall them across conversations.

### Setup Conversation
```
User: Store these preferences:
- I wake up at 6 AM Pacific time
- I prefer email summaries over Slack
- My main projects are TaskFlow (CRM) and BlogBot (content tool)
- I'm allergic to peanuts

GPT: Stored! I've extracted:
- Daily routine: 6 AM wake time (Pacific)
- Communication preference: Email over Slack
- Projects: TaskFlow (CRM), BlogBot (content tool)
- Health info: Peanut allergy

Next time you ask about your schedule, projects, or preferences, I'll recall this.
```

### Later Conversation
```
User: What time should we schedule the morning standup?

GPT: [Calls /recall with context]

Based on what I know, you wake up at 6 AM Pacific time. I'd suggest scheduling 
the standup around 9-10 AM PT to give you time for morning routine and focus work.

Would that work for you?
```

---

## Example 2: Project Context Tracking

**Goal:** Build up context about a software project over time.

### Day 1: Initial Setup
```
User: I'm starting a new project called "FlowState" - a Pomodoro timer with 
AI-powered break suggestions. It'll use React Native for mobile.

GPT: Got it! Stored:
- Project: FlowState
- Type: Pomodoro timer with AI break suggestions
- Tech stack: React Native (mobile)
```

### Day 3: Adding Details
```
User: For FlowState, I've decided on:
- Backend: Python FastAPI
- Database: PostgreSQL for user data, Redis for session state
- AI: OpenAI API for break suggestions

GPT: Updated FlowState context:
- Backend: FastAPI (Python)
- Databases: PostgreSQL (user data), Redis (sessions)
- AI integration: OpenAI API
```

### Week 2: Quick Recall
```
User: What's my backend setup for FlowState again?

GPT: [Calls /recall]

For FlowState, you're using:
- Backend: Python with FastAPI
- Databases: PostgreSQL for user data, Redis for session state
- AI: OpenAI API for generating break suggestions

Want me to recall any other project details?
```

---

## Example 3: Learning Tracker

**Goal:** Track what you're learning and build a knowledge graph.

### Storing Learning
```
User: I just learned that PostgreSQL has a JSONB type that's way faster 
than JSON for queries because it's stored in binary format.

GPT: Stored that insight! Filed under:
- Technology: PostgreSQL
- Feature: JSONB data type
- Key insight: Binary storage enables faster queries vs JSON
- Category: Database optimization
```

### Later Reference
```
User: Search my memories for "PostgreSQL"

GPT: [Calls /memories/search?q=PostgreSQL]

Found 3 memories about PostgreSQL:

1. **JSONB performance** (stored 3 days ago)
   "JSONB type is faster than JSON due to binary storage"

2. **Connection pooling** (stored 1 week ago)
   "Use PgBouncer for connection pooling in production"

3. **Full-text search** (stored 2 weeks ago)
   "Built-in FTS with tsvector and tsquery"

Want details on any of these?
```

---

## Example 4: Customer Context (B2B Use Case)

**Goal:** Remember customer details for a sales or support agent.

### Initial Meeting
```
User: Just had a call with Acme Corp:
- Contact: Sarah Chen (Head of Engineering)
- Company size: 50 engineers
- Pain point: Struggling with agent memory across customer conversations
- Budget: $5K-10K/month
- Timeline: Need solution in Q2
- Tech stack: Python, TypeScript, AWS

GPT: Customer profile stored:

**Acme Corp**
- Key contact: Sarah Chen (Head of Engineering)
- Team size: 50 engineers
- Challenge: Agent memory continuity
- Budget range: $5K-10K/month
- Timeline: Q2 implementation
- Tech: Python, TypeScript, AWS

I'll remember this for future conversations.
```

### Follow-up 2 Weeks Later
```
User: Preparing for follow-up with Acme Corp. What do I need to remember?

GPT: [Calls /recall]

**Acme Corp Context:**

Contact: Sarah Chen (Head of Engineering)

Their challenge: Agent memory across customer conversations—exactly what 
0Latency solves!

Key details:
- Team: 50 engineers
- Budget: $5K-10K/month
- Deadline: Need solution in Q2
- Tech stack: Python, TypeScript, AWS (compatible with our SDKs)

**Suggested talking points:**
1. How 0Latency integrates with their existing Python/TS stack
2. Pricing fit within their budget
3. Q2 implementation timeline
4. Case studies with similar-sized engineering teams

Want me to draft an email?
```

---

## Example 5: Content Creation Assistant

**Goal:** Remember writing style, topics covered, and content calendar.

### Style Guidelines
```
User: Remember my writing style:
- Conversational tone, avoid corporate jargon
- Use short paragraphs (2-3 sentences max)
- Include code examples whenever explaining technical concepts
- Target audience: developers who are new to AI agents

GPT: Writing style guidelines stored:
✓ Tone: Conversational, no jargon
✓ Structure: Short paragraphs (2-3 sentences)
✓ Technical content: Always include code examples
✓ Audience: Developers new to AI agents
```

### Topic Tracking
```
User: I've written articles on:
1. "Getting Started with AI Memory" - published last Monday
2. "Vector Databases Explained" - draft stage
3. "Agent Orchestration Patterns" - outline done

GPT: Content inventory stored:

Published:
- "Getting Started with AI Memory" (last Monday)

In Progress:
- "Vector Databases Explained" (draft)
- "Agent Orchestration Patterns" (outline)
```

### Content Creation
```
User: I need to write about semantic search. What style should I use?

GPT: [Calls /recall]

Based on your writing guidelines:

**Tone:** Conversational, avoid jargon  
**Structure:** Keep paragraphs to 2-3 sentences  
**Must include:** Code examples (since it's technical)  
**Audience:** Developers new to AI agents

**Recommended structure:**
1. Open with a relatable problem
2. Explain semantic search simply (avoid "embeddings" jargon initially)
3. Show a code example with 0Latency API
4. Contrast with keyword search using examples

Want me to draft an outline?
```

---

## Example 6: Health & Fitness Tracking

**Goal:** Remember workouts, nutrition preferences, and goals.

### Storing Fitness Data
```
User: Track this:
- Current weight: 180 lbs (goal: 170 lbs)
- Workout schedule: Monday/Wednesday/Friday mornings
- Diet: Vegetarian, allergic to dairy
- Sleep target: 7-8 hours

GPT: Health profile stored:
- Weight: 180 lbs → Goal: 170 lbs
- Workout days: M/W/F mornings
- Diet: Vegetarian, dairy-free (allergy)
- Sleep goal: 7-8 hours
```

### Progress Updates
```
User: Weighed in at 177 lbs this morning!

GPT: [Updates existing memory]

Great progress! Updated your profile:
- Previous: 180 lbs
- Current: 177 lbs
- Goal: 170 lbs
- Progress: 3 lbs down, 7 lbs to go

You're 30% of the way to your goal! Keep it up 💪
```

### Meal Planning
```
User: Suggest a post-workout breakfast.

GPT: [Calls /recall for dietary restrictions]

Based on your diet (vegetarian, dairy-free), here are some options:

1. **Protein smoothie:** Banana, spinach, pea protein, almond milk, peanut butter
2. **Tofu scramble:** With veggies, avocado, whole grain toast
3. **Overnight oats:** Made with oat milk, topped with berries and nuts

All are dairy-free and vegetarian. Want a recipe for any of these?
```

---

## Example 7: Code Review Context

**Goal:** Remember coding standards, common issues, and team preferences.

### Team Standards
```
User: Our team's code review standards:
- Max function length: 50 lines
- All public functions need docstrings
- Use TypeScript strict mode
- No `any` types allowed
- Prefer functional patterns over classes

GPT: Team code standards stored:
✓ Function length: 50 lines max
✓ Documentation: Docstrings required for public functions
✓ TypeScript: Strict mode, no `any` types
✓ Style: Functional over OOP
```

### Code Review Request
```
User: Review this function:

function processUser(data: any) {
  const user = data.user
  const profile = user.profile
  const settings = profile.settings
  // ... 75 lines of processing
  return result
}

GPT: [Calls /recall for team standards]

**Issues found based on your team standards:**

1. ❌ Uses `any` type (violates no-any rule)
2. ❌ Function is 78 lines (exceeds 50-line limit)
3. ❌ Missing docstring

**Suggested fixes:**

1. Define proper types:
```typescript
interface UserData {
  user: {
    profile: {
      settings: Settings;
    }
  }
}

function processUser(data: UserData): Result {
  // ...
}
```

2. Break into smaller functions (<50 lines each)
3. Add JSDoc comment explaining purpose, params, and return value

Want me to show a refactored version?
```

---

## Example 8: Travel Planning

**Goal:** Remember travel preferences, past trips, and wishlists.

### Preferences
```
User: Travel preferences:
- Prefer direct flights, window seat
- Hotels: 4-star, central location, gym required
- Food: Love street food, allergic to shellfish
- Activities: History/museums over beaches
- Travel style: Solo, budget-conscious but not backpacker

GPT: Travel profile stored:
✈️ Flights: Direct, window seat
🏨 Hotels: 4-star, central, must have gym
🍜 Food: Street food fan, shellfish allergy
🎨 Activities: History & museums
💼 Style: Solo traveler, budget-conscious
```

### Trip Planning
```
User: Planning a week in Tokyo. What should I know?

GPT: [Calls /recall for preferences]

Based on your travel style:

**Hotels:** Look for 4-star in Shinjuku or Shibuya (central, easy access)
- Must confirm: Gym availability

**Food:** 
✓ Street food heaven—try yakitori, takoyaki, ramen
❌ Avoid: Sushi with shellfish (request modifications)

**Activities:** You'll love:
- Tokyo National Museum (full day)
- Senso-ji Temple & Asakusa district
- Imperial Palace East Gardens
- Edo-Tokyo Museum

**Flight:** Book direct from your location, request window seat

**Budget tip:** Get a 7-day JR Pass for trains (saves $$)

Want specific restaurant or hotel recommendations?
```

---

## Common Patterns Across Examples

### 1. Progressive Detail Building
Start with basics, add detail over time:
```
Day 1: "I'm building a CRM"
Day 5: "The CRM will use Python and Supabase"
Day 10: "Added Stripe integration for payments"
```

### 2. Context Recall Before Decisions
Always recall before suggesting:
```
User: What should I have for lunch?
GPT: [Recalls dietary restrictions, allergies, preferences]
```

### 3. Update, Don't Duplicate
```
User: Actually, I switched from PostgreSQL to MySQL
GPT: [Updates existing database preference memory]
```

### 4. Export for Migration
```
User: Export all my project memories
GPT: [Returns JSON export]
User can import this into another system or back it up
```

---

## API Call Patterns

### Extract (Store)
```json
POST /memories/extract
{
  "agent_id": "user_default",
  "messages": [
    {"role": "user", "content": "I prefer React for frontend"},
    {"role": "assistant", "content": "Got it, I'll remember that."}
  ]
}
```

### Recall (Semantic Search)
```json
POST /recall
{
  "agent_id": "user_default",
  "messages": [
    {"role": "user", "content": "What frontend frameworks do I like?"}
  ],
  "limit": 10
}
```

### Search (Keyword)
```
GET /memories/search?agent_id=user_default&q=React&limit=20
```

### List All
```
GET /memories?agent_id=user_default&limit=50&offset=0
```

### Export
```
GET /memories/export?agent_id=user_default
```

---

These patterns work for any domain: project management, customer relations, personal productivity, health tracking, learning, and more. The key is building context incrementally and recalling it when decisions need to be made.
