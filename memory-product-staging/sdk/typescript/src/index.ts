/**
 * 0Latency — Structured memory for AI agents.
 *
 * @example
 * ```typescript
 * import { Memory } from 'zerolatency';
 *
 * const memory = new Memory('your-api-key');
 * await memory.add('User prefers dark mode');
 * const results = await memory.recall('What does the user prefer?');
 * ```
 *
 * @packageDocumentation
 */

export { Memory } from './client.js';
export {
  ZeroLatencyError,
  AuthenticationError,
  RateLimitError,
} from './errors.js';
export type {
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
