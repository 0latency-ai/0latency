# 0Latency JavaScript/TypeScript SDK

A lightweight JavaScript/TypeScript client for the [0Latency](https://0latency.ai) agent memory API.

## Installation

```bash
npm install @0latency/sdk
```

## Quick Start

```typescript
import { Memory } from '@0latency/sdk';

// Initialize the client
const memory = new Memory({ apiKey: 'your-api-key' });

// Add a memory
await memory.add('User prefers dark mode');

// Recall relevant memories
const results = await memory.recall('What are the user preferences?');
console.log(results);
```

## Features

- **TypeScript-first**: Full type safety and IntelliSense support
- **Zero dependencies**: Uses native fetch API (Node.js 18+, all modern browsers)
- **Simple API**: Intuitive methods matching the Python SDK
- **Error handling**: Custom error classes for different failure modes
- **Timeout support**: Configurable request timeouts

## API Reference

### Constructor

```typescript
const memory = new Memory({
  apiKey: 'your-api-key',          // Required
  baseUrl?: 'https://custom.api',  // Optional, defaults to api.0latency.ai
  timeout?: 30000                   // Optional, defaults to 30000ms
});
```

### Methods

#### `add(content, options?)`

Store a new memory.

```typescript
await memory.add('User loves coffee', {
  agentId: 'assistant-1',
  metadata: { category: 'preferences', confidence: 0.95 }
});
```

**Parameters:**
- `content` (string): The text content to remember
- `options` (optional):
  - `agentId` (string): Agent identifier for scoping
  - `metadata` (object): Key-value metadata to attach

**Returns:** API confirmation payload

---

#### `recall(query, options?)`

Retrieve relevant memories using semantic search.

```typescript
const results = await memory.recall('What does the user like?', {
  agentId: 'assistant-1',
  limit: 5
});
```

**Parameters:**
- `query` (string): Natural-language search query
- `options` (optional):
  - `agentId` (string): Agent identifier for scoping
  - `limit` (number): Maximum results (default: 10)

**Returns:** Matching memories from the API

---

#### `extract(conversation, options?)`

Start async memory extraction from a conversation.

```typescript
const result = await memory.extract([
  { role: 'user', content: 'I love hiking in the mountains' },
  { role: 'assistant', content: 'That sounds wonderful!' }
], { agentId: 'assistant-1' });

console.log('Job ID:', result.job_id);
```

**Parameters:**
- `conversation` (array): List of message objects with `role` and `content`
- `options` (optional):
  - `agentId` (string): Agent identifier

**Returns:** Object containing `job_id` for status polling

---

#### `extractStatus(jobId)`

Check the status of an extraction job.

```typescript
const status = await memory.extractStatus('job-123');
console.log('Status:', status);
```

**Parameters:**
- `jobId` (string): The job identifier returned by `extract()`

**Returns:** Job status payload

---

#### `health()`

Check API health.

```typescript
const health = await memory.health();
console.log('API status:', health);
```

**Returns:** Health status payload

## Usage Examples

### Simple Chatbot Memory

```typescript
import { Memory } from '@0latency/sdk';

const memory = new Memory({ apiKey: process.env.ZEROLATENCY_API_KEY });

async function chatWithMemory(userMessage: string) {
  // Recall relevant context
  const context = await memory.recall(userMessage, {
    agentId: 'chatbot-1',
    limit: 3
  });

  // Generate response using context (pseudo-code)
  const response = await generateResponse(userMessage, context);

  // Store the conversation for future recall
  await memory.extract([
    { role: 'user', content: userMessage },
    { role: 'assistant', content: response }
  ], { agentId: 'chatbot-1' });

  return response;
}
```

### Coding Agent with Project Memory

```typescript
import { Memory } from '@0latency/sdk';

const memory = new Memory({ apiKey: process.env.ZEROLATENCY_API_KEY });

async function codingAgent(projectId: string, userRequest: string) {
  // Recall project-specific knowledge
  const projectKnowledge = await memory.recall(
    `${userRequest} in the context of this project`,
    { agentId: `project-${projectId}`, limit: 5 }
  );

  // Store important facts about the project
  await memory.add('User prefers functional programming style', {
    agentId: `project-${projectId}`,
    metadata: { 
      category: 'coding-style',
      project: projectId,
      timestamp: Date.now()
    }
  });

  return projectKnowledge;
}
```

### Background Extraction

```typescript
import { Memory } from '@0latency/sdk';

const memory = new Memory({ apiKey: process.env.ZEROLATENCY_API_KEY });

async function extractAndPoll(conversation: any[]) {
  // Start extraction job
  const { job_id } = await memory.extract(conversation, {
    agentId: 'assistant-1'
  });

  // Poll for completion
  let status;
  do {
    await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
    status = await memory.extractStatus(job_id);
  } while (status.state === 'processing');

  console.log('Extraction complete:', status);
}
```

## Error Handling

The SDK provides custom error classes for different failure modes:

```typescript
import { 
  Memory, 
  AuthenticationError, 
  RateLimitError, 
  ZeroLatencyError 
} from '@0latency/sdk';

const memory = new Memory({ apiKey: 'your-api-key' });

try {
  await memory.add('Some content');
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Invalid API key');
  } else if (error instanceof RateLimitError) {
    console.error('Rate limit exceeded, retry later');
  } else if (error instanceof ZeroLatencyError) {
    console.error('API error:', error.message, error.statusCode);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

## TypeScript Support

Full TypeScript definitions are included. Import types as needed:

```typescript
import type { 
  MemoryConfig, 
  AddMemoryOptions,
  RecallOptions,
  ConversationMessage 
} from '@0latency/sdk';
```

## Requirements

- **Node.js**: 18.0.0 or higher (for native fetch support)
- **Browsers**: All modern browsers with fetch support

For older Node.js versions, you can polyfill fetch using `node-fetch` or `undici`.

## License

MIT License - see LICENSE file for details.

## Support

- **Email**: justin@0latency.ai
- **Documentation**: [docs.0latency.ai](https://docs.0latency.ai)
- **Issues**: [GitHub Issues](https://github.com/0latency/javascript-sdk/issues)

## Contributing

Contributions welcome! Please open an issue or PR on GitHub.
