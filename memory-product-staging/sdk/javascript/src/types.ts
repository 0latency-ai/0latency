/**
 * Configuration options for the Memory client.
 */
export interface MemoryConfig {
  /** Your 0Latency API key */
  apiKey: string;
  /** Base URL for the API (default: https://api.0latency.ai) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 30000) */
  timeout?: number;
}

/**
 * Message object for conversation extraction.
 */
export interface ConversationMessage {
  role: string;
  content: string;
}

/**
 * Options for adding a memory.
 */
export interface AddMemoryOptions {
  /** Optional agent identifier for scoping memories */
  agentId?: string;
  /** Optional key-value metadata to attach */
  metadata?: Record<string, any>;
}

/**
 * Options for recalling memories.
 */
export interface RecallOptions {
  /** Optional agent identifier for scoping */
  agentId?: string;
  /** Maximum number of results (default: 10) */
  limit?: number;
}

/**
 * Options for extracting memories from a conversation.
 */
export interface ExtractOptions {
  /** Optional agent identifier */
  agentId?: string;
}

/**
 * Response from adding a memory.
 */
export interface AddMemoryResponse {
  [key: string]: any;
}

/**
 * Response from recalling memories.
 */
export interface RecallResponse {
  [key: string]: any;
}

/**
 * Response from extraction job creation.
 */
export interface ExtractResponse {
  job_id: string;
  [key: string]: any;
}

/**
 * Response from extraction job status check.
 */
export interface ExtractStatusResponse {
  [key: string]: any;
}

/**
 * Response from health check.
 */
export interface HealthResponse {
  [key: string]: any;
}
