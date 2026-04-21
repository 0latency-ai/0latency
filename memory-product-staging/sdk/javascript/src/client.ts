/**
 * 0Latency Memory client.
 */

import { AuthenticationError, RateLimitError, ZeroLatencyError } from './errors';
import {
  AddMemoryOptions,
  AddMemoryResponse,
  ConversationMessage,
  ExtractOptions,
  ExtractResponse,
  ExtractStatusResponse,
  HealthResponse,
  MemoryConfig,
  RecallOptions,
  RecallResponse,
} from './types';

const DEFAULT_BASE_URL = 'https://api.0latency.ai';
const DEFAULT_TIMEOUT = 30000;

/**
 * Client for the 0Latency memory API.
 *
 * @example
 * ```typescript
 * import { Memory } from '@0latency/sdk';
 *
 * const memory = new Memory({ apiKey: 'your-api-key' });
 * await memory.add('User prefers dark mode');
 * const results = await memory.recall('What does the user prefer?');
 * ```
 */
export class Memory {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;

  constructor(config: MemoryConfig) {
    this.apiKey = config.apiKey;
    this.baseUrl = (config.baseUrl || DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeout = config.timeout || DEFAULT_TIMEOUT;
  }

  /**
   * Store a memory.
   *
   * @param content - The text content to remember
   * @param options - Optional configuration
   * @returns API confirmation payload
   *
   * @example
   * ```typescript
   * await memory.add('User loves coffee', {
   *   agentId: 'assistant-1',
   *   metadata: { category: 'preferences' }
   * });
   * ```
   */
  async add(content: string, options: AddMemoryOptions = {}): Promise<AddMemoryResponse> {
    const payload: any = { content };
    if (options.agentId) payload.agent_id = options.agentId;
    if (options.metadata) payload.metadata = options.metadata;
    return this.post('/v1/memories', payload);
  }

  /**
   * Retrieve relevant memories.
   *
   * @param query - Natural-language search query
   * @param options - Optional configuration
   * @returns Matching memories from the API
   *
   * @example
   * ```typescript
   * const results = await memory.recall('What does the user like?', {
   *   agentId: 'assistant-1',
   *   limit: 5
   * });
   * ```
   */
  async recall(query: string, options: RecallOptions = {}): Promise<RecallResponse> {
    const params: any = { query, limit: options.limit || 10 };
    if (options.agentId) params.agent_id = options.agentId;
    return this.get('/v1/memories/recall', params);
  }

  /**
   * Start async memory extraction from a conversation.
   *
   * @param conversation - List of message objects with role and content
   * @param options - Optional configuration
   * @returns Object containing job_id for status polling
   *
   * @example
   * ```typescript
   * const result = await memory.extract([
   *   { role: 'user', content: 'I love hiking' },
   *   { role: 'assistant', content: 'That sounds great!' }
   * ], { agentId: 'assistant-1' });
   * console.log('Job ID:', result.job_id);
   * ```
   */
  async extract(
    conversation: ConversationMessage[],
    options: ExtractOptions = {}
  ): Promise<ExtractResponse> {
    const payload: any = { conversation };
    if (options.agentId) payload.agent_id = options.agentId;
    return this.post('/v1/memories/extract', payload);
  }

  /**
   * Check the status of an extraction job.
   *
   * @param jobId - The job identifier returned by extract()
   * @returns Job status payload
   *
   * @example
   * ```typescript
   * const status = await memory.extractStatus('job-123');
   * console.log('Status:', status);
   * ```
   */
  async extractStatus(jobId: string): Promise<ExtractStatusResponse> {
    return this.get(`/v1/memories/extract/${jobId}`);
  }

  /**
   * Check API health.
   *
   * @returns Health status payload
   *
   * @example
   * ```typescript
   * const health = await memory.health();
   * console.log('API status:', health);
   * ```
   */
  async health(): Promise<HealthResponse> {
    return this.get('/v1/health');
  }

  // -- internals -----------------------------------------------------------

  private async post(path: string, json: any): Promise<any> {
    return this.request('POST', path, json);
  }

  private async get(path: string, params?: any): Promise<any> {
    const url = new URL(this.baseUrl + path);
    if (params) {
      Object.keys(params).forEach(key => {
        url.searchParams.append(key, params[key]);
      });
    }
    return this.request('GET', url.toString());
  }

  private async request(method: string, url: string, body?: any): Promise<any> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'User-Agent': '@0latency/sdk-js/0.1.0',
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        return await response.json();
      }

      // Handle errors
      let responseBody: any;
      try {
        responseBody = await response.json();
      } catch {
        responseBody = null;
      }

      if (response.status === 401) {
        throw new AuthenticationError(undefined, responseBody);
      }

      if (response.status === 429) {
        throw new RateLimitError(undefined, responseBody);
      }

      const message =
        responseBody && typeof responseBody === 'object' && responseBody.detail
          ? responseBody.detail
          : await response.text();

      throw new ZeroLatencyError(message, response.status, responseBody);
    } catch (error) {
      clearTimeout(timeoutId);
      
      // Re-throw if already a ZeroLatencyError
      if (error instanceof ZeroLatencyError) {
        throw error;
      }
      
      // Handle abort/timeout
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new ZeroLatencyError(`Request timeout after ${this.timeout}ms`);
        }
        // Handle other Error instances
        throw error;
      }
      
      // Handle non-Error throws
      throw error;
    }
  }
}
