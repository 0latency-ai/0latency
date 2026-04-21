# Example 3: Customer Support Agent with Memory

Build a support agent that remembers customer history, preferences, and past issues.

**What you'll build:** A support ticket system that:
- Recalls previous support interactions
- Remembers customer preferences and pain points
- Provides context-aware responses
- Never asks customers to repeat themselves

**Time:** ~20 minutes  
**Difficulty:** Intermediate

---

## The Problem

Standard support systems have amnesia:

```
Ticket #1 (Jan 5):
Customer: "My export feature is broken"
Agent: "Let me help you with that..."
[Issue resolved]

Ticket #2 (Jan 20):
Customer: "The export feature is broken AGAIN"
Agent: "What seems to be the issue?" 😞
Customer: "I JUST told you this 2 weeks ago!" 😡
```

With memory, your support agent knows:
- What issues this customer had before
- What solutions worked (or didn't)
- Customer's technical level, preferences, frustrations
- Account details, usage patterns

Let's build it.

---

## Full Working Code

```python
#!/usr/bin/env python3
"""
Customer support agent with 0Latency memory.
Remembers everything about every customer.
"""

import os
from datetime import datetime
from zerolatency import Memory
import openai

# Initialize
mem = Memory(os.getenv("ZEROLATENCY_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")

def handle_ticket(customer_id: str, ticket_message: str, ticket_id: str = None) -> str:
    """
    Handle a support ticket with full customer context.
    
    Args:
        customer_id: Unique customer identifier
        ticket_message: Customer's support request
        ticket_id: Optional ticket ID for tracking
    
    Returns:
        Agent's response message
    """
    
    agent_id = f"support_{customer_id}"
    
    # Step 1: Recall customer history
    print(f"🔍 Recalling context for customer {customer_id}...")
    
    recall_result = mem.recall(
        agent_id=agent_id,
        conversation_context=ticket_message,
        budget_tokens=3000
    )
    
    context_block = recall_result["context_block"]
    memories_used = recall_result["memories_used"]
    
    print(f"   ✅ Found {memories_used} relevant memories\n")
    
    # Step 2: Build support prompt with context
    system_prompt = """You are an expert customer support agent.

You have access to the customer's full history with our product.

Key guidelines:
- Be empathetic and helpful
- Reference past issues if relevant
- Acknowledge frustration if this is a recurring problem
- Suggest solutions based on what worked before
- Be concise but thorough
"""

    user_prompt = f"""Customer Support Ticket

{context_block}

---

**New Ticket:**
{ticket_message}

**Instructions:** Provide a helpful response that acknowledges the customer's history and context."""

    # Step 3: Get LLM response
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    
    agent_message = response.choices[0].message.content
    
    # Step 4: Store the ticket interaction
    mem.add(
        agent_id=agent_id,
        human_message=ticket_message,
        agent_message=agent_message,
        session_key=ticket_id or f"ticket_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    
    return agent_message


def get_customer_summary(customer_id: str) -> dict:
    """Get a summary of customer's support history."""
    
    agent_id = f"support_{customer_id}"
    
    # List all memories for this customer
    memories = mem.list_memories(
        agent_id=agent_id,
        limit=50
    )
    
    # Count by type
    summary = {
        "total_memories": len(memories),
        "facts": len([m for m in memories if m["memory_type"] == "fact"]),
        "preferences": len([m for m in memories if m["memory_type"] == "preference"]),
        "decisions": len([m for m in memories if m["memory_type"] == "decision"]),
        "tasks": len([m for m in memories if m["memory_type"] == "task"]),
        "corrections": len([m for m in memories if m["memory_type"] == "correction"]),
    }
    
    # Get recent issues (search for "issue", "problem", "bug", "error")
    recent_issues = mem.search_memories(
        agent_id=agent_id,
        query="issue problem bug error",
        limit=10
    )
    
    summary["recent_issues"] = [
        {
            "headline": issue["headline"],
            "created_at": issue["created_at"]
        }
        for issue in recent_issues
    ]
    
    return summary


# Example usage
if __name__ == "__main__":
    # Simulate ticket flow
    customer_id = "cust_12345"
    
    print("=" * 60)
    print("Customer Support Agent with Memory")
    print("=" * 60 + "\n")
    
    # Ticket 1: Initial issue
    print("📩 TICKET #1 (Jan 5, 2026)")
    print("-" * 60)
    
    ticket_1 = """Hi, I'm having trouble with the CSV export feature. 
When I try to export my data, I get an error saying 'File format not supported'.
I'm using Chrome on macOS."""
    
    print(f"Customer: {ticket_1}\n")
    
    response_1 = handle_ticket(
        customer_id=customer_id,
        ticket_message=ticket_1,
        ticket_id="ticket_001"
    )
    
    print(f"Agent: {response_1}\n")
    
    # Ticket 2: Follow-up
    print("\n📩 TICKET #2 (Jan 8, 2026)")
    print("-" * 60)
    
    ticket_2 = """Thanks for the fix! The export works now. 
One more thing: can I export to Excel format instead of CSV?"""
    
    print(f"Customer: {ticket_2}\n")
    
    response_2 = handle_ticket(
        customer_id=customer_id,
        ticket_message=ticket_2,
        ticket_id="ticket_002"
    )
    
    print(f"Agent: {response_2}\n")
    
    # Ticket 3: Recurring issue (weeks later)
    print("\n📩 TICKET #3 (Jan 25, 2026)")
    print("-" * 60)
    
    ticket_3 = """The export feature is broken again! Same error as before."""
    
    print(f"Customer: {ticket_3}\n")
    
    response_3 = handle_ticket(
        customer_id=customer_id,
        ticket_message=ticket_3,
        ticket_id="ticket_003"
    )
    
    print(f"Agent: {response_3}\n")
    
    # Get customer summary
    print("\n📊 CUSTOMER SUMMARY")
    print("-" * 60)
    summary = get_customer_summary(customer_id)
    print(f"Total memories: {summary['total_memories']}")
    print(f"Facts: {summary['facts']}")
    print(f"Preferences: {summary['preferences']}")
    print(f"Recent issues:")
    for issue in summary['recent_issues'][:5]:
        print(f"  - {issue['headline']}")
    print()
```

---

## Example Output

```
============================================================
Customer Support Agent with Memory
============================================================

📩 TICKET #1 (Jan 5, 2026)
------------------------------------------------------------
Customer: Hi, I'm having trouble with the CSV export feature. 
When I try to export my data, I get an error saying 'File format not supported'.
I'm using Chrome on macOS.

🔍 Recalling context for customer cust_12345...
   ✅ Found 0 relevant memories (first ticket!)

Agent: I'm sorry to hear you're having trouble with the CSV export feature. Let me help you resolve this.

The "File format not supported" error typically occurs when there's a browser compatibility issue or cached data causing conflicts. Here's what I recommend:

1. **Clear your browser cache** for our site specifically
2. **Try the export again** after refreshing the page
3. If that doesn't work, **try Safari** as an alternative

Since you're on macOS with Chrome, this should resolve the issue. Let me know if you continue to see the error after trying these steps!

📩 TICKET #2 (Jan 8, 2026)
------------------------------------------------------------
Customer: Thanks for the fix! The export works now. 
One more thing: can I export to Excel format instead of CSV?

🔍 Recalling context for customer cust_12345...
   ✅ Found 3 relevant memories

Agent: Great to hear the CSV export is working for you now!

I see you previously had issues with the export feature on Chrome/macOS, so I'm glad we got that sorted.

Regarding Excel format: **Yes, we support Excel exports!** Here's how:

1. Click the "Export" button as usual
2. You'll see a dropdown with format options
3. Select "Excel (.xlsx)" instead of "CSV"

The Excel export includes formatting, multiple sheets (if applicable), and better handles special characters. Let me know if you have any trouble finding the format dropdown!

📩 TICKET #3 (Jan 25, 2026)
------------------------------------------------------------
Customer: The export feature is broken again! Same error as before.

🔍 Recalling context for customer cust_12345...
   ✅ Found 5 relevant memories

Agent: I'm really sorry you're experiencing this issue again. I can see you had the same "File format not supported" error back on January 5th, which we resolved by clearing your browser cache.

Since this is recurring, let me suggest a more permanent fix:

**Root cause:** This appears to be related to Chrome's handling of downloads on macOS. Here's what I recommend:

1. **Update Chrome** to the latest version
2. **Check Chrome's download settings** (chrome://settings/downloads) and ensure the default download location is accessible
3. **Whitelist our domain** in Chrome's security settings

**Immediate workaround:** Use Safari for exports (which worked for you before), or try the **Excel format option** you discovered in January.

I'm also **escalating this to our engineering team** as a bug report, since you shouldn't have to deal with this repeatedly. I'll follow up once we have a permanent fix.

I really appreciate your patience with this!

📊 CUSTOMER SUMMARY
------------------------------------------------------------
Total memories: 8
Facts: 3
Preferences: 2
Recent issues:
  - Export feature error: 'File format not supported' (Chrome, macOS)
  - Prefers Excel format over CSV
  - Recurring export issues - escalated to engineering
```

---

## Key Concepts

### Customer-Specific Memory Spaces

```python
agent_id = f"support_{customer_id}"
```

Each customer gets their own memory space:
- `support_cust_12345` → Customer 12345's history
- `support_cust_67890` → Customer 67890's history

This ensures customer data stays isolated.

### Context-Aware Responses

Notice how the agent:
1. **Ticket 1:** No context (first interaction) → Generic helpful response
2. **Ticket 2:** Recalls previous export issue → Acknowledges past problem
3. **Ticket 3:** Recalls **recurring** issue → Empathizes, escalates, suggests workarounds

The more history, the better the support experience.

### Session Keys for Ticket Tracking

```python
session_key=ticket_id or f"ticket_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
```

Groups memories by ticket:
- Easy to export ticket history
- Filter memories by specific conversations
- Analyze patterns per ticket type

---

## Production Enhancements

### 1. Add Sentiment Analysis

```python
from zerolatency import Memory

mem = Memory(api_key)

# Get frustrated customers (negative sentiment)
frustrated_customers = mem.list_memories(
    agent_id=agent_id,
    sentiment="negative",
    limit=10
)

# Flag for priority handling
if frustrated_customers:
    print("⚠️ Customer may be frustrated - prioritize this ticket")
```

### 2. Detect Recurring Issues

```python
def check_recurring_issue(customer_id: str, current_issue: str) -> bool:
    """Check if customer has reported this issue before."""
    
    agent_id = f"support_{customer_id}"
    
    # Search for similar past issues
    past_issues = mem.search_memories(
        agent_id=agent_id,
        query=current_issue,
        limit=5
    )
    
    # Filter for issues (not just any mention)
    actual_issues = [
        issue for issue in past_issues
        if any(word in issue["headline"].lower() for word in ["error", "issue", "problem", "bug", "broken"])
    ]
    
    if len(actual_issues) >= 2:
        print(f"⚠️ RECURRING ISSUE: Customer has reported this {len(actual_issues)} times")
        return True
    
    return False
```

### 3. Auto-Tag Customers

```python
def tag_customer(customer_id: str):
    """Automatically tag customers based on behavior."""
    
    agent_id = f"support_{customer_id}"
    memories = mem.list_memories(agent_id=agent_id, limit=100)
    
    tags = []
    
    # Power user (many questions, detailed feedback)
    if len(memories) > 20:
        tags.append("power_user")
    
    # Churned (mentioned cancellation or refund)
    if any("cancel" in m["headline"].lower() or "refund" in m["headline"].lower() 
           for m in memories):
        tags.append("at_risk")
    
    # Happy customer (positive sentiment)
    positive_count = len([m for m in memories if m.get("sentiment") == "positive"])
    if positive_count > 5:
        tags.append("happy")
    
    return tags
```

### 4. Priority Routing

```python
def get_ticket_priority(customer_id: str, ticket_message: str) -> str:
    """Determine ticket priority based on history."""
    
    agent_id = f"support_{customer_id}"
    
    # Check for recurring issues
    is_recurring = check_recurring_issue(customer_id, ticket_message)
    
    # Check sentiment
    memories = mem.list_memories(agent_id=agent_id, limit=10)
    recent_negative = len([m for m in memories if m.get("sentiment") == "negative"]) > 3
    
    # Check urgency keywords
    urgent_keywords = ["urgent", "critical", "down", "broken", "losing money"]
    is_urgent = any(keyword in ticket_message.lower() for keyword in urgent_keywords)
    
    if is_urgent or (is_recurring and recent_negative):
        return "P0_CRITICAL"
    elif is_recurring or recent_negative:
        return "P1_HIGH"
    else:
        return "P2_NORMAL"
```

---

## Integrations

### Zendesk

```python
from zenpy import Zenpy

# Initialize Zendesk client
zendesk = Zenpy(
    subdomain='your-subdomain',
    email='agent@company.com',
    token='your-api-token'
)

def handle_zendesk_ticket(ticket_id: int):
    """Process Zendesk ticket with memory."""
    
    # Fetch ticket
    ticket = zendesk.tickets(id=ticket_id)
    customer_email = ticket.requester.email
    
    # Handle with memory
    response = handle_ticket(
        customer_id=customer_email,
        ticket_message=ticket.description,
        ticket_id=f"zendesk_{ticket_id}"
    )
    
    # Post response
    ticket.comment = Comment(body=response, public=True)
    zendesk.tickets.update(ticket)
```

### Intercom

```python
from intercom.client import Client

intercom = Client(personal_access_token='your-token')

def handle_intercom_conversation(conversation_id: str):
    """Process Intercom conversation with memory."""
    
    conversation = intercom.conversations.find(id=conversation_id)
    customer_id = conversation.user.id
    last_message = conversation.conversation_parts[-1].body
    
    # Handle with memory
    response = handle_ticket(
        customer_id=customer_id,
        ticket_message=last_message,
        ticket_id=f"intercom_{conversation_id}"
    )
    
    # Reply
    intercom.conversations.reply(
        id=conversation_id,
        type='user',
        message_type='comment',
        body=response
    )
```

### Slack

```python
from slack_sdk import WebClient

slack = WebClient(token='xoxb-your-bot-token')

def handle_slack_support_thread(channel_id: str, thread_ts: str):
    """Process Slack support thread with memory."""
    
    # Fetch thread messages
    thread = slack.conversations_replies(
        channel=channel_id,
        ts=thread_ts
    )
    
    customer_id = thread['messages'][0]['user']
    last_message = thread['messages'][-1]['text']
    
    # Handle with memory
    response = handle_ticket(
        customer_id=customer_id,
        ticket_message=last_message,
        ticket_id=f"slack_{thread_ts}"
    )
    
    # Reply in thread
    slack.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=response
    )
```

---

## Metrics & Analytics

### Track Resolution Time

```python
def analyze_resolution_efficiency(customer_id: str):
    """Analyze how memory improves resolution time."""
    
    agent_id = f"support_{customer_id}"
    
    # Get all tickets
    memories = mem.list_memories(agent_id=agent_id, limit=100)
    
    # Group by session (ticket)
    tickets = {}
    for memory in memories:
        session = memory.get("session_key", "unknown")
        if session not in tickets:
            tickets[session] = []
        tickets[session].append(memory)
    
    # Calculate messages per ticket (lower = faster resolution)
    messages_per_ticket = [len(messages) for messages in tickets.values()]
    avg_messages = sum(messages_per_ticket) / len(messages_per_ticket)
    
    return {
        "total_tickets": len(tickets),
        "avg_messages_per_ticket": avg_messages,
        "memory_count": len(memories)
    }
```

### Customer Health Score

```python
def calculate_health_score(customer_id: str) -> float:
    """Calculate customer health score (0-100)."""
    
    agent_id = f"support_{customer_id}"
    memories = mem.list_memories(agent_id=agent_id, limit=50)
    
    if not memories:
        return 50.0  # Neutral (no data)
    
    # Factor 1: Sentiment (40%)
    positive = len([m for m in memories if m.get("sentiment") == "positive"])
    negative = len([m for m in memories if m.get("sentiment") == "negative"])
    sentiment_score = (positive - negative * 2) / len(memories) * 40
    
    # Factor 2: Issue frequency (30%)
    issues = [m for m in memories if any(
        word in m["headline"].lower() 
        for word in ["error", "issue", "problem", "bug", "broken"]
    )]
    issue_score = max(0, 30 - len(issues) * 3)
    
    # Factor 3: Engagement (30%)
    engagement_score = min(30, len(memories) * 2)
    
    total = 50 + sentiment_score + issue_score + engagement_score
    return max(0, min(100, total))
```

---

## Best Practices

### 1. Always Include Context

```python
# ✅ Good
recall_result = mem.recall(
    agent_id=agent_id,
    conversation_context=ticket_message,
    budget_tokens=3000
)

# ❌ Bad (no context = no relevance)
recall_result = mem.recall(
    agent_id=agent_id,
    conversation_context="",  # Empty!
    budget_tokens=3000
)
```

### 2. Use Session Keys

```python
# ✅ Good - trackable
mem.add(
    agent_id=agent_id,
    human_message=ticket_message,
    agent_message=response,
    session_key=f"ticket_{ticket_id}"
)

# ❌ Bad - no ticket grouping
mem.add(
    agent_id=agent_id,
    human_message=ticket_message,
    agent_message=response
)
```

### 3. Handle Rate Limits

```python
import time
from zerolatency import Memory

def safe_recall(agent_id: str, context: str, retries=3):
    """Recall with retry logic."""
    for attempt in range(retries):
        try:
            return mem.recall(
                agent_id=agent_id,
                conversation_context=context,
                budget_tokens=3000
            )
        except Exception as e:
            if "429" in str(e):  # Rate limit
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"⚠️ Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    
    raise Exception("Max retries exceeded")
```

---

## Next Steps

### 📘 More Examples
- [Simple Chatbot](./chatbot.md) — Basic memory implementation
- [Claude Code Integration](./claude-code.md) — Add memory to Claude

### 📖 Deep Dives
- [Memory Types](../memory-types.md) — What gets extracted
- [Graph API](../graph-api.md) — Navigate customer relationships
- [Webhooks](../webhooks.md) — Real-time memory events

---

## Questions?

- 💬 [Discord Community](https://discord.gg/0latency)
- 📧 Email: support@0latency.ai
- 🐛 [Report a Bug](https://github.com/jghiglia2380/0Latency/issues)

---

**Your support team now has a memory.** Never ask customers to repeat themselves again.

