# MCP Tools

Auto-generated inventory of all MCP tools exposed via the Model Context Protocol server.

Source: /tmp/mcp-server-fresh/src/tools.ts

## Tool Inventory

| Tool Name | HTTP Endpoint | Method | Input Schema Fields | Description |
|-----------|---------------|--------|---------------------|-------------|
| memory_add | /memories/extract | POST | agent_id (optional), human_message, agent_message, session_key (optional), turn_id (optional) | Extract and store memories from a conversation turn |
| memory_write | /memories/seed | POST | content, memory_type, agent_id (optional), metadata (optional), importance (default: 0.5) | Store a single memory directly (bypasses extraction pipeline). Rate limited to 30 calls/min, with deduplication |
| memory_recall | /recall | POST | agent_id (optional), conversation_context, budget_tokens (default: 4000), dynamic_budget (default: false) | Recall relevant memories for a conversation context |
| memory_search | /memories/search | GET | agent_id (optional), q, limit (default: 20) | Search memories by text query |
| memory_list | /memories | GET | agent_id (optional), memory_type (optional), limit (default: 50), offset (default: 0) | List stored memories with optional filters and pagination |
| memory_delete | /memories/{memory_id} | DELETE | memory_id | Delete a specific memory by UUID |
| list_agents | /agents | GET | (none) | List all agent namespaces for the tenant with memory counts |
| memory_history | /memories/{memory_id}/history | GET | memory_id | Get version history for a specific memory |
| memory_graph_traverse | /graph/entity | GET | agent_id (optional), entity, depth (default: 2) | Query the knowledge graph to explore relationships for an entity |
| memory_entities | /graph/entities | GET | agent_id (optional), entity_type (optional), limit (default: 50) | List all entities in the knowledge graph with optional type filter |
| memory_by_entity | /graph/entity/memories | GET | agent_id (optional), entity, limit (default: 20) | Retrieve all memories associated with a specific entity |
| import_document | /memories/import | POST | agent_id (optional), content (up to 200KB), source (optional) | Bulk import a large text document - chunks it and extracts memories from each chunk |
| import_conversation | /memories/import-thread | POST | agent_id (optional), conversation (array of {role, content}), source (optional) | Import a conversation thread - extracts memories from each turn pair |
| memory_feedback | /feedback | POST | agent_id (optional), memory_id (optional), feedback_type (used/ignored/contradicted/miss), context (optional) | Submit feedback on recalled memories to improve quality |

## Endpoint Routing Summary

### Write Operations
- **memory_add** → POST /memories/extract (async extraction from conversation)
- **memory_write** → POST /memories/seed (direct memory storage, rate-limited)
- **import_document** → POST /memories/import (bulk document import)
- **import_conversation** → POST /memories/import-thread (conversation thread import)
- **memory_feedback** → POST /feedback (feedback on recalled memories)

### Read Operations
- **memory_recall** → POST /recall (semantic memory retrieval)
- **memory_search** → GET /memories/search (text search)
- **memory_list** → GET /memories (paginated list)
- **list_agents** → GET /agents (agent namespace list)
- **memory_history** → GET /memories/{memory_id}/history (version history)

### Graph Operations
- **memory_graph_traverse** → GET /graph/entity (explore entity relationships)
- **memory_entities** → GET /graph/entities (list all entities)
- **memory_by_entity** → GET /graph/entity/memories (memories for an entity)

### Delete Operations
- **memory_delete** → DELETE /memories/{memory_id} (delete single memory)

## Notes

- **Agent ID Resolution**: All tools with agent_id parameter support auto-resolution. If omitted, the API resolves from tenant default or single-agent account.
- **Rate Limiting**: memory_write is rate-limited to 30 calls per minute per API key.
- **Deduplication**: memory_write implements 60-second deduplication window to prevent duplicate storage.
- **Cross-Agent Hints**: memory_recall, memory_search, and memory_list provide helpful hints when no results are found for the specified agent but other agents have memories.
- **Hardening Features**: Active profiling, sentinel warnings, and rate limit enforcement are applied via hardening.ts.
- **Graph Path**: The API endpoint GET /graph/path exists but is NOT exposed as an MCP tool (not in the locked 14-tool list).

---

**Total Tools:** 14  
**Last Updated:** Auto-generated from /tmp/mcp-server-fresh/src/tools.ts
