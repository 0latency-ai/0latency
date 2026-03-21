/**
 * Zero Latency Memory SDK — TypeScript Client
 *
 * @example
 * ```typescript
 * import { ZeroLatencyClient } from 'zerolatency';
 *
 * const client = new ZeroLatencyClient({ apiKey: 'zl_live_...' });
 *
 * // Extract memories
 * const result = await client.extract({
 *   agentId: 'my-agent',
 *   humanMessage: 'My name is Justin',
 *   agentMessage: 'Nice to meet you!'
 * });
 *
 * // Recall context
 * const context = await client.recall({
 *   agentId: 'my-agent',
 *   conversationContext: 'What do we know about the user?'
 * });
 * ```
 */

export interface ZeroLatencyConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
}

export interface ExtractRequest {
  agentId: string;
  humanMessage: string;
  agentMessage: string;
  sessionKey?: string;
  turnId?: string;
}

export interface ExtractResponse {
  memories_stored: number;
  memory_ids: string[];
}

export interface RecallRequest {
  agentId: string;
  conversationContext: string;
  budgetTokens?: number;
}

export interface RecallResponse {
  context_block: string;
  memories_used: number;
  tokens_used: number;
  budget_remaining?: number;
  recall_details?: RecallDetail[];
}

export interface RecallDetail {
  id: string;
  headline: string;
  type: string;
  tier: string;
  composite: number;
}

export interface MemoryItem {
  id: string;
  headline: string;
  memory_type: string;
  importance: number;
  created_at: string;
  context?: string;
  full_content?: string;
  entities?: string[];
  categories?: string[];
}

export interface EntityNode {
  name: string;
  type: string;
  summary?: string;
  mention_count: number;
  first_seen?: string;
  last_seen?: string;
}

export interface GraphResult {
  root: string;
  nodes: Record<string, EntityNode>;
  edges: Array<{
    source: string;
    target: string;
    relationship: string;
    strength: number;
    hop: number;
  }>;
  total_nodes: number;
  total_edges: number;
}

export interface WebhookConfig {
  url: string;
  events: string[];
  secret?: string;
}

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
  last_triggered?: string;
  failure_count: number;
}

export interface Criteria {
  id: string;
  name: string;
  weight: number;
  description?: string;
}

export interface MemoryHistory {
  memory_id: string;
  current: {
    version: number;
    headline: string;
    memory_type: string;
    importance: number;
    is_current: boolean;
  } | null;
  history: Array<{
    version: number;
    headline: string;
    memory_type?: string;
    importance?: number;
    changed_by: string;
    change_reason?: string;
    created_at: string;
  }>;
  total_versions: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  memories_total?: number;
  db_pool?: Record<string, number>;
  redis?: string;
}

export interface TenantInfo {
  id: string;
  name: string;
  plan: string;
  memory_limit: number;
  rate_limit_rpm: number;
  api_calls_count: number;
}

class ZeroLatencyError extends Error {
  statusCode?: number;
  response?: any;

  constructor(message: string, statusCode?: number, response?: any) {
    super(message);
    this.name = 'ZeroLatencyError';
    this.statusCode = statusCode;
    this.response = response;
  }
}

class RateLimitError extends ZeroLatencyError {
  retryAfter: number;

  constructor(message: string, retryAfter: number = 60) {
    super(message, 429);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

export class ZeroLatencyClient {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;
  private maxRetries: number;

  constructor(config: ZeroLatencyConfig) {
    if (!config.apiKey.startsWith('zl_live_')) {
      throw new Error('API key must start with zl_live_');
    }
    this.apiKey = config.apiKey;
    this.baseUrl = (config.baseUrl || 'https://api.0latency.ai').replace(/\/$/, '');
    this.timeout = config.timeout || 30000;
    this.maxRetries = config.maxRetries || 3;
  }

  private async request<T>(method: string, path: string, body?: any, params?: Record<string, any>): Promise<T> {
    let url = `${this.baseUrl}${path}`;

    if (params) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      }
      const qs = searchParams.toString();
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
          },
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.status === 429) {
          const retryAfter = parseInt(response.headers.get('Retry-After') || '60', 10);
          if (attempt < this.maxRetries - 1) {
            await this.sleep(retryAfter * 1000);
            continue;
          }
          throw new RateLimitError(`Rate limit exceeded. Retry after ${retryAfter}s`, retryAfter);
        }

        if (!response.ok) {
          const errBody = await response.json().catch(() => ({}));
          throw new ZeroLatencyError(
            errBody.detail || `API error ${response.status}`,
            response.status,
            errBody
          );
        }

        return await response.json() as T;
      } catch (err: any) {
        if (err instanceof ZeroLatencyError) throw err;
        if (attempt < this.maxRetries - 1) {
          await this.sleep(Math.pow(2, attempt) * 1000);
          continue;
        }
        throw new ZeroLatencyError(err.message || 'Request failed');
      }
    }

    throw new ZeroLatencyError('Max retries exceeded');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // --- Core ---

  async extract(req: ExtractRequest): Promise<ExtractResponse> {
    return this.request('POST', '/extract', {
      agent_id: req.agentId,
      human_message: req.humanMessage,
      agent_message: req.agentMessage,
      session_key: req.sessionKey,
      turn_id: req.turnId,
    });
  }

  async recall(req: RecallRequest): Promise<RecallResponse> {
    return this.request('POST', '/recall', {
      agent_id: req.agentId,
      conversation_context: req.conversationContext,
      budget_tokens: req.budgetTokens || 4000,
    });
  }

  async listMemories(agentId: string, options?: {
    limit?: number;
    offset?: number;
    memoryType?: string;
  }): Promise<MemoryItem[]> {
    return this.request('GET', '/memories', undefined, {
      agent_id: agentId,
      limit: options?.limit,
      offset: options?.offset,
      memory_type: options?.memoryType,
    });
  }

  async searchMemories(agentId: string, query: string, limit?: number): Promise<MemoryItem[]> {
    return this.request('GET', '/memories/search', undefined, {
      agent_id: agentId,
      q: query,
      limit,
    });
  }

  async deleteMemory(memoryId: string): Promise<{ deleted: string }> {
    return this.request('DELETE', `/memories/${memoryId}`);
  }

  async updateMemory(memoryId: string, updates: Partial<{
    headline: string;
    context: string;
    full_content: string;
    memory_type: string;
    importance: number;
    confidence: number;
  }>): Promise<{ updated: string }> {
    return this.request('PUT', `/memories/${memoryId}`, updates);
  }

  async exportMemories(agentId: string): Promise<{ memories: MemoryItem[]; total_memories: number }> {
    return this.request('GET', '/memories/export', undefined, { agent_id: agentId });
  }

  // --- Batch ---

  async batchExtract(turns: ExtractRequest[]): Promise<{
    turns_processed: number;
    memories_stored: number;
    memory_ids: string[];
  }> {
    return this.request('POST', '/extract/batch', {
      turns: turns.map(t => ({
        agent_id: t.agentId,
        human_message: t.humanMessage,
        agent_message: t.agentMessage,
        session_key: t.sessionKey,
        turn_id: t.turnId,
      })),
    });
  }

  async batchDelete(memoryIds: string[]): Promise<{ deleted: string[]; errors?: any[] }> {
    return this.request('POST', '/memories/batch-delete', { memory_ids: memoryIds });
  }

  async batchSearch(agentId: string, queries: string[], limitPerQuery?: number): Promise<{
    results: Record<string, MemoryItem[]>;
  }> {
    return this.request('POST', '/memories/batch-search', {
      agent_id: agentId,
      queries,
      limit_per_query: limitPerQuery || 10,
    });
  }

  // --- Graph ---

  async getEntityGraph(agentId: string, entity: string, depth?: number): Promise<GraphResult> {
    return this.request('GET', '/graph/entity', undefined, {
      agent_id: agentId,
      entity,
      depth: depth || 2,
    });
  }

  async listEntities(agentId: string, entityType?: string, limit?: number): Promise<EntityNode[]> {
    return this.request('GET', '/graph/entities', undefined, {
      agent_id: agentId,
      entity_type: entityType,
      limit,
    });
  }

  async getEntityMemories(agentId: string, entity: string, limit?: number): Promise<MemoryItem[]> {
    return this.request('GET', '/graph/entity/memories', undefined, {
      agent_id: agentId,
      entity,
      limit,
    });
  }

  async findPath(agentId: string, source: string, target: string, maxDepth?: number): Promise<{
    source: string;
    target: string;
    path: string[];
    hops: number;
  }> {
    return this.request('GET', '/graph/path', undefined, {
      agent_id: agentId,
      source,
      target,
      max_depth: maxDepth || 4,
    });
  }

  // --- Versioning ---

  async getMemoryHistory(memoryId: string): Promise<MemoryHistory> {
    return this.request('GET', `/memories/${memoryId}/history`);
  }

  // --- Webhooks ---

  async createWebhook(config: WebhookConfig): Promise<Webhook> {
    return this.request('POST', '/webhooks', config);
  }

  async listWebhooks(): Promise<Webhook[]> {
    return this.request('GET', '/webhooks');
  }

  async deleteWebhook(webhookId: string): Promise<{ deleted: string }> {
    return this.request('DELETE', `/webhooks/${webhookId}`);
  }

  // --- Criteria ---

  async createCriteria(agentId: string, name: string, weight?: number, description?: string): Promise<Criteria> {
    return this.request('POST', '/criteria', {
      agent_id: agentId,
      name,
      weight: weight || 0.5,
      description,
    });
  }

  async listCriteria(agentId: string): Promise<Criteria[]> {
    return this.request('GET', '/criteria', undefined, { agent_id: agentId });
  }

  async deleteCriteria(criteriaId: string): Promise<{ deleted: string }> {
    return this.request('DELETE', `/criteria/${criteriaId}`);
  }

  // --- Org Memory ---

  async storeOrgMemory(data: {
    headline: string;
    context?: string;
    memoryType?: string;
    importance?: number;
  }): Promise<{ id: string; org_id: string }> {
    return this.request('POST', '/org/memories', {
      headline: data.headline,
      context: data.context,
      memory_type: data.memoryType || 'fact',
      importance: data.importance || 0.5,
    });
  }

  async recallOrgMemories(query: string, limit?: number): Promise<MemoryItem[]> {
    return this.request('GET', '/org/memories/recall', undefined, { q: query, limit });
  }

  async promoteToOrg(memoryId: string): Promise<{ promoted: string; org_memory_id: string }> {
    return this.request('POST', `/memories/${memoryId}/promote`);
  }

  // --- Utility ---

  async health(): Promise<HealthResponse> {
    const url = `${this.baseUrl}/health`;
    const response = await fetch(url, { method: 'GET' });
    return response.json();
  }

  async tenantInfo(): Promise<TenantInfo> {
    return this.request('GET', '/tenant-info');
  }

  async usage(days?: number): Promise<any> {
    return this.request('GET', '/usage', undefined, { days: days || 7 });
  }
}

export { ZeroLatencyError, RateLimitError };
export default ZeroLatencyClient;
