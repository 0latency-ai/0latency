/**
 * Type definitions for the 0Latency SDK.
 */

/** Configuration options for the Memory client. */
export interface MemoryOptions {
  /** API base URL. Defaults to https://api.0latency.ai */
  baseUrl?: string;
  /** Request timeout in milliseconds. Defaults to 30000. */
  timeout?: number;
  /** Maximum retries on transient failures. Defaults to 3. */
  maxRetries?: number;
}

/** Options for memory.add() */
export interface AddOptions {
  /** Agent identifier for scoping memories. */
  agentId?: string;
  /** Key-value metadata to attach to the memory. */
  metadata?: Record<string, unknown>;
}

/** Response from memory.add() */
export interface AddResponse {
  memories_stored: number;
  memory_ids: string[];
}

/** Options for memory.recall() */
export interface RecallOptions {
  /** Agent identifier for scoping. */
  agentId?: string;
  /** Maximum number of results. Defaults to 10. */
  limit?: number;
}

/** Response from memory.recall() */
export interface RecallResponse {
  context_block: string;
  memories_used: number;
  tokens_used: number;
}

/** A single message in a conversation for extraction. */
export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

/** Options for memory.extract() */
export interface ExtractOptions {
  /** Agent identifier for scoping. */
  agentId?: string;
  /** Session key for grouping. */
  sessionKey?: string;
}

/** Response from memory.extract() — async job accepted. */
export interface ExtractResponse {
  job_id: string;
  status: 'accepted';
}

/** Response from memory.extractStatus() */
export interface ExtractStatusResponse {
  status: 'accepted' | 'complete' | 'failed';
  agent_id: string;
  created_at: string;
  completed_at?: string;
  memories_stored: number;
  memory_ids: string[];
  error?: string;
}

/** Response from memory.health() */
export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
  memories_total?: number;
  db_pool?: Record<string, number>;
  redis?: string;
}
