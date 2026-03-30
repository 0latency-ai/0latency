import { GoogleGenerativeAI, GenerativeModel } from '@google/generative-ai';
import fetch from 'node-fetch';

interface GeminiGenerateContentParams {
  contents: Array<{ role: string; parts: Array<{ text: string }> }>;
  systemInstruction?: string;
  [key: string]: any;
}

interface GeminiGenerateContentResult {
  response: {
    text: () => string;
    candidates?: Array<any>;
    usageMetadata?: {
      promptTokenCount: number;
      candidatesTokenCount: number;
      totalTokenCount: number;
    };
  };
}

export class GeminiWithMemory {
  private client: GoogleGenerativeAI;
  private zlApiKey: string;
  private agentId: string;
  private baseUrl: string = 'https://api.0latency.ai/v1';
  private model: GenerativeModel;

  constructor(apiKey: string, zlApiKey: string, agentId: string, modelName: string = 'gemini-pro') {
    this.client = new GoogleGenerativeAI(apiKey);
    this.model = this.client.getGenerativeModel({ model: modelName });
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

    const data = await response.json();
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

  async generateContent(params: GeminiGenerateContentParams | string): Promise<GeminiGenerateContentResult> {
    // Handle string input (simple prompt)
    if (typeof params === 'string') {
      params = {
        contents: [{ role: 'user', parts: [{ text: params }] }],
      };
    }

    // 1. Get the last user message for recall
    const lastContent = params.contents[params.contents.length - 1];
    const query = lastContent.role === 'user' ? lastContent.parts[0]?.text : '';

    // 2. Recall relevant memories
    let memories: any[] = [];
    if (query) {
      try {
        memories = await this.recall(query, 10);
      } catch (err) {
        console.error('Recall failed:', err);
      }
    }

    // 3. Inject memory context into system instruction
    let systemInstruction = params.systemInstruction || '';
    if (memories.length > 0) {
      const memoryContext = memories
        .map((m, i) => `[Memory ${i + 1}] ${m.content}`)
        .join('\n');
      systemInstruction = systemInstruction
        ? `${systemInstruction}\n\n## Relevant Context from Memory:\n${memoryContext}`
        : `## Relevant Context from Memory:\n${memoryContext}`;
    }

    // 4. Call native Gemini client
    const modifiedParams = {
      ...params,
      systemInstruction,
    };

    const result = await this.model.generateContent(modifiedParams);

    // 5. Store interaction in memory (fire and forget)
    const assistantContent = result.response.text();
    this.memoryAdd(
      `User: ${query}\nAssistant: ${assistantContent}`,
      {
        model: this.model.model,
        timestamp: new Date().toISOString(),
      }
    );

    return result as GeminiGenerateContentResult;
  }
}
