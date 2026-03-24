# Memory Packs

Pre-built collections of curated facts that can be loaded into any 0Latency agent namespace via the `/memories/seed` API. Think of them as "starter kits" — they give an agent useful domain knowledge from day one.

## Available Packs

| Pack | File | Facts | Description |
|------|------|-------|-------------|
| SaaS Founder | `saas-founder.json` | 35 | Startup metrics, fundraising, pricing psychology, growth frameworks, unit economics |
| TypeScript Dev | `typescript-dev.json` | 35 | TypeScript best practices, patterns, Node.js conventions, testing, tooling |
| Python Dev | `python-dev.json` | 35 | Python best practices, async patterns, FastAPI, pytest, performance |
| Claude Power User | `claude-power-user.json` | 32 | Prompting patterns, model selection, MCP tips, artifacts, cost optimization |

## How to Load a Pack

### Via the MCP Tool

If you're using the 0Latency MCP server, use the `load_memory_pack` tool:

```
load_memory_pack(pack_name: "saas-founder", agent_id: "my-agent")
```

To list available packs:
```
load_memory_pack(action: "list")
```

### Via the API Directly

Each pack file is a JSON object with a `facts` array compatible with the `/memories/seed` endpoint:

```bash
# Extract facts and send to the seed API
PACK=$(cat memory-packs/saas-founder.json)
AGENT_ID="my-agent"

curl -X POST https://api.0latency.ai/memories/seed \
  -H "X-API-Key: $ZERO_LATENCY_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"facts\": $(echo $PACK | jq '.facts')}"
```

### Via the seed_memories MCP Tool

You can also use the existing `seed_memories` tool directly with the facts array from any pack file.

## Pack Format

Each pack is a JSON file with this structure:

```json
{
  "name": "Pack Name",
  "description": "What this pack contains",
  "version": "1.0.0",
  "facts": [
    {
      "text": "The actual knowledge to store",
      "category": "category-name",
      "importance": 0.85
    }
  ]
}
```

- **text**: The fact itself. Should be specific, actionable, and opinionated.
- **category**: Grouping label (e.g., "metrics", "pattern", "gotcha", "best-practice").
- **importance**: 0.0 to 1.0. Higher importance facts are recalled more readily.

## Creating Custom Packs

1. Create a new JSON file following the format above
2. Place it in the `memory-packs/` directory
3. It will automatically be available via the `load_memory_pack` MCP tool

Guidelines for good facts:
- Be specific, not generic ("NDR above 120% means..." not "retention is important")
- Include numbers and thresholds when applicable
- Write like a mentor giving advice, not a textbook stating definitions
- Set importance based on how frequently the knowledge is useful (0.9+ for daily-use knowledge, 0.5-0.7 for situational)
