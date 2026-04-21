/**
 * 0Latency Memory client — TypeScript SDK.
 *
 * @example
 * ```typescript
 * import { Memory } from 'zerolatency';
 *
 * const memory = new Memory('your-api-key');
 * await memory.add('User prefers dark mode');
 * const results = await memory.recall('What does the user prefer?');
 * ```
 */

import { ZeroLatencyError, AuthenticationError, RateLimitError } from './errors.js';
import type {
  MemoryOptions,
  AddOptions,
  AddResponse,
  RecallOptions,
  RecallResponse,
  ConversationMessage,
  ExtractOptions,
  ExtractResponse,
  ExtractStatusResponse,
  HealthResponse,
} from './types.js';

const DEFAULT_BASE_URL = 'https://api.0latency.ai';
const DEFAULT_TIMEOUT = 30_000;
const DEFAULT_MAX_RETRIES = 3;

export class Memory {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;

  /**
   * Create a new Memory client.
   *
   * @param apiKey - Your 0Latency API key (starts with `zl_live_`).
   * @param options - Optional configuration (baseUrl, timeout, maxRetries).
   */
  constructor(apiKey: string, options?: MemoryOptions) {
    if (!apiKey) {
      throw new AuthenticationError('API key is required.');
    }
    this.apiKey = apiKey;
    this.baseUrl = (options?.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeout = options?.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = options?.maxRetries ?? DEFAULT_MAX_RETRIES;
  }

  // ── Public API ──────────────────────────────────────────────────────

  /**
   * Store a memory.
   *
   * @param content - The text content to remember.
   * @param options - Optional agentId and metadata.
   */
  async add(content: string, options?: AddOptions): Promise<AddResponse> {
    const agentId = options?.agentId ?? 'default';
    return this._post<AddResponse>('/memories/extract', {
      agent_id: agentId,
      content,
    });
  }

  /**
   * Retrieve relevant memories.
   *
   * @param query - Natural-language search query.
   * @param options - Optional agentId and limit.
   */
  async recall(query: string, options?: RecallOptions): Promise<RecallResponse> {
    const agentId = options?.agentId ?? 'default';
    return this._post<RecallResponse>('/recall', {
      agent_id: agentId,
      conversation_context: query,
      budget_tokens: 4000,
    });
  }

  /**
   * Start async memory extraction from a conversation.
   * Returns immediately with a job_id; poll with extractStatus().
   *
   * @param conversation - Array of message objects with role and content.
   * @param options - Optional agentId and sessionKey.
   */
  async extract(
    conversation: ConversationMessage[],
    options?: ExtractOptions,
  ): Promise<ExtractResponse> {
    const agentId = options?.agentId ?? 'default';
    const content = conversation
      .map((m) => `${m.role}: ${m.content}`)
      .join('\n');
    return this._post<ExtractResponse>('/memories/extract', {
      agent_id: agentId,
      content,
      session_key: options?.sessionKey,
    });
  }

  /**
   * Check the status of an async extraction job.
   *
   * @param jobId - The job identifier returned by extract().
   */
  async extractStatus(jobId: string): Promise<ExtractStatusResponse> {
    return this._get<ExtractStatusResponse>(`/memories/extract/${jobId}`);
  }

  /**
   * Check API health. Does not require authentication.
   */
  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new ZeroLatencyError(
        `Health check failed with status ${response.status}`,
        response.status,
      );
    }
    return (await response.json()) as HealthResponse;
  }

  // ── Internal ────────────────────────────────────────────────────────

  private async _post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return this._request<T>('POST', path, body);
  }

  private async _get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
    return this._request<T>('GET', path, undefined, params);
  }

  private async _request<T>(
    method: string,
    path: string,
    body?: Record<string, unknown>,
    params?: Record<string, unknown>,
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;

    if (params) {
      const sp = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          sp.append(key, String(value));
        }
      }
      const qs = sp.toString();
      if (qs) url += `?${qs}`;
    }

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': this.apiKey,
            'User-Agent': 'zerolatency-ts/0.1.0',
          },
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.status === 401) {
          const errBody = await response.json().catch(() => ({}));
          throw new AuthenticationError(
            (errBody as Record<string, string>).detail ?? 'Invalid API key',
            errBody,
          );
        }

        if (response.status === 429) {
          const retryAfter = parseInt(
            response.headers.get('Retry-After') ?? '60',
            10,
          );
          if (attempt < this.maxRetries - 1) {
            await this._sleep(retryAfter * 1000);
            continue;
          }
          const errBody = await response.json().catch(() => ({}));
          throw new RateLimitError(
            `Rate limit exceeded. Retry after ${retryAfter}s`,
            retryAfter,
            errBody,
          );
        }

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new ZeroLatencyError(
            (errBody as Record<string, string>).detail ??
              `API error ${response.status}`,
            response.status,
            errBody,
          );
        }

        return (await response.json()) as T;
      } catch (err: unknown) {
        if (
          err instanceof ZeroLatencyError ||
          err instanceof AuthenticationError ||
          err instanceof RateLimitError
        ) {
          throw err;
        }
        if (attempt < this.maxRetries - 1) {
          await this._sleep(Math.pow(2, attempt) * 1000);
          continue;
        }
        const message =
          err instanceof Error ? err.message : 'Request failed';
        throw new ZeroLatencyError(message);
      }
    }

    throw new ZeroLatencyError('Max retries exceeded');
  }

  private _sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
