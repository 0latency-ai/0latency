/**
 * Error classes for the 0Latency SDK.
 */
/** Base exception for all 0Latency API errors. */
export declare class ZeroLatencyError extends Error {
    statusCode?: number;
    response?: unknown;
    constructor(message: string, statusCode?: number, response?: unknown);
}
/** Raised when the API key is invalid or missing. */
export declare class AuthenticationError extends ZeroLatencyError {
    constructor(message?: string, response?: unknown);
}
/** Raised when the API rate limit is exceeded. */
export declare class RateLimitError extends ZeroLatencyError {
    retryAfter: number;
    constructor(message?: string, retryAfter?: number, response?: unknown);
}
//# sourceMappingURL=errors.d.ts.map