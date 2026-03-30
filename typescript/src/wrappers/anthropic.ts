import Anthropic from '@anthropic-ai/sdk';
import type { MessageCreateParamsNonStreaming, Message } from '@anthropic-ai/sdk/resources/messages';
import fetch from 'node-fetch';

export class AnthropicWithMemory {
  private client: Anthropic;
  private zlApiKey: string;
  private agentId: string;
  private baseUrl: string = 'https://api.0latency.ai/v1';

  constructor(apiKey: string, zlApiKey: string, agentId: string) {
    this.client = new Anthropic({ apiKey });
    this.zlApiKey = zlApiKey;
    this.agentId = agentId;
  }

  private async recall(query: string, limit: number = 10): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/recall`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.zlApiKey,
      },
      body: JSON.stringify({
        agent_id: this.agentId,
        query,
        limit,
      }),
    });

    if (!response.ok) {
      throw new Error(`Recall failed: ${response.statusText}`);
    }

    const data: any = await response.json();
    return data.memories || [];
  }

  private memoryAdd(content: string, metadata?: Record<string, any>): void {
    // Fire and forget - don't await
    fetch(`${this.baseUrl}/memory/add`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.zlApiKey,
      },
      body: JSON.stringify({
        agent_id: this.agentId,
        content,
        metadata: metadata || {},
      }),
    }).catch(err => {
      console.error('Failed to add memory:', err);
    });
  }

  async create(params: MessageCreateParamsNonStreaming): Promise<Message> {
    // 1. Get the last user message for recall
    const messages = params.messages;
    const lastMessage = messages[messages.length - 1];
    const query = typeof lastMessage.content === 'string' 
      ? lastMessage.content 
      : lastMessage.content.map(c => c.type === 'text' ? c.text : '').join(' ');

    // 2. Recall relevant memories
    let memories: any[] = [];
    if (query) {
      try {
        memories = await this.recall(query, 10);
      } catch (err) {
        console.error('Recall failed:', err);
      }
    }

    // 3. Inject memory context into system prompt
    let systemPrompt = typeof params.system === 'string' ? params.system : '';
    if (memories.length > 0) {
      const memoryContext = memories
        .map((m, i) => `[Memory ${i + 1}] ${m.content}`)
        .join('\n');
      systemPrompt = systemPrompt
        ? `${systemPrompt}\n\n## Relevant Context from Memory:\n${memoryContext}`
        : `## Relevant Context from Memory:\n${memoryContext}`;
    }

    // 4. Call native Anthropic client
    const modifiedParams: MessageCreateParamsNonStreaming = {
      ...params,
      system: systemPrompt,
    };

    const response = await this.client.messages.create(modifiedParams);

    // 5. Store interaction in memory (fire and forget)
    const assistantContent =
      response.content.find((c: any) => c.type === 'text')?.text || '';
    this.memoryAdd(
      `User: ${query}\nAssistant: ${assistantContent}`,
      {
        model: params.model,
        timestamp: new Date().toISOString(),
      }
    );

    return response;
  }
}
