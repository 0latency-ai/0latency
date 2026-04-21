"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.Memory = void 0;
const errors_js_1 = require("./errors.js");
const DEFAULT_BASE_URL = 'https://api.0latency.ai';
const DEFAULT_TIMEOUT = 30_000;
const DEFAULT_MAX_RETRIES = 3;
class Memory {
    apiKey;
    baseUrl;
    timeout;
    maxRetries;
    /**
     * Create a new Memory client.
     *
     * @param apiKey - Your 0Latency API key (starts with `zl_live_`).
     * @param options - Optional configuration (baseUrl, timeout, maxRetries).
     */
    constructor(apiKey, options) {
        if (!apiKey) {
            throw new errors_js_1.AuthenticationError('API key is required.');
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
    async add(content, options) {
        const agentId = options?.agentId ?? 'default';
        return this._post('/memories/extract', {
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
    async recall(query, options) {
        const agentId = options?.agentId ?? 'default';
        return this._post('/recall', {
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
    async extract(conversation, options) {
        const agentId = options?.agentId ?? 'default';
        const content = conversation
            .map((m) => `${m.role}: ${m.content}`)
            .join('\n');
        return this._post('/memories/extract', {
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
    async extractStatus(jobId) {
        return this._get(`/memories/extract/${jobId}`);
    }
    /**
     * Check API health. Does not require authentication.
     */
    async health() {
        const response = await fetch(`${this.baseUrl}/health`, {
            method: 'GET',
        });
        if (!response.ok) {
            throw new errors_js_1.ZeroLatencyError(`Health check failed with status ${response.status}`, response.status);
        }
        return (await response.json());
    }
    // ── Internal ────────────────────────────────────────────────────────
    async _post(path, body) {
        return this._request('POST', path, body);
    }
    async _get(path, params) {
        return this._request('GET', path, undefined, params);
    }
    async _request(method, path, body, params) {
        let url = `${this.baseUrl}${path}`;
        if (params) {
            const sp = new URLSearchParams();
            for (const [key, value] of Object.entries(params)) {
                if (value !== undefined && value !== null) {
                    sp.append(key, String(value));
                }
            }
            const qs = sp.toString();
            if (qs)
                url += `?${qs}`;
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
                    throw new errors_js_1.AuthenticationError(errBody.detail ?? 'Invalid API key', errBody);
                }
                if (response.status === 429) {
                    const retryAfter = parseInt(response.headers.get('Retry-After') ?? '60', 10);
                    if (attempt < this.maxRetries - 1) {
                        await this._sleep(retryAfter * 1000);
                        continue;
                    }
                    const errBody = await response.json().catch(() => ({}));
                    throw new errors_js_1.RateLimitError(`Rate limit exceeded. Retry after ${retryAfter}s`, retryAfter, errBody);
                }
                if (!response.ok) {
                    const errBody = await response.json().catch(() => ({}));
                    throw new errors_js_1.ZeroLatencyError(errBody.detail ??
                        `API error ${response.status}`, response.status, errBody);
                }
                return (await response.json());
            }
            catch (err) {
                if (err instanceof errors_js_1.ZeroLatencyError ||
                    err instanceof errors_js_1.AuthenticationError ||
                    err instanceof errors_js_1.RateLimitError) {
                    throw err;
                }
                if (attempt < this.maxRetries - 1) {
                    await this._sleep(Math.pow(2, attempt) * 1000);
                    continue;
                }
                const message = err instanceof Error ? err.message : 'Request failed';
                throw new errors_js_1.ZeroLatencyError(message);
            }
        }
        throw new errors_js_1.ZeroLatencyError('Max retries exceeded');
    }
    _sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
}
exports.Memory = Memory;
//# sourceMappingURL=client.js.map