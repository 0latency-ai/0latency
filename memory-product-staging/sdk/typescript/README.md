# zerolatency

TypeScript SDK for the [0Latency](https://0latency.ai) Memory API — structured memory for AI agents.

## Installation

```bash
npm install zerolatency
```

## Quick Start

```typescript
import { Memory } from 'zerolatency';

const memory = new Memory('your-api-key');

// Store a memory
await memory.add('User prefers dark mode');

// Retrieve relevant memories
const results = await memory.recall('What does the user prefer?');
console.log(results.context_block);
```

## API Reference

### `new Memory(apiKey, options?)`

Create a new Memory client.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apiKey` | `string` | — | Your 0Latency API key |
| `options.baseUrl` | `string` | `https://api.0latency.ai` | API base URL |
| `options.timeout` | `number` | `30000` | Request timeout in ms |
| `options.maxRetries` | `number` | `3` | Max retries on transient failures |

### `memory.add(content, options?)`

Store a memory.

```typescript
await memory.add('User prefers dark mode', {
  agentId: 'my-agent',
  metadata: { source: 'settings' },
});
```

**Options:**
- `agentId` — Agent identifier for scoping (default: `'default'`)
- `metadata` — Key-value metadata to attach

**Returns:** `{ memories_stored: number, memory_ids: string[] }`

### `memory.recall(query, options?)`

Retrieve relevant memories by semantic search.

```typescript
const results = await memory.recall('What does the user prefer?', {
  agentId: 'my-agent',
  limit: 5,
});
console.log(results.context_block);
```

**Options:**
- `agentId` — Agent identifier for scoping (default: `'default'`)
- `limit` — Maximum number of results (default: `10`)

**Returns:** `{ context_block: string, memories_used: number, tokens_used: number }`

### `memory.extract(conversation, options?)`

Start async memory extraction from a conversation. Returns immediately with a `job_id`.

```typescript
const job = await memory.extract([
  { role: 'user', content: 'My name is Alice' },
  { role: 'assistant', content: 'Nice to meet you, Alice!' },
], { agentId: 'my-agent' });

console.log(job.job_id); // poll with extractStatus()
```

**Options:**
- `agentId` — Agent identifier (default: `'default'`)
- `sessionKey` — Session key for grouping

**Returns:** `{ job_id: string, status: 'accepted' }`

### `memory.extractStatus(jobId)`

Check the status of an async extraction job.

```typescript
const status = await memory.extractStatus(job.job_id);
if (status.status === 'complete') {
  console.log(`Stored ${status.memories_stored} memories`);
}
```

**Returns:** `{ status: 'accepted' | 'complete' | 'failed', memories_stored: number, memory_ids: string[] }`

### `memory.health()`

Check API health. Does not require authentication.

```typescript
const health = await memory.health();
console.log(health.status); // 'ok'
```

## Error Handling

```typescript
import { Memory, ZeroLatencyError, AuthenticationError, RateLimitError } from 'zerolatency';

try {
  await memory.add('some content');
} catch (err) {
  if (err instanceof AuthenticationError) {
    console.error('Bad API key');
  } else if (err instanceof RateLimitError) {
    console.error(`Rate limited. Retry after ${err.retryAfter}s`);
  } else if (err instanceof ZeroLatencyError) {
    console.error(`API error ${err.statusCode}: ${err.message}`);
  }
}
```

## Requirements

- Node.js 18+ (uses native `fetch`)
- No external dependencies

## License

MIT
