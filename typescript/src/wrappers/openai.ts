import OpenAI from 'openai';
import type { ChatCompletionCreateParamsNonStreaming, ChatCompletion, ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import fetch from 'node-fetch';

export class OpenAIWithMemory {
  private client: OpenAI;
  private zlApiKey: string;
  private agentId: string;
  private baseUrl: string = 'https://api.0latency.ai/v1';

  constructor(apiKey: string, zlApiKey: string, agentId: string) {
    this.client = new OpenAI({ apiKey });
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

  async create(params: ChatCompletionCreateParamsNonStreaming): Promise<ChatCompletion> {
    // 1. Get the last user message for recall
    const lastMessage = params.messages[params.messages.length - 1];
    const query = typeof lastMessage.content === 'string' 
      ? lastMessage.content 
      : JSON.stringify(lastMessage.content);

    // 2. Recall relevant memories
    let memories: any[] = [];
    if (query) {
      try {
        memories = await this.recall(query, 10);
      } catch (err) {
        console.error('Recall failed:', err);
      }
    }

    // 3. Inject memory context as a system message
    const messages: ChatCompletionMessageParam[] = [...params.messages];
    if (memories.length > 0) {
      const memoryContext = memories
        .map((m, i) => `[Memory ${i + 1}] ${m.content}`)
        .join('\n');
      
      // Add system message at the beginning if memories exist
      messages.unshift({
        role: 'system',
        content: `## Relevant Context from Memory:\n${memoryContext}`,
      });
    }

    // 4. Call native OpenAI client
    const modifiedParams: ChatCompletionCreateParamsNonStreaming = {
      ...params,
      messages,
    };

    const response = await this.client.chat.completions.create(modifiedParams);

    // 5. Store interaction in memory (fire and forget)
    const assistantContent = response.choices[0]?.message?.content || '';
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
