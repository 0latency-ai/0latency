# Zero Latency Memory API Reference

Complete documentation for all API endpoints, request/response formats, and error handling.

## Base URL

```
https://164.90.156.169
```

## Authentication

All API endpoints (except health check) require authentication via API key header:

```
X-API-Key: zl_live_<32-character-string>
```

### Example
```bash
curl -H "X-API-Key: zl_live_abc123..." https://164.90.156.169/api/health
```

## Endpoints

### Memory Operations

#### POST /api/extract

Extract and store memories from a conversation turn.

**Request Body:**
```json
{
  "agent_id": "string",           // Required: Unique identifier for the agent
  "human_message": "string",      // Required: User's message
  "agent_message": "string",      // Required: Agent's response  
  "session_key": "string",        // Optional: Session identifier
  "turn_id": "string"            // Optional: Turn identifier within session
}
```

**Response:**
```json
{
  "memories_stored": 3,
  "memory_ids": [
    "uuid-1",
    "uuid-2", 
    "uuid-3"
  ]
}
```

**Memory Extraction Logic:**
- Automatically identifies facts, preferences, decisions, relationships
- Detects and handles contradictions with existing memories
- Assigns importance scores (0.0-1.0)
- Creates entity relationships for cross-memory linking

**Example:**
```bash
curl -X POST https://164.90.156.169/api/extract \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "assistant_v1",
    "human_message": "I just moved to Berlin and started a new job at Spotify",
    "agent_message": "Congratulations on your move to Berlin and your new position at Spotify!",
    "session_key": "onboarding_2026",
    "turn_id": "001"
  }'
```

---

#### POST /api/recall

Retrieve contextually relevant memories for a conversation.

**Request Body:**
```json
{
  "agent_id": "string",           // Required: Agent identifier
  "conversation_context": "string", // Required: Current conversation context
  "budget_tokens": 4000,          // Optional: Max tokens for response (500-16000)
  "dynamic_budget": false         // Optional: Auto-adjust budget based on relevance
}
```

**Response:**
```json
{
  "context_block": "## Remembered Context\n\n**Location:**\n- Recently moved to Berlin...",
  "memories_used": 5,
  "tokens_used": 342
}
```

**Recall Algorithm:**
- Semantic similarity search using embeddings
- Importance-weighted scoring
- Recency bias (newer memories weighted higher)
- Budget-aware truncation with smart summarization

**Budget Guidelines:**
- **500-1000**: Essential facts only
- **2000-4000**: Good balance for most use cases  
- **8000+**: Comprehensive context for complex conversations

**Example:**
```bash
curl -X POST https://164.90.156.169/api/recall \
  -H "X-API-Key: zl_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "assistant_v1",
    "conversation_context": "User is asking about music recommendations for their commute",
    "budget_tokens": 2000,
    "dynamic_budget": true
  }'
```

---

#### GET /api/memories

List memories for an agent with optional filtering.

**Query Parameters:**
- `agent_id` (required): Agent identifier
- `limit` (optional): Max results (default: 50, max: 200)
- `memory_type` (optional): Filter by type (fact, preference, decision, etc.)

**Response:**
```json
[
  {
    "id": "uuid-123",
    "headline": "Lives in Berlin",
    "memory_type": "fact",
    "importance": 0.8,
    "created_at": "2026-03-20T22:15:30.123Z"
  },
  {
    "id": "uuid-456", 
    "headline": "Works at Spotify",
    "memory_type": "fact",
    "importance": 0.7,
    "created_at": "2026-03-20T22:15:30.456Z"
  }
]
```

**Memory Types:**
- `fact`: Factual information
- `preference`: Personal preferences  
- `decision`: Decisions made
- `relationship`: Relationship information
- `task`: Action items or TODOs
- `correction`: Updates to previous facts
- `identity`: Core identity information (never decays)

**Example:**
```bash
# Get all memories
curl "https://164.90.156.169/api/memories?agent_id=assistant_v1&limit=20" \
  -H "X-API-Key: zl_live_..."

# Get only preferences  
curl "https://164.90.156.169/api/memories?agent_id=assistant_v1&memory_type=preference" \
  -H "X-API-Key: zl_live_..."
```

---

### Account Management

#### GET /api/tenant-info

Get information about the current tenant.

**Response:**
```json
{
  "id": "uuid-tenant",
  "name": "My Company", 
  "plan": "pro",
  "memory_limit": 50000,
  "rate_limit_rpm": 100,
  "api_calls_count": 1542
}
```

**Example:**
```bash
curl https://164.90.156.169/api/tenant-info \
  -H "X-API-Key: zl_live_..."
```

---

### Admin Endpoints

*Require `X-Admin-Key` header with master admin key.*

#### POST /api/api-keys

Create a new tenant and API key.

**Request Body:**
```json
{
  "name": "New Company",
  "plan": "pro"              // free, pro, or enterprise
}
```

**Response:**
```json
{
  "tenant_id": "uuid-new-tenant",
  "name": "New Company",
  "api_key": "zl_live_new32characterstring...", 
  "plan": "pro",
  "created_at": "2026-03-20T22:30:15.123Z",
  "memory_limit": 50000,
  "rate_limit_rpm": 100
}
```

**Example:**
```bash
curl -X POST https://164.90.156.169/api/api-keys \
  -H "X-Admin-Key: admin_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "plan": "enterprise" 
  }'
```

---

#### GET /admin/tenants

List all tenants (admin only).

**Response:**
```json
{
  "tenants": [
    {
      "id": "uuid-1",
      "name": "Company A",
      "plan": "pro",
      "memory_limit": 50000,
      "rate_limit_rpm": 100,
      "active": true,
      "api_calls_count": 1542,
      "created_at": "2026-03-15T10:30:00Z"
    }
  ]
}
```

---

### System Endpoints

#### GET /health

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0", 
  "timestamp": "2026-03-20T22:35:45.941Z",
  "memories_total": null
}
```

**Example:**
```bash
curl https://164.90.156.169/health
```

---

## Error Handling

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (invalid/missing API key)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

### Common Errors

#### 401 Unauthorized
```json
{"detail": "Invalid API key"}
```
**Causes:**
- Missing `X-API-Key` header
- Malformed API key (not `zl_live_...` format)
- Expired or deactivated key
- Inactive tenant account

#### 429 Rate Limit Exceeded  
```json
{"detail": "Rate limit exceeded (100/min). Try again in 60 seconds."}
```
**Solution:** Wait 60 seconds or upgrade to higher plan.

#### 400 Bad Request
```json  
{"detail": "Field validation error: agent_id is required"}
```
**Causes:**
- Missing required fields
- Invalid parameter values
- Malformed JSON

#### 500 Internal Server Error
```json
{"detail": "Memory extraction failed: insufficient context"}
```
**Causes:**
- Server-side processing errors
- Database connectivity issues
- Embedding service unavailable

---

## Rate Limits

Rate limits are enforced per tenant, not per API key.

| Plan | Requests/Minute | Memory Limit |
|------|----------------|--------------|
| Free | 20 | 1,000 |
| Pro | 100 | 50,000 |
| Enterprise | 500 | 500,000 |

**Rate Limit Headers:**
Response headers include current usage:
- `X-RateLimit-Limit`: Requests allowed per window
- `X-RateLimit-Remaining`: Requests remaining in current window  
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Memory Lifecycle

### Storage
1. **Extraction**: Conversation parsed for factual content
2. **Classification**: Memories categorized by type
3. **Embedding**: Vector embeddings generated for semantic search
4. **Deduplication**: Similar memories merged or reinforced
5. **Storage**: Persisted with metadata and relationships

### Decay
Memories naturally decay over time unless reinforced:

| Type | Decay Rate | Notes |
|------|------------|--------|
| `identity` | Never | Core identity facts persist |
| `preference` | 0.1%/day | Personal preferences fade slowly |
| `correction` | 0.1%/day | Corrections remain important |
| `relationship` | 0.2%/day | Relationship info moderately stable |
| `decision` | 0.5%/day | Decisions become less relevant |
| `fact` | 2%/day | General facts fade normally |
| `task` | 3%/day | Tasks should be completed quickly |

### Reinforcement
Memories gain importance when:
- Referenced multiple times
- Mentioned in corrections
- Connected to other important memories
- Explicitly marked as important

---

## SDK Examples

### Python SDK (Requests)

```python
import requests
from typing import List, Dict, Optional

class MemoryAPI:
    def __init__(self, api_key: str, base_url: str = "https://164.90.156.169"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    def extract(self, agent_id: str, human_msg: str, agent_msg: str, 
                session_key: Optional[str] = None, turn_id: Optional[str] = None) -> Dict:
        """Extract memories from a conversation turn."""
        payload = {
            "agent_id": agent_id,
            "human_message": human_msg, 
            "agent_message": agent_msg
        }
        if session_key:
            payload["session_key"] = session_key
        if turn_id:
            payload["turn_id"] = turn_id
            
        resp = requests.post(f"{self.base_url}/api/extract", 
                           headers=self.headers, json=payload, verify=False)
        resp.raise_for_status()
        return resp.json()
    
    def recall(self, agent_id: str, context: str, budget: int = 4000, 
               dynamic: bool = False) -> Dict:
        """Recall relevant memories."""
        payload = {
            "agent_id": agent_id,
            "conversation_context": context,
            "budget_tokens": budget,
            "dynamic_budget": dynamic
        }
        resp = requests.post(f"{self.base_url}/api/recall",
                           headers=self.headers, json=payload, verify=False) 
        resp.raise_for_status()
        return resp.json()
        
    def list_memories(self, agent_id: str, limit: int = 50, 
                     memory_type: Optional[str] = None) -> List[Dict]:
        """List memories for an agent."""
        params = {"agent_id": agent_id, "limit": limit}
        if memory_type:
            params["memory_type"] = memory_type
            
        resp = requests.get(f"{self.base_url}/api/memories",
                          headers=self.headers, params=params, verify=False)
        resp.raise_for_status()  
        return resp.json()

# Usage
memory = MemoryAPI("zl_live_your_key_here")

# Extract memories
result = memory.extract("assistant_v1", 
                       "I love hiking in the mountains", 
                       "That's great! Mountain hiking is wonderful exercise.")
print(f"Stored {result['memories_stored']} memories")

# Recall context  
context = memory.recall("assistant_v1", 
                       "User is asking about outdoor activities")
print(context["context_block"])
```

### Node.js SDK (Axios)

```javascript
const axios = require('axios');

class MemoryAPI {
    constructor(apiKey, baseUrl = 'https://164.90.156.169') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = { 'X-API-Key': apiKey };
        
        // Disable SSL verification for self-signed certs
        process.env["NODE_TLS_REJECT_UNAUTHORIZED"] = 0;
    }
    
    async extract(agentId, humanMsg, agentMsg, sessionKey = null, turnId = null) {
        const payload = {
            agent_id: agentId,
            human_message: humanMsg,
            agent_message: agentMsg
        };
        if (sessionKey) payload.session_key = sessionKey;
        if (turnId) payload.turn_id = turnId;
        
        const resp = await axios.post(`${this.baseUrl}/api/extract`, payload, {
            headers: this.headers
        });
        return resp.data;
    }
    
    async recall(agentId, context, budget = 4000, dynamic = false) {
        const payload = {
            agent_id: agentId,
            conversation_context: context, 
            budget_tokens: budget,
            dynamic_budget: dynamic
        };
        
        const resp = await axios.post(`${this.baseUrl}/api/recall`, payload, {
            headers: this.headers
        });
        return resp.data;
    }
}

// Usage
const memory = new MemoryAPI('zl_live_your_key_here');

memory.extract('assistant_v1', 'I work in tech', 'Interesting! What area of tech?')
    .then(result => console.log(`Stored ${result.memories_stored} memories`));
```

---

## Interactive API Explorer

Visit **https://164.90.156.169/docs** for an interactive Swagger UI where you can:

- Browse all endpoints with detailed schemas
- Test API calls directly from your browser  
- View request/response examples
- Download OpenAPI specification

## Support & Troubleshooting

### Debug Tips
1. **Check API Key Format**: Must start with `zl_live_` and be 40 characters total
2. **Verify HTTPS**: Use `https://` not `http://` 
3. **Handle Self-Signed Certs**: Use `verify=False` in requests or equivalent
4. **Monitor Rate Limits**: Check response headers for usage
5. **Validate JSON**: Ensure request bodies are valid JSON

### Performance Tips
1. **Batch Operations**: Group multiple memory operations when possible
2. **Optimize Context**: Keep conversation context concise but descriptive
3. **Use Dynamic Budget**: Enable for variable-length contexts
4. **Cache Results**: Store recall results temporarily to reduce API calls

---

**Last Updated:** March 20, 2026  
**API Version:** 0.1.0