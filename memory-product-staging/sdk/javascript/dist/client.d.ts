/**
 * 0Latency Memory client.
 */
import { AddMemoryOptions, AddMemoryResponse, ConversationMessage, ExtractOptions, ExtractResponse, ExtractStatusResponse, HealthResponse, MemoryConfig, RecallOptions, RecallResponse } from './types';
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
export declare class Memory {
    private apiKey;
    private baseUrl;
    private timeout;
    constructor(config: MemoryConfig);
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
    add(content: string, options?: AddMemoryOptions): Promise<AddMemoryResponse>;
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
    recall(query: string, options?: RecallOptions): Promise<RecallResponse>;
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
    extract(conversation: ConversationMessage[], options?: ExtractOptions): Promise<ExtractResponse>;
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
    extractStatus(jobId: string): Promise<ExtractStatusResponse>;
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
    health(): Promise<HealthResponse>;
    private post;
    private get;
    private request;
}
//# sourceMappingURL=client.d.ts.map