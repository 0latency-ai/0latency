# zerolatency

TypeScript SDK for 0Latency - Add persistent memory to AI agents across Anthropic, OpenAI, and Gemini.

## Installation

```bash
npm install zerolatency
```

You'll also need to install the SDK for your chosen AI provider:

```bash
# For Anthropic Claude
npm install @anthropic-ai/sdk

# For OpenAI GPT
npm install openai

# For Google Gemini
npm install @google/generative-ai
```

## Quick Start

### Anthropic Claude

```typescript
import { AnthropicWithMemory } from 'zerolatency';

const client = new AnthropicWithMemory(
  'your-anthropic-api-key',
  'your-0latency-api-key',
  'your-agent-id'
);

const response = await client.create({
  model: 'claude-3-5-sonnet-20241022',
  max_tokens: 1024,
  messages: [
    { role: 'user', content: 'What did we discuss about the project timeline?' }
  ]
});

console.log(response.content[0].text);
```

### OpenAI GPT

```typescript
import { OpenAIWithMemory } from 'zerolatency';

const client = new OpenAIWithMemory(
  'your-openai-api-key',
  'your-0latency-api-key',
  'your-agent-id'
);

const response = await client.create({
  model: 'gpt-4',
  messages: [
    { role: 'user', content: 'What were the key points from our last meeting?' }
  ]
});

console.log(response.choices[0].message.content);
```

### Google Gemini

```typescript
import { GeminiWithMemory } from 'zerolatency';

const client = new GeminiWithMemory(
  'your-gemini-api-key',
  'your-0latency-api-key',
  'your-agent-id',
  'gemini-pro' // optional, defaults to 'gemini-pro'
);

const response = await client.generateContent({
  contents: [
    { role: 'user', parts: [{ text: 'Remind me what we decided about the architecture?' }] }
  ]
});

console.log(response.response.text());
```

## How It Works

Each wrapper automatically:

1. **Recalls** relevant memories from 0Latency before making the API call
2. **Injects** the memory context into the prompt
3. **Calls** the native SDK (Anthropic, OpenAI, or Gemini)
4. **Stores** the conversation in memory (fire-and-forget, non-blocking)
5. **Returns** the native response unchanged

## API

### `AnthropicWithMemory`

```typescript
constructor(apiKey: string, zlApiKey: string, agentId: string)
```

- `apiKey`: Your Anthropic API key
- `zlApiKey`: Your 0Latency API key (get one at https://0latency.ai)
- `agentId`: Unique identifier for your agent (groups memories)

```typescript
async create(params: MessageCreateParams): Promise<Message>
```

Takes the same parameters as `Anthropic.messages.create()`. Returns the same response type.

### `OpenAIWithMemory`

```typescript
constructor(apiKey: string, zlApiKey: string, agentId: string)
```

- `apiKey`: Your OpenAI API key
- `zlApiKey`: Your 0Latency API key
- `agentId`: Unique identifier for your agent

```typescript
async create(params: ChatCompletionCreateParams): Promise<ChatCompletion>
```

Takes the same parameters as `OpenAI.chat.completions.create()`. Returns the same response type.

### `GeminiWithMemory`

```typescript
constructor(apiKey: string, zlApiKey: string, agentId: string, modelName?: string)
```

- `apiKey`: Your Google AI API key
- `zlApiKey`: Your 0Latency API key
- `agentId`: Unique identifier for your agent
- `modelName`: Optional model name (defaults to 'gemini-pro')

```typescript
async generateContent(params: GeminiGenerateContentParams | string): Promise<GeminiGenerateContentResult>
```

Takes the same parameters as `GenerativeModel.generateContent()`. Returns the same response type.

## Environment Variables

You can use environment variables instead of hardcoding keys:

```typescript
const client = new AnthropicWithMemory(
  process.env.ANTHROPIC_API_KEY!,
  process.env.ZERO_LATENCY_API_KEY!,
  process.env.AGENT_ID!
);
```

## Features

- **Zero-latency recall**: Memory retrieval happens in parallel with your code
- **Fire-and-forget storage**: Memory writes don't block your response
- **Drop-in replacement**: Works with existing code, same API surface
- **Type-safe**: Full TypeScript support with native SDK types
- **Framework agnostic**: Use with any Node.js application

## Get Your API Key

1. Sign up at [0latency.ai](https://0latency.ai)
2. Get your API key from the dashboard
3. Start with 10,000 free memories

## Links

- [Documentation](https://0latency.ai/docs.html)
- [API Reference](https://0latency.ai/docs.html#api)
- [GitHub](https://github.com/jghiglia2380/0Latency)
- [Support](https://0latency.ai/support.html)

## License

MIT
