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
import type { MemoryOptions, AddOptions, AddResponse, RecallOptions, RecallResponse, ConversationMessage, ExtractOptions, ExtractResponse, ExtractStatusResponse, HealthResponse } from './types.js';
export declare class Memory {
    private readonly apiKey;
    private readonly baseUrl;
    private readonly timeout;
    private readonly maxRetries;
    /**
     * Create a new Memory client.
     *
     * @param apiKey - Your 0Latency API key (starts with `zl_live_`).
     * @param options - Optional configuration (baseUrl, timeout, maxRetries).
     */
    constructor(apiKey: string, options?: MemoryOptions);
    /**
     * Store a memory.
     *
     * @param content - The text content to remember.
     * @param options - Optional agentId and metadata.
     */
    add(content: string, options?: AddOptions): Promise<AddResponse>;
    /**
     * Retrieve relevant memories.
     *
     * @param query - Natural-language search query.
     * @param options - Optional agentId and limit.
     */
    recall(query: string, options?: RecallOptions): Promise<RecallResponse>;
    /**
     * Start async memory extraction from a conversation.
     * Returns immediately with a job_id; poll with extractStatus().
     *
     * @param conversation - Array of message objects with role and content.
     * @param options - Optional agentId and sessionKey.
     */
    extract(conversation: ConversationMessage[], options?: ExtractOptions): Promise<ExtractResponse>;
    /**
     * Check the status of an async extraction job.
     *
     * @param jobId - The job identifier returned by extract().
     */
    extractStatus(jobId: string): Promise<ExtractStatusResponse>;
    /**
     * Check API health. Does not require authentication.
     */
    health(): Promise<HealthResponse>;
    private _post;
    private _get;
    private _request;
    private _sleep;
}
//# sourceMappingURL=client.d.ts.map