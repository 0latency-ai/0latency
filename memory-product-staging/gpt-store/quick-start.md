# 0Latency Memory - Quick Start Guide

Get started with persistent AI memory in under 5 minutes.

## What is 0Latency Memory?

0Latency gives AI agents the ability to remember information across conversations. Store facts, preferences, and context—then recall them instantly when needed.

## How It Works

1. **Extract:** Send conversation messages → API extracts structured memories
2. **Store:** Memories are saved with semantic embeddings for search
3. **Recall:** Ask a question → API returns relevant memories ranked by relevance

## Setup (One-Time)

### 1. Get Your API Key

1. Visit https://0latency.ai
2. Sign up (free tier available)
3. Go to Dashboard
4. Copy your API key

### 2. Configure This GPT

1. In the GPT chat interface, look for "Configure" or "Settings"
2. Paste your API key when prompted
3. Test with: `Is the API working?`

You're ready! 🎉

## Basic Usage

### Store a Memory

Simply tell the GPT what to remember:

```
Store this memory: I prefer React for frontend development
```

The GPT will:
- Extract the preference
- Store it with context
- Confirm storage

### Recall Information

Ask questions naturally:

```
What frontend frameworks do I like?
```

The GPT will:
- Search stored memories
- Return relevant context
- Cite specific memories

### Search by Keyword

```
Search my memories for "React"
```

Returns all memories containing "React".

### List All Memories

```
Show me all my stored memories
```

View everything you've stored, paginated.

## Agent IDs

Memories are organized by `agent_id`. By default, this GPT uses `"user_default"` for your personal memories.

**Why it matters:**
- Different agents can have separate memory spaces
- Useful for multi-user systems or role-specific contexts
- You can export/import memories per agent

**Custom agent ID:**
```
Use agent_id "my_project_bot" for this conversation
```

## Memory Types

The API automatically categorizes memories:

- **facts**: Direct statements ("Python is my main language")
- **preferences**: Opinions and likes ("I prefer dark mode")
- **entities**: People, places, things ("Acme Corp", "New York")
- **relationships**: Connections ("works at", "located in")

You don't need to specify the type—it's inferred automatically.

## Common Patterns

### Store Preferences
```
Remember that I:
- Work in Pacific timezone
- Prefer concise responses
- Use VS Code as my editor
```

### Build Context Over Time
```
Day 1: Store this: I'm building a CRM for real estate agents
Day 2: Recall what I'm building → (returns CRM context)
Day 3: Store this: The CRM will use Python and PostgreSQL
Day 4: What tech stack am I using? → (returns Python, PostgreSQL)
```

### Export for Backup
```
Export all my memories as JSON
```

Save this file for:
- Backup
- Data portability
- Analysis
- Migration to another system

## Pro Tips

### 1. Be Explicit
Instead of: "I like Python"  
Better: "I prefer Python for backend development because it's readable and has great libraries"

More context = better recall.

### 2. Update, Don't Duplicate
If a preference changes:
```
Actually, I now prefer Go over Python for backend work
```

The GPT will update existing memories instead of creating duplicates.

### 3. Use Search for Precision
- **Recall:** Semantic, best for questions ("What do I use for backend?")
- **Search:** Keyword-based, best for exact terms ("Find all mentions of 'PostgreSQL'")

### 4. Batch Related Info
Store related facts together:
```
Store these details about my project:
- Name: TaskFlow
- Stack: Next.js, Supabase, TailwindCSS
- Target: Solo developers and small teams
```

Single extraction, related memories.

## Limitations

**What it can do:**
✅ Store structured facts and preferences  
✅ Recall relevant context semantically  
✅ Search by keywords  
✅ Handle multiple agents/contexts  
✅ Export all data  

**What it can't do:**
❌ Store arbitrary files (text/structured data only)  
❌ Store extremely long documents (chunk them first)  
❌ Real-time conversation state (use messages array instead)  
❌ Cross-tenant data access (strict isolation)  

## Privacy & Data Ownership

- **Your data is yours.** You can export and delete anytime.
- **Tenant isolation:** Your memories are never visible to other users.
- **No training:** Your data is not used to train models.
- **GDPR compliant:** Full export and deletion capabilities.

## Pricing

Check https://0latency.ai/pricing for current tiers.

**Free tier includes:**
- 1,000 extractions/month
- 10,000 recalls/month
- Full API access
- Export capabilities

**Paid tiers offer:**
- Higher limits
- Faster processing
- Priority support
- Advanced features (graph queries, webhooks)

## Next Steps

### Learn More
- **Full API docs:** https://0latency.ai/docs
- **API reference:** https://0latency.ai/api-docs.json
- **Use case examples:** See `use-cases.md`

### Advanced Features
- Knowledge graph queries (entity relationships)
- Webhooks (get notified when memories are created)
- Custom extraction schemas
- Batch operations

### Get Help
- **Email:** support@0latency.ai
- **Docs:** https://0latency.ai/docs
- **API status:** https://status.0latency.ai

---

Ready to give your AI a memory that lasts? Start storing memories now! 🧠
