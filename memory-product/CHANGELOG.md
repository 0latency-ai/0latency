# Changelog

All notable changes to the 0Latency memory API and tooling will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2026-03-24

### Added
- **Graph traversal API** - New `/v1/memory/{memory_id}/graph` endpoint for exploring memory relationships
  - `depth` parameter controls traversal depth (default: 2 hops)
  - Returns nodes and edges for visualization
- **Entity extraction** - `/v1/memory/entities` endpoint to list extracted entities (people, places, concepts)
  - Automatic entity recognition from stored memories
  - Entity type classification
- **Sentiment analysis** - `/v1/memory/sentiment` endpoint for emotional tone analysis
  - Returns sentiment distribution across memories
  - Aggregate statistics for positive/negative/neutral
- **Conversation history tools** - Better support for chat-based integrations
  - Improved context preservation across conversation turns
  - Better handling of multi-turn dialogues
- **Memory confidence scores** - All recalled memories now include confidence ratings
  - Helps filter and prioritize results
  - Based on relevance and recency
- **Memory versioning** - Internal version tracking for memory updates
  - Foundation for future conflict resolution
  - Supports audit trails
- **Consolidation endpoint** - `/v1/memory/consolidate` for merging similar memories
  - `auto_merge` parameter for automatic deduplication
  - Returns consolidation statistics

### Changed
- Improved recall algorithm for better semantic matching
- Enhanced extraction to better preserve conversation context
- Optimized search performance for large memory sets

### Fixed
- Graph endpoint now properly handles orphaned memories
- Entity extraction more accurately identifies proper nouns
- Sentiment scoring normalized across different memory types

## [0.1.3] - 2026-03-20

### Fixed
- **Agent ID defaults** - Fixed issue where `agent_id` wasn't properly defaulting in some contexts
  - Now correctly inherits from session context when not explicitly provided
  - Better error messages when agent_id is missing
- **Search endpoint bug** - Fixed keyword search returning incomplete results
  - Improved tokenization for multi-word queries
  - Better handling of special characters in search terms

### Changed
- Search now returns results sorted by relevance by default
- Improved error messages for validation failures

## [0.1.2] - 2026-03-18

### Fixed
- **Remember tool distribution** - Rebuilt distribution package for remember tool
  - Fixed missing dependencies in packaged version
  - Updated build pipeline to include all required assets
  - Verified functionality across different environments

### Changed
- Remember tool now includes better error handling for network issues
- Improved logging for debugging integration issues

## [0.1.1] - 2026-03-15

### Fixed
- **Remember tool endpoint** - Fixed incorrect API endpoint in remember tool client
  - Changed from `/api/remember` to `/v1/memory/extract`
  - Updated authentication header format
  - Fixed response parsing for new format

### Changed
- Remember tool now uses standard SDK client internally
- Improved error messages for failed remember operations

## [0.1.0] - 2026-03-10

### Added
- **Core Memory System** - Initial release of 0Latency agent memory API
  - `/v1/memory/extract` - Extract and store memories from conversations
  - `/v1/memory/recall` - Semantic search for relevant memories
  - `/v1/memory/search` - Keyword-based text search
  - `/v1/memory` (GET) - List all memories for an agent
  - `/v1/memory/{id}` (DELETE) - Delete specific memory
  - `/v1/memory/seed` - Bulk import facts
- **Authentication** - Bearer token authentication
- **Agent isolation** - Each agent has isolated memory space via `agent_id`
- **Vector search** - Semantic similarity using embeddings
- **REST API** - Clean, documented JSON API
- **Rate limiting** - Basic rate limiting to prevent abuse
- **Error handling** - Comprehensive error codes (401, 403, 422, 500)

### API Endpoints (v0.1.0)
```
POST   /v1/memory/extract      - Store conversation memories
POST   /v1/memory/recall       - Semantic recall
GET    /v1/memory/search       - Text search
GET    /v1/memory              - List memories
POST   /v1/memory/seed         - Bulk import
DELETE /v1/memory/{id}         - Delete memory
```

### Documentation
- API reference published at docs.0latency.ai
- Python SDK examples
- Integration guides for popular frameworks

---

## Version History Summary

- **0.1.4** - Graph, entities, sentiment, consolidation
- **0.1.3** - Bug fixes (agent_id, search)
- **0.1.2** - Bug fix (remember tool dist)
- **0.1.1** - Bug fix (remember tool endpoint)
- **0.1.0** - Initial release (core memory system)

## Upcoming Features (Roadmap)

### Planned for 0.2.0
- WebSocket support for real-time memory updates
- Memory tagging and categorization
- Advanced filtering (by date, confidence, entity)
- Memory importance scoring
- Automatic memory decay/archival

### Under Consideration
- Multi-agent shared memory spaces
- Memory access controls and permissions
- Cross-agent memory insights
- Memory visualization dashboard
- Webhook notifications for memory events
- Export/import memory snapshots

---

For detailed API documentation, visit [docs.0latency.ai](https://docs.0latency.ai)

For support or feature requests, contact justin@0latency.ai
